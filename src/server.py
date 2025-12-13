from flask import Flask, jsonify, request
from flask_cors import CORS
import threading
import time
import asyncio
from src.engine import MetaEngine, ProfileEngine, SmartDraft, GameplanGenerator
from src.riot_client import RiotClient
from src.data.ddragon import DataDragon
from src.engine.composition import CompositionAnalyzer

app = Flask(__name__)
CORS(app) # Allow Electron to connect

# --- GLOBAL STATE ---
# This is updated by the LCU Connector thread
current_state = {
    "status": "Waiting for Champ Select...",
    "my_team": [],
    "enemy_team": [],
    "my_pick": None,
    "assigned_position": "", # TOP, JUNGLE, MIDDLE, BOTTOM, UTILITY
    "recommendations": []
}

# Explicitly import these here as they are used in engine initialization
from src.engine.learning import LearningEngine
from src.engine.itemization import ItemizationEngine
from src.engine.ensemble_brain import EnsembleBrain
import os

# --- ENGINES ---
print("[SERVER] Initializing DataDragon...")
ddragon = DataDragon()
meta_engine = MetaEngine()
profile_engine = ProfileEngine(id_map=ddragon.get_id_map())
comp_analyzer = CompositionAnalyzer(ddragon)
learning_engine = LearningEngine()
item_engine = ItemizationEngine(ddragon)

# --- ML STARTUP (SOTA BRAIN) ---
# Initialize the Hive Mind
print("[SERVER] Initializing SOTA Ensemble Brain...")
win_predictor = EnsembleBrain()
match_dir = os.path.join("src", "data", "matches")

# Smart Load
if win_predictor.load():
    print("[SERVER] SOTA Brain Loaded from Long-Term Memory (Joblib).")
else:
    print("[SERVER] Brain memory not found. Starting Emergency Training...")
    # Force hydration if needed for training context
    if not meta_engine.champion_stats:
         meta_engine.update_meta_from_ddragon(ddragon.champions)
    
    win_predictor.train(match_dir, ddragon)
    win_predictor.save()

# Initialize SmartDraft with Brain
draft_engine = SmartDraft(meta_engine, profile_engine, comp_analyzer, learning_engine, ensemble_brain=win_predictor)
gameplan_engine = GameplanGenerator()


# --- ROUTES ---

@app.route('/status', methods=['GET'])
def get_status():
    # Enrich state with human readable names
    enriched = current_state.copy()
    try:
        id_map = ddragon.get_id_map()
        
        def resolve(details_list):
            res = []
            if not details_list: return res
            for cid in details_list:
                try:
                    # cid might be "0" or valid ID (string)
                    if cid and cid != "0":
                        name = id_map.get(int(cid), f"Unknown ({cid})")
                        res.append(name)
                except:
                    pass
            return res
            
        enriched['my_team_names'] = resolve(current_state.get('my_team', []))
        enriched['enemy_team_names'] = resolve(current_state.get('enemy_team', []))
        
        # Also resolve pick
        pick = current_state.get('my_pick')
        if pick and pick != "0":
            try:
                 enriched['my_pick_name'] = id_map.get(int(pick))
            except: pass
        # Helper: Smart Role Resolver
        def resolve_roles(team_list, known_roles):
            # 1. Start with what we know
            assignments = {k: v for k, v in known_roles.items() if v in team_list or v == "Picking..."}
            assigned_champs = set(assignments.values())
            
            print(f"[DEBUG] resolving roles for {team_list} with known {known_roles}")
            # 2. Find who needs a role
            unassigned_champs = [c for c in team_list if c not in assigned_champs]
            available_roles = [r for r in ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"] if r not in assignments]
            
            # 3. Smart/Greedy Resolution
            if unassigned_champs and available_roles:
                from itertools import permutations
                
                # Matrix: [Champ][Role] = Freq
                best_perm = None
                best_score = -1.0
                
                # If too many, just fill?
                if len(unassigned_champs) <= 5:
                    matrix = []
                    for cid in unassigned_champs:
                        c_scores = []
                        c_stats = meta_engine.champion_stats.get(int(cid), {}) if meta_engine.champion_stats else {}
                        for r in available_roles:
                            r_stats = c_stats.get(r, {})
                            games = r_stats.get('games', 0)
                            total = c_stats.get('total_games', 1)
                            freq = games / total if total > 0 else 0
                            c_scores.append(freq)
                        matrix.append(c_scores)
                    
                    n = min(len(unassigned_champs), len(available_roles))
                    for perm in permutations(range(len(available_roles)), n):
                        score = 0
                        for i, r_idx in enumerate(perm):
                            score += matrix[i][r_idx]
                        if score > best_score:
                            best_score = score
                            best_perm = perm
                
                # Apply best perm
                if best_perm:
                    for i, r_idx in enumerate(best_perm):
                        r_name = available_roles[r_idx]
                        c_id = unassigned_champs[i]
                        assignments[r_name] = c_id
                else:
                    # FALLBACK: Just fill sequentially so they show up!
                    # User handles the rest via swap
                    print(f"[WARN] No best perm found for {unassigned_champs}. Filling sequentially.")
                    for i, c_id in enumerate(unassigned_champs):
                        if i < len(available_roles):
                            assignments[available_roles[i]] = c_id
                            
            # Convert IDs to Names for Frontend
            named_assignments = {}
            # Ensure ID Map exists
            id_map = ddragon.get_id_map()
            
            for r, cid in assignments.items():
                if cid == "Picking...":
                    named_assignments[r] = "Picking..."
                    continue
                try:
                    cid_int = int(cid)
                    if cid_int in id_map:
                        named_assignments[r] = id_map[cid_int] # Returns Name (e.g. "Ahri")
                    else:
                        named_assignments[r] = str(cid)
                except Exception as e:
                    named_assignments[r] = str(cid)
            
            return named_assignments

        enriched['my_team_assignments'] = resolve_roles(current_state.get('my_team', []), current_state.get('my_team_roles', {}))
        # Enemy team typically has NO known roles, so this will guess all of them
        enriched['enemy_team_assignments'] = resolve_roles(current_state.get('enemy_team', []), current_state.get('enemy_team_roles', {}))
        
    except Exception as e:
        print(f"[SERVER] Error enriching status: {e}")
        import traceback
        traceback.print_exc()
        
    return jsonify(enriched)

def run_analysis():
    """
    Core Logic: Calculates scores based on current state.
    """
    my_team = current_state['my_team']
    enemy_team = current_state['enemy_team']
    
    # NEW Data from LCU Connector
    my_team_roles = current_state.get('my_team_roles', {})
    enemy_team_roles = current_state.get('enemy_team_roles', {})
    
    role = current_state.get('assigned_position', "")
    if isinstance(role, str): role = role.strip()
    
    valid_roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
    if not role or role not in valid_roles:
        print(f"[SERVER] Role '{role}' invalid or undetected. Defaulting to 'MIDDLE'.")
        role = "MIDDLE"
        current_state['assigned_position'] = "MIDDLE (Auto)" # Update UI to show we defaulted
    
    # 1. Get Candidates (USER REQUEST: NO FILTERING)
    # candidates = ddragon.get_champions_by_role(role)
    candidates = list(ddragon.champions.keys())
    print(f"[SERVER] Analyzing {len(candidates)} candidates for role '{role}'...")
    
    # 2. Lazy Hydrate Meta
    if not meta_engine.champion_stats:
        meta_engine.update_meta_from_ddragon(ddragon.champions)
        
    # 3. Analyze Composition Needs (Still useful for logging even if not used in score)
    needs = comp_analyzer.analyze_team(my_team)
    
    # Check if we need to hydrate profile
    # USER REQUEST: DISABLE PROFILE ENGINE (Pure AI Mode)
    # if 'puuid' in current_state:
    #     puuid = current_state['puuid']
    #     ...
    #     if not profile_engine.user_pool:
    #         profile_engine.update_id_map(ddragon.get_id_map()) 
    #         profile_engine.update_data(puuid)

    results = []
    print(f"[DEBUG] Analysis Start. My Team: {my_team}, Enemy: {enemy_team}, Role: {role}")
    
    # 3. Batch Analysis (Optimization)
    print(f"[SERVER] Batch Processing {len(candidates)} scenarios...")
    results = draft_engine.batch_rank(
        candidates=candidates,
        my_team_roles=my_team_roles,
        enemy_team_roles=enemy_team_roles,
        my_role=role,
        ddragon=ddragon
    )
    
    if not results:
        print("[DEBUG] Batch Rank returned 0 results!")
    else:
        print(f"[DEBUG] Batch Rank returned {len(results)} results. Top: {results[0]['champion']} ({results[0]['score']})")

            
    # Sort by score
    results.sort(key=lambda x: x['score'], reverse=True)
    
    # 4. Handle "My Pick" Analysis
    selection_stats = None
    my_pick_id = current_state.get('my_pick')
    if my_pick_id and my_pick_id != "0":
        # Find if it is in results first
        # We need the NAME to match DDragon (results use names?)
        # batch_rank uses names or IDs? 
        # SmartDraft.batch_rank uses ddragon for names.
        
        # Look up name
        pick_name = None
        id_map = ddragon.get_id_map()
        if int(my_pick_id) in id_map:
            pick_name = id_map[int(my_pick_id)]
            
        if pick_name:
            # Find in results
            for r in results:
                if r['champion'] == pick_name:
                    selection_stats = r
                    break
            
            # If not in results (should be, we analyze all), force calc?
            # We analyzed all keys, so it must be there unless filter removed it.
            if not selection_stats:
                pass 
                
    current_state['selection_stats'] = selection_stats
    
    # Create a quick Score Map for UI { "Ahri": 65, "Zed": 50 }
    score_map = {r['champion']: r['score'] for r in results}
    current_state['all_scores'] = score_map

    # LIMIT TO TOP 15 to prevent UI Lag
    results = results[:15]
    
    current_state['recommendations'] = results
    return results

@app.route('/analyze', methods=['POST'])
def analyze():
    # Only hydrate meta once
    if not meta_engine.champion_stats:
        print("[SERVER] Hydrating Meta Engine...")
        meta_engine.update_meta_from_ddragon(ddragon.champions)
        
    """
    Manually trigger analysis (or used by frontend to refresh).
    """
    data = request.json or {}
    # Update state if provided
    current_state['my_team'] = data.get('my_team', current_state['my_team'])
    current_state['enemy_team'] = data.get('enemy_team', current_state['enemy_team'])
    
    results = run_analysis()
    return jsonify(results)

@app.route('/gameplan', methods=['GET'])
def get_gameplan():
    champion = request.args.get('champion')
    if not champion: return jsonify({"error": "No champion specified"})
    
    # 1. Generate Text Strategy
    # Note: Server already updated to new signature? YES.
    # Checking previous replace... 
    # Ah, previous replace was:
    # plan = gameplan_engine.generate_plan(champion, current_state['enemy_team'], current_state.get('assigned_position', 'MIDDLE'), ddragon.champions)
    # The new signature is: generate_plan(self, my_champion, enemy_team, my_role, ddragon_data=None)
    # They match!
    plan = gameplan_engine.generate_plan(
        champion, 
        current_state['enemy_team'],
        current_state.get('assigned_position', 'MIDDLE'),
        ddragon.champions
    )
    
    # 2. Generate Smart Build
    # Determine Class (Simplified mapping)
    c_info = ddragon.champions.get(champion, {})
    roles = c_info.get("roles", [])
    
    build_role = "AD"
    if "Mage" in roles or "Support" in roles: build_role = "AP"
    if "Tank" in roles: build_role = "Tank"
    # Refinement needed for AD Mages vs AP Assassins etc, but good for MVP High-End Logic
    
    build_data = item_engine.generate_build(champion, current_state['enemy_team'], role=build_role)
    
@app.route('/setup_override', methods=['POST'])
def setup_override():
    """
    Called when user manually swaps lanes in the UI.
    Merges overrides into the state so the AI respects them.
    Payload: { "my_team_roles": { "TOP": "Garen", ... }, "enemy_team_roles": ... }
    """
    data = request.json or {}
    print(f"[SERVER] Received Role Override: {data}")
    
    # Helper to map Names -> IDs
    def map_names_to_ids(role_map):
        name_to_id = {}
        # Ensure we have data
        if ddragon and ddragon.champions:
            for k, v in ddragon.champions.items():
                name_to_id[v['name']] = k
        
        new_map = {}
        for r, val in role_map.items():
            if val in name_to_id:
                new_map[r] = name_to_id[val]
            else:
                # Might be already an ID or unknown
                new_map[r] = val
        return new_map

    if 'my_team_roles' in data:
        current_state['my_team_roles'] = map_names_to_ids(data['my_team_roles'])
        
    if 'enemy_team_roles' in data:
        current_state['enemy_team_roles'] = map_names_to_ids(data['enemy_team_roles'])

    if 'assigned_position' in data:
        role = data['assigned_position']
        print(f"[SERVER] Overriding My Role to: {role}")
        current_state['assigned_position'] = role

    # Force re-analysis in background (or foreground)
    # running in thread to not block response
    threading.Thread(target=run_analysis).start()
    
    return jsonify({"status": "ok"})

@app.route('/predict', methods=['GET'])
def get_prediction():
    # Expects team IDs? Or uses current state?
    # Using current state is best for the overlay.
    
    # Needs integer IDs
    try:
        my_team = [int(c) for c in current_state['my_team']]
        enemy_team = [int(c) for c in current_state['enemy_team']]
    except:
        # If they are names or empty
        return jsonify({"probability": 0.5, "text": "Waiting for teams..."})
        
    print(f"[DEBUG] Predict Request. My Team: {my_team}, Enemy: {enemy_team}")
    
    if not my_team or not enemy_team:
         return jsonify({"probability": 50.0, "text": "Draft incomplete"})
         
    prob = win_predictor.predict(my_team, enemy_team, ddragon)
    print(f"[DEBUG] Prediction Result: {prob}")
    
    text = "Even Match"
    if prob > 0.55: text = "We are favoured"
    if prob > 0.65: text = "Easy Win"
    if prob < 0.45: text = "Hard Game"
    if prob < 0.35: text = "Unplayable"
    
    return jsonify({
        "probability": round(prob * 100, 1),
        "text": text
    })


# --- LCU WORKER ---
from src.lcu_connector import LCUWorker
# Pass the analysis function so LCU worker can trigger it on update
lcu_worker = LCUWorker(current_state, on_update=run_analysis)
lcu_worker.start()

# --- META CRAWLER (The Left Brain) ---
from src.crawler import MetaCrawler

# Optional Crawler Startup
enable_crawler = os.environ.get("ENABLE_CRAWLER", "false").lower() == "true"

crawler = MetaCrawler(meta_engine)
if enable_crawler:
    print("[SERVER] Starting Embedded Crawler...")
    crawler.start()
else:
    print("[SERVER] Embedded Crawler DISABLED (Drafting Mode).")

# --- LEARNING ENGINE (The Evolution) ---
from src.engine.learning import LearningEngine
learning_engine = LearningEngine()
# Re-init SmartDraft with Learning -> DELETED (Sabotages Brain)
# draft_engine = SmartDraft(meta_engine, profile_engine, comp_analyzer, learning_engine)

def background_learning_task():
    """
    Waits for PUUID then triggers learning.
    """
    print("[LEARNING] Waiting for User Login to evolve...")
    while not current_state.get('puuid'):
        time.sleep(2)
        
    puuid = current_state['puuid']
    print(f"[LEARNING] User detected (Local ID: {puuid[:8]}...). Verifying Identity...")
    
    # FIX: LCU sometimes returns a local UUID (36 chars) instead of Riot PUUID (78 chars)
    if len(puuid) < 50:
        game_name = current_state.get('summoner_name')
        tag_line = current_state.get('tag_line')
        
        if game_name and tag_line:
            print(f"[LEARNING] UUID Detected. Resolving Global PUUID for {game_name}#{tag_line}...")
            client = profile_engine.client # ProfileEngine has the client instance
            
            acc = client.get_account_by_riot_id(game_name, tag_line)
            if acc and 'puuid' in acc:
                puuid = acc['puuid']
                print(f"[LEARNING] Resolved Global PUUID: {puuid[:10]}...")
            else:
                print(f"[LEARNING] Failed to resolve global PUUID. Using local (might fail).")
        else:
             print(f"[LEARNING] Missing Name/Tag for resolution. Using local PUUID.")

    print(f"[LEARNING] Fetching Match History for PUUID: {puuid[:10]}...")
    
    # 1. Fetch History (Deep Scan)
    # User requested "thousands".
    # Rate Limit: 100 requests / 2 minutes.
    # 1000 games = 1000 requests for details = ~20 minutes.
    # We will do it in background batches.
    
    target_games = 1000
    batch_size = 100
    current_start = 0
    
    print(f"[LEARNING] Starting Deep Analysis of last {target_games} games...")
    
    while current_start < target_games:
        print(f"[LEARNING] Fetching Batch {current_start}-{current_start+batch_size}...")
        matches = client.get_matchlist(puuid, start=current_start, count=batch_size) 
        if not matches:
            print("[LEARNING] No more matches found.")
            break
            
        history_data = [] # List of {championId, win}
        
        for mid in matches:
            # Check cache in LearningEngine to skip known matches?
            # For now, we just process. Rate Limit in RiotClient handles 429s.
            
            details = client.get_match_details(mid)
            if not details: continue
            
            # Find participant
            info = details.get('info', {})
            parts = info.get('participants', [])
            for p in parts:
                if p.get('puuid') == puuid:
                    history_data.append({
                        "championId": p['championId'],
                        "win": p['win']
                    })
                    break
        
        # Evolve after each batch
        if history_data:
            learning_engine.learn_from_history(history_data, ddragon.get_id_map(), ddragon)
            print(f"[LEARNING] Processed batch. Brain updated.")
        
        current_start += batch_size
        time.sleep(1) # Small breather between batches
    
    print("[LEARNING] Deep Analysis Complete.")

# Start Learning Thread
t_learn = threading.Thread(target=background_learning_task)
t_learn.daemon = True
# t_learn.start()
print("[SERVER] Legacy Learning Engine DISABLED (Using SOTA Brain instead).")

def start_server():
    app.run(port=5000, debug=False, use_reloader=False)

if __name__ == '__main__':
    print("\n" * 5)
    print("##################################################")
    print("#                                                #")
    print("#      HYBRID ORACLE V2.2 (HOTFIX LOADED)        #")
    print("#      -> Batch Processing: ENABLED              #")
    print("#      -> ID Mismatch Fix: APPLIED               #")
    print("#                                                #")
    print("##################################################\n")
    print("[SERVER] Starting Flask API...")
    start_server()

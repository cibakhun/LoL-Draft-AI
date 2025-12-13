
import os
import sys
# Add project root to path
sys.path.append(os.getcwd())

from src.engine.ensemble_brain import EnsembleBrain
from src.engine.recommendation import RecommendationEngine
from src.data.ddragon import DataDragon

def main():
    print("=== AI DRAFTING ASSISTANT (INTERACTIVE) ===")
    print("Loading Brain... (This may take a few seconds)")
    
    ddragon = DataDragon()
    brain = EnsembleBrain()
    
    if not brain.load("brain.joblib"):
        print("[!] No brain found. Training one quickly on available data...")
        match_dir = os.path.join("src", "data", "matches")
        brain.train(match_dir, ddragon)
        brain.save("brain.joblib")
        
    engine = RecommendationEngine(brain, ddragon)
    name_to_id = {data['name'].lower(): int(data['key']) for data in ddragon.champions.values()}
    id_to_name = {int(data['key']): data['name'] for data in ddragon.champions.values()}
    
    def get_id(name):
        n = name.strip().lower()
        if n in name_to_id: return name_to_id[n]
        # Fuzzy search? Simple substring
        for k in name_to_id:
            if n in k: return name_to_id[k]
        return 0

    # Default Config
    draft_config = {
        'meta_tolerance': 0.2, # Strict
        'proficiency_bias': 0.5 # Moderate
    }

    while True:
        print("\n" + "="*40)
        print("NEW DRAFT SCENARIO")
        print(f"[Settings] Meta Tolerance: {draft_config['meta_tolerance']:.1f} | Proficiency Bias: {draft_config['proficiency_bias']:.1f}")
        print("Type '/config' to change settings.")
        print("Enter champion names for each role. Use '?' or 'me' for the slot you want to pick.")
        print("Leave blank or '-' for empty/unknown.")
        
        try:
            roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
            my_team = []
            enemy_team = []
            target_role = "Any"
            
            # Helper to check for commands
            def check_command(val):
                if val.strip() == '/config':
                    print("\n--- CONFIGURATION MENU ---")
                    try:
                        tol = input(f"Meta Tolerance (0.0 Strict - 1.0 Loose) [{draft_config['meta_tolerance']}]: ")
                        if tol: draft_config['meta_tolerance'] = float(tol)
                        
                        bias = input(f"Proficiency Bias (0.0 None - 1.0 High) [{draft_config['proficiency_bias']}]: ")
                        if bias: draft_config['proficiency_bias'] = float(bias)
                        print("Settings Updated!")
                    except: print("Invalid input. Keeping old settings.")
                    return True
                return False
            
            print("\n--- YOUR TEAM ---")
            for r in roles:
                val = input(f"  {r:<7}: ").strip()
                if check_command(val): break # Restart loop if config changed
                
                if val in ['?', 'me', 'ME']:
                    my_team.append(0) # 0 = Search Slot
                    target_role = r
                elif val in ['', '-']:
                    my_team.append(0)
                else:
                    cid = get_id(val)
                    if cid == 0: print(f"    [!] Unknown: {val}")
                    my_team.append(cid)
            
            # Simple hack: if we broke out due to command, continue outer loop
            if len(my_team) < 5 and target_role == "Any": continue

            print("\n--- ENEMY TEAM ---")
            for r in roles:
                val = input(f"  {r:<7}: ").strip()
                if check_command(val): break
                
                if val in ['', '-', '?']:
                    enemy_team.append(0)
                else:
                    cid = get_id(val)
                    if cid == 0: print(f"    [!] Unknown: {val}")
                    enemy_team.append(cid)
                    
            if len(enemy_team) < 5: continue
                    
            print(f"\n[AI] Analyzing Draft...")
            print(f" -> Us: {[id_to_name.get(c, '?') for c in my_team]}")
            print(f" -> Them: {[id_to_name.get(c, '?') for c in enemy_team]}")
            print(f" -> Target Role: {target_role}")
            
            recs = engine.recommend(my_team, enemy_team, role=target_role, config=draft_config, top_k=5)
            
            print("\n>>> RECOMMENDED PICKS <<<")
            for i, r in enumerate(recs):
                cname = id_to_name.get(r['champion_id'], "Unknown")
                prob = r['win_probability'] * 100
                print(f"#{i+1}: {cname:<12} (Win Chance: {prob:.1f}%)")
                
            # Explanation for #1
            if recs:
                best_id = recs[0]['champion_id']
                best_name = id_to_name.get(best_id, "Unknown")
                print(f"\n[WHY {best_name}?] (Feature Importance)")
                
                sim_team = my_team.copy()
                # Find the slot
                if 0 in sim_team: sim_team[sim_team.index(0)] = best_id
                
                reasons = brain.explain_decision(sim_team, enemy_team, ddragon)
                for reason in reasons:
                    print(f" -> {reason}")
                    
        except KeyboardInterrupt:
            print("\nBye!")
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    main()

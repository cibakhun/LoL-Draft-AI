
import torch
import time
from src.engine.mcts import SpatialMCTS

class DraftStrategist:
    """
    Central brain for interpreting the draft state and generating recommendations.
    Shared by both the CLI (live_engine.py) and GUI (titan_app.py).
    """
    def __init__(self, brain, feature_engine, data_dragon, lane_metrics=None):
        self.brain = brain
        self.fe = feature_engine
        self.dd = data_dragon
        self.lane_data = lane_metrics or {}
        
        # Caching
        self.last_base_hash = None
        self.last_recs_cache = ([], [], []) # suggestions, ids, visits
        
    def _parse_bans_from_actions(self, session, am_i_blue):
        """Fallback: Extract bans from actions if 'bans' object is empty."""
        my_bans = []
        their_bans = []
        
        # Robust Logic: 0-4 is Blue, 5-9 is Red.
        # We don't need to parse 'myTeam' for this, just checking actorCellId is enough.

        actions = session.get('actions', [])
        for turn in actions:
            for action in turn:
                if action.get('type') == 'ban' and action.get('completed', False):
                    champ_id = action.get('championId', 0)
                    actor = action.get('actorCellId')
                    
                    if champ_id > 0 and actor is not None:
                        is_blue_actor = (actor < 5)
                        
                        # Map to My/Theirs relative to 'am_i_blue'
                        # if am_i_blue and is_blue_actor -> My Ban
                        # if am_i_blue and not is_blue_actor -> Their Ban
                        # if not am_i_blue (Red) and is_blue_actor -> Their Ban
                        
                        if is_blue_actor == am_i_blue:
                            my_bans.append(champ_id)
                        else:
                            their_bans.append(champ_id)
                            
        # print(f"[DEBUG] PARSED BANS RESULT: My={my_bans} Theirs={their_bans}")
        return my_bans, their_bans

    def detect_player_role(self, session):
        """
        Asks the LCU for the user's assigned role.
        """
        local_cell_id = session.get('localPlayerCellId')
        my_team = session.get('myTeam', [])
        
        # Find our player object
        me = next((p for p in my_team if p.get('cellId') == local_cell_id), None)
        
        if me:
            role = me.get('assignedPosition', '').upper()
            if role == 'UTILITY': return 'SUPPORT'
            if role in ['TOP', 'JUNGLE', 'MIDDLE', 'BOTTOM']: return role
            
        return None 

    def parse_lobby(self, session, skill, patch):
        """
        Parses LCU Session into TitanNet Spatial Tensors.
        """
        # 1. Initialize Empty Spatial Board (10 Slots)
        picks_vec = [0] * 10
        # Turns Vec: Just 1-10 to signify "Seat Number"
        turns_vec = list(range(1, 11))
        
        # 2. Identify Sides
        my_team = session.get('myTeam', [])
        their_team = session.get('theirTeam', [])
        
        am_i_blue = False
        
        # Robust Side Detection via Cell ID
        local_cell = session.get('localPlayerCellId', -1)
        if local_cell >= 0:
            am_i_blue = (local_cell < 5)
        else:
            # Fallback for spectators or weird states
            for p in my_team:
                tid = p.get('team', p.get('teamId', 0))
                if tid == 100:
                    am_i_blue = True
                    break
                
        blue_team_data = my_team if am_i_blue else their_team
        red_team_data = their_team if am_i_blue else my_team
        
        # [TITAN V3.5 SPATIAL REFACTOR]
        # Use Centralized Vectorization from FeatureEngine
        # to ensure "Train-Serve Symmetry".
        
        # 1. Transform LCU Session -> Teams Dicts
        blue_roles = {}
        red_roles = {}
        
        roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
        
        # Helper to map cell to role index (0-4)
        # Blue: 0-4, Red: 5-9
        def map_participants(team_list, target_dict, offset):
            for p in team_list:
                cell = p.get('cellId', -1)
                cid = p.get('championId', 0)
                if cid == 0: cid = p.get('championPickIntent', 0)
                # if cid == 0: continue # Keep 0s? feature_engine handles 0s
                
                # Check Bounds
                local_idx = cell - offset
                if 0 <= local_idx <= 4:
                    role_name = roles[local_idx]
                    if cid > 0: target_dict[role_name] = cid

        map_participants(blue_team_data, blue_roles, 0)
        map_participants(red_team_data, red_roles, 5)
        
        # 2. Vectorize (Spatial Order: Blue 0-4 then Red 0-4)
        # returns (draft_ids, seat_ids, temporal_turns)
        draft_ids, seat_ids, temporal_turns = self.fe.vectorize_sequence(blue_roles, red_roles)
        
        picks_vec = draft_ids
        turns_vec = seat_ids # Now contains 1-10 Spatial IDs

        # Bans
        my_bans = session.get('bans', {}).get('myTeamBans', [])
        their_bans = session.get('bans', {}).get('theirTeamBans', [])
        
        # Fallback if empty (LCU quirks)
        if not my_bans and not their_bans:
            # print(f"[DEBUG] Bans Empty, Parsing Actions...")
            mb, tb = self._parse_bans_from_actions(session, am_i_blue)
            my_bans = mb
            their_bans = tb
            
        # print(f"[DEBUG] Raw BANS: My={my_bans} Theirs={their_bans}")
        
        blue_bans = my_bans if am_i_blue else their_bans
        red_bans = their_bans if am_i_blue else my_bans
        
        bans_vec = [0] * 10
        for i, bid in enumerate(blue_bans[:5]): bans_vec[i] = self.fe.vocab.get(bid, 0)
        for i, bid in enumerate(red_bans[:5]): bans_vec[i+5] = self.fe.vocab.get(bid, 0)
        
        # Meta / Mastery
        side = 0.0 if am_i_blue else 1.0
        meta_vec = [float(skill), float(patch), side]
        mast_vec = [0.0] * 10
        
        t_picks = torch.tensor([picks_vec], dtype=torch.int16)
        t_turns = torch.tensor([turns_vec], dtype=torch.int8)
        t_bans  = torch.tensor([bans_vec], dtype=torch.int16)
        t_mast  = torch.tensor([mast_vec], dtype=torch.float16)
        t_meta  = torch.tensor([meta_vec], dtype=torch.float16)
        
        # [TITAN V3.5 TIME VECTOR]
        # Use vectorized temporal turns from FeatureEngine
        times_vec = temporal_turns
        
        t_times = torch.tensor([times_vec], dtype=torch.int8)
        
        # Raw Data for UI (Before Tokenization)
        raw_picks = [0] * 10
        raw_bans = []
        
        # Re-extract raw IDs for UI consistency
        def fill_raw(team_list, start_idx):
            for p in team_list:
                cell = p.get('cellId', -1)
                cid = p.get('championId', 0)
                if cid == 0: cid = p.get('championPickIntent', 0)
                if cid == 0: continue
                if 0 <= cell <= 9: raw_picks[cell] = cid
            
        fill_raw(blue_team_data, 0)
        fill_raw(red_team_data, 5)
        
        # Raw Bans
        for bid in blue_bans[:5]: raw_bans.append(bid)
        # Ensure 5 slots
        while len(raw_bans) < 5: raw_bans.append(0)
        for bid in red_bans[:5]: raw_bans.append(bid)
        while len(raw_bans) < 10: raw_bans.append(0)
        
        return (t_picks, t_turns, t_bans, t_mast, t_meta, t_times), (raw_picks, raw_bans)

    def analyze(self, session, skill=6.0, patch=14.23, settings=None, mastery=None):
        """
        Full pipeline: Parse -> Think -> Recommend
        Returns: (suggestions_list, win_prob, lane_status_str, detailed_context_dict)
        """
        # 1. Parse
        # 1. Parse
        t_inputs, raw_inputs = self.parse_lobby(session, skill, patch)
        xp, xt, xb, xm, xmeta, x_times = t_inputs # Unpack Time Vector
        raw_picks, raw_bans = raw_inputs
        
        # 2. Context
        local_cell = session.get('localPlayerCellId', -1)
        my_pos = self.detect_player_role(session)
        
        my_champ_id = 0
        enemy_champ = 0
        
        # Find My Pick
        for p in session.get('myTeam', []):
            if p['cellId'] == local_cell:
                my_champ_id = p.get('championId', 0)
                if my_champ_id == 0:
                    my_champ_id = p.get('championPickIntent', 0)
                break
                
        # Find Opponent
        if my_pos and my_pos != "None": 
             op_pos = "UTILITY" if my_pos == "SUPPORT" else my_pos
             for p in session.get('theirTeam', []):
                if p.get('assignedPosition', '').upper() == op_pos:
                    enemy_champ = p.get('championId', 0)
                    break
        else:
            # Mirror Logic
            target_cell = (local_cell + 5) % 10
            for p in session.get('theirTeam', []):
                if p.get('cellId') == target_cell:
                    enemy_champ = p.get('championId', 0)
                    my_pos = "Custom/Mirror"
                    break

        # Move to Device
        xp = xp.to(self.brain.device).long()
        xt = xt.to(self.brain.device).long()
        xb = xb.to(self.brain.device).long()
        xm = xm.to(self.brain.device).float()
        xmeta = xmeta.to(self.brain.device).float()
        x_times = x_times.to(self.brain.device).long()
        
        # Use tokens for logic if needed, but we have raw_picks now
        picks_list = raw_picks
        bans_list = raw_bans

        am_i_blue_local = False
        for p in session.get('myTeam', []):
             tid = p.get('team', p.get('teamId', 0))
             if tid == 100:
                am_i_blue_local = True
                break
        offset = 0 if am_i_blue_local else 5

        # Use local_cell directly as it maps 1:1 with the tensor indices in parse_lobby
        target_slot = local_cell
        
        # Fallback if local_cell is invalid (e.g. spectator?)
        if target_slot < 0 or target_slot > 9:
             target_slot = -1
             # Try to find first empty slot?
             for i in range(10):
                 if picks_list[i] == 0:
                     target_slot = i
                     break

                     target_slot = i
                     break

        # 4. MCTS Inference
        # Optimized with Base-State Caching
        
        top_ids = []
        win_prob = 0.5
        top_visits = []
        
        # Construct Base State Hash (excluding my hover)
        # We need to treat my slot as 0 for the "Search Base"
        base_picks = list(raw_picks)
        if target_slot != -1 and 0 <= target_slot < 10:
             base_picks[target_slot] = 0
             
        # Hash components: Picks (Base), Bans, Skill, Patch, Mastery Bias, Risk Level
        s_bias = settings.get("mastery_bias", 1.0) if settings else 1.0
        s_risk = settings.get("risk_level", 0.0) if settings else 0.0
        
        current_base_hash = hash(tuple(base_picks) + tuple(raw_bans) + (skill, patch, s_bias, s_risk))
        
        # Check Cache
        cache_hit = False
        if self.last_base_hash == current_base_hash:
             cache_hit = True
             # print("[STRATEGIST] Cache Hit! Reusing Search Results.")
             suggestions_cache, top_ids, top_visits = self.last_recs_cache
        else:
             # print("[STRATEGIST] Cache Miss. Running MCTS...")
             pass
        
        state_tupid = (xp, xt, xb, xm, xmeta, x_times) # Added x_times
        
        # Always evaluate Dynamic Win Probability for the ACTUAL state (with hover)
        # This ensures the "Oracle" is responsive even if suggestions are cached.
        mcts = SpatialMCTS(self.brain.model, self.fe, n_sims=50) # Lightweight instance just for eval if needed
        _, current_eval = mcts.evaluate(state_tupid)
        
        if picks_list[target_slot] != 0:
             win_prob = current_eval
             
        if not cache_hit and target_slot != -1:
             # Run Full Search
             
             # Prepare SEARCH state (Empty Slot)
             xp_search = xp.clone()
             xp_search[0][target_slot] = 0
             search_state = (xp_search, xt, xb, xm, xmeta, x_times)
             
             # Filter valid actions
             picked_set = set()
             pl_search = xp_search[0].cpu().tolist()
             for pid in pl_search:
                 if pid > 0: picked_set.add(pid)
                 
             banned_set = set(bans_list)
             valid_actions = set(range(1, len(self.fe.vocab)))
             valid_actions -= picked_set
             valid_actions -= banned_set
             
             root = mcts.search(search_state, target_slot, valid_actions)
             
             # Default sort by visits
             items = list(root.children.items())
             
             # 1. Apply Mastery Bias
             if mastery and settings:
                 bias = settings.get("mastery_bias", 1.0)
                 if abs(bias - 1.0) > 0.05:
                     m_map = {m['championId']: m['championPoints'] for m in mastery}
                     def score_func(x):
                         cid, node = x
                         raw_score = node.visits
                         pts = m_map.get(cid, 0)
                         import math
                         log_pts = math.log10(pts + 1) 
                         factor = 1.0 + (log_pts * 0.2 * (bias - 1.0))
                         return raw_score * factor
                     items.sort(key=score_func, reverse=True)
                 else:
                     items.sort(key=lambda x: x[1].visits, reverse=True)
             else:
                 items.sort(key=lambda x: x[1].visits, reverse=True)

             # 2. Apply Risk/Creativity
             if settings:
                 risk = settings.get("risk_level", 0.0)
                 if risk > 0.1:
                     import random
                     candidates = items[:10]
                     rest = items[10:]
                     
                     scored_candidates = []
                     for i, item in enumerate(candidates):
                         base_score = float(len(candidates) - i)
                         noise = random.uniform(-1.0, 1.0) * risk * 5.0
                         scored_candidates.append((base_score + noise, item))
                     
                     scored_candidates.sort(key=lambda x: x[0], reverse=True)
                     items = [x[1] for x in scored_candidates] + rest

             sorted_children = items
             top_ids = [a for a, n in sorted_children[:5]]
             top_visits = [n.visits for a, n in sorted_children[:5]]
             
             # Cache Update happens after formatting because we want to cache the FORMATTED suggestions logic?
             # Actually, suggestions formatting depends on `predicted_wr` which comes from NODE data.
             # If we only cache IDs/Visits, we lose the Node objects.
             # So we must format suggestions INSIDE the "Miss" block or cache the Nodes?
             # Node objects are not easily serializable or kept, but we can keep list of (cid, visits, confidence).
             # Let's keep the `sorted_children` list? No, MCTS tree is large.
             # Better: Format suggestions NOW and cache the final list.
             
        # 5. Format Suggestions (Executed only on Cache Miss or we duplicate logic?)
        # Logic structure constraint: We need `sorted_children` to format suggestions.
        # If Cache Hit, we don't have `sorted_children` (unless we cache them).
        
        # REFACTOR: Move formatting inside Cache Miss block, and cache the RESULT `suggestions`.
        
        if not cache_hit and target_slot != -1:
             # ... Formatting Logic ...
             pass 
             
        # Wait, I can't easily refactor the whole block with `multi_replace` if I don't replace the whole block.
        # I will replace lines 238 to 340 (Search Block) entirely.

             

             # --- Formatting Logic Inline ---
             suggestions = []
             max_v = top_visits[0] if top_visits else 1
             if max_v == 0: max_v = 1
             
             # Maps Token -> Real ID
             inv_vocab = {v: k for k, v in self.fe.vocab.items()}
             
             for i, token_id in enumerate(top_ids):
                score = int((top_visits[i] / max_v) * 100)
                
                # Convert Token to Real ID
                real_id = inv_vocab.get(token_id, 0)
                cid = real_id # Use Real ID for lookup
                
                name = self.dd.get_id_map().get(real_id, f"{real_id}")
                
                # Resolve Asset ID (Name Key) using Real ID
                asset_id = str(real_id) # Default to ID
                for c_key, c_val in self.dd.champions.items():
                     if int(c_val['key']) == real_id:
                          asset_id = c_key # This IS the Asset Name (e.g. "MissFortune")
                          break
                          
                # AI Confidence
                child_node = next((n for a, n in sorted_children if a == cid), None)
                predicted_wr = 0.5
                if child_node:
                     if child_node.visits > 0:
                         predicted_wr = child_node.value_sum / child_node.visits
                     else:
                         predicted_wr = child_node.prior
                
                # Stats
                simulated_team = []
                current_picks_sim = xp[0].cpu().tolist() # Copy from tensor
                current_picks_sim[target_slot] = cid
                
                team_slice = current_picks_sim[0:5] if (offset == 0) else current_picks_sim[5:10]
                stats = self._calculate_team_stats(team_slice)
                stats_str = f"AD: {stats['ad']:.0f}% AP: {stats['ap']:.0f}%"
                
                rec_data = {
                    "id": str(asset_id),
                    "name": name,
                    "score": score,
                    "confidence": predicted_wr,
                    "stats": stats,
                    "reasoning": stats_str,
                    "wr": predicted_wr * 100, 
                    "delta": (predicted_wr - win_prob) * 100
                }
                
                if enemy_champ > 0:
                    key = f"{cid}_vs_{enemy_champ}"
                    diff = self.lane_data.get(key)
                    if diff: rec_data["diff"] = int(diff)
                    
                suggestions.append(rec_data)
             
             # Save to Cache
             self.last_base_hash = current_base_hash
             self.last_recs_cache = (suggestions, top_ids, top_visits)

        elif cache_hit:
             suggestions = suggestions_cache
             # We do NOT update suggestions dynamically (e.g. "delta" might change if win_prob changes significantly?)
             # Yes, if `win_prob` changes (due to hover), `delta` (suggested_wr - win_prob) changes.
             # But `suggested_wr` is static for that suggestion in that Base State.
             # So we should re-calculate `delta`?
             # `suggestions_cache` has "wr" (absolute). We can update "delta".
             
             for r in suggestions:
                  r['delta'] = r['wr'] - (win_prob * 100.0)
        else:
             # Target slot -1 or something
             suggestions = []

            
        lane_status = f"Lane: {my_pos}" if my_pos else "Observing"
        if enemy_champ > 0:
             ename = self.dd.get_id_map().get(enemy_champ, str(enemy_champ))
             lane_status += f" vs {ename}"
             
        context = {
            "snapshot": (picks_list, bans_list, my_pos, enemy_champ, my_champ_id),
            "my_pos": my_pos,
            "my_champ_id": my_champ_id,
            "enemy_champ": enemy_champ,

        }
        if my_champ_id > 0:
             # Calculate stats for the hover
             # We reuse the team slice logic from "Rich Data" block
             # Ideally we refactor that logic out, but for now duplicate for safety/speed
             
             # Reconstruct team
             # current_picks[target_slot] = my_champ_id
             # Wait, xp[0] (picks_list) might already have my_champ_id if I picked it? 
             # No, if it's Intent (PickIntent), parse_lobby puts it in picks_vec if cell valid
             # So xp[0] might ALREADY contain it.
             
             if picks_list[target_slot] == 0:
                  # If logic didn't put it in (e.g. it's just intent but parse_lobby filtered it?)
                  # parse_lobby DOES include PickIntent.
                  # So picks_list[target_slot] is likely already my_champ_id.
                  pass
                  
             # Force it for stats calculation just in case
             sim_picks = list(picks_list)
             if target_slot != -1: sim_picks[target_slot] = my_champ_id
             
             team_slice = sim_picks[0:5] if (offset == 0) else sim_picks[5:10]
             h_stats = self._calculate_team_stats(team_slice)
             
             h_name = self.dd.get_id_map().get(my_champ_id, str(my_champ_id))
             
             # Resolve Asset ID
             h_asset = str(my_champ_id)
             for c_key, c_val in self.dd.champions.items():
                 if int(c_val['key']) == my_champ_id:
                      h_asset = c_key
                      break
             
             context["hover_data"] = {
                 "id": h_asset,
                 "name": h_name,
                 "stats": h_stats,
                 "reasoning": f"AD: {h_stats['ad']:.0f}% AP: {h_stats['ap']:.0f}%"
             }

        return suggestions, win_prob, lane_status, context

    def _calculate_team_stats(self, team_ids):
        total_ad = 0
        total_ap = 0
        total_tank = 0
        total_cc = 0
        count = 0
        
        for cid in team_ids:
            if cid == 0: continue
            
            # Use FE cache if available, or fetch
            c_data = self.fe.ddragon_cache.get(cid)
            if not c_data: continue
            
            count += 1
            info = c_data.get('info', {})
            
            # Riot Stats: Attack (AD), Magic (AP), Defense (Tank), Difficulty
            ad = info.get('attack', 0)
            ap = info.get('magic', 0)
            defs = info.get('defense', 0)
            
            total_ad += ad
            total_ap += ap
            total_tank += defs
            
            # Heuristics for CC based on "tags" or "roles" is hard without more data
            # Helper: Use roles
            roles = c_data.get('roles', [])
            if "Tank" in roles or "Support" in roles:
                 total_cc += 2
            if "Mage" in roles:
                 total_cc += 1
                 
        if count == 0: return {'ad':0, 'ap':0, 'tank':0}
        
        # Normalize to percentages/scores
        total_dmg = total_ad + total_ap
        pct_ad = (total_ad / total_dmg * 100) if total_dmg > 0 else 50
        pct_ap = (total_ap / total_dmg * 100) if total_dmg > 0 else 50
        
        return {
            "ad": pct_ad,
            "ap": pct_ap,
            "tank": total_tank, # sum of Defense scores
            "cc": total_cc
        }

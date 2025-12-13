import numpy as np
import os
import json
import joblib

# Optional SOTA Brain
try:
    from src.engine.neural_brain import NeuralBrain, HAS_TORCH
except ImportError:
    HAS_TORCH = False
    NeuralBrain = None

from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier

class EnsembleBrain:
    def __init__(self):
        self.neural = None
        
        # 1. The Nuclear Option (PyTorch)
        if HAS_TORCH:
            print("[HIVE MIND] PyTorch Detected. Initializing Neural Core (LeagueNet)...")
            self.neural = NeuralBrain()
        else:
            print("[HIVE MIND] PyTorch NOT Detected. Running in Legacy Mode (CPU).")

        # 2. Gradient Boosting (Logic / Optimization) - Still useful for structured data
        self.booster = HistGradientBoostingClassifier(
            max_iter=100,
            learning_rate=0.05,
            max_depth=3,
            min_samples_leaf=5,
            early_stopping=True,
            random_state=42
        )
        
        # 3. Random Forest (Experience / Memory)
        self.forest = RandomForestClassifier(
            n_estimators=150,
            max_depth=8, 
            min_samples_leaf=4, 
            n_jobs=-1, 
            random_state=42
        )
        
        self.is_trained = False
        self.model_path = "brain.joblib"

    def save(self, path=None):
        target = path or self.model_path
        if self.is_trained:
            print(f"[HIVE MIND] Saving architectural pathways to {target}...")
            joblib.dump(self.council, target)
            
            # Save Meta Stats
            if hasattr(self, 'meta_stats'):
                stats_path = target.replace(".joblib", "_stats.json")
                with open(stats_path, 'w') as f:
                    json.dump(self.meta_stats, f)
                print(f" -> Meta-Stats persisted to {stats_path}")
            
            print(" -> Memory persisted.")
            
    def load(self, path=None):
        target = path or self.model_path
        if os.path.exists(target):
            print(f"[HIVE MIND] Loading long-term memory from {target}...")
            self.council = joblib.load(target)
            
            # Load Meta Stats
            stats_path = target.replace(".joblib", "_stats.json")
            if os.path.exists(stats_path):
                with open(stats_path, 'r') as f:
                    # JSON keys are strings, convert champ IDs back to int if needed?
                    # Actually JSON supports string keys primarily. 
                    # We will likely store "103": {...}
                    raw_stats = json.load(f)
                    # Convert keys to int
                    self.meta_stats = {int(k): v for k, v in raw_stats.items()}
            else:
                self.meta_stats = {}

            self.is_trained = True
            return True
        return False
        
    def _vectorize_team(self, blue_team, red_team, ddragon=None):
        """
        Feature Engineering 3.0: Lane Awareness & Advanced Metrics.
        
        Inputs:
        - blue_team: Dict { "TOP": id, "JUNGLE": id, ... } or List of IDs (fallback)
        - red_team: Dict { "TOP": id, "JUNGLE": id, ... } or List of IDs
        
        Vector Layout:
        [Blue Top One-Hot] ... [Blue Sup One-Hot] [Red Top One-Hot] ... (10 blocks)
        + [Blue Meta] [Red Meta] (2 x 15 features)
        
        Total Size ~= (170 * 10) + 30 = 1730 features.
        """
        # 0. Initialize Index if needed
        if not hasattr(self, 'id_to_idx'):
             if ddragon:
                 all_ids = sorted([int(data['key']) for data in ddragon.champions.values()])
                 self.id_to_idx = {cid: i for i, cid in enumerate(all_ids)}
                 self.num_champs = len(all_ids)
                 
                 # New Input Size: 10 Roles * N Champs + 30 Meta + 10 Context (Freq/WR per role)
                 # Actually, we want Freq/WR per player? No, per Role Slot.
                 # Let's add Freq + Winrate for each of the 10 role slots.
                 # 10 * 2 = 20 extra features.
                 
                 self.input_size = (self.num_champs * 10) + 30 + 20
             else:
                 self.id_to_idx = {} # Should not happen
                 self.input_size = 1750 

        vec = np.zeros(self.input_size)
        
        # Helper: Role to Index Offset
        role_map = {
            "TOP": 0, "JUNGLE": 1, "MIDDLE": 2, "BOTTOM": 3, "UTILITY": 4
        }
        
        # Helper: Normalize Inputs to Dict
        def normalize_team(team_input, side_offset):
            # side_offset: 0 for Blue, 5 for Red
            # If list, we can't assume lanes. Just put them in matching slots or spread evenly?
            # Fallback: If list, put in 0,1,2,3,4 (Assumes ordered list matches roles, which is shaky but best guess)
            normalized = {}
            if isinstance(team_input, list):
                roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
                for i, cid in enumerate(team_input):
                    if i < 5: normalized[roles[i]] = cid
            elif isinstance(team_input, dict):
                # FIXED: Case-insensitive normalization
                normalized = {k.upper(): v for k, v in team_input.items()}
            return normalized

        b_norm = normalize_team(blue_team, 0)
        r_norm = normalize_team(red_team, 5)

        # 1. Fill Positional One-Hots
        for role, cid in b_norm.items():
            if role in role_map and cid in self.id_to_idx:
                # Block Offset + Champ Index
                idx = (role_map[role] * self.num_champs) + self.id_to_idx[cid]
                vec[idx] = 1

        for role, cid in r_norm.items():
            if role in role_map and cid in self.id_to_idx:
                # Red starts at block 5
                idx = ((role_map[role] + 5) * self.num_champs) + self.id_to_idx[cid]
                vec[idx] = 1

        # 2. Advanced Meta Features
        # Offset is past all champion blocks
        meta_start = self.num_champs * 10
        context_start = meta_start + 30 # After the 30 general meta features
        
        def calculate_advanced_stats(team_dict, out_vec, start_idx):
            # 15 Features:
            # 0-3: Avg [Atk, Mag, Def, Diff]
            # 4-9: Role Counts (Fighter, Tank...) - Good validation check
            # 10: Phys Dmg %
            # 11: Magic Dmg %
            # 12: True Dmg % (Heuristic)
            # 13: Hard CC Score (Heuristic)
            # 14: Range/Poke Score (Heuristic - proxied by class)
            
            stats = np.zeros(15)
            ids = team_dict.values()
            count = 0
            
            total_atk = 0
            total_mag = 0
            
            for cid in ids:
                if not ddragon: continue
                # Cache lookup
                if not hasattr(self, 'ddragon_cache'): self._build_ddragon_cache(ddragon)
                try:
                    c_data = self.ddragon_cache.get(int(cid))
                except: c_data = None
                
                if c_data:
                    count += 1
                    info = c_data.get('info', {})
                    roles = c_data.get('roles', [])
                    
                    atk = info.get('attack', 0)
                    mag = info.get('magic', 0)
                    defn = info.get('defense', 0)
                    
                    total_atk += atk
                    total_mag += mag
                    
                    stats[0] += atk
                    stats[1] += mag
                    stats[2] += defn
                    stats[3] += info.get('difficulty', 0)
                    
                    # Roles
                    if "Fighter" in roles: stats[4] += 1
                    if "Tank" in roles: 
                        stats[5] += 1
                        stats[13] += 2 # Tanks usually have CC
                    if "Mage" in roles: 
                        stats[6] += 1
                        stats[14] += 2 # Mages have range
                    if "Assassin" in roles: stats[7] += 1
                    if "Marksman" in roles: 
                        stats[8] += 1
                        stats[14] += 3 # Marksmen have range
                    if "Support" in roles: 
                        stats[9] += 1
                        stats[13] += 1 # Supports usually have partial CC
            
            if count > 0:
                # Averages
                for i in range(4): stats[i] /= count
                
                # Damage Profile
                total_dmg_potential = total_atk + total_mag
                if total_dmg_potential > 0:
                    stats[10] = total_atk / total_dmg_potential # Phys %
                    stats[11] = total_mag / total_dmg_potential # Mag %

            out_vec[start_idx : start_idx+15] = stats

        if ddragon:
            calculate_advanced_stats(b_norm, vec, meta_start)
            calculate_advanced_stats(r_norm, vec, meta_start + 15)
            
        # 3. Meta-Context Features (Pass 2 Data)
        # We need "Frequency" and "Winrate" for the specific Champ assigned to the Role.
        # normalized dicts: role -> cid
        
        def fill_context(team_norm, start_idx):
            # Order: TOP, JUNGLE, MIDDLE, BOTTOM, UTILITY
            # For each, 2 features: [Freq, WR]
            roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
            
            for i, r in enumerate(roles):
                cid = team_norm.get(r, 0)
                freq = 0.0
                wr = 0.45 # Default pessimist/average
                
                if cid != 0 and hasattr(self, 'meta_stats'):
                    # Look up stats
                    c_stats = self.meta_stats.get(cid, {})
                    r_stats = c_stats.get(r, {})
                    
                    total_games = c_stats.get('total_games', 1)
                    role_games = r_stats.get('games', 0)
                    role_wins = r_stats.get('wins', 0)
                    
                    if total_games > 0:
                        freq = role_games / total_games 
                        # Or absolute frequency? Scale 0-1.
                        # Role Rate is better: P(Role | Champ).
                        # If I pick Garen, what is P(Top | Garen)? 0.9. P(Sup | Garen)? 0.01.
                        
                    if role_games > 0:
                         # Bayesian Smoothing (C=5 games at 50% WR)
                         # Prevents 1/1 or 2/2 games (100% WR) from appearing as 1.0 to the model.
                         # 1.0 input to the model often triggers "Auto Win" logic in trees.
                         # 2/2 -> (2 + 2.5) / (2 + 5) = 0.64 (64%)
                         wr = (role_wins + 2.5) / (role_games + 5.0)
                
                vec[start_idx + (i*2)] = freq
                vec[start_idx + (i*2) + 1] = wr

        fill_context(b_norm, context_start)         # Blue Context (0-9)
        fill_context(r_norm, context_start + 10)    # Red Context (10-19)

        return vec

    def _extract_neural_features(self, blue_team, red_team, ddragon):
        """
        Extracts structured data for LeagueNet:
        - Blue IDs [5]
        - Red IDs [5]
        - Meta Features [50] (Calculated same as vectorize)
        """
        # 1. IDs (Indices)
        if not hasattr(self, 'id_to_idx'):
             # Lazily build index if needed (usually done in vectorize init)
             all_ids = sorted([int(data['key']) for data in ddragon.champions.values()])
             self.id_to_idx = {cid: i+1 for i, cid in enumerate(all_ids)} # +1 for padding
             self.num_champs = len(all_ids)
        
        # Helper: Normalize Inputs
        def normalize_team(team_input, side_offset):
            # Same logic as vectorize
            normalized = {}
            if isinstance(team_input, list):
                roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
                for i, cid in enumerate(team_input):
                    if i < 5: normalized[roles[i]] = cid
            elif isinstance(team_input, dict):
                normalized = {k.upper(): v for k, v in team_input.items()}
            return normalized

        b_norm = normalize_team(blue_team, 0)
        r_norm = normalize_team(red_team, 5)
        
        # Build ID Arrays
        # Order: TOP, JG, MID, BOT, SUP
        roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
        
        b_ids = []
        for r in roles:
            cid = b_norm.get(r, 0)
            idx = self.id_to_idx.get(cid, 0) # 0 is padding/unknown
            b_ids.append(idx)
            
        r_ids = []
        for r in roles:
            cid = r_norm.get(r, 0)
            idx = self.id_to_idx.get(cid, 0)
            r_ids.append(idx)
            
        # 2. Meta Features (Real Implementation)
        meta_vec = np.zeros(50)
        
        # We need to map role -> index for context
        # 30-39: Blue Context (Freq/WR)
        # 40-49: Red Context (Freq/WR)
        
        def fill_context_neural(cids, start_idx):
             # cids is list [TOP_ID, JG_ID, ...]
             roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
             for i, r in enumerate(roles):
                 cid = cids[i]
                 freq = 0.0
                 wr = 0.45 
                 
                 # Access self.meta_stats which should now be loaded from DB
                 if cid != 0 and hasattr(self, 'meta_stats'):
                     c_stats = self.meta_stats.get(int(cid), {}) # Ensure int key
                     r_stats = c_stats.get(r, {})
                     
                     total_games = c_stats.get('total_games', 1)
                     role_games = r_stats.get('games', 0)
                     role_wins = r_stats.get('wins', 0)
                     
                     if total_games > 0:
                         freq = role_games / total_games 
                         
                     if role_games > 0:
                         # Bayesian Smoothing (C=5)
                         wr = (role_wins + 2.5) / (role_games + 5.0)
                         
                 # Write to meta_vec
                 meta_vec[start_idx + (i*2)] = freq
                 meta_vec[start_idx + (i*2) + 1] = wr

        # b_ids contains Indices, not CIDs. We need CIDs!
        # self.id_to_idx map: CID -> IDX
        # We need reverse map or just look up in team dict
        # b_norm has CIDs.
        
        # Helper list of CIDs
        b_cids = [b_norm.get(r, 0) for r in roles]
        r_cids = [r_norm.get(r, 0) for r in roles]
        
        # Fill Context (Indices 30-49 of meta_vec)
        fill_context_neural(b_cids, 30)
        fill_context_neural(r_cids, 40)
        
        # Hardcoded 0-29 (Stats) - Leaving as 0 for now as it requires DDragon lookup per champ
        # which is slow in loop. Embedding handles "Stats" implicitly.
        # But Context (Winrate) is critical explicitly.
                 
        return b_ids, r_ids, meta_vec

    def _load_dataset(self, match_dir, ddragon):
        all_ids = sorted([int(info['key']) for info in ddragon.champions.values()])
        print(f"[HIVE MIND] Universe Size: {len(all_ids)} Champions")
        
        X = []
        y = []
        count = 0
        
        if not os.path.exists(match_dir): return X, y, all_ids
        files = [f for f in os.listdir(match_dir) if f.endswith(".json") and "_timeline" not in f]
        
        for filename in files:
            try:
                with open(os.path.join(match_dir, filename), 'r') as f:
                    data = json.load(f)
                
                parts = data.get('info', {}).get('participants', [])
                if not parts: continue
                
                blue_team = {}
                red_team = {}
                blue_win = False
                
                for p in parts:
                    role = p.get('teamPosition', '')
                    if not role: continue # Skip if no role (ARAM/Arena filter failed?)
                    
                    if p['teamId'] == 100:
                        blue_team[role] = p['championId']
                        if p['win']: blue_win = True
                    else:
                        red_team[role] = p['championId']
                
                # Only use matches with full 5v5 role assignments to reduce noise
                if len(blue_team) < 5 or len(red_team) < 5: continue
                        
                # Create Smart Vector
                vec = self._vectorize_team(blue_team, red_team, ddragon)
                
                X.append(vec)
                y.append(1 if blue_win else 0)
                count += 1
                
            except: pass
            
        print(f"[HIVE MIND] Loaded {count} valid Lane-Aware matches.")
        return X, y, all_ids

    def train(self, match_dir, ddragon):
        print(f"[HIVE MIND] Awakening... Connecting to Brain Database...")
        
        # New DB Connection
        from src.engine.persistence import BrainDatabase
        db = BrainDatabase()
        
        # Load Meta Stats from DB (Memory Cache)
        print("[HIVE MIND] Synapsing Meta-Context...")
        self.meta_stats = db.get_meta_stats()
        
        # Get Struct Data from DB
        training_data = db.get_training_data()
        
        if len(training_data) < 10:
             print("[HIVE MIND] Not enough data in DB to train (Need >10).")
             return

        if self.neural:
            # NEURAL PATH
            print(f"[HIVE MIND] Training Neural Core (LeagueNet) on {len(training_data)} matches...")
            X_champs = []
            X_meta = []
            y = []
            
            for m in training_data:
                 b, r, meta = self._extract_neural_features(m['blue'], m['red'], ddragon)
                 X_champs.append(b + r) # [10]
                 X_meta.append(meta)    # [50]
                 y.append(m['win'])
            
            self.neural.train(np.array(X_champs), np.array(X_meta), np.array(y))
            print("[HIVE MIND] Neural Core Online.")
                
        else:
            # LEGACY PATH (Legacy Brain needs old vector format, let's keep it simple check)
            print("[HIVE MIND] Fallback to Legacy Models (Not implemented for DB yet).")
            pass
            
        self.is_trained = True
        
        
    def _redundant_legacy_load(self):
        # Placeholder to completely remove _load_matches_raw
        pass
        
    def evaluate(self, match_dir, ddragon):
        from sklearn.model_selection import cross_val_score
        print(f"[HIVE MIND] Running Scientific Evaluation (5-Fold CV)...")
        X, y, _ = self._load_dataset(match_dir, ddragon)
        
        if len(X) < 20: 
            print(" -> Not enough data for Cross-Validation.")
            return

        scores = cross_val_score(self.council, X, y, cv=5)
        print(f"[HIVE MIND] REAL ACCURACY (Unseen Prediction): {scores.mean()*100:.1f}% (+/- {scores.std()*100:.1f}%)")
        
    def _build_ddragon_cache(self, ddragon):
        """Optimizes DDragon lookups O(n) -> O(1)"""
        if hasattr(self, 'ddragon_cache'): return

        self.ddragon_cache = {}
        for name, data in ddragon.champions.items():
            try:
                key = int(data['key'])
                self.ddragon_cache[key] = data
            except: pass

    def predict(self, blue_ids, red_ids, ddragon):
        return self.predict_batch([blue_ids], [red_ids], ddragon)[0]

    def predict_batch(self, blue_teams, red_teams, ddragon):
        """
        Efficiently predicts win probabilities for multiple matchups.
        """
        if not self.is_trained: return [0.5] * len(blue_teams)
        
        # Ensure Cache (if needed for Index lookup)
        # self._build_ddragon_cache(ddragon) 
        # Actually _extract_neural_features builds the index map
        
        if self.neural:
            # NEURAL PATH (Optimized Batch)
            b_batch = []
            r_batch = []
            m_batch = []
            
            # 1. Vectorize (CPU Bound, but fast O(N))
            for b, r in zip(blue_teams, red_teams):
                b_ids, r_ids, meta = self._extract_neural_features(b, r, ddragon)
                b_batch.append(b_ids)
                r_batch.append(r_ids)
                m_batch.append(meta)
                
            # 2. Predict (GPU Bound, O(1) Tensor Op)
            # Sends all 160+ scenarios to GPU in one transaction
            probs = self.neural.predict_batch(b_batch, r_batch, m_batch)
            
            return probs
            
        else:
            # LEGACY PATH
            vectors = []
            for b_team, r_team in zip(blue_teams, red_teams):
                vectors.append(self._vectorize_team(b_team, r_team, ddragon))
            
            probs = self.council.predict_proba(vectors)
            return [p[1] for p in probs]

    def explain_decision(self, blue_ids, red_ids, ddragon):
        """
        Returns a list of strings explaining WHY the AI made the decision.
        Uses Random Forest Feature Importance as a proxy for 'Reasoning'.
        """
        if not self.is_trained: return ["Model not trained."]
        
        all_ids = sorted([int(info['key']) for info in ddragon.champions.values()])
        # Create mapping ID -> Name for display
        id_to_name = {int(info['key']): info['name'] for info in ddragon.champions.values()}
        
        # Get importances from the Forest (it's the most interpretable part of the ensemble)
        # CRITICAL: VotingClassifier clones estimators. Access the fitted one.
        fitted_forest = self.council.named_estimators_['forest']
        importances = fitted_forest.feature_importances_
        
        # Current Match Vector
        vec = self._vectorize_team(blue_ids, red_ids, ddragon)
        
        # Analyze active features
        # vec has indices. importances has same indices.
        # We want to know: Which ACTIVE champions contributed most to the score?
        
        contributions = []
        
        # We need to map Index -> "Role - Champion Name"
        # 10 blocks of num_champs
        # then 30 meta features
        
        num_champs = getattr(self, 'num_champs', len(all_ids))
        role_names = ["Top", "Jungle", "Mid", "Bot", "Sup"]
        
        for i, val in enumerate(vec):
            if val != 0: # Feature is Active
                score = importances[i]
                
                # Decode Index
                if i < num_champs * 10:
                    # It's a champion
                    block_idx = i // num_champs
                    champ_idx = i % num_champs
                    
                    team = "Blue" if block_idx < 5 else "Red"
                    role_id = block_idx if block_idx < 5 else block_idx - 5
                    role = role_names[role_id]
                    
                    # Need to find name from idx. We assume self.id_to_idx is sorted?
                    # actually self.id_to_idx is {id: i}. We can reverse it.
                    # or just use all_ids[champ_idx]
                    cid = all_ids[champ_idx]
                    cname = id_to_name.get(cid, "Unknown")
                    
                    label = f"{cname} ({team} {role})"
                else:
                    # Meta feature
                    # 0-14: Blue Stats
                    # 15-29: Red Stats
                    # 30-39: Blue Context (Freq/WR)
                    # 40-49: Red Context (Freq/WR)
                    
                    meta_idx = i - (num_champs * 10)
                    
                    stat_names = ["Avg Atk", "Avg Mag", "Avg Def", "Diff", "#Fighter", "#Tank", "#Mage", "#Assassin", "#Marksman", "#Support", "Phys%", "Mag%", "True%", "CC Score", "Range Score"]
                    role_names = ["Top", "Jg", "Mid", "Bot", "Sup"]
                    
                    if meta_idx < 15:
                        team = "Blue"
                        label = f"{stat_names[meta_idx]} ({team})"
                    
                    elif meta_idx < 30:
                        team = "Red"
                        label = f"{stat_names[meta_idx-15]} ({team})"
                        
                    elif meta_idx < 40:
                        team = "Blue"
                        # 30=TopFreq, 31=TopWR, 32=JgFreq, 33=JgWR ...
                        local_idx = meta_idx - 30
                        r_idx = local_idx // 2
                        type_str = "Freq" if local_idx % 2 == 0 else "WR"
                        label = f"{role_names[r_idx]} {type_str} ({team})"
                        
                    elif meta_idx < 50:
                        team = "Red"
                        local_idx = meta_idx - 40
                        r_idx = local_idx // 2
                        type_str = "Freq" if local_idx % 2 == 0 else "WR"
                        label = f"{role_names[r_idx]} {type_str} ({team})"
                    
                    else:
                         label = f"New_Feature_{meta_idx} (?)"
                
                contributions.append( (score, label) )
                
        # Sort by impact
        contributions.sort(key=lambda x: x[0], reverse=True)
        
        reasons = []
        for score, label in contributions[:3]:
            # Scale score for readability (it's small float)
            impact = score * 1000 
            reasons.append(f"{label} [Impact: {impact:.1f}]")
            
        return reasons

    def _analyze_meta_stats(self, match_dir):
        """
        Pass 1: Scans all matches to build proficiency data.
        {
            cid: {
                "total_games": 100,
                "TOP": {"games": 80, "wins": 45},
                "JUNGLE": {"games": 2, "wins": 0}, ...
            }
        }
        """
        print("[HIVE MIND] Pass 1: Analyzing Meta-Context (Role Proficiency)...")
        self.meta_stats = {}
        
        if not os.path.exists(match_dir): return
        files = [f for f in os.listdir(match_dir) if f.endswith(".json") and "_timeline" not in f]
        
        count = 0
        for filename in files:
            try:
                with open(os.path.join(match_dir, filename), 'r') as f:
                    data = json.load(f)
                
                parts = data.get('info', {}).get('participants', [])
                for p in parts:
                    cid = p['championId']
                    role = p.get('teamPosition', '')
                    win = p['win']
                    
                    if not role: continue
                    
                    if cid not in self.meta_stats:
                        self.meta_stats[cid] = {'total_games': 0}
                    
                    self.meta_stats[cid]['total_games'] += 1
                    
                    if role not in self.meta_stats[cid]:
                        self.meta_stats[cid][role] = {'games': 0, 'wins': 0}
                        
                    self.meta_stats[cid][role]['games'] += 1
                    if win:
                        self.meta_stats[cid][role]['wins'] += 1
                count += 1
            except: pass
            
        print(f" -> Analyzed {count} matches for proficiency data.")

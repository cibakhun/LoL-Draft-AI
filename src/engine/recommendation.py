from src.engine.ensemble_brain import EnsembleBrain

class RecommendationEngine:
    def __init__(self, brain: EnsembleBrain, ddragon):
        self.brain = brain
        self.ddragon = ddragon
        
    def recommend(self, my_team, enemy_team, role, config=None, top_k=5):
        """
        config: Dict with keys:
            - 'meta_tolerance': 0.0 (Strict) to 1.0 (Loose/Theory). Default 0.2.
            - 'proficiency_bias': 0.0 (None) to 1.0 (Heavy). Default 0.5.
        """
        cfg = config or {}
        meta_tolerance = cfg.get('meta_tolerance', 0.2)
        proficiency_bias = cfg.get('proficiency_bias', 0.5)
        
        # 1. Identify Candidate Champions
        # Filter by Role using DDragon
        candidates = []
        all_champs = self.ddragon.champions.values()
        
        for data in all_champs:
            candidates.append(int(data['key']))
            
        # 2. Construct Batch Vectors
        # We need to replace the 'None' or '0' slot in my_team with each candidate
        blue_teams = []
        red_teams = [] # Red team is constant
        
        # Find the empty slot index
        try:
            slot_idx = my_team.index(0)
        except ValueError:
            try:
                slot_idx = my_team.index(None)
            except ValueError:
                slot_idx = -1 
        
        valid_candidates = []
        
        for cid in candidates:
            if cid in my_team or cid in enemy_team:
                continue # Cannot pick banned or taken
                
            # Create hypothetical team
            new_team = my_team.copy()
            if slot_idx != -1 and slot_idx < len(new_team):
                new_team[slot_idx] = cid
            else:
                new_team.append(cid)
                
            blue_teams.append(new_team)
            red_teams.append(enemy_team)
            valid_candidates.append(cid)
            
        # 3. Batch Predict
        if not valid_candidates: return []
        
        probs = self.brain.predict_batch(blue_teams, red_teams, self.ddragon)
        
        # 3b. Apply Config/Consistency Logic
        final_probs = []
        has_stats = hasattr(self.brain, 'meta_stats') and role != "Any"
        
        for i, cid in enumerate(valid_candidates):
             p_win = probs[i]
             
             if has_stats:
                 c_stats = self.brain.meta_stats.get(cid, {})
                 role_stats = c_stats.get(role, {})
                 role_games = role_stats.get('games', 0)
                 role_wins = role_stats.get('wins', 0)
                 total_games = c_stats.get('total_games', 1)
                 
                 # 1. Meta Tolerance (Frequency Penalty)
                 freq = 0.0
                 if total_games > 0:
                     freq = role_games / total_games
                     
                 penalty_factor = 1.0
                 if freq < 0.01:
                     # Base Penalty 0.5
                     # Adjusted = 0.5 + (1.0 - 0.5) * tolerance
                     # Tol 0.0 -> 0.5
                     # Tol 1.0 -> 1.0
                     penalty_factor = 0.5 + (0.5 * meta_tolerance)
                 elif freq < 0.05:
                     # Base Penalty 0.8
                     penalty_factor = 0.8 + (0.2 * meta_tolerance)
                 
                 p_win *= penalty_factor
                 
                 # 2. Proficiency Bias (Winrate Bonus) with Bayesian Smoothing
                 # Prevents 2/2 wins (100% WR) from distorting the prediction.
                 # We add 'C' fake games at 50% WR to pull small samples toward the mean.
                 C = 10 # Confidence Weight (equivalent to 10 dummy games)
                 global_avg = 0.5
                 
                 smoothed_wr = (role_wins + (C * global_avg)) / (role_games + C)
                 
                 # Center around 50%
                 diff = smoothed_wr - 0.5
                 
                 # Add to probability: e.g. +5% WR * 0.5 Bias = +2.5% p_win
                 p_win += (diff * proficiency_bias)
             
             # 3. Global Reality Clamp
             # No match in LoL is 84% winnable from draft alone.
             # We clamp to [35%, 75%] to keep expectations realistic.
             p_win = max(0.35, min(0.75, p_win))
             
             final_probs.append(p_win)
        

        
        # 4. Rank
        results = []
        for i, cid in enumerate(valid_candidates):
            results.append({
                "champion_id": cid,
                "win_probability": final_probs[i]
            })
            
        results.sort(key=lambda x: x['win_probability'], reverse=True)
        return results[:top_k]

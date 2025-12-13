import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
import random

class WinPredictor:
    def __init__(self, meta_engine):
        self.meta = meta_engine
        # Best Practice: Always scale features for Logistic Regression
        self.model = make_pipeline(StandardScaler(), LogisticRegression())
        self.is_trained = False
        
    def _extract_features(self, team_ids, ddragon):
        """
        Converts a list of Champion IDs into a Feature Vector.
        Features: [AvgWinrate, AvgPickrate, CcCount, TankCount, AdCount, ApCount]
        """
        if not team_ids: return [0]*6
        
        total_wr = 0
        total_pr = 0
        cc_count = 0
        tank_count = 0
        ad_count = 0
        ap_count = 0
        
        for cid in team_ids:
            # Resolve name
            name = ddragon.get_id_map().get(cid)
            if not name: continue
            
            # Get Stats from Meta Engine
            stats = self.meta.champion_stats.get(name, {"winrate": 0.5})
            total_wr += stats.get("winrate", 0.5)
            
            # Get Tags from DDragon
            info = ddragon.champions.get(name, {})
            roles = info.get("roles", [])
            
            if "Tank" in roles or "Fighter" in roles: tank_count += 1
            if "Mage" in roles: ap_count += 1
            if "Marksman" in roles: ad_count += 1
            if "Support" in roles: cc_count += 0.5 # Proxy for utility
            
            # Hard CC check (Simplified by name for MVP, ideally use tags)
            if name in ["Nautilus", "Leona", "Amumu", "Malphite"]: cc_count += 1

        avg_wr = total_wr / len(team_ids) if team_ids else 0.5
        
        return [avg_wr, total_pr, cc_count, tank_count, ad_count, ap_count]

    def train_from_db(self, match_dir, ddragon):
        """
        Trains the model using REAL match data from the disk.
        """
        import os
        import json
        
        print(f"[ML] Training on Real Data from {match_dir}...")
        X = []
        y = []
        matches_loaded = 0
        
        if not os.path.exists(match_dir):
            print("[ML] Error: Match directory not found.")
            return

        files = [f for f in os.listdir(match_dir) if f.endswith(".json") and "_timeline" not in f]
        print(f"[ML] Found {len(files)} match files.")
        
        for filename in files:
            try:
                with open(os.path.join(match_dir, filename), 'r') as f:
                    data = json.load(f)
                    
                info = data.get('info', {})
                participants = info.get('participants', [])
                if not participants: continue
                
                # Separate Teams
                blue_team = [] # keys/names? extract_features expects names or IDs?
                red_team = []
                # extract_features implementation in this file loop over IDs and resolve names.
                # But here we have names directly in participants.
                # Let's adapt extract_features to take NAMES or handle both.
                # Actually, participants has 'championId' and 'championName'.
                # Let's collect championIds.
                
                blue_win = False
                
                for p in participants:
                    cid = p.get('championId')
                    team = p.get('teamId') # 100 or 200
                    win = p.get('win')
                    
                    if team == 100:
                        blue_team.append(cid)
                        if win: blue_win = True
                    else:
                        red_team.append(cid)
                        
                # Extract Features
                blue_feats = self._extract_features(blue_team, ddragon)
                red_feats = self._extract_features(red_team, ddragon)
                
                # Create Training Sample (Blue - Red)
                delta_feats = np.array(blue_feats) - np.array(red_feats)
                X.append(delta_feats)
                y.append(1 if blue_win else 0)
                
                matches_loaded += 1
                
            except Exception as e:
                # print(f"[ML] Failed to process {filename}: {e}")
                pass
                
        if matches_loaded < 10:
            print("[ML] Not enough matches to train. Need at least 10.")
            return
            
        print(f"[ML] Training on {matches_loaded} matches...")
        self.model.fit(X, y)
        self.is_trained = True
        
        # Evaluate Accuracy
        accuracy = self.model.score(X, y)
        print(f"[ML] Model Trained! Accuracy on Training Set: {accuracy*100:.1f}%")
        
    # def train_bootstrap... REMOVED

    def predict(self, blue_team, red_team, ddragon):
        if not self.is_trained:
            return 0.5
            
        b_feats = np.array(self._extract_features(blue_team, ddragon))
        r_feats = np.array(self._extract_features(red_team, ddragon))
        
        delta = (b_feats - r_feats).reshape(1, -1)
        
        # Return probability of Class 1 (Win)
        return self.model.predict_proba(delta)[0][1]

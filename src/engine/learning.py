import json
import os

class LearningEngine:
    def __init__(self, config_path="brain_config.json"):
        self.config_path = config_path
        self.config = self._load_config()
        
    def _load_config(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            print(f"[LEARNING] Error loading config: {e}")
            
        # Default Weights if fail
        return {
            "weights": {"meta": 0.3, "personal": 0.4, "team_comp": 0.15, "counter": 0.15},
            "role_bias": {"Assassin": 1.0, "Fighter": 1.0, "Mage": 1.0, "Marksman": 1.0, "Support": 1.0, "Tank": 1.0},
            "learning_rate": 0.05
        }

    def save_config(self):
        try:
            with open(self.config_path, 'w') as f:
                json.dump(self.config, f, indent=4)
            print("[LEARNING] Brain updated and saved.")
        except Exception as e:
            print(f"[LEARNING] Error saving config: {e}")

    def learn_from_history(self, match_history, id_map, ddragon):
        """
        Analyzes past matches to adjust role biases.
        SIMPLIFIED: We assume match_history is a list of {championId, win}.
        """
        print("[LEARNING] Analyzing Match History for patterns...")
        
        # 1. Calculate Winrates per Role
        role_stats = {} # {Role: {wins: 0, games: 0}}
        
        for match in match_history:
            cid = match['championId']
            win = match['win']
            cname = id_map.get(cid)
            if not cname: continue
            
            info = ddragon.champions.get(cname)
            if not info: continue
            
            for role in info['roles']:
                if role not in role_stats: role_stats[role] = {"wins": 0, "games": 0}
                role_stats[role]["games"] += 1
                if win: role_stats[role]["wins"] += 1
                
        # 2. Adjust Biases
        lr = self.config.get("learning_rate", 0.05)
        changes_made = False
        
        for role, stats in role_stats.items():
            if stats["games"] < 3: continue # Need sample size
            
            wr = stats["wins"] / stats["games"]
            current_bias = self.config["role_bias"].get(role, 1.0)
            
            # If WR > 55%, boost bias. If WR < 45%, lower bias.
            if wr > 0.55:
                self.config["role_bias"][role] = min(1.5, current_bias + lr)
                print(f"[LEARNING] Evolving: Increasing trust in {role} (WR {wr:.2f})")
                changes_made = True
            elif wr < 0.45:
                self.config["role_bias"][role] = max(0.7, current_bias - lr)
                print(f"[LEARNING] Evolving: Decreasing trust in {role} (WR {wr:.2f})")
                changes_made = True
                
        if changes_made:
            self.save_config()

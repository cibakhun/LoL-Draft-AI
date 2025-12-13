import os
import json
from src.data.ddragon import DataDragon
from src.data.ddragon import DataDragon
from src.engine.meta_engine import MetaEngine
from src.engine.ensemble_brain import EnsembleBrain

def main():
    print("=== LEAGUE AI COACH: REAL AI DEMO ===")
    
    # 1. Initialize Components
    print("\n[1] Initializing Engines...")
    dd = DataDragon()
    meta = MetaEngine()
    
    # Load Meta Cache if available
    if os.path.exists("meta_cache.json"):
        with open("meta_cache.json", "r") as f:
            meta.champion_stats = json.load(f)
        print(f" -> Loaded Meta Cache ({len(meta.champion_stats)} champions)")
    
    # 2. Train Model (or Load from Memory)
    print("\n[2] Awakening Hive Mind...")
    ai = EnsembleBrain()
    
    match_dir = os.path.join("src", "data", "matches")
    brain_path = "brain.joblib"
    
    should_retrain = False
    
    # Smart Retrain Logic
    if os.path.exists(brain_path):
        brain_mtime = os.path.getmtime(brain_path)
        
        # Find newest match file
        max_match_mtime = 0
        for f in os.scandir(match_dir):
            if f.name.endswith(".json") and f.stat().st_mtime > max_match_mtime:
                max_match_mtime = f.stat().st_mtime
                
        if max_match_mtime > brain_mtime:
            print(f" -> New data detected! (Brain: {brain_mtime:.0f} < Data: {max_match_mtime:.0f})")
            print(" -> Forcing Retrain to absorb new knowledge...")
            should_retrain = True
    else:
        should_retrain = True
    
    # Execution
    if not should_retrain and ai.load():
        print(" -> Long-Term Memory Loaded! (Data is unchanged)")
    else:
        if not should_retrain: print(" -> Load failed. Training...")
        ai.train(match_dir, dd)
        ai.save()
    
    if not ai.is_trained:
        print(" -> Model failed to train (Not enough data?). Crawl more games!")
        return

    # 3. Scientific Calibration
    print("\n[3] Calibrating Hive Mind (5-Fold Cross Validation)...")
    ai.evaluate(match_dir, dd)

    # 4. Scenario Tests (Proof of Intelligence)
    print("\n[4] Running Scenario Tests...")
    
    def get_id(name):
        # 1. Try Direct Key Lookup (e.g. "Ahri", "LeeSin")
        info = dd.champions.get(name)
        if info: return info.get("key")
        
        # 2. Try Name Search (e.g. "Lee Sin" -> match "LeeSin")
        # Optimization: Build a name->key map once if slow, but for demo loop is fine.
        for key, data in dd.champions.items():
            if data['name'] == name:
                return data['key']
            # Handle tricky ones (Kai'Sa -> Kaisa/KaiSa)
            if data['name'].lower() == name.lower():
                return data['key']
            if key.lower() == name.lower().replace(" ", "").replace("'", ""):
                return data['key']
        return None
        
    def predict_scenario(name, blue_names, red_names):
        print(f"\n--- {name} ---")
        print(f"Blue: {blue_names}")
        print(f"Red:  {red_names}")
        
        b_ids = [get_id(n) for n in blue_names]
        r_ids = [get_id(n) for n in red_names]
        
        # Check for missing IDs (typographical errors or missing in ddragon)
        if any(x is None for x in b_ids) or any(x is None for x in r_ids):
            print(" -> [ERROR] One or more champions not found in DDragon.")
            return

        prob = ai.predict(b_ids, r_ids, dd)
        print(f" -> Blue Win Probability: {prob*100:.1f}%")
        
        # XAI Explanation
        reasons = ai.explain_decision(b_ids, r_ids, dd)
        print(f" -> Reasoning: {', '.join(reasons)}")
        
    # Scenario A: The "Exodia" (Yasuo + Malphite Synergy)
    # Blue has the combo. Red is squishy.
    predict_scenario(
        "TEST 1: The Wombo Combo (Synergy Check)",
        ["Malphite", "Yasuo", "Yone", "Alistar", "Orianna"], 
        ["Vayne", "Lux", "Xerath", "Caitlyn", "Sona"]
    )
    
    # Scenario B: Full AD Trap (Composition Check)
    # Blue is all AD Assassins. Red is 5 Tanks building Armor (Malphite/Rammus type).
    # The AI should penalize full AD vs Tanks.
    predict_scenario(
        "TEST 2: All AD vs Armor Stack (Comp Check)",
        ["Zed", "Talon", "Pyke", "Draven", "Rengar"],
        ["Malphite", "Rammus", "Ornn", "Leona", "Sejuani"]
    )
    
    # Scenario C: Meta Clash (Current S-Tiers)
    # Pick champions that currently have High Winrates in our data if known, otherwise typical strong picks.
    predict_scenario(
        "TEST 3: Battle of the Titans (Meta Check)",
        ["Ahri", "Lee Sin", "Kai'Sa", "Nautilus", "Jax"], 
        ["Syndra", "Viego", "Jinx", "Lulu", "Renekton"]
    )

if __name__ == "__main__":
    main()

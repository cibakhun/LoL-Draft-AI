
import os
import sys
# Add project root to path
sys.path.append(os.getcwd())

from src.engine.ensemble_brain import EnsembleBrain
from src.engine.recommendation import RecommendationEngine
from src.data.ddragon import DataDragon

def run_draft_test():
    print("=== DRAFTING ENGINE VERIFICATION ===")
    
    # 1. Init Dependencies
    print("[1/4] Loading DataDragon...")
    ddragon = DataDragon() # Will fetch or load cache
    
    print("[2/4] Loading Core Brain...")
    brain = EnsembleBrain()
    if not brain.load("brain.joblib"):
        print("[!] Brain missing or invalid. Testing Auto-Train...")
        match_dir = os.path.join("src", "data", "matches")
        brain.train(match_dir, ddragon)
        brain.save("brain.joblib")
        
    engine = RecommendationEngine(brain, ddragon)
    
    # 2. Scenario: We need a Midlaner
    # Blue Team: Malphite (Top), Sejuani (Jungle), [EMPTY], Jinx (Adc), Lulu (Supp)
    # Red Team: Fiora (Top), Lee Sin (Jungle), Ahri (Mid), Ezreal (Adc), Karma (Supp)
    
    # ID Map Helper
    name_to_id = {data['name']: int(data['key']) for data in ddragon.champions.values()}
    id_to_name = {int(data['key']): data['name'] for data in ddragon.champions.values()}

    def get_id(name): return name_to_id.get(name, 0)

    my_team = [get_id("Malphite"), get_id("Sejuani"), 0, get_id("Jinx"), get_id("Lulu")]
    enemy_team = [get_id("Fiora"), get_id("Lee Sin"), get_id("Ahri"), get_id("Ezreal"), get_id("Karma")]
    
    print(f"\n[SCENARIO] Blue Team (Us): Malphite, Sejuani, ?, Jinx, Lulu")
    print(f"[SCENARIO] Red Team (Enemy): Fiora, Lee Sin, Ahri, Ezreal, Karma")
    
    # 3. Recommend
    print("\n[3/4] Thinking (Processing 160+ Draft Scenarios)...")
    recs = engine.recommend(my_team, enemy_team, role="Mage", top_k=5)
    
    # 4. Results
    print("\n=== TOP 5 RECOMMENDATIONS ===")
    for i, r in enumerate(recs):
        cname = id_to_name.get(r['champion_id'], "Unknown")
        prob = r['win_probability'] * 100
        print(f"#{i+1}: {cname} (Win Probability: {prob:.1f}%)")
        
    # Analyze #1
    if recs:
        print("\n[ANALYSIS] Why #1?")
        # Create the winning team
        winning_team = my_team.copy()
        # Find 0 slot
        try: idx = winning_team.index(0)
        except: idx = -1
        winning_team[idx] = recs[0]['champion_id']
        
        reasons = brain.explain_decision(winning_team, enemy_team, ddragon)
        for reason in reasons:
            print(f" -> {reason}")

if __name__ == "__main__":
    run_draft_test()

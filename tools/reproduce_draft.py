
import sys
import os
import json

# Mocking the environment
sys.path.append(os.getcwd())

from src.data.ddragon import DataDragon
from src.engine.ensemble_brain import EnsembleBrain
from src.engine.smart_draft import SmartDraft

def test_batch_rank():
    print("--- 1. Init DataDragon ---")
    ddragon = DataDragon()
    # Mock champions if fetch fails (fallback)
    if not ddragon.champions:
        print("[WARN] DDragon failed, using mock.")
        ddragon.champions = {
            "Ahri": {"key": "103", "name": "Ahri", "roles": ["Mage"]},
            "Garen": {"key": "86", "name": "Garen", "roles": ["Fighter"]},
            "Zed": {"key": "238", "name": "Zed", "roles": ["Assassin"]}
        }
    else:
        print(f"Loaded {len(ddragon.champions)} champs.")

    print("--- 2. Init Brain ---")
    brain = EnsembleBrain()
    # Mock training
    brain.is_trained = True 
    # Mock predict_batch to avoid needing real models/files
    brain.predict_batch = lambda b, r, d: [0.55] * len(b)

    print("--- 3. Init SmartDraft ---")
    draft = SmartDraft(None, None, None, None, ensemble_brain=brain)

    print("--- 4. Setup Inputs ---")
    # Simulation inputs from logs
    candidates = list(ddragon.champions.keys())[:10] # Test top 10
    print(f"Candidates: {candidates}")
    
    my_team_roles = {"TOP": "86", "JUNGLE": "11"} # Garen, yi (Strings!)
    enemy_team_roles = {"BOTTOM": "22", "UTILITY": "117"}
    my_role = "MIDDLE"

    print("--- 5. Run Batch Rank ---")
    try:
        results = draft.batch_rank(candidates, my_team_roles, enemy_team_roles, my_role, ddragon)
        print(f"Results Count: {len(results)}")
        if results:
            print(f"Top Result: {results[0]}")
        else:
            print("FAILURE: No results returned.")
            
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_batch_rank()

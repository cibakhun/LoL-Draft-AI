import os
import shutil
import numpy as np
from src.engine.persistence import BrainDatabase
from src.engine.ensemble_brain import EnsembleBrain
from src.engine.features import FeatureEngine

def test():
    print("Starting Manual Deep Brain Test...")
    test_db = "test_brain_manual.db"
    if os.path.exists(test_db):
        os.remove(test_db)
    
    db = BrainDatabase(test_db)
    
    # 1. Create Fake Match (Mid Game Win)
    fake_match = {
        "metadata": {"matchId": "EUW1_MANUAL"},
        "info": {
            "gameMode": "CLASSIC",
            "queueId": 420,
            "gameCreation": 1000000,
            "gameDuration": 1800, # 30 mins
            "participants": [
                {"puuid": "B1", "championId": 1, "teamId": 100, "teamPosition": "TOP", "win": True},
                {"puuid": "B2", "championId": 2, "teamId": 100, "teamPosition": "JUNGLE", "win": True},
                {"puuid": "B3", "championId": 3, "teamId": 100, "teamPosition": "MIDDLE", "win": True},
                {"puuid": "B4", "championId": 4, "teamId": 100, "teamPosition": "BOTTOM", "win": True},
                {"puuid": "B5", "championId": 5, "teamId": 100, "teamPosition": "UTILITY", "win": True},
                {"puuid": "R1", "championId": 6, "teamId": 200, "teamPosition": "TOP", "win": False},
                {"puuid": "R2", "championId": 7, "teamId": 200, "teamPosition": "JUNGLE", "win": False},
                {"puuid": "R3", "championId": 8, "teamId": 200, "teamPosition": "MIDDLE", "win": False},
                {"puuid": "R4", "championId": 9, "teamId": 200, "teamPosition": "BOTTOM", "win": False},
                {"puuid": "R5", "championId": 10, "teamId": 200, "teamPosition": "UTILITY", "win": False}
            ]
        }
    }
    
    if db.save_match(fake_match):
        print("Fake Match Saved.")
    else:
        print("Failed to save match.")
        return

    brain = EnsembleBrain()
    brain.feature_engine.set_vocab({i: i for i in range(1, 11)})
    
    # Train
    brain.train(db=db, batch_size=10, epochs=1)
    
    fe = brain.feature_engine
    
    # Check Spikes
    s1 = fe.spike_stats.get(1)
    if s1:
        print(f"Champ 1 Stats: {s1}")
        if s1['mid']['games'] == 1 and s1['mid']['wins'] == 1:
            print("✅ Spike Stats Recorded Correctly.")
        else:
            print("❌ Spike Stats Mismatch.")
    else:
        print("❌ Champ 1 not found in spike_stats.")
        
    # Check Counters (1 vs 6)
    c1 = fe.counter_matrix.get(1, {}).get(6)
    if c1:
        print(f"Counter 1vs6: {c1}")
        if c1['wins'] == 1:
            print("✅ Counter Stats Recorded Correctly.")
        else:
             print("❌ Counter Stats Mismatch.")
    else:
         print("❌ Counter 1vs6 not found.")
         
    # Check Vectors
    blue = {"TOP": 1, "JUNGLE": 2, "MIDDLE": 3, "BOTTOM": 4, "UTILITY": 5}
    red = {"TOP": 6, "JUNGLE": 7, "MIDDLE": 8, "BOTTOM": 9, "UTILITY": 10}
    flat, (b, r, meta) = fe.vectorize(blue, red)
    
    print(f"Meta Vector Size: {len(meta)}")
    if len(meta) == 72:
        print("✅ Correct Dimension (72).")
    else:
        print(f"❌ Incorrect Dimension: {len(meta)}")
        
    # Check Blue Mid Spike (Index 61)
    spike_val = meta[61]
    print(f"Blue Mid Spike Value: {spike_val}")
    if abs(spike_val - 0.6) < 0.01:
        print("✅ Spike Value Verification Passed.")
    else:
        print("❌ Spike Value Mismatch (Expected 0.6).")

    if os.path.exists(test_db):
        try: os.remove(test_db)
        except: pass

if __name__ == "__main__":
    test()

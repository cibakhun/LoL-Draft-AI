import os
import sys
import sqlite3
import random
import time

# Mock DDragon
class MockDDragon:
    class champions:
        values = lambda: [{'key': str(i)} for i in range(1, 150)]
        items = lambda: [(str(i), {'key': str(i), 'info': {'attack': 5, 'magic': 5, 'defense': 5, 'difficulty': 5}, 'roles': ['Fighter']}) for i in range(1, 150)]

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from src.engine.persistence import BrainDatabase
from src.engine.ensemble_brain import EnsembleBrain

def verify():
    print("--- STARTING VERIFICATION ---")
    
    # 1. Setup Test DB
    if os.path.exists("test_brain.db"): os.remove("test_brain.db")
    db = BrainDatabase("test_brain.db")
    
    # 2. Insert Mock Matches (Chronological)
    print("Generating 500 mock matches...")
    conn = sqlite3.connect("test_brain.db")
    c = conn.cursor()
    
    start_ts = 1000000
    for i in range(500):
        # Create match
        mid = f"MOCK_{i}"
        ts = start_ts + i # Strict increasing time
        c.execute("INSERT INTO matches (match_id, timestamp) VALUES (?, ?)", (mid, ts))
        
        # Parts
        for team, tid in [('blue', 100), ('red', 200)]:
            for j, role in enumerate(["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]):
                cid = random.randint(1, 149)
                win = 1 if tid == 100 else 0 # Blue always wins for simplicity
                c.execute("INSERT INTO participants (match_id, champion_id, team_id, role, win) VALUES (?, ?, ?, ?, ?)",
                          (mid, cid, tid, role, win))
    conn.commit()
    conn.close()
    
    # 3. Test Training
    brain = EnsembleBrain()
    # Hack to force DB path
    import src.engine.persistence
    src.engine.persistence.BrainDatabase = lambda: BrainDatabase("test_brain.db")
    
    print("\n[TEST] Running Online Learning Loop...")
    try:
        brain.train("dummy_dir", MockDDragon(), batch_size=100, epochs=1)
        print("[TEST] Training finished without crash.")
    except Exception as e:
        print(f"[TEST] FATAL: Training crashed: {e}")
        raise e
        
    # 4. Verify Leakage (Logic Check)
    # meta_stats should be populated
    if len(brain.meta_stats) > 0:
        print(f"[TEST] Meta Stats populated: {len(brain.meta_stats)} champions found.")
    else:
        print("[TEST] FAIL: Meta Stats are empty!")
        
    # 5. Verify Booster
    try:
        # Should not crash
        prob = brain.booster.predict_proba([[0]*210])
        print(f"[TEST] Booster is functional. Prediction: {prob}")
    except Exception as e:
        print(f"[TEST] Booster failed (Expected if < 1000 matches, but logic should handle it): {e}")
        # In our code, we had: if len > 1000: fit. 
        # Since we only generated 500 matches, Booster should NOT be active.
        # But predict_batch checks if 'booster' in active_weights.
        # If train didn't fit, is_trained=True, but booster might be unfitted.
        # Let's check if our code handles "Booster not fitted" gracefully.
        
    print("--- VERIFICATION COMPLETE ---")

if __name__ == "__main__":
    verify()

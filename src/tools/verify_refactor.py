import sys
import os

# Modify path to allow imports from src
current_dir = os.path.dirname(os.path.abspath(__file__))
# If this script is in root, current_dir is root.
# src is in root/src.
sys.path.append(current_dir)

from src.engine.datasets import BrainDataset
from src.engine.features import FeatureEngine
from src.engine.schema import FeatureConfig as Cfg

def test_dataset_init():
    print("--- Verification Test: BrainDataset Refactor ---")
    
    # 1. Check Constant
    print(f"Checking Constant: {Cfg.QUEUE_COOP_VS_AI} ... ", end="")
    if Cfg.QUEUE_COOP_VS_AI != 830:
        print("FAIL (Value mismatch)")
        sys.exit(1)
    print("OK")
    
    # 2. Check Import & Init
    # We pass a fake DB path first to see if it even initializes the object (checking imports)
    # Then we might want to check the real DB if it exists, to check SQL syntax.
    
    db_path = "brain.db"
    if not os.path.exists(db_path):
        print(f"Warning: {db_path} not found. Creating dummy for SQL syntax check.")
        import sqlite3
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("CREATE TABLE matches (match_id INT, queue_id INT, timestamp INT)")
        c.execute("CREATE TABLE match_frames (match_id INT, frame_data BLOB)")
        # Insert a Co-op game (830) and a Normal game (420)
        c.execute(f"INSERT INTO matches VALUES (1, 830, 1000)")
        c.execute(f"INSERT INTO matches VALUES (2, 420, 2000)")
        c.execute(f"INSERT INTO match_frames VALUES (1, NULL)")
        c.execute(f"INSERT INTO match_frames VALUES (2, NULL)")
        conn.commit()
        conn.close()
        created_dummy = True
    else:
        created_dummy = False
        
    print("Initializing BrainDataset (runs SQL query)...")
    try:
        fe = FeatureEngine()
        ds = BrainDataset(fe, db_path=db_path)
        print(f"Dataset Initialized. Matches found: {len(ds)}")
        
        # Verify 830 was filtered
        if created_dummy:
             if len(ds) == 1 and ds.match_ids[0] == 2:
                 print("Filter Verification: SUCCESS (Bot game 830 excluded)")
             else:
                 print(f"Filter Verification: FAIL (Expected 1 match, got {len(ds)})")
        else:
             print("SQL Query Executed Successfully (Real DB).")
             
    except Exception as e:
        print(f"CRITICAL FAIL: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if created_dummy:
            try:
                os.remove(db_path)
                print("Dummy DB removed.")
            except: pass

    print("--- TEST PASSED ---")

if __name__ == "__main__":
    test_dataset_init()

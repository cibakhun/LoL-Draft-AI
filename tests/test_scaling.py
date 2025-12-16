
import sys
import os
import shutil
import random

# Mock Environment
sys.path.append(os.getcwd())
from src.engine.ensemble_brain import EnsembleBrain
from src.engine.persistence import BrainDatabase

# Mock DDragon
class MockDDragon:
    def __init__(self):
        self.champions = {}
        for i in range(1, 151):
            self.champions[str(i)] = {'key': str(i), 'name': f"Champ{i}", 'info': {'attack': 5, 'magic': 5, 'defense': 5, 'difficulty': 5}, 'roles': ['Fighter']}

def setup_mock_db(db_path="test_brain.db", num_matches=120000):
    if os.path.exists(db_path):
        os.remove(db_path)
        
    db = BrainDatabase(db_path)
    
    # Create fake matches
    print(f"Generating {num_matches} mock matches...")
    
    # We need to manually insert to speed up
    # We need to manually insert to speed up
    import sqlite3
    conn = sqlite3.connect(db_path)
    c = conn.cursor() # Access internal if possible or use public API
    
    # Actually let's just use the public API but faster?
    # No, save_match is too slow for 100k mocks in a test.
    # Let's insert raw SQL.
    
    import sqlite3
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    match_data = []
    part_data = []
    
    for i in range(num_matches):
        mid = f"MOCK_{i}"
        match_data.append((mid, "CLASSIC", 420, 100000 + i))
        
        # 10 participants
        for p in range(10):
            tid = 100 if p < 5 else 200
            win = 1 if (tid == 100 and i % 2 == 0) else 0
            role = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"][p % 5]
            cid = random.randint(1, 150)
            
            part_data.append((mid, f"puuid_{i}_{p}", cid, tid, role, win))
            
    c.executemany("INSERT INTO matches (match_id, game_mode, queue_id, timestamp) VALUES (?, ?, ?, ?)", match_data)
    c.executemany("INSERT INTO participants (match_id, puuid, champion_id, team_id, role, win) VALUES (?, ?, ?, ?, ?, ?)", part_data)
    
    conn.commit()
    conn.close()
    return db_path

def test_scaling():
    print("--- STARTING SCALING TEST ---")
    
    # 1. Setup Data (120k matches -> Should spawn 3 Council Members with 50k cap)
    db_path = setup_mock_db()
    
    # 2. Init Brain
    brain = EnsembleBrain()
    brain.neural = None # Disable neural to speed up test
    
    # Patch persistence to use our test db
    # We can't easily injection dependency into `train` method as it imports BrainDatabase internally.
    # We will Monkey Patch the class.
    
    import src.engine.ensemble_brain
    OriginalDB = src.engine.persistence.BrainDatabase
    
    class TestDB(OriginalDB):
        def __init__(self):
            super().__init__("test_brain.db")
            
    # Swap
    src.engine.persistence.BrainDatabase = TestDB
    
    # 3. Train
    print("Training Brain...")
    # Mock DDragon
    ddragon = MockDDragon()
    
    # 2 Epochs, Batch 10k
    brain.train("dummy_dir", ddragon, batch_size=10000, epochs=2)
    
    # 4. Verify
    print(f"Council Size: {len(brain.forest_council)}")
    if len(brain.forest_council) >= 2:
        print("PASS: Multiple Council Members Spawned.")
    else:
        print(f"FAIL: Expected >1 Members, got {len(brain.forest_council)}")
        
    # Cleanup
    if os.path.exists("test_brain.db"):
        try: os.remove("test_brain.db")
        except: pass
    if os.path.exists("test_brain.db-shm"):
        try: os.remove("test_brain.db-shm")
        except: pass
    if os.path.exists("test_brain.db-wal"):
        try: os.remove("test_brain.db-wal")
        except: pass
        
    # Restore
    src.engine.persistence.BrainDatabase = OriginalDB

if __name__ == "__main__":
    test_scaling()


import unittest
import os
import shutil
import tempfile
import json
import sqlite3
import numpy as np
from src.engine.ensemble_brain import EnsembleBrain
from src.engine.persistence import BrainDatabase

class MockDDragon:
    def __init__(self):
        self.champions = {
            "Aatrox": {"key": "1", "roles": ["Fighter"], "info": {"attack": 8, "defense": 4, "magic": 3, "difficulty": 4}},
            "Ahri": {"key": "103", "roles": ["Mage", "Assassin"], "info": {"attack": 3, "defense": 4, "magic": 8, "difficulty": 5}},
            "LeeSin": {"key": "64", "roles": ["Fighter", "Assassin"], "info": {"attack": 8, "defense": 5, "magic": 3, "difficulty": 6}},
            "Yasuo": {"key": "157", "roles": ["Fighter", "Assassin"], "info": {"attack": 8, "defense": 4, "magic": 4, "difficulty": 10}},
        } # Small universe

class TestBrainPerfection(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_brain.db")
        self.brain = EnsembleBrain()
        self.brain.model_path = os.path.join(self.test_dir, "brain.joblib")
        # Initialize DB
        self.db = BrainDatabase(self.db_path)
        
    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_sliding_window_council(self):
        """Verify that Council rotates members when full (Infinite Learning)."""
        # 1. Fill Council to Limit (Size 30)
        # We Mock the fits to save time
        self.brain.council_size = 5 # Reduce for test speed
        self.brain.forest_batch_size = 10 # Tiny batch
        
        # Simulate 10 batches
        for i in range(10):
            # Mock Data
            X = np.random.rand(20, 100)
            y = np.random.randint(0, 2, 20)
            
            self.brain._spawn_council_member(X, y)
            
            # Tag the forest with an ID to check rotation
            setattr(self.brain.forest_council[-1], "batch_id", i)
            
        # 2. Check Size Limit
        self.assertEqual(len(self.brain.forest_council), 5, "Council should not exceed max size")
        
        # 3. Check Rotation (Sliding Window)
        # Expected IDs in council: [5, 6, 7, 8, 9] (Last 5)
        current_ids = [getattr(m, "batch_id") for m in self.brain.forest_council]
        print(f"Council Batch IDs: {current_ids}")
        
        self.assertIn(9, current_ids, "Council should contain newest batch")
        self.assertNotIn(0, current_ids, "Council should have discarded oldest batch")
        self.assertEqual(current_ids, [5, 6, 7, 8, 9], "Council should be FIFO sliding window")

    def test_chronological_integrity(self):
        """Verify that training happens in order of Timestamps."""
        matches = [
            ("m_future", 2000), 
            ("m_past", 1000), 
            ("m_present", 1500)
        ]
        
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
        
        for mid, ts in matches:
             # 1. Match
             c.execute("INSERT INTO matches (match_id, timestamp) VALUES (?, ?)", (mid, ts))
             
             # 2. Participants (5v5)
             for r in roles:
                 # Blue
                 c.execute("INSERT INTO participants (match_id, team_id, role, champion_id, win) VALUES (?, ?, ?, ?, ?)", 
                           (mid, 100, r, 1, 1))
                 # Red
                 c.execute("INSERT INTO participants (match_id, team_id, role, champion_id, win) VALUES (?, ?, ?, ?, ?)", 
                           (mid, 200, r, 1, 0))
                           
        conn.commit()
        conn.close()
        
        # 2. Yield Batches
        mock_db = BrainDatabase(self.db_path)
        gen = mock_db.yield_training_batches(batch_size=1, shuffle=False)
        
        # 3. Verify Order
        # We expect: 1000 -> 1500 -> 2000
        
        batch1 = next(gen)
        ts1 = batch1[0]['timestamp']
        
        batch2 = next(gen)
        ts2 = batch2[0]['timestamp']
        
        batch3 = next(gen)
        ts3 = batch3[0]['timestamp']
        
        print(f"Timestamps: {ts1} -> {ts2} -> {ts3}")
        
        self.assertEqual(ts1, 1000, "First match should be oldest (1000)")
        self.assertEqual(ts2, 1500, "Second match should be middle (1500)")
        self.assertEqual(ts3, 2000, "Third match should be newest (2000)")

if __name__ == '__main__':
    unittest.main()

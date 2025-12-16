import unittest
import os
import shutil
import numpy as np
from src.engine.persistence import BrainDatabase
from src.engine.ensemble_brain import EnsembleBrain
from src.engine.features import FeatureEngine

class TestDeepBrain(unittest.TestCase):
    def setUp(self):
        self.test_db = "test_brain.db"
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        self.db = BrainDatabase(self.test_db)
        
    def tearDown(self):
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
            
    def test_deep_pipeline(self):
        # 1. Create Fake Match
        fake_match = {
            "metadata": {"matchId": "EUW1_12345"},
            "info": {
                "gameMode": "CLASSIC",
                "queueId": 420,
                "gameCreation": 1000000,
                "gameDuration": 1800, # 30 mins (Mid Game)
                "participants": [
                    {"puuid": "Blue1", "championId": 1, "teamId": 100, "teamPosition": "TOP", "win": True},
                    {"puuid": "Blue2", "championId": 2, "teamId": 100, "teamPosition": "JUNGLE", "win": True},
                    {"puuid": "Blue3", "championId": 3, "teamId": 100, "teamPosition": "MIDDLE", "win": True},
                    {"puuid": "Blue4", "championId": 4, "teamId": 100, "teamPosition": "BOTTOM", "win": True},
                    {"puuid": "Blue5", "championId": 5, "teamId": 100, "teamPosition": "UTILITY", "win": True},
                    
                    {"puuid": "Red1", "championId": 6, "teamId": 200, "teamPosition": "TOP", "win": False},
                    {"puuid": "Red2", "championId": 7, "teamId": 200, "teamPosition": "JUNGLE", "win": False},
                    {"puuid": "Red3", "championId": 8, "teamId": 200, "teamPosition": "MIDDLE", "win": False},
                    {"puuid": "Red4", "championId": 9, "teamId": 200, "teamPosition": "BOTTOM", "win": False},
                    {"puuid": "Red5", "championId": 10, "teamId": 200, "teamPosition": "UTILITY", "win": False}
                ]
            }
        }
        
        self.db.save_match(fake_match)
        
        # 2. Init Brain
        brain = EnsembleBrain()
        
        # Mock Vocab to avoid needing DDragon
        dummy_vocab = {i: i for i in range(1, 11)}
        brain.feature_engine.set_vocab(dummy_vocab)
        
        # 3. Train
        # This triggers feature updates
        brain.train(db=self.db, batch_size=10)
        
        # 4. Verify Feature Engine State
        fe = brain.feature_engine
        
        # Check Spikes
        # Champ 1 (Blue Top) won at 30 mins (Mid Game)
        # Should have 1 game, 1 win in 'mid' bucket
        self.assertIn(1, fe.spike_stats)
        self.assertEqual(fe.spike_stats[1]['mid']['games'], 1)
        self.assertEqual(fe.spike_stats[1]['mid']['wins'], 1)
        self.assertEqual(fe.spike_stats[1]['early']['games'], 0) # Shouldn't touch early
        
        # Check Counters
        # Champ 1 vs Champ 6 (Top vs Top)
        # Counter Matrix should record 1 vs 6 win
        self.assertIn(1, fe.counter_matrix)
        self.assertIn(6, fe.counter_matrix[1])
        self.assertEqual(fe.counter_matrix[1][6]['wins'], 1)
        
        # Champ 6 vs 1 should have 0 wins
        self.assertIn(6, fe.counter_matrix)
        self.assertIn(1, fe.counter_matrix[6])
        self.assertEqual(fe.counter_matrix[6][1]['wins'], 0)
        
        print("\n[TEST] Deep Features Verified (Spikes & Counters Active).")
        
        # 5. Verify Dimensions
        # Vectorize a team
        blue = {"TOP": 1, "JUNGLE": 2, "MIDDLE": 3, "BOTTOM": 4, "UTILITY": 5}
        red = {"TOP": 6, "JUNGLE": 7, "MIDDLE": 8, "BOTTOM": 9, "UTILITY": 10}
        
        flat, (b_ids, r_ids, meta) = fe.vectorize(blue, red)
        
        self.assertEqual(len(meta), 72)
        print(f"[TEST] Meta Vector Correct Dimension: {len(meta)}")
        
        # Check Spike Feature (Index 60 for Blue)
        # We trained on one mid-game win.
        # Blue Team Spikes: Early(0.5), Mid(1.0 - smoothed?), Late(0.5)
        # Smoothing: (1+2)/(1+4) = 3/5 = 0.6
        # Wait, my smoothing in code is (w+2)/(g+4) for spikes? 
        # No, for spikes it uses _get_wr which is (w+2)/(g+4) if g<5 else ...
        # Yes. (1+2)/(1+4) = 0.6
        # So Index 61 (Mid) should be 0.6.
        
        # print(f"Spike Vec: {meta[60:63]}")
        self.assertAlmostEqual(meta[61], 0.6, places=2)
        
if __name__ == '__main__':
    unittest.main()

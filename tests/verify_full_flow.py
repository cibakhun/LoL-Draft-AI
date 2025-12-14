import unittest
import sys
import os
import shutil
import json
import numpy as np

# Inject src path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.engine.ensemble_brain import EnsembleBrain
from src.engine.persistence import BrainDatabase

# Mock Objects
class MockDataDragon:
    def __init__(self):
        self.champions = {
            "Garen": {"key": "1", "name": "Garen", "info": {"attack": 8, "magic": 0, "defense": 8, "difficulty": 2}, "roles": ["Fighter", "Tank"]},
            "Annie": {"key": "2", "name": "Annie", "info": {"attack": 2, "magic": 10, "defense": 3, "difficulty": 1}, "roles": ["Mage"]},
            "Ashe": {"key": "3", "name": "Ashe", "info": {"attack": 7, "magic": 0, "defense": 3, "difficulty": 4}, "roles": ["Marksman"]},
            "Alistar": {"key": "4", "name": "Alistar", "info": {"attack": 6, "magic": 5, "defense": 9, "difficulty": 7}, "roles": ["Tank", "Support"]},
            "MasterYi": {"key": "5", "name": "Master Yi", "info": {"attack": 10, "magic": 0, "defense": 2, "difficulty": 4}, "roles": ["Assassin"]},
            "Yasuo": {"key": "6", "name": "Yasuo", "info": {"attack": 8, "magic": 4, "defense": 4, "difficulty": 9}, "roles": ["Fighter", "Assassin"]} # New Champ for test
        }

class TestDeepSystemVerification(unittest.TestCase):
    def setUp(self):
        # Temp dir for models
        self.test_dir = "tests/temp_brain_test"
        if not os.path.exists(self.test_dir): os.makedirs(self.test_dir)
        
        self.model_path = os.path.join(self.test_dir, "test_brain.joblib")
        self.dd = MockDataDragon()
        
        # Logging
        self.log_file = open("verification_debug.log", "w")
        
    def log(self, msg):
        self.log_file.write(msg + "\n")
        self.log_file.flush()
        print(msg)

    def tearDown(self):
        self.log_file.close()
        # Cleanup
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_full_lifecycle(self):
        self.log("\n[TEST] Starting Deep System Verification: Cycle 1...")
        
        # 1. Create Mock Database (Training Data)
        mock_data = []
        for i in range(20):
            match = {
                'match_id': f'test_match_{i}',
                'blue': {'TOP': 1, 'JUNGLE': 5, 'MIDDLE': 2, 'BOTTOM': 3, 'UTILITY': 4},
                'red': {'TOP': 6, 'JUNGLE': 1, 'MIDDLE': 3, 'BOTTOM': 2, 'UTILITY': 4},
                'win': True if i % 2 == 0 else False
            }
            mock_data.append(match)
            
        self.log(f"[TEST] Mock Data Created. Size: {len(mock_data)}")
            
        # 2. Train Brain
        brain = EnsembleBrain()
        brain.model_path = self.model_path
        
        # Monkey Patch DB
        original_get_data = BrainDatabase.get_training_data
        original_get_meta = BrainDatabase.get_meta_stats
        
        BrainDatabase.get_training_data = lambda self: mock_data
        BrainDatabase.get_meta_stats = lambda self: {} 
        
        try:
            self.log("[TEST] Invoking brain.train()...")
            brain.train(None, self.dd)
            self.log("[TEST] brain.train() returned.")
        except Exception as e:
            self.log(f"[TEST] CRITICAL: brain.train crashed: {e}")
            import traceback
            self.log(traceback.format_exc())
            
        self.log(f"[TEST] Verify is_trained: {brain.is_trained}")
        self.assertTrue(brain.is_trained, "Brain failed to train.")
        
        self.log(f"[TEST] Verify vocab exists: {hasattr(brain, 'vocab')}")
        self.assertTrue(hasattr(brain, 'vocab'))
        self.log(f"[TEST] Vocab size: {len(brain.vocab)}")
        self.assertEqual(len(brain.vocab), 6) # 6 champs in Universe
        
        # 3. Predict before Save
        self.log("[TEST] Testing In-Memory Prediction...")
        blue = {"TOP": 1, "JUNGLE": 5, "MIDDLE": 2, "BOTTOM": 3, "UTILITY": 4}
        red = {"TOP": 6, "JUNGLE": 1, "MIDDLE": 3, "BOTTOM": 2, "UTILITY": 4}
        
        prob_memory = brain.predict(blue, red, self.dd)
        self.log(f" -> Memory Prob: {prob_memory:.4f}")
        
        # 4. Save
        self.log("[TEST] Saving Brain...")
        brain.save()
        
        self.assertTrue(os.path.exists(self.model_path), "Model file not found")
        # Vocab is now bundled in joblib, so _vocab.json check is obsolete
        # self.assertTrue(os.path.exists(self.model_path.replace(".joblib", "_vocab.json")), "Vocab file not found")
        
        # 5. Load into New Brain
        self.log("[TEST] Testing Persistence (Load)...")
        brain2 = EnsembleBrain()
        brain2.model_path = self.model_path
        
        success = brain2.load()
        self.log(f"[TEST] Load result: {success}")
        self.assertTrue(success, "Failed to load brain")
        self.assertTrue(brain2.is_trained, "Loaded brain is not marked trained")
        self.assertEqual(len(brain2.vocab), 6, "Loaded vocab size mismatch")
        
        # 6. Verify Consistency
        prob_loaded = brain2.predict(blue, red, self.dd)
        self.log(f" -> Loaded Prob: {prob_loaded:.4f}")
        
        self.assertAlmostEqual(prob_memory, prob_loaded, places=5)
        
        # 7. Test "New Champion" Handling (Index Shift / Unseen ID)
        self.log("[TEST] Testing Unseen Champion Handling...")
        self.dd.champions["Ambessa"] = {"key": "7", "name": "Ambessa", "info": {}, "roles": ["Top"]}
        
        unknown_team = {"TOP": 7} # Ambessa Top
        
        try:
            prob_unk = brain2.predict(unknown_team, red, self.dd)
            self.log(f" -> Unknown Prob: {prob_unk:.4f}")
            self.assertTrue(0.0 <= prob_unk <= 1.0)
        except Exception as e:
            self.log(f"[TEST] Crash handling Unknown: {e}")
            self.fail(f"Handling new champion crashed the brain: {e}")
            
        self.log("[TEST] Full Cycle Validated.")

if __name__ == '__main__':
    unittest.main()

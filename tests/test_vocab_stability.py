import unittest
import os
import shutil
import json
import numpy as np
from src.engine.ensemble_brain import EnsembleBrain

class MockDDragon:
    def __init__(self, champs):
        self.champions = champs

class TestVocabStability(unittest.TestCase):
    def setUp(self):
        self.test_dir = "test_brain_env"
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir)
        
        self.model_path = os.path.join(self.test_dir, "brain.joblib")
        
    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_vocab_persistence(self):
        with open("vocab_debug.log", "w") as log:
            def dlog(msg):
                log.write(msg + "\n")
                print(msg)
                
            dlog("Starting Test Vocab Persistence")
            
            # 1. Patch A
            ddragon_a = MockDDragon({
                "A": {"key": "1", "name": "Atrox"},
                "C": {"key": "3", "name": "Camille"},
                "E": {"key": "5", "name": "Ezreal"}
            })
            
            brain = EnsembleBrain()
            brain.model_path = self.model_path
            
            # Force build to debug flake
            brain._build_vocab(ddragon_a)
            
            dlog(f"Vocab Keys: {list(brain.vocab.keys())}")
            dlog(f"Vocab content: {brain.vocab}")
            
            idx_a = brain.vocab[1]
            idx_c = brain.vocab[3]
            idx_e = brain.vocab[5]
        
        print(f"Gen 1 Indices: 1->{idx_a}, 3->{idx_c}, 5->{idx_e}")
        
        
        # Save
        brain.is_trained = True # Fake it
        # brain.council removed
        brain.save()
        
        # 2. Patch B (New Champs inserted) - Keys 1, 2, 3, 4, 5
        ddragon_b = MockDDragon({
             "A": {"key": "1", "name": "Atrox"},
             "B": {"key": "2", "name": "Brand"}, # NEW
             "C": {"key": "3", "name": "Camille"},
             "D": {"key": "4", "name": "Darius"}, # NEW
             "E": {"key": "5", "name": "Ezreal"}
        })
        
        # Load fresh brain
        brain_loaded = EnsembleBrain()
        brain_loaded.model_path = self.model_path
        brain_loaded.load()
        
        # Verify Integrity
        # The LOADED brain should rely on vocab, NOT ddragon_b sorting
        
        new_idx_a = brain_loaded.vocab.get(1)
        new_idx_c = brain_loaded.vocab.get(3)
        new_idx_e = brain_loaded.vocab.get(5)
        
        print(f"Gen 2 Indices: 1->{new_idx_a}, 3->{new_idx_c}, 5->{new_idx_e}")
        
        self.assertEqual(idx_a, new_idx_a, "Index for Champ 1 changed! Model Memory Corrupted.")
        self.assertEqual(idx_c, new_idx_c, "Index for Champ 3 changed!")
        self.assertEqual(idx_e, new_idx_e, "Index for Champ 5 changed!")
        
        # Bonus: Ensure new champs are not in vocab (since we didn't retrain)
        self.assertIsNone(brain_loaded.vocab.get(2), "New champ 2 should be unknown until retrain.")

if __name__ == '__main__':
    unittest.main()

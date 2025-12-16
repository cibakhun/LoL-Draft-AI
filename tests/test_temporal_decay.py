import unittest
import sys
import os
import math
import time
from unittest.mock import MagicMock
import numpy as np

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.engine.ensemble_brain import EnsembleBrain
from src.engine.neural_brain import NeuralBrain

class TestTemporalDecay(unittest.TestCase):
    def setUp(self):
        self.brain = EnsembleBrain()
        self.ddragon = MagicMock()
        self.ddragon.champions = {'1': {'key': '1'}}
        self.brain.vocab = {1: 1} # Mock Vocab
        
    def test_weight_calculation(self):
        """Verify that older matches get lower weights."""
        now = time.time()
        matches = [
            {'blue': {'TOP': 1}, 'red': {'TOP': 1}, 'win': 1, 'timestamp': now}, # New
            {'blue': {'TOP': 1}, 'red': {'TOP': 1}, 'win': 1, 'timestamp': now - (86400 * 100)}, # 100 Days Old
            {'blue': {'TOP': 1}, 'red': {'TOP': 1}, 'win': 1, 'timestamp': now - (86400 * 300)} # 300 Days Old
        ]
        
        try:
            X_c, X_m, X_f, y, weights = self.brain._prepare_dataset(matches, self.ddragon, augment=False)
        except Exception:
            import traceback
            with open('error.log', 'w') as f:
                traceback.print_exc(file=f)
            raise
        
        print("\nWeights:", weights)
        self.assertEqual(len(weights), 3)
        self.assertAlmostEqual(weights[0], 1.0, places=1) # Recent map ~ 1.0
        self.assertLess(weights[1], weights[0]) # 100 days < New
        self.assertLess(weights[2], weights[1]) # 300 days < 100 days
        
    def test_weighted_training(self):
        """Verify Neural Brain accepts weights."""
        nb = NeuralBrain()
        nb.initialize(vocab_size=10)
        
        # Fake Batch
        X_champs = np.zeros((2, 10))
        X_meta = np.zeros((2, 50))
        y = np.array([1, 0])
        weights = np.array([1.0, 0.1])
        
        # Mock Torch
        if nb.model: # If torch exists
             loss = nb.train_on_batch(X_champs, X_meta, y, weights=weights)
             self.assertIsInstance(loss, float)

if __name__ == '__main__':
    unittest.main()

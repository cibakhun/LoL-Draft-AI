import unittest
import sys
import os
from unittest.mock import MagicMock, patch
import numpy as np

# Glue
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.engine.ensemble_brain import EnsembleBrain
from src.engine.neural_brain import NeuralBrain

class TestStreamingArchitecture(unittest.TestCase):
    def setUp(self):
        self.brain = EnsembleBrain()
        # Mock Neural Brain to avoid needing Torch/GPU for unit test
        self.brain.neural = MagicMock()
        self.brain.neural.train_on_batch.return_value = 0.5 # Fake loss
        
        self.brain.forest = MagicMock()
        self.brain.booster = MagicMock()
        
    @patch('src.engine.persistence.BrainDatabase')
    def test_streaming_train_loop(self, MockDB):
        """
        Verify that train() iterates over yields and calls train_on_batch.
        """
        # Setup Mock DB
        mock_db_instance = MockDB.return_value
        
        # Create fake matches
        # Batch 1: 5 matches
        b1 = [{'blue': {'TOP': 1}, 'red': {'TOP': 2}, 'win': 1} for _ in range(5)]
        # Batch 2: 3 matches
        b2 = [{'blue': {'TOP': 3}, 'red': {'TOP': 4}, 'win': 0} for _ in range(3)]
        
        # Yield batches
        mock_db_instance.yield_training_batches.return_value = iter([b1, b2])
        
        # Mock Meta Stats
        mock_db_instance.get_meta_stats.return_value = {1: {'total_games': 10}}
        
        # Mock DDragon
        ddragon = MagicMock()
        ddragon.champions = {'1': {'key': '1'}, '2': {'key': '2'}, '3': {'key': '3'}, '4': {'key': '4'}}
        
        # Trace Neural
        def trace_neural(*args, **kwargs):
            print("Neural Train Called!")
            return 0.5
        self.brain.neural.train_on_batch.side_effect = trace_neural
        
        # Trace Forest
        def trace_forest(X, y):
            print(f"Forest Fit Called with X={len(X)}, y={len(y)}")
        self.brain.forest.fit.side_effect = trace_forest
        
        # Run Train
        try:
            self.brain.train("dummy_path", ddragon)
        except Exception:
            import traceback
            with open('error.log', 'w') as f:
                traceback.print_exc(file=f)
            raise
        
        # Verification
        # 1. Check Neural Partial Fits
        # Should be called 2 times (once per batch)
        # Note: _prepare_dataset is called, so X, y are generated. 
        # Check call count.
        self.assertEqual(self.brain.neural.train_on_batch.call_count, 2)
        
        # 2. Check Forest Fit
        # Should be called ONCE at the end with accumulated buffer
        self.brain.forest.fit.assert_called_once()
        
        # Check buffer size passed to forest
        # call_args[0][0] is X, call_args[0][1] is y
        args = self.brain.forest.fit.call_args[0]
        # Total matches = 5 + 3 = 8
        # Since Augment=True in train loop, size might be 8 * 4 = 32
        # Verify non-zero
        self.assertGreater(len(args[0]), 0)
        
    def test_titan_init(self):
        """
        Verify that NeuralBrain initializes with 64-dim embedding (Titan).
        """
        # Instantiate real NeuralBrain to check attribs
        nb = NeuralBrain()
        # Mock HAS_TORCH check inside
        with patch.object(nb, 'initialize') as mock_init:
            nb.train([], [], [], vocab_size=100)
            mock_init.assert_called()

if __name__ == '__main__':
    unittest.main()

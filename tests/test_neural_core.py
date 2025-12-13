import unittest
import numpy as np
import os
import shutil
from src.engine.neural_brain import NeuralBrain, LeagueNet, HAS_TORCH

@unittest.skipUnless(HAS_TORCH, "PyTorch not installed")
class TestNeuralCore(unittest.TestCase):
    def setUp(self):
        self.brain = NeuralBrain(model_path="test_brain.pt")
        # Dummy Training Data (Batch=2)
        # 10 Champs (Ids 1-10) + 50 Meta Features
        self.X_champs = np.random.randint(1, 20, size=(2, 10))
        self.X_meta = np.random.rand(2, 50)
        self.y = np.array([1.0, 0.0])
        
    def tearDown(self):
        if os.path.exists("test_brain.pt"):
            os.remove("test_brain.pt")

    def test_initialization(self):
        """Verify LeagueNet structure."""
        self.brain.initialize(num_champions=50)
        self.assertIsNotNone(self.brain.model)
        # Check Embedding Layer size
        self.assertEqual(self.brain.model.embedding.num_embeddings, 51) # 50 + 1 padding

    def test_overfit_single_batch(self):
        """Model should be able to memorize a small batch (Training logic works)."""
        self.brain.initialize(num_champions=100)
        
        initial_loss = None
        final_loss = None
        
        # Train for 5 epochs and capture loss
        self.brain.train(self.X_champs, self.X_meta, self.y, epochs=5, batch_size=2)
        
        self.assertTrue(len(self.brain.losses) > 0)
        self.assertTrue(self.brain.losses[0] > self.brain.losses[-1]) # Loss should decrease

    def test_batch_inference_consistency(self):
        """Verify that predict_batch returns same results as single predict."""
        self.brain.initialize(num_champions=100)
        self.brain.train(self.X_champs, self.X_meta, self.y, epochs=1)
        
        # Batch Predict
        # Input format for predict_batch is list of lists
        b_list = [list(self.X_champs[0][:5])] # [[1,2,3,4,5]]
        r_list = [list(self.X_champs[0][5:])]
        m_list = [list(self.X_meta[0])]
        
        batch_prob = self.brain.predict_batch(b_list, r_list, m_list)[0]
        
        # Single Predict (Internal)
        single_prob = self.brain.predict(b_list[0], r_list[0], m_list[0])
        
        # Precision check (float32 vs float64 might diff slightly, but should be close)
        self.assertAlmostEqual(batch_prob, single_prob, places=5)

    def test_save_load(self):
        """Verify weights persistence."""
        self.brain.initialize(num_champions=100)
        self.brain.train(self.X_champs, self.X_meta, self.y, epochs=1)
        self.brain.save()
        
        self.assertTrue(os.path.exists("test_brain.pt"))
        
        # Load into new brain
        new_brain = NeuralBrain(model_path="test_brain.pt")
        success = new_brain.load(num_champions=100)
        self.assertTrue(success)
        self.assertTrue(new_brain.is_trained)

if __name__ == '__main__':
    unittest.main()

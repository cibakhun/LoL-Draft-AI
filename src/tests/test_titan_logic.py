
import unittest
import torch
import sys
import os

# Fix Path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from engine.titan_brain import TitanBrain
from engine.mcts import SpatialMCTS, MCTSNode

class MockFE:
    def __init__(self, vocab_size):
        self.vocab = {i:i for i in range(vocab_size)}

class TestTitanLogic(unittest.TestCase):
    def setUp(self):
        self.device = torch.device("cpu")
        self.brain = TitanBrain()
        self.brain.device = self.device
        self.brain.initialize(vocab_size=100) # Small vocab
        # Ensure model is in eval mode for inference tests
        self.brain.model.eval()

    def test_forward_pass_shape(self):
        """Verify the model outputs [B, 10, Vocab] for Policy."""
        B = 2
        Vocab = 100
        
        xp = torch.zeros(B, 10).long()
        xt = torch.zeros(B, 10).long()
        xb = torch.zeros(B, 10).long()
        xm = torch.zeros(B, 10).float()
        xmeta = torch.zeros(B, 3).float()
        
        out = self.brain.model(xp, xt, xb, xm, xmeta)
        
        self.assertEqual(out['policy'].shape, (B, 20, Vocab))
        self.assertEqual(out['value'].shape, (B, 1))

    def test_overfit_single_sample(self):
        self.brain.model.train()
        optimizer = self.brain.optimizer
        
        # Sample: [10, 20, 30 ... 0]
        xp = torch.tensor([[10, 20, 30, 40, 50, 0, 0, 0, 0, 0]], dtype=torch.long)
        # Fix: valid x_times starts from 11
        xt = torch.tensor([[11, 12, 13, 14, 15, 0, 0, 0, 0, 0]], dtype=torch.long)
        xb = torch.zeros(1, 10).long()
        xm = torch.zeros(1, 10).float()
        xmeta = torch.zeros(1, 3).float()
        y_win = torch.tensor([[1.0]]).float()
        
        print("\n[Test] Overfitting single sample...")
        for i in range(50):
            l_pol, l_val = self.brain.train_step(xp, xt, xb, xm, xmeta, y_win)
            if i % 10 == 0:
                print(f"Iter {i}: Pol {l_pol:.4f} Val {l_val:.4f}")
                
        self.brain.model.eval()
        with torch.no_grad():
            out = self.brain.model(xp, xt, xb, xm, xmeta)
            val = out['value'].item()
            pol = out['policy']
            
            # Since bans are 0, Pick 1 (10) is predicted after Ban 10. That's index 10.
            p1_pred = torch.argmax(pol[0, 10]).item()
            p2_pred = torch.argmax(pol[0, 11]).item()
            
            print(f"Final Value: {val:.4f} (Target 1.0)")
            print(f"P1 Pred: {p1_pred} (Target 10)")
            print(f"P2 Pred: {p2_pred} (Target 20)")
            
            self.assertTrue(val > 0.9)
            self.assertEqual(p1_pred, 10)
            self.assertEqual(p2_pred, 20)
            
    def test_mcts_expand_index(self):
        fe = MockFE(100)
        mcts = SpatialMCTS(self.brain, fe)
        
        # Case 1: Empty Draft (Len 0)
        # Should query Index 0.
        root = MCTSNode(state_tensors=[], parent=None)
        
        # We Mock the Model to return specific logits at specific indices
        # to see which one MCTS reads.
        
        # Create a Mock Model Wrapper
        class MockPyTorchModel:
            def __init__(self, policy, value, sort_idx):
                self.policy = policy
                self.value = value
                self.sort_idx = sort_idx
            def eval(self): pass
            def __call__(self, *args, **kwargs):
                 return {'policy': self.policy, 'value': self.value, 'sort_indices': self.sort_idx}

        class MockBrain:
            def __init__(self):
                self.device = torch.device("cpu")
                # Policy: [1, 20, 100]
                self.policy = torch.zeros(1, 20, 100)
                # Set specific spikes
                self.policy[0, 10, 5] = 100.0 # Pick 1 prediction before any move -> pred_index 10
                self.policy[0, 11, 6] = 100.0 # Pick 2 prediction -> pred_index 11
                
                self.value = torch.tensor([[0.5]])
                # Sort indices mock: [0, 1..10, 11..20]
                self.sort_idx = torch.arange(21).unsqueeze(0) 
                
                self.model = MockPyTorchModel(self.policy, self.value, self.sort_idx)
        
        mcts.model = MockBrain()
        
        # Expand Empty (Len 0), active_slot_id = 0, raw_index = 11.
        # sort_idx == 11 at pos 11. pred_index = 10.
        # Should pick up Token 5
        mcts._expand(root)
        
        self.assertIn(5, root.children)
        self.assertNotIn(6, root.children)
        
        # Case 2: Draft Len 1 (State=[5])
        # active_slot_id = 1, raw_index = 12.
        # sort_idx == 12 at pos 12. pred_index = 11.
        # Should pick up Token 6
        node1 = MCTSNode(state_tensors=[5], parent=root)
        node1.slot_idx = 1
        mcts._expand(node1)
        
        self.assertIn(6, node1.children)
        self.assertNotIn(5, node1.children)
        
        print("\n[Test] MCTS Index Logic Verified.")

if __name__ == '__main__':
    unittest.main()

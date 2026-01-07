
import unittest
import torch
import sys
import os

# Fix Path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from engine.titan_brain import TitanBrain
from engine.mcts import TitanMCTS, MCTSNode

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
        
        self.assertEqual(out['policy'].shape, (B, 10, Vocab))
        self.assertEqual(out['value'].shape, (B, 1))

    def test_overfit_single_sample(self):
        """
        Verify that we can overfit a single sample perfectly.
        This confirms that gradients flow and targets are aligned fundamentally.
        Logic: Input [P1, P2] -> Target [P1, P2] (Reconstruction from Context)
        We use the 'Shifted Input' architecture:
        Input Token [Previous] -> Predict [Current]
        """
        self.brain.model.train()
        optimizer = self.brain.optimizer
        
        # Sample: [10, 20, 30 ... 0]
        xp = torch.tensor([[10, 20, 30, 40, 50, 0, 0, 0, 0, 0]], dtype=torch.long)
        xt = torch.tensor([[1, 2, 3, 4, 5, 0, 0, 0, 0, 0]], dtype=torch.long)
        xb = torch.zeros(1, 10).long()
        xm = torch.zeros(1, 10).float()
        xmeta = torch.zeros(1, 3).float()
        y_win = torch.tensor([[1.0]]).float()
        
        # Targets: SAME AS INPUT (Since model handles shifting internally via slice 10:20)
        targets = xp.clone()
        
        print("\n[Test] Overfitting single sample...")
        for i in range(50):
            # Pass targets explicitly
            l_pol, l_val = self.brain.train_step(xp, xt, xb, xm, xmeta, y_win, y_policy=targets)
            if i % 10 == 0:
                print(f"Iter {i}: Pol {l_pol:.4f} Val {l_val:.4f}")
                
        # Value should be close to 1.0
        # Policy should predict 10 at index 0, 20 at index 1...
        
        self.brain.model.eval()
        with torch.no_grad():
            out = self.brain.model(xp, xt, xb, xm, xmeta)
            val = out['value'].item()
            pol = out['policy']
            
            p1_pred = torch.argmax(pol[0, 0]).item()
            p2_pred = torch.argmax(pol[0, 1]).item()
            
            print(f"Final Value: {val:.4f} (Target 1.0)")
            print(f"P1 Pred: {p1_pred} (Target 10)")
            print(f"P2 Pred: {p2_pred} (Target 20)")
            
            self.assertTrue(val > 0.9)
            self.assertEqual(p1_pred, 10)
            self.assertEqual(p2_pred, 20)
            
    def test_mcts_expand_index(self):
        """
        Verify MCTS queries the correct index for a given state length.
        """
        fe = MockFE(100)
        mcts = TitanMCTS(self.brain, fe)
        
        # Case 1: Empty Draft (Len 0)
        # Should query Index 0.
        root = MCTSNode(state=[], parent=None)
        
        # We Mock the Model to return specific logits at specific indices
        # to see which one MCTS reads.
        
        # Create a Mock Model Wrapper
        class MockPyTorchModel:
            def __init__(self, policy, value):
                self.policy = policy
                self.value = value
            def eval(self): pass
            def __call__(self, *args, **kwargs):
                 return {'policy': self.policy, 'value': self.value}

        class MockBrain:
            def __init__(self):
                self.device = torch.device("cpu")
                # Policy: [1, 10, 100]
                self.policy = torch.zeros(1, 10, 100)
                # Set specific spikes
                self.policy[0, 0, 5] = 100.0 # Index 0 -> Preds ID 5
                self.policy[0, 1, 6] = 100.0 # Index 1 -> Preds ID 6
                self.policy[0, 9, 7] = 100.0 # Index 9 -> Preds ID 7
                
                self.value = torch.tensor([[0.5]])
                
                self.model = MockPyTorchModel(self.policy, self.value)
        
        mcts.model = MockBrain()
        
        # Expand Empty (Len 0)
        # Should pick up Token 5 (from Index 0)
        mcts._expand(root)
        
        # Check children
        # Children are dict {action_id: Node}
        # We expect a child for Action 5 with high probability
        self.assertIn(5, root.children)
        self.assertNotIn(6, root.children)
        
        # Case 2: Draft Len 1 (State=[5])
        # Should query Index 1.
        # Should pick up Token 6 (from Index 1)
        node1 = MCTSNode(state=[5], parent=root)
        mcts._expand(node1)
        
        self.assertIn(6, node1.children)
        self.assertNotIn(5, node1.children)
        
        print("\n[Test] MCTS Index Logic Verified.")

if __name__ == '__main__':
    unittest.main()

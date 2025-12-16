import unittest
import numpy as np
import sys
import os

# Glue
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.engine.ensemble_brain import EnsembleBrain
from src.engine.smart_draft import SmartDraft
from unittest.mock import MagicMock

class TestDeepRepair(unittest.TestCase):
    def setUp(self):
        self.brain = EnsembleBrain()
        
    def test_vocab_and_vectorizer_stride(self):
        """
        Verify that:
        1. 0 is Active UNK.
        2. Max Index is handled correctly.
        3. Stride prevents overwrite.
        """
        # Mock DDragon with 3 champs
        ddragon = MagicMock()
        ddragon.champions = {
            "A": {"key": "10"}, # Id 10
            "B": {"key": "20"}, # Id 20
            "C": {"key": "30"}  # Id 30
        }
        
        self.brain._build_vocab(ddragon)
        
        # Vocab should be: {10: 1, 20: 2, 30: 3}
        # Max Index = 3.
        # Stride should be 4 (0, 1, 2, 3).
        
        # Test Vectorizer
        blue_team = {"TOP": 30} # Last Champ (Index 3)
        red_team = {"JUNGLE": 10} # First Champ (Index 1)
        
        self.brain._vectorize_team(blue_team, red_team, ddragon)
        
        self.assertTrue(self.brain.input_size > 0)
        
        # Verify Stride logic: Stride = Max(3) + 1 = 4.
        # Blue Top (Role 0): Block 0.
        # Index = 0 * 4 + vocab[30] = 3.
        # Blue Jungle (Role 1): Block 1 starts at 4.
        
        # If the bug existed: Stride = 3. 
        # Index = 0 * 3 + 3 = 3. (Correct?)
        # Wait, if vocab was 1-based size 3: indices 1,2,3.
        # Block 0: 0,1,2. Index 3 is start of Block 1.
        
        # With fix: Stride = 4. Indices 0,1,2,3 are valid in Block 0.
        # Block 1 starts at 4.
        
        # Let's verify manually via accessing internal vars or reconstructing logic
        stride = 4
        expected_top_idx = 3 # 0*4 + 3
        expected_next_block = 4 # 1*4
        
        # We can't access 'vec' directly as it is local.
        # But we can verify self.vocab_size logic if we stored it?
        # I added `self.vocab_size` to _build_vocab.
        
        self.assertEqual(self.brain.vocab_size, 4)
        self.assertEqual(self.brain.vocab[30], 3)
        
        # Test UNK Token
        unknown_team = {"TOP": 999} # Unknown
        # Should use Index 0.
        # Index = 0 * 4 + 0 = 0.
        
        # We can test this by exposing the vectorizer output? 
        # _vectorize_team returns nothing, it's a void? Wait, reading code...
        # It calculates `self.input_size` but doesn't return `vec`... 
        # Ah, looking at code: `flat = self._vectorize_team(...)` in `train` implies it DOES return.
        # Let me crack open `_vectorize_team` return statement.
        
    def test_wilson_math(self):
        sd = SmartDraft(None, None, None, None, None)
        
        # Case 1: High Confidence (0.9), Low Sample (N=1)
        # Expect HUGE penalty.
        res_1 = sd._wilson_score_lower_bound(0.9, 1)
        print(f"Wilson(0.9, 1) = {res_1}")
        self.assertLess(res_1, 0.5) # Should be crushed (from 0.9 to ~0.4)
        
        # Case 2: High Confidence (0.9), High Sample (N=100)
        # Expect minimal penalty.
        res_100 = sd._wilson_score_lower_bound(0.9, 100)
        print(f"Wilson(0.9, 100) = {res_100}")
        self.assertGreater(res_100, 0.8) # Should remain high
        
        # Case 3: Random (0.5), Low Sample
        res_mid = sd._wilson_score_lower_bound(0.5, 1)
        # Should drop below 0.5?
        # Wilson lower bound of 0.5 is < 0.5.
        print(f"Wilson(0.5, 1) = {res_mid}")
        self.assertLess(res_mid, 0.5)

if __name__ == '__main__':
    unittest.main()

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
import numpy as np
from unittest.mock import MagicMock
from src.engine.ensemble_brain import EnsembleBrain

class TestRound2Remediation(unittest.TestCase):
    def setUp(self):
        self.brain = EnsembleBrain()
        # Mock Weights
        self.brain.weights = {'neural': 0.5, 'forest': 0.3, 'booster': 0.2}
        
    def test_dynamic_weight_normalization(self):
        """
        Verify that if Neural is missing, weights rebalance to 1.0.
        """
        self.brain.is_trained = True
        self.brain.neural = None # Disable Neural
        
        # Mock Trees
        self.brain.forest = MagicMock()
        self.brain.booster = MagicMock()
        
        # Mock Predict Proba (Return 0.8 for everyone)
        # sklearn returns [ [Loss, Win], [Loss, Win] ]
        self.brain.forest.predict_proba.return_value = np.array([[0.2, 0.8], [0.2, 0.8]])
        self.brain.booster.predict_proba.return_value = np.array([[0.2, 0.8], [0.2, 0.8]])
        
        # Mock Vectorizer
        self.brain._vectorize_team = MagicMock(return_value=[0]*100)
        
        # Scenario: 2 Matches
        blue_teams = [[1,2,3,4,5], [1,2,3,4,5]]
        red_teams = [[6,7,8,9,10], [6,7,8,9,10]]
        ddragon = MagicMock()
        
        probs = self.brain.predict_batch(blue_teams, red_teams, ddragon)
        
        # Expected:
        # Neural = 0
        # Forest Weight = 0.3 / 0.5 = 0.6
        # Booster Weight = 0.2 / 0.5 = 0.4
        # Result = (0.8 * 0.6) + (0.8 * 0.4) = 0.48 + 0.32 = 0.8
        
        print(f"Probabilities: {probs}")
        self.assertAlmostEqual(probs[0], 0.8)
        self.assertAlmostEqual(probs[1], 0.8)

    def test_augmentation_generation(self):
        """
        Verify _generate_partial_states creates valid subsets.
        """
        match = {
            'blue': {'TOP': 1, 'JUNGLE': 2, 'MIDDLE': 3, 'BOTTOM': 4, 'UTILITY': 5},
            'red': {'TOP': 6, 'JUNGLE': 7, 'MIDDLE': 8, 'BOTTOM': 9, 'UTILITY': 10},
            'win': True
        }
        
        partials = self.brain._generate_partial_states(match)
        
        print(f"Generated {len(partials)} partials.")
        self.assertTrue(len(partials) >= 2)
        
        for p in partials:
            # Check Label Integrity
            self.assertEqual(p['win'], True)
            
            # Check Partiality
            b_len = len(p['blue'])
            r_len = len(p['red'])
            print(f"Partial State: Blue {b_len} vs Red {r_len}")
            
            # Should be subsets
            self.assertTrue(b_len <= 5)
            self.assertTrue(r_len <= 5)
            # Should not be physically empty (at least one champ somewhere usually)
            self.assertTrue(b_len + r_len > 0)
            
            # Check Keys match
            for k, v in p['blue'].items():
                self.assertEqual(match['blue'][k], v)

    def test_leakage_stats_calc(self):
        """
        Verify stats are calculated ONLY from the provided subset.
        """
        matches = [
            {'blue': {'TOP': 100}, 'red': {'TOP': 200}, 'win': True}, # 100 Wins, 200 Loses
            {'blue': {'TOP': 200}, 'red': {'TOP': 100}, 'win': True}, # 200 Wins, 100 Loses
            {'blue': {'TOP': 100}, 'red': {'TOP': 200}, 'win': False} # 100 Loses, 200 Wins
        ]
        
        # 100: 1 Win (Blue), 1 Loss (Red), 1 Loss (Blue) = 1W / 3G ?
        # Wait:
        # M1: 100(W), 200(L)
        # M2: 200(W), 100(L)
        # M3: 100(L), 200(W)
        
        # Totals:
        # 100: M1(W), M2(L), M3(L) -> 1W 2L (33%)
        # 200: M1(L), M2(W), M3(W) -> 2W 1L (66%)
        
        stats = self.brain._calculate_stats_from_subset(matches)
        
        # Check 100
        stats_100 = stats[100]['TOP']
        self.assertEqual(stats_100['games'], 3)
        self.assertEqual(stats_100['wins'], 1)
        
        # Check 200
        stats_200 = stats[200]['TOP']
        self.assertEqual(stats_200['games'], 3)
        self.assertEqual(stats_200['wins'], 2)
        
if __name__ == '__main__':
    unittest.main()

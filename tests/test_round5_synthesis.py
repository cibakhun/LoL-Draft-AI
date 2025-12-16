import unittest
import sys
import os
from unittest.mock import MagicMock

# Glue
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.engine.smart_draft import SmartDraft
from src.engine.ensemble_brain import EnsembleBrain

class TestRound5Synthesis(unittest.TestCase):
    def setUp(self):
        self.brain = EnsembleBrain()
        self.sd = SmartDraft(None, None, None, None, self.brain)

    def test_bayesian_average(self):
        """
        Verify Bayesian Average Logic.
        Formula: (P_neural * N + P_prior * K) / (N + K)
        Prior = 0.5, K = 10
        """
        # Case 1: N=0 (New Champ). Neural says 0.9.
        # Score = (0.9 * 0 + 0.5 * 10) / (0 + 10) = 5.0 / 10 = 0.5
        # Result: Neural is ignored, Prior dominates. Safely Neutral.
        res_new = self.sd._bayesian_average(0.9, 0, k=10)
        self.assertAlmostEqual(res_new, 0.5)
        
        # Case 2: N=10 (Equal weight). Neural says 0.9.
        # Score = (0.9 * 10 + 0.5 * 10) / (20) = 14 / 20 = 0.7
        # Result: Blended.
        res_mid = self.sd._bayesian_average(0.9, 10, k=10)
        self.assertAlmostEqual(res_mid, 0.7)
        
        # Case 3: N=100 (Veteran). Neural says 0.9.
        # Score = (0.9 * 100 + 0.5 * 10) / 110 = 95 / 110 = 0.86
        # Result: Neural dominates.
        res_vet = self.sd._bayesian_average(0.9, 100, k=10)
        self.assertGreater(res_vet, 0.85)

    def test_stats_imputation(self):
        """
        Verify that unknown tokens get imputed stats instead of 0s.
        """
        # Mock ddragon
        ddragon = MagicMock()
        ddragon.champions = {} # Empty
        
        # Mock Cache to fail lookup
        self.brain.ddragon_cache = {} 
        
        team_dict = {"TOP": 999} # Unknown ID
        vec = [0] * 100
        start_idx = 0
        
        self.brain._calculate_comp_stats(team_dict, vec, start_idx, ddragon)
        
        # Stats[0] is Attack. Default Imputation is 6.
        # Stats are normalized by count (1). So 6/1 = 6.
        # But wait, logic divides by count.
        
        # Verify Attack Stat (Index 0)
        # Check logic: stats[0] += atk. Then stats[i] /= count.
        # Imputed Atk = 6.
        self.assertEqual(vec[0], 6.0)
        
        # Verify Defense (Index 2). Imputed = 5.
        self.assertEqual(vec[2], 5.0)

if __name__ == '__main__':
    unittest.main()

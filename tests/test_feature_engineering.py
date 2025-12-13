import unittest
import numpy as np
import sys
import os

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.engine.ensemble_brain import EnsembleBrain

class MockDataDragon:
    def __init__(self):
        # Create a tiny universe of 5 champions
        self.champions = {
            "Garen": {"key": "1", "name": "Garen", "info": {"attack": 8, "magic": 0, "defense": 8, "difficulty": 2}, "roles": ["Fighter", "Tank"]},
            "Annie": {"key": "2", "name": "Annie", "info": {"attack": 2, "magic": 10, "defense": 3, "difficulty": 1}, "roles": ["Mage"]},
            "Ashe": {"key": "3", "name": "Ashe", "info": {"attack": 7, "magic": 0, "defense": 3, "difficulty": 4}, "roles": ["Marksman"]},
            "Alistar": {"key": "4", "name": "Alistar", "info": {"attack": 6, "magic": 5, "defense": 9, "difficulty": 7}, "roles": ["Tank", "Support"]},
            "MasterYi": {"key": "5", "name": "Master Yi", "info": {"attack": 10, "magic": 0, "defense": 2, "difficulty": 4}, "roles": ["Assassin"]}
        }

class TestFeatureEngineering(unittest.TestCase):
    def setUp(self):
        self.brain = EnsembleBrain()
        self.dd = MockDataDragon()
        
        # Manually inject meta stats for deterministic testing
        self.brain.meta_stats = {
            1: {"TOP": {"games": 10, "wins": 5}, "total_games": 20}, # Garen: 50% Top WR
            2: {"MIDDLE": {"games": 100, "wins": 60}, "total_games": 100} # Annie: 60% Mid WR
        }

    def test_vector_dimensions_and_indices(self):
        """Verify that the vector is the correct size and mapping is consistent."""
        # Initialize internal index map
        # Universe size = 5.
        # Vector size: (5 champs * 10 roles) + 30 meta + 20 context = 100 inputs
        
        vec = self.brain._vectorize_team({}, {}, self.dd)
        
        expected_champs = 5
        self.assertEqual(len(self.brain.id_to_idx), expected_champs)
        
        # Check calculated input size
        # (5 * 10) + 30 + 20 = 100
        expected_size = (5 * 10) + 30 + 20  
        self.assertEqual(len(vec), expected_size)
        self.assertEqual(self.brain.input_size, expected_size)

    def test_role_encoding_correctness(self):
        """Verify that a Top Laner goes into the Top Lane block."""
        blue_team = {"TOP": 1} # Garen
        vec = self.brain._vectorize_team(blue_team, {}, self.dd)
        
        # Garen ID=1 -> Index in sorted keys [1,2,3,4,5] -> idx 0
        # Role TOP -> Block 0
        # Vector Index = (Block 0 * 5) + 0 = 0
        
        self.assertEqual(vec[0], 1.0)
        
        # Verify NO other bits are set in the first 50 entries (Champion Blocks)
        # We check sum of slice
        self.assertEqual(np.sum(vec[0:50]), 1.0)

    def test_meta_context_integration(self):
        """Verify that Winrate/Frequency data is correctly injected."""
        # Scenario: Annie Mid (Blue)
        blue_team = {"MIDDLE": 2} # Annie
        vec = self.brain._vectorize_team(blue_team, {}, self.dd)
        
        # Context Start Index calculation
        # Champs: 5 * 10 = 50
        # Aggregated Stats: 30
        # Context Start: 80
        
        context_start = 80
        # Blue Middle is index 2 in context (TOP, JG, MID, BOT, SUP)
        # So offset = 2 * 2 = 4
        # Index = 84 (Freq), 85 (WR)
        
        freq_idx = context_start + 4
        wr_idx = context_start + 5
        
        freq = vec[freq_idx]
        wr = vec[wr_idx]
        
        # Annie Stats: 100 games, 60 wins.
        # Freq: 100/100 = 1.0
        # WR (smoothed): (60 + 2.5) / (100 + 5) = 62.5 / 105 = 0.5952
        
        self.assertEqual(freq, 1.0)
        self.assertAlmostEqual(wr, 0.5952, places=4)

if __name__ == '__main__':
    unittest.main()

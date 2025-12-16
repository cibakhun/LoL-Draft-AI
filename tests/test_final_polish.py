import unittest
import sys
import os
from unittest.mock import MagicMock, patch

# Glue
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.engine.ensemble_brain import EnsembleBrain
from src.engine.smart_draft import SmartDraft

class TestFinalPolish(unittest.TestCase):
    def setUp(self):
        self.brain = EnsembleBrain()
        self.sd = SmartDraft(None, None, None, None, self.brain)

    def test_ghost_token_dropout(self):
        """
        Verify that _apply_dropout replaces items with 0 based on probability.
        """
        team = {'TOP': 100, 'JUNGLE': 200, 'MID': 300}
        
        # Force random to be < p (always drop)
        with patch('random.random', return_value=0.0): 
            dropped = self.brain._apply_dropout(team, p=0.01)
            # All should be 0
            self.assertEqual(dropped['TOP'], 0)
            self.assertEqual(dropped['JUNGLE'], 0)
            self.assertEqual(dropped['MID'], 0)
            
        # Force random to be > p (never drop)
        with patch('random.random', return_value=0.9):
            kept = self.brain._apply_dropout(team, p=0.01)
            self.assertEqual(kept['TOP'], 100)
            
    def test_doppleganger_check(self):
        """
        Verify that SmartDraft skips candidates that are already in base team.
        """
        candidates = ["Yasuo", "Ahri"]
        ddragon = MagicMock()
        ddragon.champions = {
            "Yasuo": {"key": "157"},
            "Ahri": {"key": "103"}
        }
        
        # Teammate already picked Yasuo (157)
        my_team_roles = {"TOP": "157"} 
        enemy_team_roles = {}
        my_role = "MIDDLE"
        
        # Mock Brain Predict to avoid crash
        self.brain.is_trained = True
        self.brain.predict_batch = MagicMock(return_value=[0.5]) # Should return 1 result (for Ahri)
        
        results = self.sd.batch_rank(candidates, my_team_roles, enemy_team_roles, my_role, ddragon)
        
        # Yasuo should be skipped. Ahri should be processed.
        # Check generated teams passed to predict_batch
        
        # Verify predict_batch was called with 1 team, not 2
        calls = self.brain.predict_batch.call_args[0]
        blue_teams_batch = calls[0]
        
        print(f"Batch Blue Teams: {blue_teams_batch}")
        self.assertEqual(len(blue_teams_batch), 1)
        self.assertEqual(blue_teams_batch[0]['MIDDLE'], 103) # Ahri
        # Yasuo (157) logic shouldn't have been generated

if __name__ == '__main__':
    unittest.main()

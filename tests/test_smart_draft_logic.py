import unittest
from unittest.mock import MagicMock
import sys
import os

# Ensure src is in path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.engine.smart_draft import SmartDraft

class TestSmartDraftLogic(unittest.TestCase):
    def setUp(self):
        self.mock_meta = MagicMock()
        self.mock_profile = MagicMock()
        self.mock_comp = MagicMock()
        self.mock_learn = MagicMock()
        self.mock_brain = MagicMock()
        
        # Default behavior: Brain predicts 50% winrate
        self.mock_brain.predict.return_value = 0.5 
        # Crucial: Initialize meta_stats to prevent MagicMock auto-creation and TypeErrors
        self.mock_brain.meta_stats = {}
        
        self.draft = SmartDraft(
            self.mock_meta, 
            self.mock_profile, 
            self.mock_comp, 
            self.mock_learn, 
            ensemble_brain=self.mock_brain
        )

    def test_hybrid_wilson_score_logic(self):
        """
        Verify 'The Realist' (Stats) vs 'The Dreamer' (Neural) weighting using Wilson Score.
        """
        # Setup specific stats in Mock Brain
        # Garen (High N=100, WR=60%)
        # Teemo (Low N=10, WR=60%)
        self.mock_brain.meta_stats = {
            1: {"TOP": {"games": 100, "wins": 60}},
            2: {"TOP": {"games": 5, "wins": 3}} # Teemo: 5 games -> Trigger <10 penalty
        }
        
        # Mock DataDragon for name lookup
        mock_dd = MagicMock()
        mock_dd.champions = {
            "Garen": {"key": "1"}, 
            "Teemo": {"key": "2"}
        }
        
        # Test: Logic should value the High Confidence one DIFFERENTLY (usually lower bound is higher if N is high for same WR?)
        # Wait, Wilson Lower Bound:
        # 60/100 -> Lower Bound ~ 0.50
        # 6/10 -> Lower Bound ~ 0.30 (Much wider interval)
        
        # So High N with same positive winrate -> Higher Score! 
        # Low N -> Lower Score (Uncertainty penalty).
        
        # Case 1: High N (Garen)
        # Neural says 0.8
        score_high_n = self.draft._calculate_hybrid_score(0.8, "Garen", "TOP", mock_dd)
        
        # Case 2: Low N (Teemo)
        # Neural says 0.8
        score_low_n = self.draft._calculate_hybrid_score(0.8, "Teemo", "TOP", mock_dd)
        
        # High Confidence (Garen) should result in a HIGHER score because the lower bound is higher.
        print(f"High N Score: {score_high_n}")
        print(f"Low N Score: {score_low_n}")
        
        self.assertGreater(score_high_n, score_low_n)

    def test_synergy_boost_integration(self):
        """Verify that composition analysis boosts the final score."""
        cid = 1
        my_team = [2, 3] # Teammates
        
        # Mock Comp engine to return Synergy +10
        self.mock_comp.analyze_comp_impact.return_value = 10.0
        
        # Mock Brain to return 0.5
        self.mock_brain.predict.return_value = 0.5
        
        # Calculate Score
        # We mock _calculate_hybrid_score to just return the win prob * 100 for simplicity of this test logic test
        # OR we just rely on the full flow. 
        
        # Calculate Score
        # We pass role="TOP" as keyword arg to avoid positional confusion
        self.mock_meta.get_champion_stats.return_value = (0, 0)
        
        score, details = self.draft.calculate_score(
            champion=cid, 
            my_team=my_team, 
            enemy_team=[], 
            my_team_roles={}, 
            my_role="TOP"
        )
        
        # Base (Neutral) = ~50 (Neural 0.5 * 100)
        # Synergy = +10
        # Expected ~60
        
        self.assertGreater(score, 55.0)
        self.assertIn("Synergy", str(details))

if __name__ == '__main__':
    unittest.main()

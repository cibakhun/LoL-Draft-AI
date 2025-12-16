
import unittest
from unittest.mock import MagicMock
from src.engine.smart_draft import SmartDraft
# We mock EnsembleBrain to avoid loading heavy models or needing data
class MockBrain:
    def __init__(self):
        self.is_trained = True
        
    def predict(self, blue, red, ddragon):
        # Return a fixed probability based on champion ID to verify flow
        # If ID is "103" (Ahri), return 0.8
        # If ID is "1" (Annie), return 0.2
        
        # Check if blue team has Ahri
        if "103" in blue.values(): return 0.8
        if "1" in blue.values(): return 0.2
        return 0.5
        
class TestBrainIntegration(unittest.TestCase):
    def test_smart_draft_uses_brain(self):
        # Setup
        mock_meta = MagicMock()
        mock_profile = MagicMock()
        mock_comp = MagicMock()
        mock_learn = MagicMock()
        mock_brain = MockBrain()
        
        draft = SmartDraft(mock_meta, mock_profile, mock_comp, mock_learn, ensemble_brain=mock_brain)
        
        # Case 1: Pick Ahri (Win)
        score, details = draft.calculate_score("103", [], [], my_team_roles={}, my_role="MIDDLE")
        print(f"Ahri Score: {score}")
        self.assertEqual(score, 80.0)
        self.assertIn("High", details["AI_Confidence"])
        
        # Case 2: Pick Annie (Loss)
        score, details = draft.calculate_score("1", [], [], my_team_roles={}, my_role="MIDDLE")
        print(f"Annie Score: {score}")
        self.assertEqual(score, 20.0)
        
        print("Integration Test Passed!")

if __name__ == '__main__':
    unittest.main()

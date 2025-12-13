
import unittest
from unittest.mock import MagicMock
from src.engine.smart_draft import SmartDraft

class TestSmartDraftLogic(unittest.TestCase):
    def test_clamp_logic(self):
        # Setup Mocks
        brain = MagicMock()
        brain.is_trained = True
        
        # Test 1: Batch Rank Clamp
        # Return crazy high probs
        brain.predict_batch.return_value = [0.10, 0.50, 0.99, 0.85]
        
        draft = SmartDraft(None, None, None, None, ensemble_brain=brain)
        
        candidates = ["Fiddle", "Feed", "God", "Pro"]
        ddragon = MagicMock()
        # Mock ddragon.champions for key lookup
        ddragon.champions = {
            "Fiddle": {"key": 1}, "Feed": {"key": 2}, 
            "God": {"key": 3}, "Pro": {"key": 4}
        }
        
        results = draft.batch_rank(candidates, {}, {}, "MIDDLE", ddragon)
        
        print("\nSmartDraft Batch Test Results:")
        for r in results:
            print(f"{r['champion']}: {r['score']}%")
            
        # Assertions
        # 0.10 raw -> 0.30 calibrated -> clamped to 0.35
        self.assertEqual(results[0]['score'], 35.0)
        # 0.50 -> 50.0 (unchanged)
        self.assertEqual(results[1]['score'], 50.0)
        # 0.99 raw -> 0.5 + 0.49*0.5 = 0.745 (74.5%)
        self.assertEqual(results[2]['score'], 74.5)
        # 0.85 raw -> 0.5 + 0.35*0.5 = 0.675 (67.5%)
        self.assertEqual(results[3]['score'], 67.5)
        
    def test_calculate_score_clamp(self):
        # Setup Mocks
        brain = MagicMock()
        brain.is_trained = True
        
        draft = SmartDraft(None, None, MagicMock(), None, ensemble_brain=brain)
        
        # Case High: 0.90 -> 0.5 + 0.2 = 0.7 -> 70.0%
        brain.predict.return_value = 0.90
        # Mock ddragon needs to be passed
        ddragon = MagicMock()
        score, details = draft.calculate_score(1, {}, {}, ddragon=ddragon)
        self.assertEqual(score, 70.0)
        
        # Case Low: 0.10 -> 0.30 -> Clamped 35.0
        brain.predict.return_value = 0.10
        score, details = draft.calculate_score(1, {}, {}, ddragon=ddragon)
        self.assertEqual(score, 35.0)

if __name__ == '__main__':
    unittest.main()

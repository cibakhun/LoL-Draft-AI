import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from unittest.mock import MagicMock
from src.engine.smart_draft import SmartDraft

class TestSmartDraftFilter(unittest.TestCase):
    def test_role_filtering(self):
        # Mock Dependencies
        mock_meta = MagicMock()
        mock_profile = MagicMock()
        mock_comp = MagicMock()
        mock_learning = MagicMock()
        
        # Mock EnsemleBrain with specific stats
        mock_brain = MagicMock()
        mock_brain.is_trained = True
        
        # Scenario:
        # Aatrox: 100 Games Top (Should PASS)
        # Yuumi: 0 Games Top (Should FAIL)
        # Teemo: 30 Games Top (Should PASS but PENALTY)
        
        mock_brain.meta_stats = {
            266: {"TOP": {"games": 100, "wins": 55}}, # Aatrox (55% WR, Verified)
            17:  {"TOP": {"games": 30, "wins": 16}},  # Teemo (53% WR, Some proof)
            350: {"TOP": {"games": 0, "wins": 0}}     # Yuumi (Unknown)
        }
        
        # Mock Predict to return 0.6 (60%) for everyone initially
        mock_brain.predict_batch.return_value = [0.6, 0.6, 0.6] 
        
        candidates = ["Aatrox", "Yuumi", "Teemo"]
        
        # Mock DDragon for ID lookup
        mock_ddragon = MagicMock()
        mock_ddragon.champions = {
            "Aatrox": {"key": "266"},
            "Yuumi": {"key": "350"},
            "Teemo": {"key": "17"}
        }
        
        sd = SmartDraft(mock_meta, mock_profile, mock_comp, mock_learning, mock_brain)
        
        results = sd.batch_rank(candidates, {}, {}, "TOP", mock_ddragon)
        
        # Expectation for "Gold Standard" Hybrid:
        # Aatrox: 100 Games, Solid WR -> High Realist -> High Score.
        # Teemo: 30 Games, Solid WR -> Good Realist -> Good Score (slightly lower than Aatrox due to N).
        # Yuumi: 0 Games -> Realist = 0.40 (Penalty). Dreamer (0.6) drags it up, but Realist drags it down.
        # Score ~ (0.6 * 0.7) + (0.4 * 0.3) = 0.54 (54%)
        
        names = [r['champion'] for r in results]
        
        aatrox = next(r for r in results if r['champion'] == "Aatrox")
        teemo = next(r for r in results if r['champion'] == "Teemo")
        yuumi = next(r for r in results if r['champion'] == "Yuumi")
        
        print(f"Aatrox Score: {aatrox['score']} (N=100)")
        print(f"Teemo Score: {teemo['score']} (N=30)")
        print(f"Yuumi Score: {yuumi['score']} (N=0)")
        
        # 1. Aatrox should still be king (High Data Reliability)
        self.assertGreater(aatrox['score'], yuumi['score'])
        
        # 2. Yuumi should NOT be 0 (Dreamer allows innovation), but significantly lower
        self.assertGreater(yuumi['score'], 0)
        self.assertLess(yuumi['score'], 60.0) # Should be dragged below confident threshold

if __name__ == '__main__':
    unittest.main()

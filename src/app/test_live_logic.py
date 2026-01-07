
import sys
import os
import torch
import unittest
from unittest.mock import MagicMock

# Add src to path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(src_dir)

from src.app.live_engine import parse_lobby
from src.engine.features import FeatureEngine

class MockDD:
    def __init__(self):
        self.champions = {
            "Aatrox": {"key": "266", "id": "Aatrox"},
            "Ahri": {"key": "103", "id": "Ahri"},
            "Zed": {"key": "238", "id": "Zed"}
        }

class TestLiveEngine(unittest.TestCase):
    def setUp(self):
        self.dd = MockDD()
        self.fe = FeatureEngine()
        self.fe.build_vocab(self.dd)
        # Vocab: 103->1, 238->2, 266->3 (sorted keys) or similar.
        # Keys: 103, 238, 266.
        # Vocab: {103: 1, 238: 2, 266: 3}
        
    def test_parse_lobby_actions(self):
        # Mock Session
        # Scenario: 
        # Blue Team (Cell 0-4): Cell 0 (Ahri/103)
        # Red Team (Cell 5-9): Cell 5 (Zed/238)
        # Actions: Cell 5 picks FIRST (Turn 1). Cell 0 picks SECOND (Turn 2).
        
        session = {
            'myTeam': [
                {'cellId': 0, 'championId': 103, 'assignedPosition': 'MIDDLE'},
                {'cellId': 1, 'championId': 0, 'assignedPosition': 'TOP'}
            ],
            'theirTeam': [
                {'cellId': 5, 'championId': 238, 'assignedPosition': 'MIDDLE'}
            ],
            'actions': [
                # Phase 1: Cell 5 (Red) picks
                [{'actorCellId': 5, 'type': 'pick', 'completed': True}],
                # Phase 2: Cell 0 (Blue) picks
                [{'actorCellId': 0, 'type': 'pick', 'completed': True}],
                # Remaining phases (Placeholders for Cells 1-4 (Blue) and 6-9 (Red))
                # Let's say: 1, 6, 2, 7, 3, 8, 4, 9
                [{'actorCellId': 1, 'type': 'pick', 'completed': False}], 
                [{'actorCellId': 6, 'type': 'pick', 'completed': False}],
                [{'actorCellId': 2, 'type': 'pick', 'completed': False}],
                [{'actorCellId': 7, 'type': 'pick', 'completed': False}],
                [{'actorCellId': 3, 'type': 'pick', 'completed': False}],
                [{'actorCellId': 8, 'type': 'pick', 'completed': False}],
                [{'actorCellId': 4, 'type': 'pick', 'completed': False}],
                [{'actorCellId': 9, 'type': 'pick', 'completed': False}]
            ],
            'bans': {}
        }
        
        # Run
        # We expect:
        # P1 (Turn 1) = Cell 5 (Zed/238) -> Token for 238
        # P2 (Turn 2) = Cell 0 (Ahri/103) -> Token for 103
        
        xp, xt, xb, xm, xmeta = parse_lobby(session, self.fe)
        
        print("\n--- Tensor Output ---")
        print(f"Picks: {xp}")
        print(f"Turns: {xt}")
        
        # Verify Shapes
        self.assertEqual(xp.shape, (1, 10))
        self.assertEqual(xt.shape, (1, 10))
        
        # Verify Content
        # Vocab: 103->1 (Ahri), 238->2 (Zed), 266->3 (Aatrox)
        token_ahri = self.fe.vocab[103]
        token_zed = self.fe.vocab[238]
        
        # Picks Vector (Chronological)
        # Slot 0 should be First Pick (Zed)
        self.assertEqual(xp[0, 0].item(), token_zed)
        # Slot 1 should be Second Pick (Ahri)
        self.assertEqual(xp[0, 1].item(), token_ahri)
        
        # Turns Vector (Should be 1..10)
        self.assertEqual(xt[0, 0].item(), 1)
        self.assertEqual(xt[0, 1].item(), 2)

if __name__ == "__main__":
    unittest.main()

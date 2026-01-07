import sys
import os
import unittest
from unittest.mock import MagicMock

# Add src to path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, src_dir)

from src.app.live_engine import get_player_skill

class TestSkillLogic(unittest.TestCase):
    def test_ranked_user(self):
        # Mock LCU
        mock_lcu = MagicMock()
        mock_lcu.get_current_summoner.return_value = {'puuid': '123'}
        mock_lcu.get_ranked_stats.return_value = {
            'queues': [
                {'queueType': 'RANKED_SOLO_5x5', 'tier': 'GOLD', 'division': 'IV'}
            ]
        }
        
        skill = get_player_skill(mock_lcu)
        print(f"Ranked User (Gold IV) -> {skill}")
        self.assertEqual(skill, 4.0)

    def test_unranked_user_explicit(self):
        # Mock LCU returning unranked tier or no queue
        mock_lcu = MagicMock()
        mock_lcu.get_current_summoner.return_value = {'puuid': '123'}
        mock_lcu.get_ranked_stats.return_value = {'queues': []}
        
        skill = get_player_skill(mock_lcu)
        print(f"Unranked User (Empty Queues) -> {skill}")
        self.assertEqual(skill, 3.0)

    def test_api_error(self):
        # Mock LCU raising exception
        mock_lcu = MagicMock()
        mock_lcu.get_current_summoner.side_effect = Exception("LCU Down")
        
        skill = get_player_skill(mock_lcu)
        print(f"API Error -> {skill}")
        self.assertEqual(skill, 3.0)

if __name__ == '__main__':
    unittest.main()

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
from unittest.mock import MagicMock, patch
from src.riot_client import RiotClient

class TestMultiKey(unittest.TestCase):
    
    @patch('src.riot_client.get_riot_api_key')
    @patch('src.riot_client.get_region')
    def test_key_rotation(self, mock_region, mock_get_keys):
        # Mock Config to return 2 keys (Simpler for global limit test)
        mock_get_keys.return_value = ["KEY_1", "KEY_2"]
        mock_region.return_value = "euw1"
        
        client = RiotClient()
        
        # Verify Init
        self.assertEqual(client.api_keys, ["KEY_1", "KEY_2"])
        self.assertEqual(client.session.headers["X-Riot-Token"], "KEY_1")
        
        # Mock Session to fail first 2 times with 429
        mock_response_fail = MagicMock()
        mock_response_fail.status_code = 429
        mock_response_fail.text = "Rate Limit"
        
        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"status": "ok"}
        
        # Scenario: Key 1 -> 429 -> Key 2 -> 429 -> Sleep -> Key 2 -> 200
        # We need to mock time.sleep to avoid waiting
        with patch('time.sleep') as mock_sleep:
             # Logic:
             # 1. Key 1 (Index 0) -> 429. keys_tried = 1. Rotate to Key 2 (Index 1).
             # 2. Key 2 (Index 1) -> 429. keys_tried = 2. 2 >= 2. Wait 30s. Reset keys_tried = 0.
             # 3. Retry Key 2 (Index 1) -> 200.
             
             client.session.get = MagicMock(side_effect=[
                mock_response_fail, # Key 1 fail
                mock_response_fail, # Key 2 fail (Global Limit Hit)
                mock_response_success # Key 2 success after sleep
             ])
             
             result = client._request("/test_global_limit")
             
             self.assertIsNotNone(result)
             self.assertEqual(result['status'], "ok")
             
             # Verify Sleep was called
             mock_sleep.assert_called_with(30)
             
    @patch('src.riot_client.get_riot_api_key')
    @patch('src.riot_client.get_region')
    def test_invalid_key_rotation(self, mock_region, mock_get_keys):
        # Mock Config to return 2 keys
        mock_get_keys.return_value = ["INVALID_KEY", "VALID_KEY"]
        mock_region.return_value = "euw1"
        
        client = RiotClient()
        
        # Mock Session: Key 1 -> 401, Key 2 -> 200
        mock_response_401 = MagicMock()
        mock_response_401.status_code = 401
        
        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.json.return_value = {"status": "ok"}
        
        client.session.get = MagicMock(side_effect=[mock_response_401, mock_response_200])
        
        url = "/test_auth"
        result = client._request(url)
        
        self.assertIsNotNone(result)
        self.assertEqual(client.current_key_index, 1)
        self.assertEqual(client.session.headers["X-Riot-Token"], "VALID_KEY")

if __name__ == '__main__':
    unittest.main()

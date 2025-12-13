import unittest
import os
import sqlite3
import shutil
from src.engine.persistence import BrainDatabase

class TestPersistence(unittest.TestCase):
    def setUp(self):
        # Use a temp DB for testing
        self.test_db = "test_brain.db"
        if os.path.exists(self.test_db):
            os.remove(self.test_db)
        # Also remove WAL files if any
        if os.path.exists(self.test_db + "-wal"): os.remove(self.test_db + "-wal")
        if os.path.exists(self.test_db + "-shm"): os.remove(self.test_db + "-shm")
            
        self.db = BrainDatabase(db_path=self.test_db)
        
    def tearDown(self):
        # We can't easily delete the DB file while the process is running on Windows sometimes locally due to locks
        # But we try.
        del self.db 
        # Wait a bit or ignore errors
        try:
            if os.path.exists(self.test_db):
                os.remove(self.test_db)
            if os.path.exists(self.test_db + "-wal"): os.remove(self.test_db + "-wal")
            if os.path.exists(self.test_db + "-shm"): os.remove(self.test_db + "-shm")
        except: pass

    def test_wal_mode_enabled(self):
        """Verify that Write-Ahead Logging is active."""
        conn = sqlite3.connect(self.test_db)
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode;")
        mode = cursor.fetchone()[0]
        conn.close()
        self.assertEqual(mode.lower(), "wal")

    def test_save_and_retrieve_match(self):
        """Test strict schema saving and retrieval."""
        match_data = {
            "metadata": {"matchId": "EUW1_123456"},
            "info": {
                "gameMode": "CLASSIC",
                "queueId": 420,
                "gameCreation": 1600000000000,
                "participants": [
                    # Team 100
                    {"puuid": "p1", "championId": 1, "teamId": 100, "teamPosition": "TOP", "win": True},
                    {"puuid": "p2", "championId": 2, "teamId": 100, "teamPosition": "JUNGLE", "win": True},
                    {"puuid": "p3", "championId": 3, "teamId": 100, "teamPosition": "MIDDLE", "win": True},
                    {"puuid": "p4", "championId": 4, "teamId": 100, "teamPosition": "BOTTOM", "win": True},
                    {"puuid": "p5", "championId": 5, "teamId": 100, "teamPosition": "UTILITY", "win": True},
                    # Team 200
                    {"puuid": "p6", "championId": 6, "teamId": 200, "teamPosition": "TOP", "win": False},
                    {"puuid": "p7", "championId": 7, "teamId": 200, "teamPosition": "JUNGLE", "win": False},
                    {"puuid": "p8", "championId": 8, "teamId": 200, "teamPosition": "MIDDLE", "win": False},
                    {"puuid": "p9", "championId": 9, "teamId": 200, "teamPosition": "BOTTOM", "win": False},
                    {"puuid": "p10", "championId": 10, "teamId": 200, "teamPosition": "UTILITY", "win": False},
                ]
            }
        }
        
        # 1. Save
        success = self.db.save_match(match_data)
        self.assertTrue(success)
        
        # 2. Duplicate Check
        success_dup = self.db.save_match(match_data)
        self.assertFalse(success_dup) # Should fail/return False
        
        # 3. Check Count
        self.assertEqual(self.db.get_processed_count(), 1)
        
        # 4. Check Training Data Format
        data = self.db.get_training_data()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['win'], 1)
        self.assertEqual(data[0]['blue']['TOP'], 1)
        self.assertEqual(data[0]['red']['TOP'], 6)

    def test_meta_stats_aggregation(self):
        """Test that meta stats update incrementally."""
        # Match 1: Garen (Top) Wins
        m1 = {
            "metadata": {"matchId": "M1"},
            "info": {
                "participants": [
                    {"puuid": "p1", "championId": 86, "teamId": 100, "teamPosition": "TOP", "win": True}
                ]
            }
        }
        self.db.save_match(m1)
        
        stats = self.db.get_meta_stats()
        self.assertEqual(stats[86]['TOP']['games'], 1)
        self.assertEqual(stats[86]['TOP']['wins'], 1)
        
        # Match 2: Garen (Top) Loses
        m2 = {
            "metadata": {"matchId": "M2"},
            "info": {
                "participants": [
                    {"puuid": "p1", "championId": 86, "teamId": 100, "teamPosition": "TOP", "win": False}
                ]
            }
        }
        self.db.save_match(m2)
        
        stats = self.db.get_meta_stats()
        self.assertEqual(stats[86]['TOP']['games'], 2)
        self.assertEqual(stats[86]['TOP']['wins'], 1)

if __name__ == '__main__':
    unittest.main()

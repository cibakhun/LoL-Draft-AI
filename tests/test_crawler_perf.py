import time
import json
import os
from unittest.mock import MagicMock
from datetime import datetime, timedelta
from src.crawler import MetaCrawler
from src.riot_client import RiotClient

# Mock Data
MOCK_PLAYERS = [{"summonerId": f"sum_{i}", "summonerName": f"Player_{i}"} for i in range(10)]

def mock_get_match_details(match_id):
    time.sleep(0.01) 
    return {
        "info": {
            "gameMode": "CLASSIC",
            "queueId": 420,
            "participants": [
                {"championName": "Aatrox", "win": True, "participantId": 1},
                {"championName": "Ahri", "win": False, "participantId": 2},
            ]
        }
    }

def run_perf_test():
    print("=== STARTING CRAWLER PERF & CACHE TEST ===")
    
    # Setup
    engine = MagicMock()
    engine.champion_stats = {}
    
    # Ensure dirs exist for test
    if not os.path.exists("src/data/matches"):
        os.makedirs("src/data/matches")
        
    crawler = MetaCrawler(engine)
    crawler.player_cache_file = "test_player_cache.json" # Use test file
    crawler.player_cache = {}
    
    # Mock Client
    crawler.client = MagicMock()
    crawler.client.get_challenger_league.return_value = {"entries": MOCK_PLAYERS}
    crawler.client.get_summoner_by_id.side_effect = lambda sid: {"puuid": f"puuid_{sid}"}
    crawler.client.get_matchlist.return_value = [f"EUW1_{i}" for i in range(100, 110)] 
    crawler.client.get_match_details.side_effect = mock_get_match_details
    mock_timeline = {
        "info": {
            "frames": [
                {
                    "events": [
                        {"type": "SKILL_LEVEL_UP", "participantId": 1, "skillSlot": 1}, # Q
                        {"type": "ITEM_PURCHASED", "participantId": 1, "itemId": 1056, "timestamp": 1000} # D. Ring
                    ]
                }
            ]
        }
    }
    crawler.client.get_match_timeline.return_value = mock_timeline
    
    # Override sleep
    time.sleep = lambda x: None 
    
    # TEST 1: Performance (Parallelism)
    print("\n[TEST 1] Performance...")
    new_matches = set()
    for i in range(20): 
        new_matches.add(f"EUW1_{i}")
        
    start_time = time.perf_counter()
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(crawler._analyze_match, mid) for mid in new_matches]
        concurrent.futures.wait(futures)
    end_time = time.perf_counter()
    duration = end_time - start_time
    print(f"Processed {len(new_matches)} matches in {duration:.4f}s")
    
    if duration < 1.0: print("[PASS] Speed OK.")
    else: print("[WARN] Speed might be slow.")

    # Verify Timeline Analysis
    print("[TEST] Verifying Timeline Analysis...")
    if "Aatrox" in crawler.meta_engine.champion_stats:
        stats = crawler.meta_engine.champion_stats["Aatrox"]
        if "skill_orders" in stats and stats["skill_orders"]:
             print(f"[PASS] Timeline data extracted for Aatrox: {stats['skill_orders'][0]}")
        else:
             print(f"[FAIL] 'skill_orders' missing or empty for Aatrox. Stats keys: {stats.keys()}")
    else:
        print("[FAIL] Aatrox not found in stats.")

    # TEST 2: Caching Logic
    print("\n[TEST 2] Player Caching...")
    puuid = "test_puuid_123"
    
    # Case A: New Player -> Should Scan
    if crawler._should_scan_player(puuid):
        print(f"[PASS] New player {puuid} marked for scan.")
    else:
        print(f"[FAIL] New player {puuid} skipped incorrectly.")
        
    # Case B: Recently Scanned -> Should Skip
    crawler.player_cache[puuid] = datetime.now().isoformat()
    if not crawler._should_scan_player(puuid):
        print(f"[PASS] Recently scanned player {puuid} skipped.")
    else:
        print(f"[FAIL] Recently scanned player {puuid} NOT skipped.")
        
    # Case C: Old Scan -> Should Scan
    crawler.player_cache[puuid] = (datetime.now() - timedelta(hours=7)).isoformat()
    if crawler._should_scan_player(puuid):
        print(f"[PASS] Old scanned player {puuid} marked for rescan.")
    else:
        print(f"[FAIL] Old scanned player {puuid} skipped incorrectly.")

    # Clean up
    if os.path.exists("test_player_cache.json"):
        os.remove("test_player_cache.json")

if __name__ == "__main__":
    run_perf_test()

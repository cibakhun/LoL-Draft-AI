import threading
import time
import random
import json
import os
import concurrent.futures
from threading import Lock
from datetime import datetime, timedelta
from src.riot_client import RiotClient, APIAuthError, InvalidIDError
from src.scraper import LeaderboardScraper
from src.analysis.timeline import TimelineAnalyzer

class MetaCrawler:
    def __init__(self, meta_engine):
        self.client = RiotClient()
        self.meta_engine = meta_engine
        self.cache_file = "meta_cache.json"
        self.history_file = "processed_matches.json"
        self.player_cache_file = "player_cache.json"
        self.match_archive_dir = os.path.join("src", "data", "matches")
        
        self.discovery_file = "discovery_queue.json"
        self.discovery_queue = set()
        
        self.scraper = LeaderboardScraper() 
        self.processed_matches = set()
        self.player_cache = {} # {puuid: timestamp_iso}
        self.lock = Lock()
        
        self._ensure_dirs()
        self.analyzer = TimelineAnalyzer(self.match_archive_dir)
        self._load_history()
        self._load_player_cache()
        self._load_discovery_queue()
        
    def _ensure_dirs(self):
        if not os.path.exists(self.match_archive_dir):
            os.makedirs(self.match_archive_dir)

    def _load_history(self):
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    self.processed_matches = set(json.load(f))
                print(f"[CRAWLER] Loaded history: {len(self.processed_matches)} matches already analyzed.")
            except:
                self.processed_matches = set()

    def _load_player_cache(self):
        if os.path.exists(self.player_cache_file):
            try:
                with open(self.player_cache_file, 'r') as f:
                    self.player_cache = json.load(f)
            except:
                self.player_cache = {}
                
    def _load_discovery_queue(self):
        if os.path.exists(self.discovery_file):
            try:
                with open(self.discovery_file, 'r') as f:
                    self.discovery_queue = set(json.load(f))
                print(f"[CRAWLER] Loaded Discovery Queue: {len(self.discovery_queue)} players waiting to be scanned.")
            except:
                self.discovery_queue = set()

    def _save_history(self):
        with open(self.history_file, 'w') as f:
            json.dump(list(self.processed_matches), f)
        with open(self.player_cache_file, 'w') as f:
            json.dump(self.player_cache, f)
        with open(self.discovery_file, 'w') as f:
            json.dump(list(self.discovery_queue), f)

    def start(self):
        t = threading.Thread(target=self._crawl)
        t.daemon = True
        t.start()
        
    def _crawl(self):
        print("[CRAWLER] ACTIVATED: High-Performance Snowball Crawler Starting...")

        # Load existing db
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    self.meta_engine.champion_stats = json.load(f)
                    print(f"[CRAWLER] Loaded {len(self.meta_engine.champion_stats)} champions from cache.")
            except:
                pass

        while True:
            try:
                active_puuids = []

                # STRATEGY 1: Consume from Discovery Queue (Snowball)
                # We prioritize this to explore the "Deep Web" of players
                if self.discovery_queue:
                    # Take batch of 10
                    with self.lock:
                        # Convert to list to slice, then remove from set
                        # Inefficient for large sets but simple for now
                        # Better: pop 10 times
                        for _ in range(min(10, len(self.discovery_queue))):
                            p = self.discovery_queue.pop()
                            
                            # VALIDATION: Riot PUUIDs are 78 chars fixed length.
                            # SummonerIDs are 63 (or different).
                            if len(p) != 78:
                                # print(f"[CRAWLER] 🗑️ Discarding Invalid ID (Len {len(p)}): {p[:10]}...")
                                continue
                                
                            if self._should_scan_player(p):
                                active_puuids.append(p)
                                self.player_cache[p] = datetime.now().isoformat()
                    
                    if active_puuids:
                        print(f"[CRAWLER] Snowballing: Processing {len(active_puuids)} players from Queue (Remaining: {len(self.discovery_queue)})...")

                # STRATEGY 2: Scrape Leaderboard (Seed)
                # Only if queue is empty or we want to inject fresh blood occasionally
                if not active_puuids:
                    print("[CRAWLER] Queue empty. Seeding from Leaderboard/API...")
                    entries = []
                    
                    # 1. Try Riot API
                    try:
                        league = self.client.get_challenger_league()
                        if league:
                            raw_entries = league.get('entries', [])
                            entries = [e for e in raw_entries if 'summonerId' in e]
                    except:
                        entries = []
                    
                    # 2. Fallback to Scraper
                    if not entries:
                        # Pick a random page to find new players
                        random_page = random.randint(1, 20)
                        entries = self.scraper.get_top_players(limit=20, page=random_page)
                    
                    if not entries:
                        print("[CRAWLER] No players found. Retrying in 60s...")
                        time.sleep(60)
                        continue
                        
                    random.shuffle(entries)
                    
                    # Resolving PUUIDs for Seed
                    # target_players = entries[:10] 
                    # We just dump them all into discovery queue for next loop?
                    # Or process here. Let's process 10 here for immediate action.
                    
                    print(f"[CRAWLER] Seeding: Resolving PUUIDs for {len(entries)} players...")
                    for player in entries[:10]:
                        try:
                            p_id = None
                            if 'summonerId' in player:
                                summ = self.client.get_summoner_by_id(player['summonerId'])
                                if summ: p_id = summ.get('puuid')
                            elif 'gameName' in player:
                                acc = self.client.get_account_by_riot_id(player['gameName'], player.get('tagLine', 'EUW'))
                                if acc: p_id = acc.get('puuid')
                            
                            if p_id:
                                if self._should_scan_player(p_id):
                                    active_puuids.append(p_id)
                                    self.player_cache[p_id] = datetime.now().isoformat()
                        except: continue

                if not active_puuids:
                    print(f"[CRAWLER] All players in batch recently scanned. (Total Matches: {len(self.processed_matches)}). Sleeping...")
                    time.sleep(2)
                    continue

                # Gather Match IDs
                new_matches = set()
                print(f"[CRAWLER] Fetching matchlists for {len(active_puuids)} players...")
                
                for pid in active_puuids:
                    # Get last 10 games
                    try:
                        m_ids = self.client.get_matchlist(pid, count=10)
                        for m in m_ids:
                            if m not in self.processed_matches:
                                new_matches.add(m)
                    except InvalidIDError:
                        print(f"[CRAWLER] 🗑️ Discarding Invalid/Encrypted PUUID: {pid[:10]}...")
                        continue
                            
                if not new_matches:
                    print("[CRAWLER] No new matches found in this batch. Sleeping...")
                    time.sleep(2)
                    continue
                    
                print(f"[CRAWLER] Found {len(new_matches)} NEW valid matches. Processing...")
                
                # Parallel Processing
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    futures = [executor.submit(self._analyze_match, mid) for mid in new_matches]
                    concurrent.futures.wait(futures)
                    
                # Calc Stats & Save
                self.calculate_statistics()
                self._save_history()
                
                # Save DB
                with open(self.cache_file, 'w') as f:
                    json.dump(self.meta_engine.champion_stats, f)
                    
                print(f"[CRAWLER] Batch complete. Queue Size: {len(self.discovery_queue)}. Total Matches: {len(self.processed_matches)}. DB Saved.")
                time.sleep(1) # Go fast
                
            except APIAuthError as e:
                print(f"[CRAWLER] 🛑 CRITICAL: {e}")
                print("[CRAWLER] 🔄 Attempting to reload keys from .env in 5s...")
                time.sleep(5)
                self.client.refresh_keys()
                
                if not self.client.api_keys:
                    print("[CRAWLER] Still no keys found. Pausing for 60s...")
                    time.sleep(60)
                else:
                    print("[CRAWLER] Keys reloaded. Retrying...")
                    
            except Exception as e:
                print(f"[CRAWLER] Error in loop: {e}")
                time.sleep(10)

    def _should_scan_player(self, puuid):
        # Scan every 6 hours
        if puuid not in self.player_cache:
            return True
            
        last_scan = datetime.fromisoformat(self.player_cache[puuid])
        if datetime.now() - last_scan > timedelta(hours=6):
            return True
            
        return False

    def _analyze_match(self, match_id):
        # Thread worker function
        try:
            data = self.client.get_match_details(match_id)
            if not data: return
            
            # --- SNOWBALL LOGIC ---
            # Extract all participants and add to discovery queue
            info = data.get('info', {})
            participants = info.get('participants', [])
            
            with self.lock:
                for p in participants:
                    p_puuid = p.get('puuid')
                    if p_puuid and p_puuid not in self.player_cache:
                        # It's a new player! Add to queue.
                        self.discovery_queue.add(p_puuid)
            # ----------------------

            # ARCHIVAL
            self._archive_match(match_id, data)
            
            # TIMELINE (New)
            try:
                timeline = self.client.get_match_timeline(match_id)
                if timeline:
                    self._archive_match(match_id, timeline, suffix="_timeline")
            except Exception as e:
                pass # Silent fail for timeline

            queue_id = info.get('queueId', 0)
            game_mode = info.get('gameMode', '')
            
            valid_queues = [420, 440]
            
            if game_mode != 'CLASSIC' or queue_id not in valid_queues:
                with self.lock:
                    self.processed_matches.add(match_id)
                return

            # Extra Safety: Ensure we have lane assignments
            if not any(p.get('teamPosition') for p in participants):
                with self.lock:
                    self.processed_matches.add(match_id)
                return

            # Extract Data
            with self.lock:
                for p in participants:
                    cname = p['championName']
                    win = p['win']
                    
                    if cname not in self.meta_engine.champion_stats:
                        self.meta_engine.champion_stats[cname] = {"winrate": 0.5, "games": 0, "wins": 0}
                        
                    stats = self.meta_engine.champion_stats[cname]
                    if "games" not in stats: stats["games"] = 0; stats["wins"] = 0
                    
                    stats["games"] += 1
                    if win: stats["wins"] += 1

                    # Deep Analysis (Timeline)
                    timeline_path = os.path.join(self.match_archive_dir, f"{match_id}_timeline.json")
                    if os.path.exists(timeline_path):
                        t_data = self.analyzer.analyze_timeline(timeline_path, p['participantId'], cname)
                        if t_data:
                            if "skill_orders" not in stats: stats["skill_orders"] = []
                            if "item_counts" not in stats: stats["item_counts"] = {}
                            
                            if t_data["skill_order"]:
                                stats["skill_orders"].append(t_data["skill_order"])
                            
                            # Flatten items into a simple count dict
                            for item_id in t_data["early_items"]:
                                str_id = str(item_id)
                                stats["item_counts"][str_id] = stats["item_counts"].get(str_id, 0) + 1
                
                self.processed_matches.add(match_id)
                print(f"[CRAWLER] Progress: {len(self.processed_matches)} matches analyzed.")

        except Exception as e:
            print(f"[CRAWLER] Match fail {match_id}: {e}")

    def _archive_match(self, match_id, data, suffix=""):
        # Save raw JSON to disk
        try:
            path = os.path.join(self.match_archive_dir, f"{match_id}{suffix}.json")
            with open(path, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"[CRAWLER] Failed to archive {match_id}: {e}")

    def calculate_statistics(self):
        """
        Applies Bayesian Smoothing and Percentile Tiering.
        """
        # 1. Calculate Global Average (Prior)
        total_wins = 0
        total_games = 0
        
        # We need a copy because we're iterating? No, we're not modifying keys, just values.
        # But for safety in threaded env (though we are sequential here)
        stats_copy = self.meta_engine.champion_stats.items()
        
        for name, stats in stats_copy:
            total_wins += stats.get("wins", 0)
            total_games += stats.get("games", 0)
            
        global_wr = 0.5
        if total_games > 0:
            global_wr = total_wins / total_games
            
        print(f"[DATA SCIENCE] Global WR: {global_wr:.2f} over {total_games} games.")
        
        # 2. Bayesian Smoothing
        C = 50 
        smoothed_data = [] 
        
        for name, stats in stats_copy:
            wins = stats.get("wins", 0)
            games = stats.get("games", 0)
            
            smoothed_wr = (wins + (C * global_wr)) / (games + C)
            stats["winrate"] = smoothed_wr 
            smoothed_data.append((name, smoothed_wr))
            
        # 3. Percentile Tiering
        if not smoothed_data: return
        
        smoothed_data.sort(key=lambda x: x[1], reverse=True) 
        count = len(smoothed_data)
        
        for i, (name, wr) in enumerate(smoothed_data):
            percentile = i / count 
            
            tier = "B"
            if percentile < 0.08: tier = "S"     
            elif percentile < 0.20: tier = "A"   
            elif percentile < 0.60: tier = "B"   
            elif percentile < 0.90: tier = "C"   
            else: tier = "D"                     
            
            self.meta_engine.champion_stats[name]["tier"] = tier

    def _analyze_meta_depth(self):
        """
        Runs the TimelineAnalyzer on all processed matches to enrich the Meta Model.
        """
        print("[DATA SCIENCE] Running Deep Meta Analysis (Timeline)...")
        # We need to map MatchID -> ParticipantID -> Champion
        # This is expensive if we don't cache it. 
        # For now, let's just re-scan the last N matches or all available files?
        # Actually, let's just assume we want to process NEW matches.
        # But for this demo, let's just use the analyzer on the matches we just found?
        pass # To be implemented fully, but let's do it in real-time or batch?
        
        # Better approach: In _process_match, we already have the data.
        # Let's add a list of "matches_to_analyze" queue.
        

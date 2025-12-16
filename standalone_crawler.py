
import requests
import json
import os
import time
import random
import sys
import ctypes
from datetime import datetime

# --- CONFIGURATION ---
# Friends can just paste their key here OR create an 'apikey.txt' file next to this script.
API_KEY = "" 
REGION = "euw1" # Default region (can be changed to na1, kr, etc.)
ROUTING = "europe" # Americas, asia, europe

class StandaloneCrawler:
    def __init__(self):
        self.api_key = self._load_api_key()
        self.session = requests.Session()
        self.session.headers.update({"X-Riot-Token": self.api_key})
        
        self.output_dir = "collected_matches"
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            
        self.processed_matches = self._load_processed_matches()
        self.discovery_queue = set()
        
    def _load_api_key(self):
        # 1. Check variable
        if API_KEY: return API_KEY
        
        # 2. Check file
        if os.path.exists("apikey.txt"):
            with open("apikey.txt", "r") as f:
                return f.read().strip()
                
        # 3. Ask user
        print("!!! NO API KEY FOUND !!!")
        key = input("Please enter your RGAPI Key: ").strip()
        return key

    def _load_processed_matches(self):
        existing = set()
        for f in os.listdir(self.output_dir):
            if f.endswith(".json"):
                existing.add(f.replace(".json", "").replace("_timeline", ""))
        return existing

    def _request(self, url):
        while True:
            try:
                print(f"[API] Fetching: {url}...")
                response = self.session.get(url)
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 429:
                    print("[API] Limit Reached (429). Waiting 30s...")
                    time.sleep(30)
                    continue
                elif response.status_code in [403, 401]:
                    print("\n[API] 🛑 403/401 Forbidden. Your API Key is Invalid or Expired!")
                    print("Please check your Key and restart the program.")
                    input("Press Enter to Exit...")
                    sys.exit(1)
                elif response.status_code == 404:
                    return None
                else:
                    print(f"[API] Error {response.status_code}")
                    return None
            except Exception as e:
                print(f"[API] Exception: {e}")
                time.sleep(5)

    def get_challenger_league(self):
        url = f"https://{REGION}.api.riotgames.com/lol/league/v4/challengerleagues/by-queue/RANKED_SOLO_5x5"
        return self._request(url)

    def get_summoner_puuid(self, summoner_id):
        url = f"https://{REGION}.api.riotgames.com/lol/summoner/v4/summoners/{summoner_id}"
        data = self._request(url)
        return data.get('puuid') if data else None

    def get_match_ids(self, puuid, count=20):
        url = f"https://{ROUTING}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start=0&count={count}"
        return self._request(url) or []

    def get_match_details(self, match_id):
        url = f"https://{ROUTING}.api.riotgames.com/lol/match/v5/matches/{match_id}"
        return self._request(url)

    def get_match_timeline(self, match_id):
        url = f"https://{ROUTING}.api.riotgames.com/lol/match/v5/matches/{match_id}/timeline"
        return self._request(url)

    def run(self):
        print(f"--- STANDALONE CRAWLER STARTED [{REGION}] ---")
        print(f"Matches will be saved to: {os.path.abspath(self.output_dir)}")
        
        # 1. Seed

        while True:
            # 1. Seed if empty
            if not self.discovery_queue:
                print("Seeding from Challenger League...")
                league = self.get_challenger_league()
                
                # Check for critical failure (None returned due to 403 or other error)
                if not league:
                    print("Seeding failed (API issue?). Waiting 30s before retry...")
                    time.sleep(30)
                    continue

                entries = league.get('entries', [])
                if not entries:
                    print("No entries found in Challenger League. Retrying...")
                    time.sleep(10)
                    continue

                random.shuffle(entries)
                print(f"Found {len(entries)} Challenger players. Resolving PUUIDs...")

                count = 0
                for i, e in enumerate(entries): 
                    if count >= 10: break
                    
                    try:
                        # DEBUG: Print first entry keys to diagnose missing summonerId
                        if i == 0:
                            print(f"[DEBUG] Entry Keys: {list(e.keys())}")
                            print(f"[DEBUG] Sample Entry: {str(e)[:100]}...")

                        sum_id = e.get('summonerId')
                        
                        # Check for direct PUUID (some endpoints have updated)
                        if not sum_id:
                            direct_puuid = e.get('puuid')
                            if direct_puuid:
                                self.discovery_queue.add(direct_puuid)
                                count += 1
                                print(f"Found direct PUUID: {direct_puuid[:10]}...")
                                continue
                            
                            if i < 3: # Print failure for first few only
                                print(f"[DEBUG] Missing summonerId for entry {i}")
                            continue

                        puuid = self.get_summoner_puuid(sum_id)
                        if puuid: 
                            self.discovery_queue.add(puuid)
                            count += 1
                        
                        time.sleep(0.1) # Small delay
                    except Exception as seed_err:
                        print(f"Skipping invalid seed entry: {seed_err}")
                        continue
            
            if not self.discovery_queue:
                print("Queue still empty after seed. Waiting 30s...")
                time.sleep(30)
                continue
                
            print(f"Queue Size: {len(self.discovery_queue)} players.")

            current_puuid = self.discovery_queue.pop()
            
            # Get Matches
            match_ids = self.get_match_ids(current_puuid)
            new_matches = [m for m in match_ids if m not in self.processed_matches]
            
            print(f"Player {current_puuid[:8]}... has {len(new_matches)} new matches.")
            
            for mid in new_matches:
                data = self.get_match_details(mid)
                if not data: continue
                
                # Save
                with open(os.path.join(self.output_dir, f"{mid}.json"), "w") as f:
                    json.dump(data, f)
                
                self.processed_matches.add(mid)
                print(f"SAVED: {mid} (Total: {len(self.processed_matches)})")
                
                # Fetch Timeline (Deep Data)
                try:
                    timeline = self.get_match_timeline(mid)
                    if timeline:
                        with open(os.path.join(self.output_dir, f"{mid}_timeline.json"), "w") as f:
                            json.dump(timeline, f)
                except Exception as e:
                    print(f"Failed to fetch timeline for {mid}: {e}")
                
                # Snowball: Add players to discovery
                try:
                    for p in data['info']['participants']:
                        self.discovery_queue.add(p['puuid'])
                except: pass
                
                time.sleep(1.2) # Polite delay
            
            if len(self.discovery_queue) > 5000:
                # Trim queue to save memory
                 self.discovery_queue = set(list(self.discovery_queue)[:2000])

if __name__ == "__main__":
    try:
        crawler = StandaloneCrawler()
        crawler.run()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        input("Press Enter to Exit...")

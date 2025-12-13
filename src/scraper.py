import requests
from bs4 import BeautifulSoup
import random
import time

class LeaderboardScraper:
    def __init__(self, region="euw"):
        self.region = region
        # LeagueOfGraphs is easier to scrape than OP.GG (less anti-bot)
        self.base_url = f"https://www.leagueofgraphs.com/rankings/summoners/{self.region}"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def get_top_players(self, limit=50, page=1):
        # LeagueOfGraphs pagination: /rankings/summoners/euw?page=2
        url = self.base_url if page == 1 else f"{self.base_url}?page={page}"
        print(f"[SCRAPER] Fetching Leaderboard (Page {page}) from {url}...")
        players = []
        try:
            r = requests.get(url, headers=self.headers, timeout=10)
            if r.status_code != 200:
                print(f"[SCRAPER] Failed to fetch leaderboard: {r.status_code}")
                return []

            soup = BeautifulSoup(r.text, 'html.parser')
            # Look for the main table
            table = soup.find('table', {'class': 'data_table'})
            if not table:
                print("[SCRAPER] Could not find data table.")
                return []

            rows = table.find_all('tr')
            for row in rows:
                # Name is usually in a span with class 'name'
                name_span = row.find('span', {'class': 'name'})
                if name_span:
                    raw_name = name_span.text.strip()
                    # LeagueOfGraphs format: "Name #Tag" (sometimes) or just "Name"
                    # We need to split
                    if "#" in raw_name:
                        name, tag = raw_name.split("#", 1)
                        players.append({"gameName": name.strip(), "tagLine": tag.strip()})
                    else:
                        # Guess Tag based on region? EUW -> #EUW usually works as default
                        players.append({"gameName": raw_name, "tagLine": self.region.upper()})
            
            # Shuffle to avoid analyzing same top 10 forever
            random.shuffle(players)
            print(f"[SCRAPER] Found {len(players)} players.")
            return players[:limit]

        except Exception as e:
            print(f"[SCRAPER] Exception: {e}")
            return []

if __name__ == "__main__":
    s = LeaderboardScraper()
    print(s.get_top_players(5))

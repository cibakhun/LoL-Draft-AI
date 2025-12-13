from src.riot_client import RiotClient

class ProfileEngine:
    def __init__(self, id_map=None):
        self.summoner_name = None
        self.client = RiotClient()
        self.user_pool = {} # Starts empty, fills via API
        self.id_map = id_map or {}
        
    def update_id_map(self, new_map):
        self.id_map = new_map
        
    def update_data(self, puuid):
        print(f"[PROFILE] Fetching Mastery for PUUID: {puuid[:10]}...")
        data = self.client.get_champion_mastery(puuid)
        
        for entry in data:
            cid = entry['championId']
            cname = self.id_map.get(cid, str(cid)) # Use DDragon Map
            
            self.user_pool[cname] = {
                "mastery": entry['championPoints'],
                "recent_winrate": 0.55, 
                "games_played": entry['championLevel'] * 10 
            }
        print(f"[PROFILE] Loaded {len(self.user_pool)} champions.")
        
    def get_profile_score(self, champion_name):
        """
        Calculates a score based on Mastery, Comfort, and recent performance.
        Returns 0 if mastery is too low (No-Go rule).
        """
        stats = self.user_pool.get(champion_name)
        if not stats:
            return 0 # User doesn't play this champ -> Score 0 (Rule: No first time picks)
            
        # Thresholds
        if stats["mastery"] < 10000:
            return 0
            
        # Calculation
        # Base on Winrate (0-100 scale)
        score = stats["recent_winrate"] * 100
        
        # Mastery Bonus (Logarithmic-ish via tiers)
        if stats["mastery"] > 100000:
            score += 15
        elif stats["mastery"] > 50000:
            score += 10
        elif stats["mastery"] > 20000:
            score += 5
            
        return min(100, score)

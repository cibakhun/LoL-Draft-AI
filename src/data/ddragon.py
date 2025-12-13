import requests

class DataDragon:
    def __init__(self):
        self.version = self._get_latest_version()
        self.champions = self._get_champions()
        
    def _get_latest_version(self):
        try:
            r = requests.get("https://ddragon.leagueoflegends.com/api/versions.json")
            if r.status_code == 200:
                return r.json()[0]
        except:
            pass
        return "14.1.1" # Fallback
        
    def _get_champions(self):
        print(f"[DDRAGON] Fetching Champion Data (v{self.version})...")
        url = f"https://ddragon.leagueoflegends.com/cdn/{self.version}/data/en_US/champion.json"
        try:
            r = requests.get(url)
            if r.status_code == 200:
                data = r.json()['data']
                # Process into a lighter format: Name -> {tags: [], id: key}
                processed = {}
                for name, info in data.items():
                    processed[name] = {
                        "key": int(info['key']),
                        "name": info['name'],
                        "roles": info['tags'], # e.g. ["Mage", "Assassin"]
                        "title": info['title'],
                        "stats": info['stats'], # Capture Base Stats for Matchup Engine
                        "info": info['info'] # Capture Attack/Defense/Magic for AI Features
                    }
                print(f"[DDRAGON] Loaded {len(processed)} champions.")
                return processed
        except Exception as e:
            print(f"[DDRAGON] Error: {e}")
        return {}

    def get_id_map(self):
        """Returns Dict {ID: Name}"""
        if not hasattr(self, 'id_map'):
            self.id_map = {int(info['key']): name for name, info in self.champions.items()}
        return self.id_map
        
    def get_champions_by_role(self, role_filter):
        """
        Naive Role Filter based on Tags.
        Roles: Fighter, Tank, Mage, Assassin, Support, Marksman
        """
        # Mapping LCU Positions to Tags is tricky.
        # TOP -> Fighter, Tank
        # JUNGLE -> Fighter, Assassin, Tank
        # MIDDLE -> Mage, Assassin
        # BOTTOM -> Marksman
        # UTILITY -> Support, Mage
        
        valid_tags = []
        if role_filter == "TOP": valid_tags = ["Fighter", "Tank"]
        elif role_filter == "JUNGLE": valid_tags = ["Fighter", "Assassin", "Tank"]
        elif role_filter == "MIDDLE": valid_tags = ["Mage", "Assassin"]
        elif role_filter == "BOTTOM": valid_tags = ["Marksman"]
        elif role_filter == "UTILITY": valid_tags = ["Support", "Tank", "Mage"]
        else: return list(self.champions.keys()) # Return all
        
        results = []
        for name, info in self.champions.items():
            if any(tag in valid_tags for tag in info['roles']):
                results.append(name)
        return results

if __name__ == "__main__":
    dd = DataDragon()
    print("Ahri ID:", dd.champions['Ahri']['key'])

import requests

class DataDragon:
    def __init__(self):
        self.version = self._get_latest_version()
        self.champions = self._get_champions()
        self.items = self._get_items()
        self.runes = self._get_runes()
        
    def _get_latest_version(self):
        try:
            r = requests.get("https://ddragon.leagueoflegends.com/api/versions.json")
            if r.status_code == 200:
                return r.json()[0]
        except Exception as e:
            print(f"[DDRAGON] Version Fetch Error: {e}")
            pass
        return "14.23.1" # Fallback to TitanNet Training Version
        
    def _get_champions(self):
        # Cache Path
        cache_dir = "src/data/cache_dd"
        import os
        import json
        
        if not os.path.exists(cache_dir): os.makedirs(cache_dir, exist_ok=True)
        cache_file = os.path.join(cache_dir, f"champions_{self.version}.json")
        
        # Try Load Cache
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    print(f"[DDRAGON] Loading from cache: {cache_file}")
                    return json.load(f)
            except: pass
            
        print(f"[DDRAGON] Fetching Champion Data (v{self.version})...")
        url = f"https://ddragon.leagueoflegends.com/cdn/{self.version}/data/en_US/champion.json"
        
        try:
            r = requests.get(url, timeout=10) # Added Timeout
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
                        "stats": info['stats'], 
                        "info": info['info'] 
                    }
                
                # Save Cache
                try:
                    with open(cache_file, 'w', encoding='utf-8') as f:
                        json.dump(processed, f)
                except Exception as e: print(f"[DDRAGON] Cache Save Error: {e}")
                
                print(f"[DDRAGON] Loaded {len(processed)} champions. (Network)")
                return processed
            else:
                 print(f"[DDRAGON] Fetch Failed: {r.status_code}")
                 
        except Exception as e:
            print(f"[DDRAGON] Network Error: {e}")
            
        # Fallback: Try loading ANY cache if specific version failed?
        return {}
    def _get_items(self):
        print(f"[DDRAGON] Fetching Item Data...")
        url = f"https://ddragon.leagueoflegends.com/cdn/{self.version}/data/en_US/item.json"
        try:
            r = requests.get(url)
            if r.status_code == 200:
                data = r.json()['data']
                # Key = ID (String)
                return data
        except Exception as e:
            print(f"[DDRAGON] Item Fetch Error: {e}")
        return {}

    def _get_runes(self):
        print(f"[DDRAGON] Fetching Rune Data...")
        url = f"https://ddragon.leagueoflegends.com/cdn/{self.version}/data/en_US/runesReforged.json"
        try:
            r = requests.get(url)
            if r.status_code == 200:
                data = r.json()
                # Runes Reforged is a List of Trees
                # We want a Flat Map: ID -> Name
                flat_runes = {}
                for tree in data:
                    flat_runes[tree['id']] = tree['name'] # Tree Name
                    # Slots
                    for slot in tree['slots']:
                        for rune in slot['runes']:
                             flat_runes[rune['id']] = rune['name']
                return flat_runes
        except Exception as e:
            print(f"[DDRAGON] Rune Fetch Error: {e}")
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

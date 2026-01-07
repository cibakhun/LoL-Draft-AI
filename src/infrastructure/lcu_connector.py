import os
import time
import requests
import urllib3
import base64

# Suppress InsecureRequestWarning (Self-signed certs)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class TitanLCU:
    def __init__(self):
        self.connected = False
        self.port = None
        self.password = None
        self.session = requests.Session()
        self.protocol = "https"
        self.base_url = ""
        
        # Initial connect attempt
        self.connect()
        
    def find_lockfile(self):
        """Scans standard install paths for League lockfile."""
        paths = [
            r"C:\Riot Games\League of Legends\lockfile",
            r"D:\Riot Games\League of Legends\lockfile",
            r"E:\Riot Games\League of Legends\lockfile",
            # Fallback for G: since user is on G:
            r"G:\Riot Games\League of Legends\lockfile" 
        ]
        
        for p in paths:
            if os.path.exists(p):
                return p
        return None
        
    def connect(self):
        """Reads lockfile and configures the session."""
        path = self.find_lockfile()
        if not path:
            self.connected = False
            return False
            
        try:
            with open(path, 'r') as f:
                data = f.read()
            
            # Format: 'Process:PID:Port:Password:Protocol'
            parts = data.split(':')
            if len(parts) < 5: 
                return False
            
            self.port = parts[2]
            self.password = parts[3]
            self.protocol = parts[4]
            self.base_url = f"{self.protocol}://127.0.0.1:{self.port}"
            
            # Configure Session
            self.session.auth = ('riot', self.password)
            self.session.verify = False
            self.session.headers.update({
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            })
            
            self.connected = True
            return True
        except Exception as e:
            # print(f"Connection Error: {e}")
            self.connected = False
            return False

    def request(self, method, endpoint, data=None):
        """Generic wrapper for requests."""
        if not self.connected:
            if not self.connect():
                print(f"[LCU Debug] Connect Failed for {method} {endpoint}")
                return None
                
        url = f"{self.base_url}{endpoint}"
        try:
            if method == 'GET':
                r = self.session.get(url, timeout=2.0)
            elif method == 'POST':
                r = self.session.post(url, json=data, timeout=2.0)
            elif method == 'PATCH':
                r = self.session.patch(url, json=data, timeout=2.0)
            elif method == 'PUT':
                r = self.session.put(url, json=data, timeout=2.0)
            else:
                print(f"[LCU Debug] Unknown Method: {method}")
                return None
                
            if r.status_code == 401: # Auth failed/expired
                print(f"[LCU Debug] Auth Failed (401)")
                self.connected = False
                return None
                
            return r
        except requests.RequestException as e:
            print(f"[LCU Debug] Request Exception: {e}")
            self.connected = False
            return None

    def get_current_summoner(self):
        r = self.request('GET', '/lol-summoner/v1/current-summoner')
        if r and r.status_code == 200:
            return r.json()
        return None

    def get_champ_select(self):
        r = self.request('GET', '/lol-champ-select/v1/session')
        if r and r.status_code == 200:
            return r.json()
        return None

    def get_gameflow_phase(self):
        r = self.request('GET', '/lol-gameflow/v1/gameflow-phase')
        if r and r.status_code == 200:
            return r.text.strip('"') # Returns string like "ChampSelect"
        return "None"

    def get_ranked_stats(self, puuid):
        r = self.request('GET', f'/lol-ranked/v1/ranked-stats/{puuid}')
        if r and r.status_code == 200:
            return r.json()
        return None

    def hover_champion(self, action_id, champion_id):
        """
        Interacts with the LCU to hover (declare intent) for a champion.
        Endpoint: PATCH /lol-champ-select/v1/session/actions/{id}
        """
        endpoint = f'/lol-champ-select/v1/session/actions/{action_id}'
        data = {"championId": int(champion_id)}
        r = self.request('PATCH', endpoint, data=data)
        if r and r.status_code in [200, 204]:
            return True
        elif r:
            print(f"[LCU Error] Hover Failed: {r.status_code} - {r.text}")
        return False
        
    def complete_action(self, action_id):
        """Locks in the selection."""
        endpoint = f'/lol-champ-select/v1/session/actions/{action_id}/complete'
        r = self.request('POST', endpoint)
        return r and r.status_code in [200, 204]

    def get_champion_mastery(self, puuid):
        """Fetches all champion mastery entries for the summoner."""
        endpoint = f'/lol-collections/v1/inventories/{puuid}/champion-mastery'
        r = self.request('GET', endpoint)
        if r and r.status_code == 200:
            return r.json()
        return []


if __name__ == "__main__":
    print("--- Titan LCU Connector ---")
    print("Searching for League Client...")
    
    lcu = TitanLCU()
    
    while True:
        try:
            if not lcu.connected:
                path = lcu.find_lockfile()
                if path:
                    print(f"\n[+] Lockfile found at {path}")
                    if lcu.connect():
                        print(f"✅ Connected to LCU on Port {lcu.port}")
                    else:
                        print("[-] Failed to auth with lockfile.")
                else:
                    print(".", end="", flush=True)
                
                if not lcu.connected:
                    time.sleep(2)
                    continue
            
            # Active Loop
            summ = lcu.get_current_summoner()
            phase = lcu.get_gameflow_phase()
            
            name = "Unknown"
            if summ:
                # Support Riot ID (gameName #tagLine)
                if 'gameName' in summ:
                    name = f"{summ['gameName']}#{summ.get('tagLine', '')}"
                else:
                    name = summ.get('displayName', 'NoName')
            else:
                # Debug why it failed - Check last response
                # We can't easily see it here without refactoring request, 
                # but let's just assume it failed.
                name = "Err:Fetch"
            
            print(f"\r👤 ID: {name: <25} | 🌊 Flow: {phase: <15}", end="")
            
            time.sleep(1)
            
        except KeyboardInterrupt:
            print("\nExiting.")
            break

import requests
from src.config import get_riot_api_key, get_region, load_config
import time

class APIAuthError(Exception):
    pass

class RiotClient:
    def __init__(self):
        self.api_keys = get_riot_api_key() # Now returns a LIST
        if not self.api_keys:
            self.api_keys = []
            
        self.current_key_index = 0
        self.region = get_region()
        self.base_url = f"https://{self.region}.api.riotgames.com"
        self.session = requests.Session()
        
        # Init with first key if available
        self._init_session()
        
    def _init_session(self):
        if self.api_keys:
            self.session.headers.update({"X-Riot-Token": self.api_keys[0]})
            masked = self.api_keys[0][:5] + "*" * 5
            print(f"[RIOT] Client Initialized. Region: {self.region} | Active Key: {masked} (Total: {len(self.api_keys)})")
        else:
            print(f"[RIOT] Client Initialized. Region: {self.region} | NO KEYS FOUND!")

    def refresh_keys(self):
        print("[RIOT] 🔄 Reloading Configuration...")
        load_config()
        self.api_keys = get_riot_api_key()
        self.current_key_index = 0
        self._init_session()

    MAX_RETRIES = 2
    
    MAX_RETRIES = 2
    
    def _rotate_key(self, silent=False):
        if len(self.api_keys) <= 1:
            return False
            
        self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
        new_key = self.api_keys[self.current_key_index]
        self.session.headers.update({"X-Riot-Token": new_key})
        
        if not silent:
            masked = new_key[:5] + "*" * 5
            print(f"[RIOT] ⚠️ Switching to Key #{self.current_key_index + 1}: {masked}")
        return True


class InvalidIDError(Exception):
    pass

    def _request(self, endpoint, region_prefix=None):
        """
        Internal helper for requests with error handling and robust multi-key rotation.
        """
        prefix = region_prefix or self.region
        url = f"https://{prefix}.api.riotgames.com{endpoint}"
        
        keys_tried = 0
        total_keys = len(self.api_keys)
        
        while True:
            try:
                r = self.session.get(url)
                
                if r.status_code == 200:
                    return r.json()
                    
                elif r.status_code == 429:
                    keys_tried += 1
                    # If we tried all keys and they are all 429, we MUST wait.
                    if keys_tried >= total_keys:
                        print(f"[API] 🛑 All {total_keys} keys Rate Limited. Sleeping 30s...")
                        time.sleep(30)
                        keys_tried = 0 # Reset counter to try cycle again
                        continue
                    
                    # Otherwise, rotate and try next
                    if self._rotate_key(silent=True):
                        time.sleep(0.5) 
                        continue
                    else:
                        print(f"[API] ⏳ Rate Limit (429). Waiting 10s...")
                        time.sleep(10)
                        continue
                
                elif r.status_code in [403, 401]:
                    print(f"[API] ❌ Key #{self.current_key_index + 1} Invalid/Types (403/401). Rotating...")
                    if self._rotate_key():
                         keys_tried += 1 
                         if keys_tried >= total_keys:
                             print("[API] ☠️ All keys failed auth. Aborting.")
                             raise APIAuthError("All API keys are invalid or expired.")
                         continue
                    else:
                        print("[API] All keys failed or only one key present.")
                        raise APIAuthError("API Key Invalid or Expired.")

                elif r.status_code == 400:
                    try:
                        err_msg = r.json().get('status', {}).get('message', '')
                        if "decrypting" in err_msg:
                            raise InvalidIDError(f"Invalid/Encrypted ID: {err_msg}")
                    except InvalidIDError:
                        raise
                    except:
                        pass # Valid 400 error?

                # Other errors
                print(f"[API] Error {r.status_code} for {endpoint} | Msg: {r.text}")
                return None

            except (APIAuthError, InvalidIDError):
                raise
            except Exception as e:
                print(f"[API] Exception: {e}")
                return None

    def get_champion_mastery(self, puuid):
        return self._request(f"/lol/champion-mastery/v4/champion-masteries/by-puuid/{puuid}") or []

    def get_summoner_by_id(self, summoner_id):
        """Resolves SummonerID to PUUID."""
        return self._request(f"/lol/summoner/v4/summoners/{summoner_id}")

    def get_account_by_riot_id(self, game_name, tag_line):
        """Resolves GameName#Tag to PUUID (Regional)."""
        routing = "europe" # Simplified for MVP
        return self._request(f"/riot/account/v1/accounts/by-riot-id/{game_name}/{tag_line}", region_prefix=routing)

    def get_challenger_league(self, queue="RANKED_SOLO_5x5"):
        """Get Challenger Players."""
        return self._request(f"/lol/league/v4/challengerleagues/by-queue/{queue}")

    def get_matchlist(self, puuid, start=0, count=10):
        """Get Recent Match IDs. Uses 'europe' routing for EUW."""
        # Note: MatchV5 uses "Regional" routing (americas, europe, asia)
        # We need a mapper. For 'euw1', it's 'europe'.
        routing = "europe" # simplified for MVP
        return self._request(f"/lol/match/v5/matches/by-puuid/{puuid}/ids?start={start}&count={count}", region_prefix=routing) or []

    def get_match_details(self, match_id):
        routing = "europe"
        return self._request(f"/lol/match/v5/matches/{match_id}", region_prefix=routing)

    def get_match_timeline(self, match_id):
        """Get Match Timeline (Position, Events, Build Order)."""
        routing = "europe"
        return self._request(f"/lol/match/v5/matches/{match_id}/timeline", region_prefix=routing)

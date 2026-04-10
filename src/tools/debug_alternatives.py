
import sys
import os
import json
sys.path.append(os.path.join(os.getcwd(), 'src'))
from infrastructure.lcu_connector import TitanLCU
import time

def check_alternatives():
    lcu = TitanLCU()
    lcu.connect()
    
    print("--- CHECKING LOL-CHAT-V1-ME ---")
    try:
        r = lcu.request('GET', '/lol-chat/v1/me')
        if r and r.status_code == 200:
            data = r.json()
            print(f"Name: {data.get('name')}")
            print(f"StatusMsg: {data.get('statusMessage')}")
            print(f"LOL Dictionary: {data.get('lol', {})}")
            print(f"RankedLeagueQueue: {data.get('lol', {}).get('rankedLeagueQueue')}")
            print(f"RankedLeagueTier: {data.get('lol', {}).get('rankedLeagueTier')}")
            print(f"RankedLeagueDivision: {data.get('lol', {}).get('rankedLeagueDivision')}")
        else:
            print("Failed.")
    except Exception as e: print(e)

    print("\n--- CHECKING LOL-LEAGUE-SESSION ---")
    try:
        r = lcu.request('GET', '/lol-league-session/v1/league-session-token')
        if r:
             print(f"Session Token Exists: {r.status_code}")
    except: pass
    
    print("\n--- CHECKING LOL-HOVERCARD ---")
    try:
        summ = lcu.get_current_summoner()
        if summ:
             puuid = summ['puuid']
             r = lcu.request('GET', f'/lol-hovercard/v1/hovercard/{puuid}')
             if r:
                  print(json.dumps(r.json(), indent=2))
    except: pass

if __name__ == "__main__":
    check_alternatives()

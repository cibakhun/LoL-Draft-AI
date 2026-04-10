
import sys
import os
import json
sys.path.append(os.path.join(os.getcwd(), 'src'))
from infrastructure.lcu_connector import TitanLCU
import time

def dump_all():
    print("Connecting...")
    lcu = TitanLCU()
    tries = 0
    while not lcu.connected and tries < 5:
        lcu.connect()
        time.sleep(1)
        tries += 1
        
    if not lcu.connected:
        print("FAILED TO CONNECT")
        return

    summ = lcu.get_current_summoner()
    if not summ:
        print("NO SUMMONER")
        return
        
    puuid = summ['puuid']
    print(f"PUUID: {puuid}")
    
    # 1. Current Stats
    try:
        r = lcu.request('GET', '/lol-ranked/v1/current-ranked-stats')
        if r:
            with open('dump_current.json', 'w') as f:
                json.dump(r.json(), f, indent=2)
            print("Dumped dump_current.json")
    except Exception as e: print(f"Err Current: {e}")

    # 2. Hovercard
    try:
        r = lcu.request('GET', f'/lol-hovercard/v1/hovercard/{puuid}')
        if r:
            with open('dump_hover.json', 'w') as f:
                json.dump(r.json(), f, indent=2)
            print("Dumped dump_hover.json")
    except Exception as e: print(f"Err Hover: {e}")

    # 3. Ranked Stats
    try:
        r = lcu.request('GET', f'/lol-ranked/v1/ranked-stats/{puuid}')
        if r:
            with open('dump_stats.json', 'w') as f:
                json.dump(r.json(), f, indent=2)
            print("Dumped dump_stats.json")
    except Exception as e: print(f"Err Stats: {e}")

if __name__ == "__main__":
    dump_all()

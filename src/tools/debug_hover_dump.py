
import sys
import os
import json
sys.path.append(os.path.join(os.getcwd(), 'src'))
from infrastructure.lcu_connector import TitanLCU
import time

def dump_hover_json():
    lcu = TitanLCU()
    if not lcu.connect(): return

    summ = lcu.get_current_summoner()
    if not summ: return
    
    puuid = summ['puuid']
    
    try:
        r = lcu.request('GET', f'/lol-hovercard/v1/hovercard/{puuid}')
        if r and r.status_code == 200:
            data = r.json()
            with open('hover_data.json', 'w') as f:
                json.dump(data, f, indent=2)
            print("Dumped hover_data.json")
    except Exception as e:
        print(e)
        
if __name__ == "__main__":
    dump_hover_json()

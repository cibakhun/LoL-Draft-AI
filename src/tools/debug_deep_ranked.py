
import sys
import os
import json
sys.path.append(os.path.join(os.getcwd(), 'src'))
from infrastructure.lcu_connector import TitanLCU
import time

def debug_deep_ranked():
    lcu = TitanLCU()
    if not lcu.connect():
        print("Failed to connect.")
        return

    summ = lcu.get_current_summoner()
    if not summ:
        print("No summoner.")
        return

    print(f"Summoner: {summ.get('displayName')} | PUUID: {summ.get('puuid')}")
    
    stats = lcu.get_ranked_stats(summ['puuid'])
    
    print(f"Splits Progress: {list(stats.get('splitsProgress', {}).keys())}")
    
    if stats and 'queues' in stats:
        print(f"\nFound {len(stats['queues'])} queue entries.")
        for i, q in enumerate(stats['queues']):
            qt = q.get('queueType')
            tier = q.get('tier')
            rank = q.get('rank')
            lp = q.get('leaguePoints')
            wins = q.get('wins')
            print(f"[{i}] {qt} -> {tier} {rank} ({lp} LP) | Wins: {wins}")
            
            # Print full dump if it looks like Gold
            if tier == "GOLD":
                print("!!! FOUND GOLD ENTRY !!!")
                print(json.dumps(q, indent=2))
    else:
        print("No queues found.")

if __name__ == "__main__":
    debug_deep_ranked()

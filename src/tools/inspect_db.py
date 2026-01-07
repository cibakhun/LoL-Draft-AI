import sqlite3
import zlib
import json
import os

DB_PATH = os.path.join("src", "engine", "brain_v2.db")

def inspect():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    print("--- Match Data ---")
    c.execute("SELECT match_id, json_data FROM matches_raw LIMIT 1")
    row = c.fetchone()
    if row:
        mid, blob = row
        data = json.loads(zlib.decompress(blob).decode('utf-8'))
        print(f"Match ID: {mid}")
        print("Keys:", list(data.keys()))
        if 'info' in data:
            print("Info Keys:", list(data['info'].keys()))
            parts = data['info'].get('participants', [])
            if parts:
                print("Participant 0 Keys:", list(parts[0].keys()))
                print("Participant 0 PickTurn:", parts[0].get('pickTurn'))
            
            teams = data['info'].get('teams', [])
    print(f"Team 0 Bans: {teams[0].get('bans')}")
            
    print("\n--- Timeline Data ---")
    c.execute("SELECT match_id, json_data FROM timelines_raw LIMIT 1")
    row = c.fetchone()
    if row:
        mid, blob = row
        data = json.loads(zlib.decompress(blob).decode('utf-8'))
        print(f"Timeline ID: {mid}")
        info = data.get('info', {})
        frames = info.get('frames', [])
        
        event_types = set()
        for f in frames:
            for e in f.get('events', []):
                event_types.add(e.get('type'))
                if "CHAMP" in e.get('type', "") or "PICK" in e.get('type', "") or "SWAP" in e.get('type', ""):
                    print(f"Interesting Event: {e}")
                    
        print(f"Unique Event Types in Timeline: {event_types}")

if __name__ == "__main__":
    inspect()

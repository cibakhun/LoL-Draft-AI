
import sqlite3
import json
import os
import zlib
from collections import Counter
from typing import List, Dict, Tuple

DB_PATH = "src/engine/brain_v2.db"
OUTPUT_PATH = "data/item_metrics.json"

def get_db_connection() -> sqlite3.Connection:
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Database not found at {DB_PATH}")
    return sqlite3.connect(DB_PATH)

def extract_match_data(conn: sqlite3.Connection):
    """
    Extracts relevant data from all matches by parsing the JSON blob.
    Returns a list of participant dictionaries.
    """
    print("Extracting match data from JSON blobs... (this make take a moment)")
    cursor = conn.cursor()
    cursor.execute("SELECT json_data FROM matches_raw")
    
    rows = cursor.fetchall()
    all_participants = []
    
    for row in rows:
        try:
            json_blob = row[0]
            json_str = None
            
            # Decompression / Decoding Logic
            if isinstance(json_blob, bytes):
                try:
                    # Try simple decode first
                    json_str = json_blob.decode('utf-8')
                except UnicodeDecodeError:
                    # Try zlib
                    try:
                        decompressed = zlib.decompress(json_blob)
                        json_str = decompressed.decode('utf-8')
                    except Exception:
                         continue # Failed both
            else:
                json_str = json_blob
            
            if not json_str:
                continue

            match_data = json.loads(json_str)
            
            # Navigate to participants
            # Structure usually: data -> info -> participants OR just info -> participants
            # Adapting to common Riot API structures
            if 'info' in match_data:
                participants = match_data['info']['participants']
            elif 'participants' in match_data:
                participants = match_data['participants']
            else:
                continue # Unknown structure
                
            for p in participants:
                p_data = {
                    'championId': p.get('championId'),
                    'win': p.get('win'),
                    'items': [
                        p.get('item0', 0),
                        p.get('item1', 0),
                        p.get('item2', 0),
                        p.get('item3', 0),
                        p.get('item4', 0),
                        p.get('item5', 0)
                    ]
                }
                all_participants.append(p_data)
                
        except Exception as e:
            # Skip malformed rows
            continue
            
    print(f"Extracted data for {len(all_participants)} participants.")
    return all_participants

def calculate_metrics(participants: List[Dict]) -> Dict:
    """
    Calculates Step A (Winrates) and Step B (Core Builds).
    """
    print("Calculating metrics...")
    
    # Storage
    champ_stats = {} # {id: {wins: 0, total: 0, winning_items: []}}
    
    for p in participants:
        cid = p['championId']
        win = p['win']
        items = p['items']
        
        if cid not in champ_stats:
            champ_stats[cid] = {'wins': 0, 'total': 0, 'winning_items': []}
            
        champ_stats[cid]['total'] += 1
        if win:
            champ_stats[cid]['wins'] += 1
            # Add non-zero items
            valid_items = [i for i in items if i != 0]
            champ_stats[cid]['winning_items'].extend(valid_items)
            
    # Format output
    output = {}
    
    for cid, stats in champ_stats.items():
        total = stats['total']
        wins = stats['wins']
        winrate = round(wins / total, 3) if total > 0 else 0.0
        
        # Core Items (Top 6 Unique)
        item_counts = Counter(stats['winning_items'])
        most_common = item_counts.most_common()
        core_items = [item_id for item_id, count in most_common[:6]]
        
        output[str(cid)] = {
            "winrate": winrate,
            "core_items": core_items
        }
        
    return output

def main():
    try:
        conn = get_db_connection()
        
        # Single pass extraction
        participants = extract_match_data(conn)
        
        conn.close()
        
        # Calculate
        metrics = calculate_metrics(participants)
        
        # Save
        with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
            json.dump(metrics, f, indent=4)
            
        print(f"Successfully saved item metrics for {len(metrics)} champions to {OUTPUT_PATH}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

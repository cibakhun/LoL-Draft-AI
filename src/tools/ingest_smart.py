import sqlite3
import json
import os
import zlib
import glob
import sys
from collections import defaultdict

# --- CONFIG ---
DB_PATH = os.path.join("src", "engine", "brain_v2.db")
SOURCE_DIR = os.path.join("src", "data", "matches")

# Human Queues: Draft Pick, Ranked Solo, Blind Pick, Ranked Flex, Quickplay, Clash
VALID_QUEUES = {400, 420, 430, 440, 490, 700}
MIN_DURATION = 600 # 10 Minutes

def setup_db():
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
            print(f"Removed existing {DB_PATH}")
        except:
            print(f"Warning: Could not remove {DB_PATH}")
            
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Text ID, Blob Data
    c.execute("""
    CREATE TABLE IF NOT EXISTS matches_raw (
        match_id TEXT PRIMARY KEY,
        json_data BLOB
    )
    """)
    
    c.execute("""
    CREATE TABLE IF NOT EXISTS timelines_raw (
        match_id TEXT PRIMARY KEY,
        json_data BLOB
    )
    """)
    
    conn.commit()
    conn.close()
    print(f"Database created: {DB_PATH}")

def is_valid_match(data):
    """
    Quality Gate.
    Returns: (bool, reason)
    """
    info = data.get('info')
    if not info:
        return False, "No Info"
        
    # 1. Queue Check
    q = info.get('queueId')
    if q not in VALID_QUEUES:
        return False, f"Bad Queue ({q})"
        
    # 2. Duration Check
    dur = info.get('gameDuration', 0)
    if dur < MIN_DURATION:
        return False, f"Short Game ({dur}s)"
        
    # 3. Data Depth (Runes)
    parts = info.get('participants', [])
    if not parts:
        return False, "No Participants"
    
    p1 = parts[0]
    # Check Perks/Runes
    if 'perks' not in p1 and 'runes' not in p1:
         return False, "No Runes/Perks"
         
    return True, "OK"

def compress_data(data_dict):
    """
    JSON -> String -> Bytes -> Zlib
    """
    json_str = json.dumps(data_dict)
    return zlib.compress(json_str.encode('utf-8'))

def safe_load_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        return None

def run_ingestion():
    setup_db()
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    stats = defaultdict(int)
    valid_ids = set()
    
    print(f"Scanning {SOURCE_DIR}...")
    
    # --- PASS 1: MATCHES ---
    match_files = glob.glob(os.path.join(SOURCE_DIR, "EUW1_*.json"))
    # Filter out timelines
    match_files = [f for f in match_files if not f.endswith("_timeline.json")]
    
    print(f"Found {len(match_files)} potential match files.")
    
    batch = []
    BATCH_SIZE = 1000
    
    for i, fpath in enumerate(match_files):
        stats['processed'] += 1
        
        data = safe_load_json(fpath)
        if not data:
            stats['error_read'] += 1
            print(f"\rError reading {fpath}", end="")
            continue
            
        is_val, reason = is_valid_match(data)
        
        if is_val:
            mid = data['metadata']['matchId']
            valid_ids.add(mid)
            stats['accepted'] += 1
            
            blob = compress_data(data)
            batch.append((mid, blob))
            
            if len(batch) >= BATCH_SIZE:
                c.executemany("INSERT OR REPLACE INTO matches_raw (match_id, json_data) VALUES (?, ?)", batch)
                conn.commit()
                batch = []
                print(f"\rMatches: {stats['processed']}/{len(match_files)} | Acc: {stats['accepted']}", end="")
        else:
            stats[f'reject_{reason.split()[0]}'] += 1 # 'Bad', 'Short', 'No'
            
    # Flush remaining
    if batch:
        c.executemany("INSERT OR REPLACE INTO matches_raw (match_id, json_data) VALUES (?, ?)", batch)
        conn.commit()
        
    print(f"\nPass 1 Complete. Accepted: {len(valid_ids)}")
    
    # --- PASS 2: TIMELINES ---
    print("Starting Pass 2: Timelines...")
    timeline_files = glob.glob(os.path.join(SOURCE_DIR, "*_timeline.json"))
    
    t_processed = 0
    t_accepted = 0
    t_batch = []
    
    for fpath in timeline_files:
        t_processed += 1
        fname = os.path.basename(fpath)
        # Extract ID: EUW1_12345_timeline.json -> EUW1_12345
        mid = fname.replace("_timeline.json", "")
        
        if mid in valid_ids:
            data = safe_load_json(fpath)
            if data:
                t_accepted += 1
                
                blob = compress_data(data)
                t_batch.append((mid, blob))
                
                if len(t_batch) >= BATCH_SIZE:
                    c.executemany("INSERT OR REPLACE INTO timelines_raw (match_id, json_data) VALUES (?, ?)", t_batch)
                    conn.commit()
                    t_batch = []
                    print(f"\rTimelines: {t_processed}/{len(timeline_files)} | Acc: {t_accepted}", end="")
        else:
            stats['reject_orphan_timeline'] += 1
            
    if t_batch:
        c.executemany("INSERT OR REPLACE INTO timelines_raw (match_id, json_data) VALUES (?, ?)", t_batch)
        conn.commit()
        
    print("\n" + "="*40)
    print("INGESTION REPORT")
    print("="*40)
    print(f"Matches Processed: {stats['processed']}")
    print(f"Matches Accepted:  {stats['accepted']}")
    print(f"Matches Rejected:  {stats['processed'] - stats['accepted']}")
    print("  Rejection Reasons:")
    for k, v in stats.items():
        if k.startswith('reject_') and not 'orphan' in k:
            print(f"  - {k}: {v}")
            
    print("-" * 20)
    print(f"Timelines Scanned: {t_processed}")
    print(f"Timelines Linked:  {t_accepted}")
    print(f"Timelines Orphaned: {stats['reject_orphan_timeline']}")
    print("="*40)
    
    conn.close()

if __name__ == "__main__":
    run_ingestion()

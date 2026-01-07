import os
import sqlite3
import json
import zlib
import glob
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

# --- CONFIG ---
RAW_DATA_DIR = r"g:\Projects\Lol Ai Coach - profiling & meta\src\data\matches"
DB_PATH = r"src/engine/brain_v2.db"
MIN_DURATION = 900 # 15 Minutes
MIN_CS_PER_MIN = 5.0
VALID_QUEUES = {400, 420, 440, 700}

# --- DB INIT ---
def init_db():
    if os.path.exists(DB_PATH):
        try:
            os.remove(DB_PATH)
            print(f"[DB] Deleted existing {DB_PATH}")
        except Exception as e:
            print(f"[DB] Error removing DB: {e}")
            
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS matches_raw (
            match_id TEXT PRIMARY KEY,
            queue_id INTEGER,
            game_duration INTEGER,
            game_version TEXT,
            json_data BLOB
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS timelines_raw (
            match_id TEXT PRIMARY KEY,
            json_data BLOB,
            FOREIGN KEY(match_id) REFERENCES matches_raw(match_id)
        )
    """)
    conn.commit()
    return conn

# --- WORKER FUNCTION ---
def process_pair(args):
    """
    Reads Match & Timeline JSON.
    Validates rules.
    Returns: (MatchId, MatchBlob, TimelineBlob, Status)
    """
    match_path, timeline_path = args
    
    try:
        # 1. Read Match
        with open(match_path, 'r', encoding='utf-8') as f:
            match_data = json.load(f)
            
        info = match_data.get('info', {})
        
        # 2. Basic Filters
        if info.get('queueId') not in VALID_QUEUES:
            return (None, None, None, 'REJECT_QUEUE')
            
        duration = info.get('gameDuration', 0)
        if duration < MIN_DURATION:
             return (None, None, None, 'REJECT_DURATION')
             
        # 3. Quality Filter (CS Score)
        total_cs = 0
        participants = info.get('participants', [])
        for p in participants:
            total_cs += p.get('totalMinionsKilled', 0) + p.get('neutralMinionsKilled', 0)
            
        if len(participants) == 0: return (None, None, None, 'REJECT_EMPTY')

        avg_cs_game = total_cs / len(participants) # Avg CS per player
        game_min = duration / 60.0
        cs_per_min = avg_cs_game / game_min
        
        if cs_per_min < MIN_CS_PER_MIN:
            return (None, None, None, f'REJECT_QUALITY_{cs_per_min:.2f}')
            
        # 4. Read Timeline (Only if Match Passed)
        if not os.path.exists(timeline_path):
             return (None, None, None, 'REJECT_ORPHAN_TL')
             
        with open(timeline_path, 'r', encoding='utf-8') as f:
            timeline_data = json.load(f)
            
        # 5. Compress
        m_blob = zlib.compress(json.dumps(match_data).encode('utf-8'))
        t_blob = zlib.compress(json.dumps(timeline_data).encode('utf-8'))
        match_id = match_data['metadata']['matchId']
        
        return (match_id, info.get('queueId'), duration, info.get('gameVersion'), m_blob, t_blob, 'ACCEPT')

    except Exception as e:
        return (None, None, None, f'ERROR_{str(e)}')

def main():
    print(f"--- DIAMOND REFINERY (Rebuild DB) ---")
    print(f"Source: {RAW_DATA_DIR}")
    print(f"Target: {DB_PATH}")
    print(f"Filter: Queue in {VALID_QUEUES}, Duration > {MIN_DURATION}s, CS/m >= {MIN_CS_PER_MIN}")
    
    # 1. Scan Files
    print("[1] Scanning Files...")
    all_files = glob.glob(os.path.join(RAW_DATA_DIR, "*.json"))
    print(f"    Found {len(all_files)} files total.")
    
    # Group by Match ID
    # Pattern: {Prefix}_{ID}.json and {Prefix}_{ID}_timeline.json
    pairs = {}
    for f in all_files:
        if 'timeline' in f:
            # EUW1_123_timeline.json -> ID: EUW1_123
            base = os.path.basename(f).replace("_timeline.json", "")
            if base not in pairs: pairs[base] = {}
            pairs[base]['timeline'] = f
        else:
            # EUW1_123.json -> ID: EUW1_123
            base = os.path.basename(f).replace(".json", "")
            if base not in pairs: pairs[base] = {}
            pairs[base]['match'] = f
            
    # Filter Complete Pairs
    work_items = []
    for mid, paths in pairs.items():
        if 'match' in paths and 'timeline' in paths:
            work_items.append((paths['match'], paths['timeline']))
            
    print(f"    Identified {len(work_items)} complete match/timeline pairs.")
    
    # 2. Init DB
    conn = init_db()
    cursor = conn.cursor()
    
    # 3. Process
    print("[2] Processing & Filtering...")
    stats = {
        'ACCEPT': 0,
        'REJECT_QUEUE': 0,
        'REJECT_DURATION': 0,
        'REJECT_ORPHAN_TL': 0,
        'REJECT_EMPTY': 0,
        'ERRORS': 0,
        'LOW_QUALITY': 0
    }
    
    # Batch Insert
    batch_m = []
    batch_t = []
    
    t0 = time.time()
    
    # Use ProcessPool
    # Windows requires if __name__ == '__main__': logic which we have.
    # We cannot pass sqlite connection to workers.
    
    with ProcessPoolExecutor(max_workers=6) as executor:
        # submit all
        # Use chunksize for efficiency? map returns generator.
        results = executor.map(process_pair, work_items)
        
        for idx, res in enumerate(results):
            # unpack
            # (match_id, q_id, dur, ver, m_blob, t_blob, status)
            # OR (None, ..., status)
            
            # map returns in order or as completed? executor.map preserves order.
            
            # Handle unpacked size variation?
            # Returns fixed 7 tuple or 4 tuple?
            # My worker returns (None, None, None, Status) = 4 items
            # Success returns 7 items.
            # Fix worker signature to always return 7 items ? 
            # Or just check len.
            
            status_code = res[-1] # Last item is ALWAYS status
            
            if status_code == 'ACCEPT':
                mid, qid, dur, ver, mb, tb, _ = res
                stats['ACCEPT'] += 1
                
                batch_m.append((mid, qid, dur, ver, mb))
                batch_t.append((mid, tb))
                
                if len(batch_m) >= 1000:
                    cursor.executemany("INSERT OR IGNORE INTO matches_raw VALUES (?,?,?,?,?)", batch_m)
                    cursor.executemany("INSERT OR IGNORE INTO timelines_raw VALUES (?,?)", batch_t)
                    conn.commit()
                    batch_m = []
                    batch_t = []
                    print(f"    Saved {stats['ACCEPT']} matches...", end='\r')
            
            elif status_code.startswith('REJECT_QUALITY'):
                 stats['LOW_QUALITY'] += 1
            elif status_code.startswith('ERROR'):
                 stats['ERRORS'] += 1
            else:
                 if status_code in stats: stats[status_code] += 1
                 else: stats[status_code] = stats.get(status_code, 0) + 1
                 
    # Final Commit
    if batch_m:
        cursor.executemany("INSERT OR IGNORE INTO matches_raw VALUES (?,?,?,?,?)", batch_m)
        cursor.executemany("INSERT OR IGNORE INTO timelines_raw VALUES (?,?)", batch_t)
        conn.commit()
    
    t1 = time.time()
    
    print("\n[3] Report")
    print(f"    Total Pairs Checked: {len(work_items)}")
    print(f"    Accepted: {stats['ACCEPT']}")
    print(f"    Rejected (Queue): {stats['REJECT_QUEUE']}")
    print(f"    Rejected (Short): {stats['REJECT_DURATION']}")
    print(f"    Rejected (Low Skill): {stats['LOW_QUALITY']}")
    print(f"    Time Elapsed: {t1-t0:.2f}s")
    
    conn.close()
    
if __name__ == "__main__":
    main()

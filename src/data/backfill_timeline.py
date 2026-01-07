
import os
import json
import sqlite3
import glob

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, '../../brain.db')
MATCHES_DIR = os.path.join(BASE_DIR, 'matches')

def backfill():
    if not os.path.exists(DB_PATH):
        print(f"[Error] Database not found at {DB_PATH}")
        return

    print(f"[Backfill] Connecting to database at {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Ensure Columns Exist
    try:
        c.execute("ALTER TABLE participants ADD COLUMN gold_at_15 INTEGER DEFAULT 0")
        print("[Schema] Added gold_at_15 column.")
    except sqlite3.OperationalError:
        pass # Already exists

    try:
        c.execute("ALTER TABLE participants ADD COLUMN xp_at_15 INTEGER DEFAULT 0")
        print("[Schema] Added xp_at_15 column.")
    except sqlite3.OperationalError:
        pass # Already exists
        
    conn.commit()

    # Find all timeline files
    timeline_files = glob.glob(os.path.join(MATCHES_DIR, "*_timeline.json"))
    print(f"[Backfill] Found {len(timeline_files)} timeline files.")

    count = 0
    updated_matches = 0
    
    for tl_file in timeline_files:
        # 1. Parse Match ID
        # Format: EUW1_1234567890_timeline.json
        base_name = os.path.basename(tl_file)
        match_id = base_name.replace('_timeline.json', '')
        
        # 2. Check if Match JSON exists (needed for mapping)
        match_file = os.path.join(MATCHES_DIR, f"{match_id}.json")
        if not os.path.exists(match_file):
            print(f"[Skip] Match {match_id}: No detailed match JSON found.")
            continue
            
        # 3. Load Match Data for Mapping (Participant ID -> Champion ID)
        try:
            with open(match_file, 'r', encoding='utf-8') as f:
                match_data = json.load(f)
        except Exception as e:
            print(f"[Error] Match {match_id}: Failed to load match JSON: {e}")
            continue
            
        part_map = {} # participantId (int) -> championId (int)
        
        try:
            if 'info' in match_data and 'participants' in match_data['info']:
                for p in match_data['info']['participants']:
                    pid = p['participantId']
                    cid = p['championId']
                    part_map[pid] = cid
            else:
                 print(f"[Skip] Match {match_id}: Invalid match JSON structure.")
                 continue
        except Exception as e:
             print(f"[Error] Match {match_id}: Error parsing match participants: {e}")
             continue

        # 4. Load Timeline Data
        try:
            with open(tl_file, 'r', encoding='utf-8') as f:
                tl_data = json.load(f)
        except Exception as e:
            print(f"[Error] Match {match_id}: Failed to load timeline JSON: {e}")
            continue

        # 5. Extract Stats at 15m
        TARGET_MS = 15 * 60 * 1000 # 900,000 ms
        frames = tl_data.get('info', {}).get('frames', [])
        
        if not frames:
            print(f"[Skip] Match {match_id}: No frames found in timeline.")
            continue
            
        # Find closest frame
        target_frame = None
        min_diff = float('inf')
        
        for frame in frames:
            ts = frame.get('timestamp', 0)
            diff = abs(ts - TARGET_MS)
            if diff < min_diff:
                min_diff = diff
                target_frame = frame
                
        if not target_frame:
            # Should technically not happen if frames exist
            continue
            
        # 6. Update Database
        # target_frame['participantFrames'] is a dict with keys "1", "2"...
        p_frames = target_frame.get('participantFrames', {})
        
        updates_made = False
        for pid_str, stats in p_frames.items():
            pid = int(pid_str)
            if pid not in part_map:
                continue
                
            cid = part_map[pid]
            gold = stats.get('totalGold', 0)
            xp = stats.get('xp', 0)
            
            # Update
            # WHERE match_id=? AND champion_id=?
            # Note: participants table might identify by (match_id, team_id, role) or match_id + champion_id
            # Assuming match_id + champion_id is unique enough for this table
            
            c.execute("""
                UPDATE participants 
                SET gold_at_15 = ?, xp_at_15 = ?
                WHERE match_id = ? AND champion_id = ?
            """, (gold, xp, match_id, cid))
            
            if c.rowcount > 0:
                updates_made = True
                
        if updates_made:
            updated_matches += 1
            
        count += 1
        if count % 100 == 0:
            conn.commit()
            print(f"[Progress] Processed {count} timelines...")

    conn.commit()
    conn.close()
    print(f"[Done] Processed {count} timelines. Updated records for {updated_matches} matches.")

if __name__ == "__main__":
    backfill()

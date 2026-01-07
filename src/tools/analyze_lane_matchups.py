import sqlite3
import json
import zlib
import os
from collections import defaultdict

DB_PATH = r"src/engine/brain_v2.db"
OUTPUT_PATH = r"data/lane_metrics.json"

def get_role_map(participants):
    # Map Role -> {team: {pid, cid}}
    # Roles: TOP, JUNGLE, MIDDLE, BOTTOM, UTILITY
    # We ignore Jungle.
    
    # Bucket by team then role
    # team 100 vs 200
    
    team_roles = {100: {}, 200: {}}
    
    for p in participants:
         tid = p['teamId']
         lane = p.get('teamPosition', '')
         if not lane: lane = p.get('role', 'UTILITY') 
         
         if lane == 'JUNGLE': continue
         if lane not in ['TOP', 'MIDDLE', 'BOTTOM', 'UTILITY']: continue
         
         # Store if not duplicate
         if lane in team_roles[tid]:
             team_roles[tid][lane] = None # Mark ambiguous
         else:
             team_roles[tid][lane] = {'pid': p['participantId'], 'cid': p['championId']}
             
    # Find Pairs
    pairs = []
    for lane in ['TOP', 'MIDDLE', 'BOTTOM', 'UTILITY']:
        blue = team_roles[100].get(lane)
        red = team_roles[200].get(lane)
        
        # Must be non-None (exists and unique)
        if blue and red and blue['pid'] and red['pid']:
            pairs.append((lane, blue, red))
            
    return pairs

def analyze():
    print(f"--- Lane Dominance Analyzer (GD@15) ---")
    print(f"DB: {DB_PATH}")
    
    if not os.path.exists(DB_PATH):
        print("Error: DB not found.")
        return

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Check count
    try:
        total = c.execute("SELECT COUNT(*) FROM matches_raw").fetchone()[0]
        print(f"Total Matches in DB: {total}")
    except:
        print("Error reading DB.")
        return
        
    print("Streaming Match + Timeline data...")
    # Join matches and timelines
    c.execute("""
        SELECT m.json_data, t.json_data 
        FROM matches_raw m 
        JOIN timelines_raw t ON m.match_id = t.match_id
    """)
    
    metrics = defaultdict(list) # "CID_vs_CID" -> [diffs]
    count = 0
    valid_matches = 0
    
    while True:
        rows = c.fetchmany(1000)
        if not rows: break
        
        for m_blob, t_blob in rows:
            count += 1
            try:
                m_data = json.loads(zlib.decompress(m_blob).decode('utf-8'))
                t_data = json.loads(zlib.decompress(t_blob).decode('utf-8'))
                
                parts = m_data.get('info', {}).get('participants', [])
                if not parts: continue
                
                pairs = get_role_map(parts)
                if not pairs: continue
                
                # Find Frame @ 15 min (900,000 ms)
                frames = t_data.get('info', {}).get('frames', [])
                if not frames: frames = t_data.get('frames', []) # Legacy format support
                if not frames: continue
                
                target_frame = None
                closest_dist = float('inf')
                
                # Logic: Find frame closest to 15m
                for f in frames:
                    t_ms = f['timestamp']
                    dist = abs(t_ms - 900000)
                    if dist < closest_dist:
                        closest_dist = dist
                        target_frame = f
                
                if not target_frame: continue
                
                # Ensure match lasted at least 14 mins (840s)
                if target_frame['timestamp'] < 840000: continue
                
                # Extract Gold
                # Frame structure: participantFrames: {"1": {totalGold: ...}}
                p_frames = target_frame.get('participantFrames', {})
                if not p_frames: continue
                
                valid_matches += 1
                
                for lane, blue, red in pairs:
                    pid_b = str(blue['pid'])
                    cid_b = blue['cid']
                    
                    pid_r = str(red['pid'])
                    cid_r = red['cid']
                    
                    # Handle int/str keys
                    data_b = p_frames.get(pid_b) or p_frames.get(int(pid_b))
                    data_r = p_frames.get(pid_r) or p_frames.get(int(pid_r))
                    
                    if not data_b or not data_r: continue
                    
                    gold_b = data_b.get('totalGold', 0)
                    gold_r = data_r.get('totalGold', 0)
                    
                    diff = gold_b - gold_r
                    
                    # Store
                    metrics[f"{cid_b}_vs_{cid_r}"].append(diff)
                    metrics[f"{cid_r}_vs_{cid_b}"].append(-diff)
                    
            except Exception as e:
                # print(e)
                pass
                
        print(f"\rProcessed: {count} | Valid for 15m: {valid_matches}", end="")
        
    print("\n\nAggregating results...")
    
    final_data = {}
    skipped_low_sample = 0
    
    for k, v in metrics.items():
        if len(v) >= 10:
             avg_diff = sum(v) / len(v)
             final_data[k] = round(avg_diff, 1)
        else:
            skipped_low_sample += 1
            
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, 'w') as f:
        json.dump(final_data, f, indent=2)
        
    print(f"Analysis Complete.")
    print(f"Saved {len(final_data)} matchups to {OUTPUT_PATH}")
    print(f"Skipped {skipped_low_sample} rare matchups (<10 samples).")

if __name__ == "__main__":
    analyze()

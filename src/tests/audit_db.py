import sqlite3
import zlib
import json
import os
import sys
import random

DB_PATH = os.path.join("src", "engine", "brain_v2.db")

def check_integrity():
    if not os.path.exists(DB_PATH):
        print(f"ERROR: {DB_PATH} not found.")
        return

    print(f"Connecting to {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # 1. Count Verification
    print("\n--- 1. COUNT VERIFICATION ---")
    c.execute("SELECT COUNT(*) FROM matches_raw")
    match_count = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM timelines_raw")
    timeline_count = c.fetchone()[0]
    
    print(f"Total Matches: {match_count}")
    print(f"Total Timelines: {timeline_count}")
    
    if match_count == 0:
        print("FAIL: DB IS EMPTY")
        return

    # 2. Null Check
    print("\n--- 2. NULL CHECK ---")
    c.execute("SELECT COUNT(*) FROM matches_raw WHERE json_data IS NULL OR json_data = ''")
    null_matches = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM timelines_raw WHERE json_data IS NULL OR json_data = ''")
    null_timelines = c.fetchone()[0]
    
    if null_matches == 0 and null_timelines == 0:
        print("✅ PASS: No NULL data found.")
    else:
        print(f"❌ FAIL: Found NULLs! Matches: {null_matches}, Timelines: {null_timelines}")

    # 3. Content Sampling
    print("\n--- 3. CONTENT SAMPLING (Taste Test) ---")
    # Get 5 random match IDs
    c.execute("SELECT match_id, json_data FROM matches_raw ORDER BY RANDOM() LIMIT 5")
    samples = c.fetchall()
    
    issues_found = False
    
    for i, (mid, blob) in enumerate(samples):
        print(f"\nSample {i+1}: {mid}")
        try:
            # Decompress
            try:
                json_str = zlib.decompress(blob).decode('utf-8')
            except:
                json_str = blob.decode('utf-8') # maybe not compressed?
                
            data = json.loads(json_str)
            info = data.get('info', {})
            
            # Checks
            dur = info.get('gameDuration', 0)
            queue = info.get('queueId', 0)
            participants = info.get('participants', [])
            
            # Runes Check
            has_runes = False
            if participants:
                p1 = participants[0]
                if 'perks' in p1: # New format
                     if 'styles' in p1['perks']: has_runes = True
                elif 'runes' in p1: # Old format?
                     has_runes = True
            
            print(f"  Duration: {dur}s")
            print(f"  Queue: {queue}")
            print(f"  Runes: {'✅ Found' if has_runes else '❌ MISSING'}")
            
            if dur <= 600: 
                print("  ⚠️ WARNING: SHORT GAME")
                issues_found = True
            if queue == 830: 
                print("  ⚠️ WARNING: BOT GAME")
                issues_found = True
            if not has_runes: issues_found = True
                
        except Exception as e:
            print(f"  ❌ ERROR: Could not parse ({e})")
            issues_found = True

    # 4. Timeline Linking
    print("\n--- 4. TIMELINE LINKING ---")
    # check one ID from matches that SHOULD have a timeline (if any exist)
    # Just take a random one from earlier
    mid_to_check = samples[0][0]
    
    # Does it exist in timelines?
    c.execute("SELECT count(*) FROM timelines_raw WHERE match_id = ?", (mid_to_check,))
    exists = c.fetchone()[0]
    
    if exists:
        print(f"✅ PASS: Match {mid_to_check} has a linked Timeline.")
        # Verify content
        c.execute("SELECT json_data FROM timelines_raw WHERE match_id = ?", (mid_to_check,))
        t_blob = c.fetchone()[0]
        if len(t_blob) > 10:
             print("  - Timeline Data Size: OK")
        else:
             print("  - ⚠️ WARNING: Timeline Data suspiciously small.")
    else:
        print(f"⚠️ NOTE: Match {mid_to_check} does NOT have a timeline (Orphan).")
        print("  (This is expected if some timeline files were missing in source directory)")
        
    print("\n" + "="*30)
    if not issues_found:
        print("INTEGRITY CHECK: ✅ PASS")
    else:
        print("INTEGRITY CHECK: ⚠️ ISSUES DETECTED")
    print("="*30)
    
    conn.close()

if __name__ == "__main__":
    check_integrity()

import sqlite3
import zlib
import json
import sys
import os

# Adjust path to find brain.db
DB_PATHS = [
    "brain.db",
    "src/engine/brain.db",
    "g:/Projects/Lol Ai Coach - profiling & meta/brain.db"
]

def find_db():
    for p in DB_PATHS:
        if os.path.exists(p):
            return p
    return None

def verify_data():
    db_path = find_db()
    if not db_path:
        print("ERROR: brain.db not found!")
        sys.exit(1)
        
    print(f"[VERIFY] Connecting to {db_path}...")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    
    # 1. Check Matches (Metadata)
    print("\n--- CHECKING MATCHES TABLE ---")
    try:
        # Check columns first
        c.execute("PRAGMA table_info(matches)")
        cols = [r[1] for r in c.fetchall()]
        print(f"Columns: {cols}")
        
        # Fetch one row
        # Often metadata is split. We might look for 'json_data' or similar if raw blob is stored.
        # Based on datasets.py, there is no direct raw blob usage from 'matches' table, likely just metadata.
        # But User asks "If our database only stored simplified summaries".
        # Let's see if there is a blob column.
        if 'json_data' in cols:
            c.execute("SELECT json_data FROM matches LIMIT 1")
            row = c.fetchone()
            if row:
                print("Found 'json_data' column. analyzing...")
                # Decode if needed? usually text.
                try:
                    data = json.loads(row[0])
                    print("Keys in match JSON:", list(data.keys())[:10])
                except:
                    print("Could not parse match JSON.")
        else:
            print("No 'json_data' column in matches table. Likely normalized.")
            
    except Exception as e:
        print(f"Error checking matches: {e}")

    # 2. Check Match Frames (Timeline)
    print("\n--- CHECKING TIMELINE (match_frames) ---")
    verdict = "PARTIAL SCHEMA"
    details = []
    
    try:
        c.execute("SELECT match_id, frame_data FROM match_frames LIMIT 1")
        row = c.fetchone()
        
        if not row:
            print("Table match_frames is empty!")
            sys.exit(1)
            
        mid, blob = row
        print(f"Analyzing Timeline for Match {mid}...")
        
        # Decode
        try:
            decompressed = zlib.decompress(blob).decode('utf-8')
        except:
            decompressed = blob # Plain text?
            if isinstance(decompressed, bytes): decompressed = decompressed.decode('utf-8')
            
        data = json.loads(decompressed)
        
        # Normalize structure
        frames = []
        if isinstance(data, list): frames = data
        elif isinstance(data, dict):
            if 'info' in data: frames = data['info'].get('frames', [])
            elif 'frames' in data: frames = data['frames']
            
        print(f"Frame Count: {len(frames)}")
        if not frames:
            print("No frames found in blob.")
        else:
            first_frame = frames[0]
            last_frame = frames[-1]
            
            # --- CHECK 1: SKILL ORDER ---
            has_skills = False
            skill_ex = None
            # Scan events
            for f in frames:
                for e in f.get('events', []):
                    if e.get('type') == 'SKILL_LEVEL_UP':
                        has_skills = True
                        skill_ex = e
                        break
                if has_skills: break
            
            if has_skills:
                details.append(f"✅ SKILL ORDER (Found SKILL_LEVEL_UP: {skill_ex})")
            else:
                details.append("❌ SKILL ORDER (No SKILL_LEVEL_UP events)")

            # --- CHECK 2: ITEM TIMINGS ---
            has_items = False
            item_ex = None
            for f in frames:
                for e in f.get('events', []):
                    if e.get('type') == 'ITEM_PURCHASED':
                        has_items = True
                        item_ex = e
                        break
                if has_items: break
                
            if has_items:
                details.append(f"✅ ITEM TIMINGS (Found ITEM_PURCHASED: {item_ex})")
            else:
                details.append("❌ ITEM TIMINGS (No ITEM_PURCHASED events)")
                
            # --- CHECK 3: RUNES & SUMMONERS ---
            # Usually in Metadata (Participants) or Info, not always in Timeline frames unless enriched.
            # "Participants" table usually has this. Let's check Participants Table.
            
    except Exception as e:
        print(f"Error checking timeline: {e}")

    print("\n--- CHECKING PARTICIPANTS (Runes/Summs) ---")
    try:
        c.execute("PRAGMA table_info(participants)")
        p_cols = [r[1] for r in c.fetchall()]
        print(f"Participant Columns: {p_cols}")
        
        # Check for deep columns
        c.execute("SELECT * FROM participants LIMIT 1")
        p_row = c.fetchone()
        
        # Ideally we want a 'json_data' or specific columns
        if 'perks' in p_cols or 'runes' in p_cols:
             details.append("✅ RUNES (Column exists)")
        elif 'json_data' in p_cols:
            # check inside json
            c.execute("SELECT json_data FROM participants LIMIT 1")
            jp = c.fetchone()
            if jp:
                try:
                    pdata = json.loads(jp[0])
                    # Check Runes
                    if 'perks' in pdata or 'runes' in pdata:
                        details.append("✅ RUNES (Found in JSON)")
                        # Check deep
                        if 'styles' in pdata.get('perks', {}):
                             details.append("   - Deep Runes (Styles) Found")
                    else:
                        details.append("❌ RUNES (Not in JSON)")
                        
                    # Check Summoners
                    if 'summoner1Id' in pdata:
                        details.append("✅ SUMMONERS (Found in JSON)")
                    else:
                        details.append("❌ SUMMONERS (Not in JSON)")
                        
                    # Check Damage
                    if 'totalDamageDealtToChampions' in pdata:
                        details.append("✅ DAMAGE STATS (Found in JSON)")
                    else:
                        details.append("❌ DAMAGE STATS (Not in JSON)")
                        
                except:
                    details.append("❌ PARTICIPANT JSON (Corrupt/Unparseable)")
        else:
            details.append("❌ PARTICIPANT DEEP DATA (No JSON/Runes columns)")

    except Exception as e:
        print(f"Error checking participants: {e}")

    with open("verification_report.txt", "w", encoding="utf-8") as f:
        f.write("\n" + "="*30 + "\n")
        f.write("VERDICT REPORT\n")
        f.write("="*30 + "\n")
        for d in details:
            f.write(d + "\n")
            
        if all(x.startswith("✅") for x in details):
            f.write("\n🏆 VERDICT: FULL BLOB\n")
        else:
            f.write("\n⚠️ VERDICT: PARTIAL SCHEMA\n")
            
    print("Report written to verification_report.txt")

if __name__ == "__main__":
    verify_data()

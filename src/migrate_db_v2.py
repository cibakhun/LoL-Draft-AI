import sqlite3
import os
import json

DB_PATH = "brain.db"
MATCH_DIR = "src/data/matches"

def migrate():
    print("Starting DB Migration v2 (Game Duration)...")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 1. Add Column (Safe)
    try:
        c.execute("ALTER TABLE matches ADD COLUMN game_duration INTEGER")
        print("✅ Added 'game_duration' column.")
    except sqlite3.OperationalError:
        print("ℹ️ 'game_duration' column already exists.")
        
    conn.commit()
    
    # 2. Backfill from JSON
    print("Backfilling timestamps and durations from JSON archives...")
    
    if not os.path.exists(MATCH_DIR):
        print(f"⚠️ Match directory {MATCH_DIR} not found. Skipping backfill.")
        conn.close()
        return

    files = [f for f in os.listdir(MATCH_DIR) if f.endswith(".json") and "_timeline" not in f]
    print(f"Found {len(files)} JSON files. Scanning...")
    
    updates = 0
    batch_data = []
    
    for fn in files:
        try:
            with open(os.path.join(MATCH_DIR, fn), 'r') as f:
                data = json.load(f)
                
            mid = data.get('metadata', {}).get('matchId')
            info = data.get('info', {})
            duration = info.get('gameDuration', 0)
            
            if mid and duration > 0:
                batch_data.append((duration, mid))
                
                if len(batch_data) >= 1000:
                    c.executemany("UPDATE matches SET game_duration = ? WHERE match_id = ?", batch_data)
                    updates += len(batch_data)
                    batch_data = []
                    print(f"Updated {updates} matches...")
                    conn.commit()
        except Exception as e:
            # print(f"Error reading {fn}: {e}")
            pass
            
    if batch_data:
        c.executemany("UPDATE matches SET game_duration = ? WHERE match_id = ?", batch_data)
        updates += len(batch_data)
        conn.commit()
        
    print(f"✅ Migration Complete. Backfilled {updates} matches.")
    conn.close()

if __name__ == "__main__":
    migrate()

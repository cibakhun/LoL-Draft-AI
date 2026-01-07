import os
import json
import sqlite3
import glob
import zlib

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, '../../brain.db')
MATCHES_DIR = os.path.join(BASE_DIR, 'matches')

def populate_frames():
    if not os.path.exists(DB_PATH):
        print(f"[Error] Database not found at {DB_PATH}")
        return

    print(f"[Populate] Connecting to database at {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Ensure Table Exists (Just in case)
    c.execute('''CREATE TABLE IF NOT EXISTS match_frames (
                match_id TEXT PRIMARY KEY,
                frame_data BLOB,
                compressed BOOLEAN DEFAULT 1,
                FOREIGN KEY(match_id) REFERENCES matches(match_id)
            )''')
    conn.commit()

    # Find file pairs
    timeline_files = glob.glob(os.path.join(MATCHES_DIR, "*_timeline.json"))
    print(f"[Populate] Found {len(timeline_files)} timeline files.")

    count = 0
    inserted = 0
    errors = 0

    for tl_file in timeline_files:
        base_name = os.path.basename(tl_file)
        match_id = base_name.replace('_timeline.json', '')
        
        try:
            # Check if exists first to avoid expensive read
            c.execute("SELECT 1 FROM match_frames WHERE match_id = ?", (match_id,))
            if c.fetchone():
                continue # Skip existing

            with open(tl_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Extract Frames ONLY to save space/time if needed? 
            # BrainDataset expects the whole JSON or at least 'info' -> 'frames'
            # Let's save the list of frames directly if possible, or the whole object.
            # Dataset expects: frames = json.loads(...)
            # And expects frames to be a list of frame objects directly OR the full json.
            # Let's check datasets.py... 
            # It loads: `decompressed = ... decode` -> `match_meta[mid]['frames'] = json.loads(decompressed)`
            # Then usage: `raw_frames = self.feature_engine.encode_timeline(state['timeline_frames'])`
            # FeatureEngine.encode_timeline expects a LIST of frames.
            
            frames_list = []
            if 'info' in data and 'frames' in data['info']:
                frames_list = data['info']['frames']
            elif 'frames' in data: # Direct list
                frames_list = data['frames']
            
            if not frames_list:
                # print(f"[Skip] No frames in {match_id}")
                continue

            # Compress
            json_str = json.dumps(frames_list)
            compressed_data = zlib.compress(json_str.encode('utf-8'))
            
            c.execute("INSERT INTO match_frames (match_id, frame_data, compressed) VALUES (?, ?, 1)", 
                      (match_id, compressed_data))
            
            inserted += 1
            if inserted % 100 == 0:
                conn.commit()
                print(f"[Progress] Inserted {inserted} matches...")
                
        except Exception as e:
            # print(f"[Error] Failed {match_id}: {e}")
            errors += 1

        count += 1

    conn.commit()
    conn.close()
    print(f"[Done] Scanned {count} files. Inserted {inserted} new records. Errors: {errors}")

if __name__ == "__main__":
    populate_frames()

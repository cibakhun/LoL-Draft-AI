import sqlite3
import zlib
import json
import os
import sys

def debug_structure():
    # Path to DB
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.abspath(os.path.join(base_dir, "../../brain.db"))
    
    print(f"--- Brain DB Structure Debugger ---")
    print(f"Target DB: {db_path}")

    if not os.path.exists(db_path):
        print("Error: DB file not found.")
        return

    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # Get one valid entry
        # Using frame_data based on previous findings
        c.execute("SELECT match_id, frame_data FROM match_frames WHERE frame_data IS NOT NULL LIMIT 1")
        row = c.fetchone()
        
        if not row:
            print("Error: No valid entries found in match_frames.")
            conn.close()
            return
            
        mid, blob = row
        print(f"Analyzing Match ID: {mid}")
        
        # Decompress
        try:
            decompressed = zlib.decompress(blob).decode('utf-8')
            data = json.loads(decompressed)
        except Exception as e:
            print(f"Error decoding blob: {e}")
            conn.close()
            return

        # Check Structure
        print("\nStructure Analysis:")
        
        # Format A: Riot V5 (json -> info -> frames)
        has_v5 = False
        v5_count = 0
        if isinstance(data, dict) and 'info' in data and 'frames' in data['info']:
            has_v5 = True
            v5_count = len(data['info']['frames'])
            print(f"[Format A (Riot V5)] Detected: YES (Frames: {v5_count})")
        else:
             print(f"[Format A (Riot V5)] Detected: NO")

        # Format B: Legacy (json -> frames directly)
        has_legacy = False
        legacy_count = 0
        if isinstance(data, dict) and 'frames' in data:
            has_legacy = True
            legacy_count = len(data['frames'])
            print(f"[Format B (Legacy)]  Detected: YES (Frames: {legacy_count})")
        else:
            print(f"[Format B (Legacy)]  Detected: NO")
            
        # Fallback dump
        if not has_v5 and not has_legacy:
            print("\nFallback Analysis (Unknown Structure):")
            if isinstance(data, dict):
                print(f"Top-Level Keys: {list(data.keys())}")
            else:
                print(f"Data Type: {type(data)}")
                
        conn.close()
        
    except sqlite3.Error as e:
        print(f"SQLite Error: {e}")
    except Exception as e:
        print(f"General Error: {e}")

if __name__ == "__main__":
    debug_structure()

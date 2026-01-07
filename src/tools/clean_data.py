import os
import json
import argparse
import glob

def clean_data(data_dir, min_frames=5):
    print(f"--- Data Cleaner Tool ---")
    print(f"Target Directory: {data_dir}")
    print(f"Min Frames: {min_frames}")
    
    if not os.path.exists(data_dir):
        print(f"Error: Directory {data_dir} does not exist.")
        return

    # Gather files
    # Assumption: *_match.json and *_timeline.json
    match_files = glob.glob(os.path.join(data_dir, "*_match.json"))
    timeline_files = glob.glob(os.path.join(data_dir, "*_timeline.json"))
    
    print(f"Found {len(match_files)} match files and {len(timeline_files)} timeline files.")
    
    files_to_delete = set()
    kept_files = 0
    
    # Map MatchID -> Paths
    # Filename format: {MatchID}_match.json
    matches = {}
    timelines = {}
    
    for p in match_files:
        basename = os.path.basename(p)
        mid = basename.replace("_match.json", "")
        matches[mid] = p
        
    for p in timeline_files:
        basename = os.path.basename(p)
        mid = basename.replace("_timeline.json", "")
        timelines[mid] = p

    # PASS 1: Orphans (Match without Timeline)
    print("\n--- Pass 1: Checking Orphans ---")
    for mid, m_path in matches.items():
        if mid not in timelines:
            print(f"Deleting {os.path.basename(m_path)}... (Reason: Orphan Match - No Timeline)")
            files_to_delete.add(m_path)
    
    # Note: Timeline without matched match? Usually cleaner to keep or delete?
    # User Spec: "if NOT -> Delete match file". Doesn't specify reverse.
    # Assuming we need both.
    
    # PASS 2 & 3: Iterate Timelines (Remakes & Corruption)
    print("\n--- Pass 2 & 3: Checking Content (Remakes & Corruption) ---")
    
    for mid, t_path in timelines.items():
        if t_path in files_to_delete: continue # Already marked? Unlikely.
        
        # Check integrity
        try:
            with open(t_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Check Frames
            # Structure: data['info']['frames'] or just data['frames']? 
            # DDragon timeline usually: {'metadata':..., 'info': {'frames': [...]}}
            # User Context: "data['info']['frames']"
            
            frames = []
            if 'info' in data and 'frames' in data['info']:
                frames = data['info']['frames']
            elif 'frames' in data: # Fallback
                frames = data['frames']
            else:
                # Ambiguous structure
                # print(f"Warning: Unexpected structure in {t_path}")
                pass
            
            if len(frames) < min_frames:
                print(f"Deleting {mid}... (Reason: Short Game / Remake - {len(frames)} frames)")
                files_to_delete.add(t_path)
                if mid in matches:
                    files_to_delete.add(matches[mid])
            else:
                # Valid
                kept_files += 1

        except json.JSONDecodeError:
            print(f"Deleting {os.path.basename(t_path)}... (Reason: Corrupt JSON)")
            files_to_delete.add(t_path)
            if mid in matches:
                files_to_delete.add(matches[mid])
        except Exception as e:
            print(f"Deleting {os.path.basename(t_path)}... (Reason: Read Error {e})")
            files_to_delete.add(t_path)
            if mid in matches:
                files_to_delete.add(matches[mid])

    # Execution of Deletion
    print("\n--- Execution ---")
    deleted_count = 0
    
    for p in files_to_delete:
        try:
            if os.path.exists(p):
                os.remove(p)
                deleted_count += 1
        except Exception as e:
            print(f"Failed to delete {p}: {e}")

    print("-" * 30)
    print(f"Summary: Deleted {deleted_count} files. Kept ~{kept_files * 2} files (Pairs).")
    print("-" * 30)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # Updated defaults based on project structure and FF15 rule
    parser.add_argument('--dir', type=str, default='src/data/matches', help='Directory containing JSON files')
    parser.add_argument('--min_frames', type=int, default=15, help='Minimum timeline frames required')
    args = parser.parse_args()
    
    clean_data(args.dir, args.min_frames)

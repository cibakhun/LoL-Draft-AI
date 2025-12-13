import os
import json

def clean_database():
    match_dir = os.path.join("src", "data", "matches")
    if not os.path.exists(match_dir):
        print(f"Directory not found: {match_dir}")
        return

    # 420 = Ranked Solo/Duo
    # 440 = Ranked Flex
    VALID_QUEUES = {420, 440}
    
    files = [f for f in os.listdir(match_dir) if f.endswith(".json")]
    print(f"Scanning {len(files)} matches...")
    
    deleted = 0
    kept = 0
    errors = 0
    
    for filename in files:
        if "timeline" in filename:
            continue
            
        path = os.path.join(match_dir, filename)
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            
            # Check for Queue ID
            # Structure: data['info']['queueId']
            info = data.get('info', {})
            queue_id = info.get('queueId')
            
            if queue_id not in VALID_QUEUES:
                # Delete Match
                f.close()
                os.remove(path)
                deleted += 1
                
                # Delete associated Timeline if it exists
                timeline_path = path.replace(".json", "_timeline.json")
                if os.path.exists(timeline_path):
                    os.remove(timeline_path)
                    # print(f"Deleted Timeline for {filename}")
            else:
                kept += 1
                
        except Exception as e:
            print(f"Error reading {filename}: {e}")
            errors += 1
            
    print("-" * 30)
    print(f"Cleanup Complete.")
    print(f"Kept (Ranked): {kept}")
    print(f"Deleted (Other): {deleted}")
    print(f"Errors: {errors}")
    print("-" * 30)

if __name__ == "__main__":
    clean_database()

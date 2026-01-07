import sqlite3
import os
import sys

def check_db_health():
    # Locate DB
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../'))
    db_path = os.path.join(root_dir, 'brain.db')
    
    print(f"[Health] Checking DB at: {db_path}")
    if not os.path.exists(db_path):
        print("[Health] Error: DB not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # 1. Heads (Total Matches Registered)
        cursor.execute("SELECT COUNT(*) FROM matches")
        count_matches = cursor.fetchone()[0]

        # 2. Content (Total Timeline Blobs)
        # Note: Assuming table is 'match_frames' based on prompt, but checking 'timeline' if that fails might be smart.
        # User said 'match_frames'. I will stick to 'match_frames'.
        try:
            cursor.execute("SELECT COUNT(*) FROM match_frames")
            count_frames = cursor.fetchone()[0]
            table_name = "match_frames"
        except sqlite3.OperationalError:
            # Fallback for legacy schema names if needed, but user was specific.
            # Checking if maybe it's called 'timelines'
            try:
                cursor.execute("SELECT COUNT(*) FROM timelines")
                count_frames = cursor.fetchone()[0]
                table_name = "timelines"
                print(f"[Health] Note: Table 'match_frames' not found, using '{table_name}' instead.")
            except:
                print("[Health] Error: Could not find 'match_frames' or 'timelines' table.")
                return

        # 3. Ghosts (Matches without Frames)
        # matches m LEFT JOIN {table_name} mf ON m.match_id = mf.match_id WHERE mf.match_id IS NULL
        query = f"""
            SELECT COUNT(*) 
            FROM matches m 
            LEFT JOIN {table_name} mf ON m.match_id = mf.match_id 
            WHERE mf.match_id IS NULL
        """
        cursor.execute(query)
        count_ghosts = cursor.fetchone()[0]

        print("-" * 30)
        print(f"DATABASE HEALTH REPORT")
        print("-" * 30)
        print(f"1. Registered Matches (Heads): {count_matches}")
        print(f"2. Actual Data Blobs (Content): {count_frames}")
        print(f"3. Ghosts (No Data):            {count_ghosts}")
        print("-" * 30)
        
        if count_ghosts > 0:
            print(f"WARNING: {count_ghosts} matches have metadata but no timeline data.")
            print("Recommendation: Run cleanup to remove ghosts or re-fetch data.")
        else:
            print("Status: HEALTHY. Metadata and Content are synced.")

    except Exception as e:
        print(f"[Health] Analysis failed: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_db_health()

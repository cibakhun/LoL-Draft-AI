
import os
import time
from src.engine.persistence import BrainDatabase

def run_migration():
    print("##################################################")
    print("#      VANTAGE DATA MIGRATION (JSON -> SQLITE)   #")
    print("##################################################\n")
    
    db = BrainDatabase()
    match_dir = os.path.join("src", "data", "matches")
    
    print(f"[MIGRATION] Scanning {match_dir}...")
    db.migrate_json_files(match_dir)
    
    final_count = db.get_processed_count()
    print(f"\n[MIGRATION] SUCCESS! Total Matches in Brain Node: {final_count}")

if __name__ == "__main__":
    run_migration()

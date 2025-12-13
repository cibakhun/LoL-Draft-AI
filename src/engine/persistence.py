import sqlite3
import json
import os
import threading
from datetime import datetime

class BrainDatabase:
    def __init__(self, db_path="brain.db"):
        self.db_path = db_path
        self.lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            # Enable WAL Mode for Concurrency (Reader doesn't block Writer)
            conn.execute("PRAGMA journal_mode=WAL;")
            c = conn.cursor()
            
            # Matches Table
            c.execute('''CREATE TABLE IF NOT EXISTS matches (
                        match_id TEXT PRIMARY KEY,
                        game_mode TEXT,
                        queue_id INTEGER,
                        timestamp INTEGER,
                        processed_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )''')
            
            # Participants Table (Linked to Matches)
            c.execute('''CREATE TABLE IF NOT EXISTS participants (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        match_id TEXT,
                        puuid TEXT,
                        champion_id INTEGER,
                        team_id INTEGER,
                        role TEXT,
                        win BOOLEAN,
                        FOREIGN KEY(match_id) REFERENCES matches(match_id)
                    )''')
                    
            # Meta Stats (Aggregated) - Optional Cache
            # We can compute this dynamically, but caching is faster for "Realist" score
            c.execute('''CREATE TABLE IF NOT EXISTS meta_stats (
                        champion_id INTEGER,
                        role TEXT,
                        games INTEGER DEFAULT 0,
                        wins INTEGER DEFAULT 0,
                        PRIMARY KEY (champion_id, role)
                    )''')
            
            # Indices for speed
            c.execute("CREATE INDEX IF NOT EXISTS idx_participants_puuid ON participants (puuid)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_participants_champion ON participants (champion_id)")
            
            conn.commit()
            conn.close()

    def save_match(self, match_data):
        """
        Saves a full match JSON object into the relational DB.
        """
        info = match_data.get('info', {})
        match_id = match_data.get('metadata', {}).get('matchId')
        if not match_id: return False
        
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            try:
                # 1. Check Existence
                c.execute("SELECT 1 FROM matches WHERE match_id = ?", (match_id,))
                if c.fetchone():
                    return False # Already processed
                
                # 2. Insert Match
                c.execute("INSERT INTO matches (match_id, game_mode, queue_id, timestamp) VALUES (?, ?, ?, ?)",
                          (match_id, info.get('gameMode'), info.get('queueId'), info.get('gameCreation')))
                
                # 3. Insert Participants
                parts = info.get('participants', [])
                for p in parts:
                    c.execute('''INSERT INTO participants (match_id, puuid, champion_id, team_id, role, win)
                                VALUES (?, ?, ?, ?, ?, ?)''',
                                (match_id, p.get('puuid'), p.get('championId'), p.get('teamId'), 
                                 p.get('teamPosition', ''), p.get('win'))
                    )
                    
                    # 4. Update Meta Stats (Incremental)
                    role = p.get('teamPosition', '')
                    cid = p.get('championId')
                    win = 1 if p.get('win') else 0
                    
                    if role and cid:
                        # Upsert Meta
                        c.execute('''INSERT INTO meta_stats (champion_id, role, games, wins) 
                                    VALUES (?, ?, 1, ?)
                                    ON CONFLICT(champion_id, role) DO UPDATE SET
                                    games = games + 1,
                                    wins = wins + ?''', (cid, role, win, win))
                
                conn.commit()
                return True
            except Exception as e:
                print(f"[DB] Error saving match {match_id}: {e}")
                return False
            finally:
                conn.close()

    def get_processed_count(self):
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM matches")
            count = c.fetchone()[0]
            conn.close()
            return count

    def get_training_data(self, min_samples=0):
        """
        Returns structured data for LeagueNet Training.
        X_champs: List of [Blue_ID_1...5, Red_ID_1...5]
        y: List of Win (0/1)
        """
        print("[DB] Fetching Training Data (High Performance Join)...")
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # We need to reconstruct matches. 
            # SQLite doesn't have array_agg, so we might need to fetch all and process in python
            # Or fetch ordered by match_id
            
            query = """
                SELECT match_id, team_id, role, champion_id, win 
                FROM participants 
                WHERE role != '' 
                ORDER BY match_id, team_id
            """
            
            c.execute(query)
            rows = c.fetchall()
            conn.close()
            
        # Process in Python (O(N) single pass)
        # Assuming rows are sorted by Match -> Team
        
        training_set = [] # [{blue: [], red: [], win: 1/0}]
        
        current_match = None
        current_data = {'blue': {}, 'red': {}}
        valid = True
        
        # Valid Roles
        expected_roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
        
        for mid, tid, role, cid, win in rows:
            if mid != current_match:
                # Save previous
                if current_match and valid:
                     # Check completeness
                     if len(current_data['blue']) == 5 and len(current_data['red']) == 5:
                         training_set.append({
                             'blue': current_data['blue'], 
                             'red': current_data['red'], 
                             'win': current_data['win_val']
                        })
                
                # Reset
                current_match = mid
                current_data = {'blue': {}, 'red': {}, 'win_val': 0}
                valid = True
            
            if role not in expected_roles: 
                valid = False # Invalid role (ARAM?)
                continue
                
            team_key = 'blue' if tid == 100 else 'red'
            current_data[team_key][role] = cid
            
            if tid == 100:
                current_data['win_val'] = 1 if win else 0
                
        print(f"[DB] Extracted {len(training_set)} full 5v5 matches for training.")
        return training_set

    def migrate_json_files(self, match_dir):
        """
        One-time migration of JSON files to SQLite.
        """
        if not os.path.exists(match_dir): return
        
        files = [f for f in os.listdir(match_dir) if f.endswith(".json") and "_timeline" not in f]
        print(f"[DB] Migrating {len(files)} legacy JSON matches to SQLite...")
        
        count = 0
        for fn in files:
            try:
                path = os.path.join(match_dir, fn)
                with open(path, 'r') as f:
                    data = json.load(f)
                
                if self.save_match(data):
                    count += 1
                    
                # Rename to .bak to mark as migrated? 
                # Or just keep them as backup? User said "20k+ matches".
                # Let's keep them but maybe move them to a "legacy" folder later.
            except: pass
            
            if count % 1000 == 0:
                print(f"[DB] Migrated {count}...")
                
        print(f"[DB] Migration Complete. Imported {count} matches.")

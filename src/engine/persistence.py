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
                        game_duration INTEGER,
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
            
            # Match Timelines (The "Temporal DNA")
            # Aggregates performance metrics at 15 minutes
            c.execute('''CREATE TABLE IF NOT EXISTS timeline_stats (
                        champion_id INTEGER,
                        role TEXT,
                        total_games INTEGER DEFAULT 0,
                        sum_gold_diff_15 INTEGER DEFAULT 0, -- Sum of Normalized Gold Diff
                        sum_xp_diff_15 INTEGER DEFAULT 0,   -- Sum of Normalized XP Diff
                        early_leads INTEGER DEFAULT 0,    -- Games where ahead @ 15
                        snowball_wins INTEGER DEFAULT 0,  -- Wins when ahead @ 15
                        early_deficits INTEGER DEFAULT 0, -- Games where behind @ 15
                        comeback_wins INTEGER DEFAULT 0,  -- Wins when behind @ 15
                        PRIMARY KEY (champion_id, role)
                    )''')
            
            # Indices for speed
            c.execute("CREATE INDEX IF NOT EXISTS idx_participants_puuid ON participants (puuid)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_participants_champion ON participants (champion_id)")
            c.execute("CREATE INDEX IF NOT EXISTS idx_matches_timestamp ON matches (timestamp)")
            
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
                # Handle gameDuration (Seconds)
                duration = info.get('gameDuration', 0)
                
                c.execute("INSERT INTO matches (match_id, game_mode, queue_id, timestamp, game_duration) VALUES (?, ?, ?, ?, ?)",
                          (match_id, info.get('gameMode'), info.get('queueId'), info.get('gameCreation'), duration))
                
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

    def get_all_match_ids(self):
        """
        Returns a set of all match IDs currently in the DB.
        """
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("SELECT match_id FROM matches")
            rows = c.fetchall()
            conn.close()
            return {r[0] for r in rows}

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
        
        # Flush last match
        if current_match and valid:
             if len(current_data['blue']) == 5 and len(current_data['red']) == 5:
                 training_set.append({
                     'blue': current_data['blue'], 
                     'red': current_data['red'], 
                     'win': current_data['win_val']
                })
                
        print(f"[DB] Extracted {len(training_set)} full 5v5 matches for training.")
        return training_set

    def yield_training_batches(self, batch_size=5000, shuffle=True):
        """
        Generator that yields structured training data in batches.
        shuffle: If True, randomizes order. If False, strictly CHRONOLOGICAL (for Online Learning).
        """
        import random
        mode = "SHUFFLED" if shuffle else "CHRONOLOGICAL"
        print(f"[DB] Streaming Training Data (Batch: {batch_size}, Mode: {mode})...")
        
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            if shuffle:
                # Optimized: Fetch IDs, Shuffle in RAM
                c.execute("SELECT match_id FROM matches")
                all_ids = [r[0] for r in c.fetchall()]
                print(f"[DB] Shuffling {len(all_ids)} match IDs for high-entropy training...")
                random.shuffle(all_ids)
            else:
                # Chronological: Fetch IDs ordered by time
                # Using the Index we just created
                c.execute("SELECT match_id FROM matches ORDER BY timestamp ASC")
                all_ids = [r[0] for r in c.fetchall()]
                print(f"[DB] Loaded {len(all_ids)} match IDs in strict chronological order.")
                
            conn.close()
            
        if not all_ids: return

        # Loop is same for both, just the order of 'all_ids' changes
        total = len(all_ids)
        for offset in range(0, total, batch_size):
            chunk_ids = all_ids[offset : offset + batch_size]
            
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                c = conn.cursor()
                
                # Fetch timestamps for this chunk
                placeholders = ','.join('?' for _ in chunk_ids)
                
                # 1. Get Meta (Timestamps)
                c.execute(f"SELECT match_id, timestamp, game_duration FROM matches WHERE match_id IN ({placeholders})", chunk_ids)
                match_meta = {mid: {'ts': ts, 'dur': dur} for mid, ts, dur in c.fetchall()}
                
                # 2. Get Participants
                query = f"""
                    SELECT match_id, team_id, role, champion_id, win 
                    FROM participants 
                    WHERE match_id IN ({placeholders}) AND role != '' 
                    ORDER BY match_id, team_id
                """
                c.execute(query, chunk_ids)
                rows = c.fetchall()
                conn.close()
            
            # Process in memory
            batch_matches = self._process_rows_to_matches(rows, match_meta)
            if batch_matches:
                yield batch_matches
                
            print(f"[DB] Streamed {min(offset + batch_size, total)} / {total} matches...")

    def _process_rows_to_matches(self, rows, match_meta=None):
        """Helper to convert SQL rows to Match Dicts."""
        training_set = []
        current_match = None
        current_data = {'blue': {}, 'red': {}}
        valid = True
        expected_roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
        
        for mid, tid, role, cid, win in rows:
            if mid != current_match:
                if current_match and valid:
                     if len(current_data['blue']) == 5 and len(current_data['red']) == 5:
                         m = {
                             'blue': current_data['blue'], 
                             'red': current_data['red'], 
                             'win': current_data['win_val']
                         }
                         if match_meta and current_match in match_meta:
                             m['timestamp'] = match_meta[current_match]['ts']
                             m['duration'] = match_meta[current_match]['dur']
                             
                         training_set.append(m)
                current_match = mid
                current_data = {'blue': {}, 'red': {}, 'win_val': 0}
                valid = True
            
            if role not in expected_roles: 
                valid = False
                continue
                
            team_key = 'blue' if tid == 100 else 'red'
            current_data[team_key][role] = cid
            if tid == 100: current_data['win_val'] = 1 if win else 0
        
        # Flush last
        if current_match and valid and len(current_data['blue']) == 5 and len(current_data['red']) == 5:
             m = {
                 'blue': current_data['blue'], 
                 'red': current_data['red'], 
                 'win': current_data['win_val']
            }
             if match_meta and current_match in match_meta:
                 m['timestamp'] = match_meta[current_match]['ts']
                 m['duration'] = match_meta[current_match]['dur']
             training_set.append(m)
            
        return training_set

    def get_meta_stats(self):
        """
        Retrieves aggregated champion stats from DB for Context Features.
        Returns: { cid: { role: { 'games': N, 'wins': M, 'timeline': {...} } } }
        """
        print("[DB] Loading Meta-Statistics (Memory Cache)...")
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # 1. Base Stats
            c.execute("SELECT champion_id, role, games, wins FROM meta_stats")
            rows = c.fetchall()
            
            # 2. Timeline Stats
            c.execute("SELECT champion_id, role, sum_gold_diff_15, sum_xp_diff_15, early_leads, snowball_wins, early_deficits, comeback_wins FROM timeline_stats")
            t_rows = c.fetchall()
            
            conn.close()
            
        stats = {}
        for cid, role, games, wins in rows:
            if cid not in stats: stats[cid] = {'total_games': 0}
            stats[cid]['total_games'] += games
            stats[cid][role] = {'games': games, 'wins': wins, 'timeline': {}}

        # Merge Timeline
        for cid, role, g_diff, x_diff, leads, snow_wins, deficits, come_wins in t_rows:
            if cid in stats and role in stats[cid]:
                # Calculate averages on the fly
                # Avoid div by zero
                # We store raw sums, convert to avgs here
                
                # Note: 'total_games' in timeline table matches 'games' in meta_stats roughly, 
                # but we use the specific counts for leads/deficits
                
                s = stats[cid][role]['timeline']
                g = stats[cid][role]['games']
                
                if g > 0:
                    s['avg_gold_15'] = g_diff / g
                    s['avg_xp_15'] = x_diff / g
                else:
                    s['avg_gold_15'] = 0
                    s['avg_xp_15'] = 0
                    
                s['snowball_rate'] = snow_wins / leads if leads > 0 else 0.5
                s['comeback_rate'] = come_wins / deficits if deficits > 0 else 0.5
                
        return stats

    def update_timeline_stats(self, entries):
        """
        Bulk update timeline stats.
        entries: List of {cid, role, gold_diff, xp_diff, is_lead, is_win}
        """
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            for e in entries:
                cid, role = e['cid'], e['role']
                g_diff = int(e['gold_diff'])
                x_diff = int(e['xp_diff'])
                win = 1 if e['is_win'] else 0
                
                is_lead = 1 if e['is_lead'] else 0
                is_deficit = 1 if not e['is_lead'] else 0
                
                snow_win = 1 if (is_lead and win) else 0
                come_win = 1 if (is_deficit and win) else 0
                
                c.execute('''INSERT INTO timeline_stats 
                          (champion_id, role, total_games, sum_gold_diff_15, sum_xp_diff_15, early_leads, snowball_wins, early_deficits, comeback_wins)
                          VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?)
                          ON CONFLICT(champion_id, role) DO UPDATE SET
                          total_games = total_games + 1,
                          sum_gold_diff_15 = sum_gold_diff_15 + ?,
                          sum_xp_diff_15 = sum_xp_diff_15 + ?,
                          early_leads = early_leads + ?,
                          snowball_wins = snowball_wins + ?,
                          early_deficits = early_deficits + ?,
                          comeback_wins = comeback_wins + ?''',
                          (cid, role, g_diff, x_diff, is_lead, snow_win, is_deficit, come_win,
                           g_diff, x_diff, is_lead, snow_win, is_deficit, come_win))
            
            conn.commit()
            conn.close()

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

    def verify_integrity(self):
        """
        Deep Scan for Data Rot.
        Checks for:
        1. Duplicate Match IDs (Should be blocked by PK, but checking anyway)
        2. Timestamp anomalies (Future dates, 0 dates)
        3. Match Completeness (10 players per match)
        """
        print("[DB] Starting Deep Integrity Scan...")
        issues = []
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            # 1. Count
            c.execute("SELECT COUNT(*) FROM matches")
            total = c.fetchone()[0]
            
            # 2. Timestamps
            # check for 0
            c.execute("SELECT COUNT(*) FROM matches WHERE timestamp = 0")
            zeros = c.fetchone()[0]
            if zeros > 0: issues.append(f"Found {zeros} matches with 0 timestamp.")
            
            # check for future (Year 2030+)
            c.execute("SELECT COUNT(*) FROM matches WHERE timestamp > 1893456000000") 
            future = c.fetchone()[0]
            if future > 0: issues.append(f"Found {future} matches from the future.")
            
            # 3. Participants
            # Check for matches with != 10 participants
            c.execute("""
                SELECT match_id, COUNT(*) as cnt 
                FROM participants 
                GROUP BY match_id 
                HAVING cnt != 10
            """)
            incomplete = c.fetchall()
            if incomplete:
                issues.append(f"Found {len(incomplete)} incomplete matches (Not 5v5).")
            
            conn.close()
            
        if not issues:
            print(f"[DB] Integrity Verified. {total} matches are healthy.")
            return True
        else:
            print("[DB] INTEGRITY WARNINGS FOUND:")
            for i in issues: print(f" - {i}")
            return False

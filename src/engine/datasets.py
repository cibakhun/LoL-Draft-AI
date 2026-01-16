
import torch
from torch.utils.data import Dataset
import sqlite3
import numpy as np
import zlib
import json
import os
from src.engine.schema import FeatureConfig as Cfg

class TitanMemoryDataset(Dataset):
    """
    Mental Sandbox Dataset.
    Loads data using Memory Mapping (mmap) for instant access and zero RAM usage.
    Ideal for datasets > RAM size (e.g. 40GB+).
    """
    def __init__(self, path):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Dataset not found at {path}")
            
        print(f"[MEMORY] Mapping {path} to Virtual Address Space...")
        # 'weights_only=True' for safety, 'mmap=True' for speed/scale
        try:
            # mmap=True requires the file to be a dictionary of tensors saved via torch.save
            self.data = torch.load(path, mmap=True, weights_only=True)
        except Exception as e:
             print(f"[MEMORY] Failed to mmap: {e}. Falling back to standard load (Warning: Slow)")
             self.data = torch.load(path, weights_only=True)

        self.picks = self.data['X_picks']
        self.turns = self.data['X_pick_turn']
        self.bans  = self.data['X_bans']
        self.mast  = self.data['X_mastery']
        self.meta  = self.data['X_meta']
        self.y     = self.data['Y_win']
        
        self.length = len(self.picks)
        print(f"[MEMORY] Mapped {self.length} samples.")

    def __len__(self):
        return self.length

    def __getitem__(self, idx):
        # Casting on-the-fly saves 4x RAM (keeping data on disk as generic, casting only batch)
        # Assuming source is stored efficiently (e.g. uint8/int16)
        
        p = self.picks[idx].long()
        t = self.turns[idx].long()
        b = self.bans[idx].long()
        m = self.mast[idx].float()
        meta = self.meta[idx].float()
        label = self.y[idx].float()
        
        # Sanitize (Safety Clamp)
        b = torch.clamp(b, min=0)
        # b[b > 2000] = 0 # Optional safety, slow?
        p = torch.clamp(p, min=0)
        # p[p > 2000] = 0
        
        # [TITAN V3.5 UPGRADE]
        # Check if x_times exists in data, else zeros
        if 'X_times' in self.data:
             times = self.data['X_times'][idx].long()
        else:
             times = torch.zeros_like(p) # Default 0 (Full Visibility) if missing
        
        return p, t, b, m, meta, times, label

class BrainDataset(Dataset):
    """
    Lazy-Loading PyTorch Dataset.
    Fetches one match at a time from SQLite to keep RAM usage low.
    """
    def __init__(self, feature_engine, db_path="brain.db"):
        self.db_path = db_path
        self.feature_engine = feature_engine
        self.match_ids = []
        
        # Hybrid Caching Strategy for 64GB RAM
        self.ram_cache = {}
        self.cache_limit = 20000 
        
        # 1. Load Index (Fast)
        print("[Dataset] Indexing Matches from DB...")
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            # Only use matches that have frames? Or all?
            # Ideally intersection of matches w/ participants and match_frames
            # For now, just all from matches. logic in getitem handles missing data.
            # Robust Query: Filter out matches without frames and Bot games (Queue 830)
            # Robust Query: Filter out matches without frames and Bot games (Queue 830)
            q = f"""
            SELECT m.match_id
            FROM matches m
            INNER JOIN match_frames f ON m.match_id = f.match_id
            WHERE m.queue_id != {Cfg.QUEUE_COOP_VS_AI}
            ORDER BY m.timestamp ASC
            """
            c.execute(q)
            rows = c.fetchall()
            self.match_ids = [r[0] for r in rows]
            conn.close()
            print(f"[Dataset] Indexed {len(self.match_ids)} matches.")
        except Exception as e:
            print(f"[Dataset] Init Error: {e}")

    def __len__(self):
        return len(self.match_ids)

    def __getitem__(self, idx):
        mid = self.match_ids[idx]
        
        # 1. Check RAM Cache
        if mid in self.ram_cache:
            return self.ram_cache[mid]
        
        # New Connection per thread/worker
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # 1. Fetch Participants
        # We need this to build the team dicts for Vectorization
        q = """
        SELECT p.team_id, p.role, p.champion_id, p.win, p.gold_at_15
        FROM participants p
        WHERE p.match_id = ? AND p.role IN ('TOP', 'JUNGLE', 'MIDDLE', 'BOTTOM', 'UTILITY')
        """
        c.execute(q, (mid,))
        rows = c.fetchall()
        
        # 2. Fetch Timeline Blob
        c.execute("SELECT frame_data FROM match_frames WHERE match_id = ?", (mid,))
        blob_row = c.fetchone()
        
        conn.close()
        
        # Pivot Structure
        blue = {}
        red = {}
        win_label = 0
        
        # rows: (team, role, cid, win, gold)
        # Note: We need full team? training requires it.
        
        for r in rows:
            tid, role, cid, win, gold = r
            if tid == 100:
                blue[role] = cid
                if win: win_label = 1
            else:
                red[role] = cid
        
        # Vectorize Sequence
        # Returns (draft_ids, spatial_seats, temporal_turns)
        d_ids, s_ids, t_ids = self.feature_engine.vectorize_sequence(blue, red, training_mode=True)
        
        # Process Timeline
        if blob_row and blob_row[0]:
            try:
                # 1. Decoding Layer (Zlib Fallback)
                raw_blob = blob_row[0]
                try:
                    decompressed = zlib.decompress(raw_blob).decode('utf-8')
                except (zlib.error, OSError):
                    # Fallback: Maybe it's not compressed?
                    if isinstance(raw_blob, bytes):
                        decompressed = raw_blob.decode('utf-8')
                    else:
                        decompressed = str(raw_blob)

                # 2. JSON Parse
                data = json.loads(decompressed)
                
                # Polymorphic Parsing Logic
                full_timeline = []
                if isinstance(data, list):
                    # Case 1: Direct List
                    full_timeline = data
                elif isinstance(data, dict) and 'info' in data and 'frames' in data['info']:
                    # Case 2: Riot V5
                    full_timeline = data['info']['frames']
                elif isinstance(data, dict) and 'frames' in data:
                    # Case 3: Legacy Dict
                    full_timeline = data['frames']
                else:
                    # Invalid Format
                    # We might mark this as corrupt, but for now just fail hard as requested
                    # Or return recursion? User asked to "mark as corrupt" (via Exception?)
                    # "Code soll einen Fehler werfen, der den Match als korrupt markiert" -> implies raising logic
                    raise ValueError(f"Unknown timeline format for match {mid}")

                # Quality Filter: FF@15 Rule
                if len(full_timeline) < 15:
                    raise ValueError(f"Match {mid} is too short ({len(full_timeline)} frames). Min required: 15.")

                # Validation: Frame 0
                if not full_timeline[0].get('participantFrames'):
                    # This is also a form of corruption
                    raise ValueError(f"Match {mid} missing participantFrames in Frame 0.")

            except Exception as e:
                # Log error and skip
                with open("error_log.txt", "a") as f:
                    f.write(f"{mid}: {e}\n")
                print(f"[Dataset] Skip {mid}: Parse Error {e}")
                return self.__getitem__((idx + 1) % len(self.match_ids))
        else:
            # Missing Blob
            print(f"[Dataset] Skip {mid}: No blob data.")
            return self.__getitem__((idx + 1) % len(self.match_ids))
        
        # Encode Timeline -> Tensor [T, 20]
        # X_time is np.array
        X_time = self.feature_engine.encode_timeline(full_timeline)
        
        
        # Convert to Tensors immediately?
        # DataLoader prefers returning numpy or tensors.
        # Let's return Typed Tensors to save collation work, or Numpy.
        # Numpy is standard.
        
        # Synthesize missing V3 inputs for Online Dataset
        # Bans: Empty (0)
        # Mastery: Empty (0.0)
        # Meta: Default (Skill 6.0, Patch 14.1, Side 0)
        
        bans = np.zeros(10, dtype=np.int64)
        mast = np.zeros(10, dtype=np.float32)
        meta = np.array([6.0, 14.1, 0.0], dtype=np.float32)
        
        input_times = np.array(t_ids, dtype=np.int64)
        
        sample = (
            np.array(d_ids, dtype=np.int64),    # xp
            np.array(s_ids, dtype=np.int64),    # xt
            bans,                               # xb
            mast,                               # xm
            meta,                               # xmeta
            input_times,                        # x_times
            np.float32(win_label)               # y
        )
        
        # 2. Store in Cache (if room)
        if len(self.ram_cache) < self.cache_limit:
            self.ram_cache[mid] = sample
            
        return sample

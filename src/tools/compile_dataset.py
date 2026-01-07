import sys
import os
import torch
import sqlite3
import zlib
import json
import numpy as np
import re
import math
import hashlib

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.engine.features import FeatureEngine

# --- CONFIG ---
DB_PATH = os.path.join("src", "engine", "brain_v2.db")
OUTPUT_TRAIN = os.path.join("data", "titan_train_v3.pt")
OUTPUT_VAL = os.path.join("data", "titan_val_v3.pt")

# Valid Draft Queues
# 400: Draft Pick, 420: Ranked Solo, 440: Flex 5v5, 700: Clash
VALID_QUEUES = {400, 420, 440, 700}

def parse_patch(version_str):
    if not version_str: return 0.0
    try:
        match = re.match(r"(\d+\.\d+)", str(version_str))
        if match:
            return float(match.group(1))
    except:
        pass
    return 0.0

def get_snake_turn(pid):
    """
    Maps Participant ID (1-10) to Draft Pick Turn (1-10) using Standard Snake Draft.
    Assumption: PID 1-5 is Blue, 6-10 is Red.
    Slot Order: B1, R1, R2, B2, B3, R3, R4, B4, B5, R5.
    """
    # PID is 1-based.
    # Map: PID -> Turn
    mapping = {
        1: 1,
        6: 2,
        7: 3,
        2: 4,
        3: 5,
        8: 6,
        9: 7,
        4: 8,
        5: 9,
        10: 10
    }
    return mapping.get(pid, 0) # 0 if invalid

def save_tensor_dict(data_lists, path):
    if not data_lists['picks']:
        print(f"Warning: No data to save for {path}")
        return

    print(f"[Compiler] Stacking Tensors for {path}...")
    
    # Sanitize inputs
    sanitized_picks = [[max(0, min(32000, x)) for x in row] for row in data_lists['picks']]
    sanitized_bans = [[max(0, min(32000, x)) for x in row] for row in data_lists['bans']]
    
    # Create Tensors
    t_picks = torch.tensor(sanitized_picks, dtype=torch.int16)
    t_turns = torch.tensor(data_lists['turns'], dtype=torch.int8)
    t_bans = torch.tensor(sanitized_bans, dtype=torch.int16)
    t_mastery = torch.tensor(data_lists['mast'], dtype=torch.float16)
    t_meta = torch.tensor(data_lists['meta'], dtype=torch.float16)
    t_y = torch.tensor(data_lists['y'], dtype=torch.float16).unsqueeze(1)
    
    os.makedirs(os.path.dirname(path), exist_ok=True)
    
    torch.save({
        'X_picks': t_picks,
        'X_pick_turn': t_turns,
        'X_bans': t_bans,
        'X_mastery': t_mastery,
        'X_meta': t_meta,
        'Y_win': t_y
    }, path)
    
    print(f"[Compiler] Saved {path} | Samples: {len(t_picks)}")


def compile_dataset():
    print(f"--- TitanNet V3 Compiler (Safe Split) ---")
    print(f"Source: {DB_PATH}")
    print(f"Train Trgt: {OUTPUT_TRAIN}")
    print(f"Val Trgt:   {OUTPUT_VAL}")
    
    fe = FeatureEngine()
    if not fe.vocab:
        print("[Compiler] Warning: FeatureEngine vocab empty. Attempting to build or load...")
        pass

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    print("[Compiler] Streaming matches...")
    
    c.execute("SELECT match_id, json_data FROM matches_raw")
    
    BATCH_SIZE = 5000
    
    # Storage Lists
    train_data = {'picks': [], 'turns': [], 'bans': [], 'mast': [], 'meta': [], 'y': []}
    val_data = {'picks': [], 'turns': [], 'bans': [], 'mast': [], 'meta': [], 'y': []}
    
    count = 0
    skipped = 0
    aug_count = 0
    
    while True:
        rows = c.fetchmany(BATCH_SIZE)
        if not rows: break
        
        for mid, m_blob in rows:
            try:
                m_data = json.loads(zlib.decompress(m_blob).decode('utf-8'))
                info = m_data.get('info', {})
                parts = info.get('participants', [])
                teams = info.get('teams', [])
                
                # --- FILTER: Valid Queue ---
                queue_id = info.get('queueId', 0)
                if queue_id not in VALID_QUEUES:
                    skipped += 1
                    continue
                
                if not parts or len(parts) != 10:
                    skipped += 1 # "Invalid Participant Count"
                    continue
                
                # --- FILTER: Remakes (Short Games) ---
                duration = info.get('gameDuration', 0)
                if duration < 300: # 5 Minutes
                    skipped += 1
                    continue

                # --- 1. SPATIAL SORT (The Seating Chart) ---
                # We ignore "Turns" and "Draft Order".
                # We simply list champions by Seat (PID 1-10).
                # Sequence: [BlueTop, BlueJg, BlueMid, BlueBot, BlueSup, RedTop, RedJg, ... RedSup]
                
                # Verify PIDs are 1-10
                pids = [p.get('participantId', 0) for p in parts]
                if len(set(pids)) != 10 or min(pids) != 1 or max(pids) != 10:
                     skipped += 1 # "Invalid PIDs"
                     continue
                     
                sorted_parts = sorted(parts, key=lambda x: x['participantId'])
                
                # --- 2. EXTRACT FEATURES ---
                picks_vec = [p['championId'] for p in sorted_parts]
                turns_vec = list(range(1, 11))
                
                team_bans = {100: [], 200: []}
                for t in teams:
                    tid = t.get('teamId')
                    if tid in team_bans:
                        raw_bans = t.get('bans', [])
                        b_ids = [b['championId'] for b in raw_bans]
                        team_bans[tid] = b_ids
                
                def get_PAD_bans(b_list):
                    valid_bans = [b for b in b_list if b > 0]
                    res = valid_bans[:5]
                    while len(res) < 5: res.append(0)
                    return res
                
                bans_vec = get_PAD_bans(team_bans[100]) + get_PAD_bans(team_bans[200])
                
                mast_vec = []
                for p in sorted_parts:
                    val = 0.0
                    if 'championMastery' in p:
                        val = float(p['championMastery'])
                    elif 'summonerLevel' in p: 
                        val = float(p['summonerLevel']) * 1000 
                    val = math.log1p(val) 
                    mast_vec.append(val)
                    
                duration = info.get('gameDuration', 9999) 
                if duration < 60: duration = 60
                minutes = duration / 60.0
                
                total_cs = 0
                for p in parts: 
                    cs = p.get('totalMinionsKilled', 0) + p.get('neutralMinionsKilled', 0)
                    total_cs += cs
                
                avg_cs_min = (total_cs / 10.0) / minutes
                patch_id = parse_patch(info.get('gameVersion', '0.0'))
                
                blue_win = False
                for t in teams:
                    if t.get('teamId') == 100:
                        if t.get('win'): blue_win = True
                        break
                        
                # --- 3. SPLIT LOGIC ---
                # Deterministic split based on Match ID hash
                # Ensure same match always goes to same set, regardless of rerun
                # 10% Validation (mod 10 == 0)
                
                mid_hash = int(hashlib.md5(str(mid).encode('utf-8')).hexdigest(), 16)
                is_val = (mid_hash % 10 == 0)
                
                target_dict = val_data if is_val else train_data
                
                # --- 4. PERSPECTIVE AUGMENTATION ---
                
                # Sample 1: Blue Perspective
                meta_blue = [avg_cs_min, patch_id, 0.0]
                y_blue = 1.0 if blue_win else 0.0
                
                target_dict['picks'].append(picks_vec)
                target_dict['turns'].append(turns_vec)
                target_dict['bans'].append(bans_vec)
                target_dict['mast'].append(mast_vec)
                target_dict['meta'].append(meta_blue)
                target_dict['y'].append(y_blue)
                aug_count += 1
                
                # Sample 2: Red Perspective
                meta_red = [avg_cs_min, patch_id, 1.0]
                y_red = 1.0 if not blue_win else 0.0
                
                target_dict['picks'].append(picks_vec)
                target_dict['turns'].append(turns_vec)
                target_dict['bans'].append(bans_vec)
                target_dict['mast'].append(mast_vec)
                target_dict['meta'].append(meta_red)
                target_dict['y'].append(y_red)
                aug_count += 1
                
                count += 1
                
            except Exception as e:
                skipped += 1
                continue
                
        print(f"\r[Compiler] Compiling... Matches: {count} | Samples: {aug_count} | Skipped: {skipped}", end="")

    print(f"\n[Compiler] Done. Total Matches: {count}. Total Samples: {aug_count}. Skipped: {skipped}.")
    
    if count == 0:
        print("Error: No valid matches found.")
        return

    # SAVE
    save_tensor_dict(train_data, OUTPUT_TRAIN)
    save_tensor_dict(val_data, OUTPUT_VAL)

if __name__ == "__main__":
    compile_dataset()

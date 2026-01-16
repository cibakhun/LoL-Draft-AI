import numpy as np
import json
import os
import joblib

class FeatureEngine:
    """
    The Cortex of the Brain (Titan V3.5 Lite Edition).
    Responsibilities:
    1. Manage Vocabulary (Champion ID -> Index).
    2. Maintain DDragon Cache (Icons/Stats for UI).
    3. Transform Raw Match Data into Sequences for Transformer (TitanNet).
    """
    def __init__(self, vocab=None):
        self.vocab = vocab if vocab else {}
        self.ddragon_cache = {}
        
        # Vocabularies
        self.item_vocab = {} 
        self.rune_vocab = {} 
        
    def set_vocab(self, vocab):
        self.vocab = vocab
        
    def build_vocab(self, ddragon):
        """Builds vocab from DDragon if not already present."""
        if self.vocab: return
        try:
            all_ids = sorted([int(data['key']) for data in ddragon.champions.values()])
            # 1-Based Indexing. 0 is Valid "Empty/Unknown".
            self.vocab = {cid: i+1 for i, cid in enumerate(all_ids)}
            print(f"[CORTEX] Vocabulary Built: {len(self.vocab)} tokens.")
        except Exception as e:
            print(f"[CORTEX] Vocab Build Error: {e}")

    def build_item_vocab(self, ddragon):
        """Builds item vocab from DDragon."""
        if self.item_vocab: return
        try:
            if hasattr(ddragon, 'items'):
                all_ids = sorted([int(k) for k in ddragon.items.keys()])
                # 0 is "Empty Item"
                self.item_vocab = {iid: i+1 for i, iid in enumerate(all_ids)}
                print(f"[CORTEX] Item Vocab Built: {len(self.item_vocab)} items.")
        except Exception as e:
            print(f"[CORTEX] Item Vocab Build Error: {e}")

    def build_rune_vocab(self, ddragon):
        """Builds rune vocab (Keystones + Secondary Trees)."""
        if self.rune_vocab: return
        try:
            if hasattr(ddragon, 'runes'):
                all_runes = []
                for tree in ddragon.runes:
                    all_runes.append(int(tree['id']))
                    for slot in tree.get('slots', []):
                        for rune in slot.get('runes', []):
                            all_runes.append(int(rune['id']))
                
                sorted_ids = sorted(list(set(all_runes)))
                self.rune_vocab = {rid: i+1 for i, rid in enumerate(sorted_ids)}
                print(f"[CORTEX] Rune Vocab Built: {len(self.rune_vocab)} runes.")
        except Exception as e:
            print(f"[CORTEX] Rune Vocab Build Error: {e}")

    # --- TITAN V3.5 CORE ---
    
    def vectorize_sequence(self, blue_team, red_team, blue_turns=None, red_turns=None, training_mode=False):
        """
        Creates an ORDERED sequence of champion IDs for TitanNet.
        If blue_turns/red_turns provided (Dict[Role, Turn]), uses them to sort.
        Format: List of 10 IDs, sorted by Turn (1-10).
        
        Returns:
            draft_ids: List[int] (Length 10)
            role_ids: List[int] (Length 10) (0-4 for Blue, 0-4 for Red)
        """
        # Collect all picks with metadata
        picks = [] # (turn, team_code, role_code, cid)
        
        b_norm = self._normalize_team(blue_team)
        r_norm = self._normalize_team(red_team)
        
        roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
        
        # Deterministic / Inference Mode (Naive Heuristic)
        # Blue
        for i, r in enumerate(roles):
            cid = b_norm.get(r, 0)
            token = self.vocab.get(cid, 0)
            turn = 0
            if blue_turns and r in blue_turns:
                turn = blue_turns[r]
            else:
                # Default Assumption: Blue gets 1, 4, 5, 8, 9
                if i == 0: turn = 1
                elif i == 1: turn = 4
                elif i == 2: turn = 5
                elif i == 3: turn = 8
                elif i == 4: turn = 9
            
            picks.append({'turn': turn, 'token': token, 'role': i, 'team': 0})
            
        # Red
        for i, r in enumerate(roles):
            cid = r_norm.get(r, 0)
            token = self.vocab.get(cid, 0)
            turn = 0
            if red_turns and r in red_turns:
                turn = red_turns[r]
            else:
                # Fallback: Naive Role Order
                if i == 0: turn = 2 
                elif i == 1: turn = 3 
                elif i == 2: turn = 6 
                elif i == 3: turn = 7 
                elif i == 4: turn = 10 
                
            picks.append({'turn': turn, 'token': token, 'role': i, 'team': 1})
                
        # Sort by turn
        # [TITAN V3.5 SPATIAL FIX]
        # We REMOVE time-sorting to guarantee Spatial Order (Cell IDs 0-9).
        # Whitepaper 1.3: X is ordered by Seat (Blue Top -> Red Support).
        # picks.sort(key=lambda x: x['turn'])
        
        draft_ids = [p['token'] for p in picks]
        
        # Return Seat IDs (1-10) instead of Role IDs (0-4) 
        # to provide unique "Positional Embeddings" for all 10 players.
        # Blue: 1-5, Red: 6-10.
        spatial_seats = []
        for p in picks:
             # If team 0 (Blue): Role 0->1, 4->5
             # If team 1 (Red):  Role 0->6, 4->10
             s = p['role'] + 1
             if p['team'] == 1: s += 5
             spatial_seats.append(s)
             
        # role_ids = [p['role'] for p in picks] 
        # Used as "Turns" input in datasets.py/TitanNet
        
        # [TITAN V3.5 DYNAMIC MASKING]
        # We need the actual time-step (1-10) for mask construction, 
        # separated from spatial seat ID.
        temporal_turns = [p['turn'] for p in picks]
        
        return draft_ids, spatial_seats, temporal_turns

    def encode_timeline(self, full_timeline):
        """
        Converts raw timeline frames into a Tensor for TitanNet.
        High-Resolution Mode: Returns [T, 20] 
        Features: [P1_Gold, P1_XP ... P10_Gold, P10_XP]
        Ordered by Participant ID (1-10).
        Normalization: Gold / 1000, XP / 1000.
        """
        if not full_timeline:
            return np.zeros((1, 20)) # Single empty frame
            
        matrix = []
        for frame in full_timeline:
            p_data = frame.get('participants')
            if not p_data:
                p_data = frame.get('participantFrames')
                
            if p_data is None:
                p_data = {}
            
            row = []
            # Iterate 1 to 10
            for pid in range(1, 11):
                # PID keys are usually strings in JSON
                d = p_data.get(str(pid), {})
                if not d: d = p_data.get(pid, {})
                
                # Gold/XP keys differ in Raw vs Processed
                g = d.get('gold', d.get('totalGold', 0))
                x = d.get('xp', 0)
                
                row.append(g / 1000.0)
                row.append(x / 1000.0)
                
            if len(row) == 20: 
                matrix.append(row)
            else:
                matrix.append(np.zeros(20))
            
        return np.array(matrix)

    # --- Helpers ---
    def _normalize_team(self, team_input):
        normalized = {}
        if isinstance(team_input, list):
            roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
            for i, cid in enumerate(team_input):
                if i < 5: normalized[roles[i]] = int(cid)
        elif isinstance(team_input, dict):
            normalized = {str(k).upper(): int(v) for k, v in team_input.items()}
        return normalized

    def _build_ddragon_cache(self, ddragon):
        for name, data in ddragon.champions.items():
            try:
                key = int(data['key'])
                self.ddragon_cache[key] = data
            except: pass

    def save_state(self, path):
         state = {
             'vocab': self.vocab,
             'item_vocab': self.item_vocab,
             'rune_vocab': self.rune_vocab
         }
         joblib.dump(state, path)

    def load_state(self, path):
        if not os.path.exists(path): return False
        try:
            state = joblib.load(path)
            self.vocab = state.get('vocab', {})
            self.item_vocab = state.get('item_vocab', {})
            self.rune_vocab = state.get('rune_vocab', {})
            return True
        except: return False

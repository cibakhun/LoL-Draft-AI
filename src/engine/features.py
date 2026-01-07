import numpy as np
import json
import os
import joblib
from src.engine.schema import FeatureConfig as Cfg, RomanScaler

class FeatureEngine:
    """
    The Cortex of the Brain.
    Responsibilities:
    1. Manage Vocabulary (Champion ID -> Index).
    2. Maintain 'World Knowledge' (Winrates, Playrates, Synergies).
    3. Transform Raw Match Data into Vector Representations for Neural/Forest models.
    """
    def __init__(self, vocab=None):
        self.vocab = vocab if vocab else {}
        # Meta Stats: { cid: { role: { games, wins, timeline: {...} }, total_games } }
        self.meta_stats = {} 
        
        # Synergy Matrix: REMOVED (Scalability)
        # Counter Matrix: REMOVED (Scalability)
        # Power Spike Stats: REMOVED (Scalability)
        
        # In-Memory Timeline Stats (Approximations) so we don't rely on DB Future Data
        self.timeline_memory = {}
        
        self.ddragon_cache = {}
        
        # Vocabularies
        self.item_vocab = {} 
        self.rune_vocab = {} # Future proofing
        
        # Internal State
        self.frozen = False # If True, statistical models (Meta/Synergy) will NOT update.
        
    def set_vocab(self, vocab):
        self.vocab = vocab
        
    def set_frozen(self, frozen=True):
        """
        Freezes the 'World Knowledge' to prevent Data Leakage during training.
        When frozen, update_stats() becomes a no-op.
        """
        self.frozen = frozen
        if frozen:
            print("[CORTEX] FeatureEngine is now FROZEN. No new stats will be learned.")
        else:
            print("[CORTEX] FeatureEngine is UN-FROZEN. Learning active.")
        
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
            # DDragon items are dict of {id: data}
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
            # DDragon runesReforged is a list of trees (Domination, Precision, etc.)
            # Each tree has 'slots', each slot has 'runes'
            if hasattr(ddragon, 'runes'):
                all_runes = []
                # Traverse the trees
                for tree in ddragon.runes:
                    # Tree ID itself (e.g. 8000 for Precision) is sometimes a feature
                    all_runes.append(int(tree['id']))
                    for slot in tree.get('slots', []):
                        for rune in slot.get('runes', []):
                            all_runes.append(int(rune['id']))
                
                # Sort for deterministic index
                sorted_ids = sorted(list(set(all_runes)))
                self.rune_vocab = {rid: i+1 for i, rid in enumerate(sorted_ids)}
                print(f"[CORTEX] Rune Vocab Built: {len(self.rune_vocab)} runes.")
        except Exception as e:
            print(f"[CORTEX] Rune Vocab Build Error: {e}")

    def update_stats(self, matches):
        """
        Incrementally updates internal knowledge (Winrates, Synergies, Counters, Spikes).
        CRITICAL: This must be called AFTER prediction/training on a batch to avoid leaks.
        """
        if self.frozen: return

        # Optimization: Pre-allocate batch updates if possible
        # For now, we stick to the loop but ensure it respects 'frozen' state.
        
        for m in matches:
            # SAFETY CHECK: Do not learn from incomplete matches or validation set if flagged
            # We assume 'matches' passed here are valid for learning (Training Set).
            
            win = 1 if m['win'] else 0
            duration = m.get('duration', 0) # Seconds
            
            # 1. Update Individual Stats
            self._update_team_stats(m['blue'], win)
            self._update_team_stats(m['red'], 0 if win else 1)
            
            # Synergy/Counter/Spike updates removed for Scalability.
            # TitanNet learns these via Attention.

            # 5. Update Timeline Memory (In-Memory Approximation)
            if duration > 0:
                self._update_timeline_memory(m['blue'], win, duration, m.get('blue_gold_diff_15', 0))
                # For Red, the gold diff is inverted
                self._update_timeline_memory(m['red'], 0 if win else 1, duration, -m.get('blue_gold_diff_15', 0))

    def _update_team_stats(self, team_dict, win):
        for role, cid in team_dict.items():
            try: cid = int(cid)
            except: continue
            if cid == 0: continue
            
            if cid not in self.meta_stats:
                self.meta_stats[cid] = {'total_games': 0}
            
            self.meta_stats[cid]['total_games'] += 1
            
            if role not in self.meta_stats[cid]:
                self.meta_stats[cid][role] = {'games': 0, 'wins': 0}
            
            self.meta_stats[cid][role]['games'] += 1
            self.meta_stats[cid][role]['wins'] += win

    # Removed _update_synergy, _update_counters, _record_interaction, _update_spikes to prevent OOM

    def _update_timeline_memory(self, team_dict, win, duration, gold_diff_15=0):
        is_short = duration < 1500 # 25m
        is_long = duration > 2100 # 35m
        
        for cid in team_dict.values():
            try: cid = int(cid)
            except: continue
            if cid == 0: continue
            
            if cid not in self.timeline_memory:
                self.timeline_memory[cid] = {
                    'games': 0, 'wins': 0,
                    'short_games': 0, 'short_wins': 0, # Snowball proxy
                    'long_games': 0, 'long_wins': 0,    # Scaling proxy
                    'total_gold_diff_15': 0, 'gold_diff_count': 0
                }
            
            s = self.timeline_memory[cid]
            s['games'] += 1
            s['wins'] += win
            
            if is_short:
                s['short_games'] += 1
                s['short_wins'] += win
                
            if is_long:
                s['long_games'] += 1
                s['long_wins'] += win
            
            if gold_diff_15 != 0:
                s['total_gold_diff_15'] += gold_diff_15
                s['gold_diff_count'] += 1

    def vectorize(self, blue_team, red_team, ddragon=None, update_scalars=False, training_mode=False):
        """
        Main Vectorization Entry Point.
        Returns: 
         - flat_vec: Numpy array (High Dim)
         - neural_payload: Tuple (blue_ids, red_ids, meta_vec)
        """
        if ddragon and not self.ddragon_cache:
            self._build_ddragon_cache(ddragon)

        b_norm = self._normalize_team(blue_team)
        r_norm = self._normalize_team(red_team)
        
        # --- Neural Payload ---
        b_ids = self._get_id_list(b_norm)
        r_ids = self._get_id_list(r_norm)
        
        # Use FeatureConfig for Size
        meta_vec = np.zeros(Cfg.TOTAL_DIM)
        
        # 1. Comp Stats
        self._fill_comp_stats(b_norm, meta_vec, Cfg.BLUE_COMP_START)
        self._fill_comp_stats(r_norm, meta_vec, Cfg.RED_COMP_START)
        
        # 2. Context Stats (Winrates etc)
        self._fill_context_stats(b_norm, meta_vec, Cfg.BLUE_CONTEXT_START)
        self._fill_context_stats(r_norm, meta_vec, Cfg.RED_CONTEXT_START)
        
        # 3. Synergy
        self._fill_synergy_stats(b_norm, meta_vec, Cfg.BLUE_SYNERGY_START)
        self._fill_synergy_stats(r_norm, meta_vec, Cfg.RED_SYNERGY_START)
        
        # 4. Spikes
        self._fill_spike_stats(b_norm, meta_vec, Cfg.BLUE_SPIKE_START)
        self._fill_spike_stats(r_norm, meta_vec, Cfg.RED_SPIKE_START)
        
        # 5. Counters
        self._fill_counter_stats(b_norm, r_norm, meta_vec, Cfg.COUNTER_START)

        # 6. Timeline
        self._fill_timeline_stats(b_norm, meta_vec, Cfg.BLUE_TIMELINE_START, training_mode)
        self._fill_timeline_stats(r_norm, meta_vec, Cfg.RED_TIMELINE_START, training_mode)
        
        # --- DEEP CORRECTNESS: SCALING ---
        # Fixed Roman Scaler
        RomanScaler.scale(meta_vec)
        
        neural_payload = (b_ids, r_ids, meta_vec)
        
        # --- Flat Vector ---
        vocab_size = max(self.vocab.values()) + 1 if self.vocab else 170
        stride = vocab_size
        input_size = (stride * 10) + Cfg.TOTAL_DIM
        
        flat_vec = np.zeros(input_size)
        
        role_map = {"TOP": 0, "JUNGLE": 1, "MIDDLE": 2, "BOTTOM": 3, "UTILITY": 4}
        
        for role, cid in b_norm.items():
            if role in role_map:
                idx = (role_map[role] * stride) + self.vocab.get(cid, 0)
                if idx < input_size: flat_vec[idx] = 1
                
        for role, cid in r_norm.items():
            if role in role_map:
                idx = ((role_map[role] + 5) * stride) + self.vocab.get(cid, 0)
                if idx < input_size: flat_vec[idx] = 1
                
        flat_vec[-Cfg.TOTAL_DIM:] = meta_vec
        
        return flat_vec, neural_payload

    def _fill_timeline_stats(self, team_norm, vec, start_idx, training_mode=False):
        """
        Extracts Temporal DNA.
        """
        gold_diffs = []
        snowball_rates = []
        comeback_rates = []
        
        for role, cid in team_norm.items():
            s_snow = 0.5
            s_come = 0.5
            
            # Use Memory (Consistent for Train/Infer mainly)
            if cid in self.timeline_memory:
                mem = self.timeline_memory[cid]
                if mem['short_games'] > 0:
                    s_snow = mem['short_wins'] / mem['short_games']
                if mem['long_games'] > 0:
                    s_come = mem['long_wins'] / mem['long_games']
            
            snowball_rates.append(s_snow)
            comeback_rates.append(s_come)
            
            # Get Gold Diff Avg
            avg_g_diff = 0
            if cid in self.timeline_memory:
                mem = self.timeline_memory[cid]
                if mem.get('gold_diff_count', 0) > 0:
                    avg_g_diff = mem['total_gold_diff_15'] / mem['gold_diff_count']

            gold_diffs.append(avg_g_diff)

        # 0: Tempo (Gold Diff)
        avg_gold_diff = sum(gold_diffs) / 5.0
        vec[start_idx + Cfg.IDX_TEMPO] = avg_gold_diff 
        
        # 1: Snowball
        vec[start_idx + Cfg.IDX_SNOWBALL] = sum(snowball_rates) / 5.0
        
        # 2: Comeback
        vec[start_idx + Cfg.IDX_COMEBACK] = sum(comeback_rates) / 5.0

    def _fill_comp_stats(self, team_norm, vec, start_idx):
        if not self.ddragon_cache: return
        # Working array
        stats = np.zeros(15)
        count = 0
        total_atk = 0; total_mag = 0
        
        for cid in team_norm.values():
            c_data = self.ddragon_cache.get(cid)
            if not c_data: continue
            
            info = c_data.get('info', {})
            roles = c_data.get('roles', [])
            count += 1
            atk = info.get('attack', 0); mag = info.get('magic', 0); defn = info.get('defense', 0)
            total_atk += atk; total_mag += mag
            
            stats[Cfg.IDX_ATK] += atk
            stats[Cfg.IDX_MAG] += mag
            stats[Cfg.IDX_DEF] += defn
            stats[Cfg.IDX_DIFF] += info.get('difficulty', 0)
            
            if "Fighter" in roles: stats[Cfg.IDX_FIGHTER] += 1
            if "Tank" in roles: stats[Cfg.IDX_TANK] += 1; stats[Cfg.IDX_TANKINESS] += 2
            if "Mage" in roles: stats[Cfg.IDX_MAGE] += 1; stats[Cfg.IDX_CARRY_SCORE] += 2
            if "Assassin" in roles: stats[Cfg.IDX_ASSASSIN] += 1
            if "Marksman" in roles: stats[Cfg.IDX_MARKSMAN] += 1; stats[Cfg.IDX_CARRY_SCORE] += 3
            if "Support" in roles: stats[Cfg.IDX_SUPPORT] += 1; stats[Cfg.IDX_TANKINESS] += 1
        
        if count > 0:
            for i in [Cfg.IDX_ATK, Cfg.IDX_MAG, Cfg.IDX_DEF, Cfg.IDX_DIFF]:
                stats[i] /= count
            
            total_dmg = total_atk + total_mag
            if total_dmg > 0:
                stats[Cfg.IDX_DMG_PHYS] = total_atk / total_dmg
                stats[Cfg.IDX_DMG_MAGIC] = total_mag / total_dmg
        
        # Copy to vec
        vec[start_idx : start_idx+15] = stats

    def _fill_context_stats(self, team_norm, vec, start_idx):
        roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
        for i, r in enumerate(roles):
            cid = team_norm.get(r, 0)
            freq = 0.0; wr = 0.50
            
            if cid in self.meta_stats:
                stats = self.meta_stats[cid]
                total = stats.get('total_games', 0)
                r_stats = stats.get(r, {'games':0, 'wins':0})
                
                if total > 0: freq = r_stats['games'] / total
                if r_stats['games'] > 0:
                    wr = (r_stats['wins'] + 5.0) / (r_stats['games'] + 10.0)
            
            vec[start_idx + (i*2)] = freq
            vec[start_idx + (i*2) + 1] = wr

    # Updated helpers to return defaults (Legacy Support)
    
    def _fill_synergy_stats(self, team_norm, vec, start_idx):
        # PURE LEARNING: Heuristics Removed.
        # TitanNet learns synergy via Attention.
        # We fill with 0.0 (Neutral/Empty) to preserve schema shape.
        vec[start_idx : start_idx+5] = 0.0

    def _fill_spike_stats(self, team_norm, vec, start_idx):
        # Simple Early vs Late heuristic based on winrates by game time (if available)
        # For now, default to mid-game
        vec[start_idx] = 0.5   # Early
        vec[start_idx+1] = 0.5 # Mid
        vec[start_idx+2] = 0.5 # Late

    def _fill_counter_stats(self, b_team, r_team, vec, start_idx):
        # PURE LEARNING: Heuristics Removed.
        # Counters are complex and context-dependent.
        # We let the model learn P(Win | P1, P2...).
        vec[start_idx : start_idx+5] = 0.0

    def _get_wr(self, data):
        g, w = data['games'], data['wins']
        if g < 5: return 0.5 
        return (w + 2.0) / (g + 4.0)

    # --- TITAN V2 FEATURES ---
    
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
        
        if training_mode:
             # Reverting Stochastic Shuffle based on User Architecture Review.
             # We stick to the Naive Heuristic (Spatial = Role) to preserve "Lane Matchups".
             # The MCTS will handle the temporal search; the Brain learns the Spatial Board.
             pass

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
                # This is a naive heuristic for legacy data
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
                if i == 0: turn = 2 # Top
                elif i == 1: turn = 3 # Jg
                elif i == 2: turn = 6 # Mid
                elif i == 3: turn = 7 # Bot
                elif i == 4: turn = 10 # Sup
                
            picks.append({'turn': turn, 'token': token, 'role': i, 'team': 1})
                

            
        # Sort by turn
        # If turns are all 0 (legacy), this sort might be unstable or result in role order.
        # We want to fallback to role order if turns are missing.
        # But if we used the heuristic above, we have turns.
        
        picks.sort(key=lambda x: x['turn'])
        
        draft_ids = [p['token'] for p in picks]
        role_ids = [p['role'] for p in picks] # Note: This loses Team info if we don't have team embedding?
        # TitanNet has pos_embedding (1-10) which implicitly encodes team order.
        # But it also has role_embedding.
        
        return draft_ids, role_ids

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
            # Frame has 'participants' dict: {pid_str: {gold, xp, dmg}}
            # OR 'participantFrames' (Raw Riot API)
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
                # Processed: 'gold', 'xp'
                # Raw: 'totalGold', 'xp'
                g = d.get('gold', d.get('totalGold', 0))
                x = d.get('xp', 0)
                
                row.append(g / 1000.0)
                row.append(x / 1000.0)
                
            if len(row) == 20: 
                matrix.append(row)
            else:
                # Should not happen if loop logic is correct
                matrix.append(np.zeros(20))
            
        return np.array(matrix)

    # --- Boilerplate Helpers ---
    def _normalize_team(self, team_input):
        normalized = {}
        if isinstance(team_input, list):
            roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
            for i, cid in enumerate(team_input):
                if i < 5: normalized[roles[i]] = int(cid)
        elif isinstance(team_input, dict):
            normalized = {str(k).upper(): int(v) for k, v in team_input.items()}
        return normalized

    def _get_id_list(self, team_norm):
        roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
        return [self.vocab.get(team_norm.get(r, 0), 0) for r in roles]

    def _build_ddragon_cache(self, ddragon):
        for name, data in ddragon.champions.items():
            try:
                key = int(data['key'])
                self.ddragon_cache[key] = data
            except: pass

    def save_state(self, path):
         state = {
             'vocab': self.vocab,
             'meta_stats': self.meta_stats,
             'timeline_memory': self.timeline_memory,
             'item_vocab': self.item_vocab,
             'rune_vocab': self.rune_vocab
         }
         joblib.dump(state, path)

    def load_state(self, path):
        if not os.path.exists(path): return False
        try:
            state = joblib.load(path)
            self.vocab = state.get('vocab', {})
            self.meta_stats = state.get('meta_stats', {})
            self.meta_stats = state.get('meta_stats', {})
            # Legacy fields ignored for load to enforce leanness
            # Legacy fields ignored for load to enforce leanness
            self.timeline_memory = state.get('timeline_memory', {})
            self.item_vocab = state.get('item_vocab', {})
            self.rune_vocab = state.get('rune_vocab', {})
            return True
        except: return False

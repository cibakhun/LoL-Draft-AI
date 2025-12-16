import numpy as np
import json
import os
import joblib

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
        
        # Synergy Matrix: { cid1: { cid2: { games, wins } } } (Teammates)
        self.synergy_matrix = {}
        
        # Counter Matrix: { cid1: { cid2: { games, wins } } } (Opponents)
        # Tracks how cid1 performs AGAINT cid2
        self.counter_matrix = {}
        
        # Power Spike Stats: { cid: { 'early': {g,w}, 'mid': {g,w}, 'late': {g,w} } }
        self.spike_stats = {}
        
        self.ddragon_cache = {}
        
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

    def update_stats(self, matches):
        """
        Incrementally updates internal knowledge (Winrates, Synergies, Counters, Spikes).
        CRITICAL: This must be called AFTER prediction/training on a batch to avoid leaks.
        """
        for m in matches:
            win = 1 if m['win'] else 0
            duration = m.get('duration', 0) # Seconds
            
            # 1. Update Individual Stats
            self._update_team_stats(m['blue'], win)
            self._update_team_stats(m['red'], 0 if win else 1)
            
            # 2. Update Synergy (Duo) Stats
            self._update_synergy(m['blue'], win)
            self._update_synergy(m['red'], 0 if win else 1)
            
            # 3. Update Counter Stats (Blue vs Red)
            self._update_counters(m['blue'], m['red'], win)
            
            # 4. Update Power Spikes
            if duration > 0:
                self._update_spikes(m['blue'], win, duration)
                self._update_spikes(m['red'], 0 if win else 1, duration)

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

    def _update_synergy(self, team_dict, win):
        """Updates O(N^2) synergy matrix for the team."""
        cids = []
        for r, c in team_dict.items():
            try: cids.append(int(c))
            except: pass
            
        for i in range(len(cids)):
            for j in range(i+1, len(cids)):
                c1, c2 = cids[i], cids[j]
                if c1 == 0 or c2 == 0: continue
                
                self._record_interaction(self.synergy_matrix, c1, c2, win)
                self._record_interaction(self.synergy_matrix, c2, c1, win)

    def _update_counters(self, blue_dict, red_dict, blue_win):
        """
        Updates Counter Matrix.
        Blue Win = 1 -> Blue Champs get 'Win' vs Red Champs.
        """
        b_cids = [int(c) for c in blue_dict.values() if int(c) != 0]
        r_cids = [int(c) for c in red_dict.values() if int(c) != 0]
        
        # Cross Product
        for b in b_cids:
            for r in r_cids:
                # Record Blue vs Red
                self._record_interaction(self.counter_matrix, b, r, blue_win)
                # Record Red vs Blue (inverse result)
                self._record_interaction(self.counter_matrix, r, b, 0 if blue_win else 1)

    def _record_interaction(self, matrix, c1, c2, win):
        if c1 not in matrix: matrix[c1] = {}
        if c2 not in matrix[c1]: matrix[c1][c2] = {'games': 0, 'wins': 0}
        
        matrix[c1][c2]['games'] += 1
        matrix[c1][c2]['wins'] += win

    def _update_spikes(self, team_dict, win, duration):
        # Buckets: Early (<25m), Mid (25-35m), Late (>35m)
        bucket = 'early'
        if duration > 2100: bucket = 'late'
        elif duration > 1500: bucket = 'mid'
        
        for cid in team_dict.values():
            cid = int(cid)
            if cid == 0: continue
            
            if cid not in self.spike_stats:
                self.spike_stats[cid] = {
                    'early': {'games': 0, 'wins': 0},
                    'mid': {'games': 0, 'wins': 0},
                    'late': {'games': 0, 'wins': 0}
                }
            
            self.spike_stats[cid][bucket]['games'] += 1
            self.spike_stats[cid][bucket]['wins'] += win

    def vectorize(self, blue_team, red_team, ddragon=None):
        """
        Main Vectorization Entry Point. (Deep Update)
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
        
        # Meta Features: 72 Dimensions
        # 0-14: Blue Comp (15)
        # 15-29: Red Comp (15)
        # 30-39: Blue Role Mastery (10)
        # 40-49: Red Role Mastery (10)
        # 50-54: Blue Synergy (5)
        # 55-59: Red Synergy (5)
        # 60-62: Blue Power Spike (3)
        # 63-65: Red Power Spike (3)
        # 66-70: Lane Counters (5)
        # 71: Team Counter Score (1)
        # NEW (Project Chronos): 10 Dimensions
        # 72-76: Blue Timeline (Tempo, Snowball, Comeback, EarlyLead, Diff)
        # 77-81: Red Timeline
        
        meta_vec = np.zeros(82) # INCREASED DIMENSION
        
        self._fill_comp_stats(b_norm, meta_vec, 0)
        self._fill_comp_stats(r_norm, meta_vec, 15)
        
        self._fill_context_stats(b_norm, meta_vec, 30)
        self._fill_context_stats(r_norm, meta_vec, 40)
        
        self._fill_synergy_stats(b_norm, meta_vec, 50)
        self._fill_synergy_stats(r_norm, meta_vec, 55)
        
        # Power Spikes
        self._fill_spike_stats(b_norm, meta_vec, 60)
        self._fill_spike_stats(r_norm, meta_vec, 63)
        
        self._fill_counter_stats(b_norm, r_norm, meta_vec, 66)

        # Timeline Stats
        self._fill_timeline_stats(b_norm, meta_vec, 72)
        self._fill_timeline_stats(r_norm, meta_vec, 77)
        
        # --- DEEP CORRECTNESS: SCALING ---
        # Neural Networks struggle with mixed scales (e.g. 0.5 vs 40.0).
        # We perform hard normalization to [0, 1] range based on theoretical max values.
        self._scale_meta_features(meta_vec)
        
        neural_payload = (b_ids, r_ids, meta_vec)
        
        # --- Flat Vector ---
        vocab_size = max(self.vocab.values()) + 1 if self.vocab else 170
        stride = vocab_size
        vocab_size = max(self.vocab.values()) + 1 if self.vocab else 170
        stride = vocab_size
        input_size = (stride * 10) + 82 # INCREASED
        
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
                
        flat_vec[-82:] = meta_vec
        
        return flat_vec, neural_payload

    def _scale_meta_features(self, vec):
        """
        Scales the 72-dim meta vector to roughly [0, 1].
        """
        # Blue (0-14) and Red (15-29)
        for base in [0, 15]:
            # 0-3: Sums (Atk, Mag, Def, Diff). Max ~50.
            vec[base+0] /= 50.0
            vec[base+1] /= 50.0
            vec[base+2] /= 50.0
            vec[base+3] /= 50.0
            
            # 4-9: Class Counts. Max 5.
            for i in range(4, 10):
                vec[base+i] /= 5.0
                
            # 10-11: Ratios (Already 0-1)
            
            # 12: Unused (Reserved)
            
            # 13: Tank Score (Max ~15). 5 Tanks * 3 ? Code says Tank+2, Supp+1. Max 5*2 = 10.
            vec[base+13] /= 15.0
            
            # 14: Carry Score. Mage+2, Marksman+3. Max 5*3 = 15.
            vec[base+14] /= 15.0

            # 14: Carry Score. Mage+2, Marksman+3. Max 5*3 = 15.
            vec[base+14] /= 15.0

        # 30-71 are already Winrates/Frequencies (0-1)
        
        # 72-81: Timeline Metrics
        # Tempo (Gold Diff) is usually -2000 to +2000. Scale by 2000.
        for i in [72, 76, 77, 81]: # Indices of Gold/Diff if aligned? 
            # Actually indices are:
            # 72, 73, 74, 75, 76 (Blue)
            # 77, 78, 79, 80, 81 (Red)
            # 0=Tempo(Gold), 1=Snowball, 2=Comeback, 3=Leads, 4=XP/Diff
            pass # We handle scaling inside _fill_timeline_stats for clarity

    def _fill_timeline_stats(self, team_norm, vec, start_idx):
        """
        Extracts Temporal DNA.
        0: Avg Tempo (Gold@15) - Scaled / 2000
        1: Snowball Efficiency (Winrate when Ahead)
        2: Comeback Potential (Winrate when Behind)
        3: Early Game Aggression (Frequency of Lead@15)
        4: Lane Dominance (XP Diff) - Scaled / 1000
        """
        gold_diffs = []
        snowball_rates = []
        comeback_rates = []
        lead_freqs = []
        xp_diffs = []
        
        for role, cid in team_norm.items():
            if cid in self.meta_stats and role in self.meta_stats[cid]:
                s = self.meta_stats[cid][role].get('timeline', {})
                gold_diffs.append(s.get('avg_gold_15', 0))
                snowball_rates.append(s.get('snowball_rate', 0.5))
                comeback_rates.append(s.get('comeback_rate', 0.5))
                
                # Check raw games to calc lead freq?
                # We need leads / total_games
                if 'total_games' in self.meta_stats[cid]: # total_games is at cid level
                     # Actually we need role level total
                     g = self.meta_stats[cid][role].get('games', 1)
                     # But we don't have 'early_leads' count easily here unless we fetched it
                     # For now use defaults or 0.5
                     lead_freqs.append(0.5) 
                else: 
                     lead_freqs.append(0.5)
                     
                xp_diffs.append(s.get('avg_xp_15', 0))
            else:
                gold_diffs.append(0); snowball_rates.append(0.5); comeback_rates.append(0.5)
                lead_freqs.append(0.5); xp_diffs.append(0)
                
        # 0: Tempo
        vec[start_idx] = (sum(gold_diffs) / 5.0) / 1000.0 # Normalize 1000 gold avg diff
        
        # 1: Snowball
        vec[start_idx+1] = sum(snowball_rates) / 5.0
        
        # 2: Comeback
        vec[start_idx+2] = sum(comeback_rates) / 5.0
        
        # 3: Aggression (Leads)
        # Placeholder for now
        vec[start_idx+3] = 0.5
        
        # 4: Lane Dom
        vec[start_idx+4] = (sum(xp_diffs) / 5.0) / 500.0


    def _fill_spike_stats(self, team_norm, vec, start_idx):
        # 3 Buckets: Avg Winrate of team in Early, Mid, Late
        avg_early, avg_mid, avg_late = [], [], []
        
        for cid in team_norm.values():
            if cid in self.spike_stats:
                s = self.spike_stats[cid]
                avg_early.append(self._get_wr(s['early']))
                avg_mid.append(self._get_wr(s['mid']))
                avg_late.append(self._get_wr(s['late']))
            else:
                # Default 0.5
                avg_early.append(0.5); avg_mid.append(0.5); avg_late.append(0.5)
                
        vec[start_idx] = sum(avg_early) / 5.0
        vec[start_idx+1] = sum(avg_mid) / 5.0
        vec[start_idx+2] = sum(avg_late) / 5.0

    def _fill_counter_stats(self, b_team, r_team, vec, start_idx):
        """
        Calculates how much Blue counters Red.
        > 0.5 means Blue has advantage.
        """
        roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
        
        # 1. Lane Counters (0-4)
        for i, r in enumerate(roles):
            bc = b_team.get(r, 0)
            rc = r_team.get(r, 0)
            
            wr = 0.5
            if bc in self.counter_matrix and rc in self.counter_matrix[bc]:
                 wr = self._get_wr(self.counter_matrix[bc][rc])
            
            vec[start_idx + i] = wr
            
        # 2. Team Counter (Average of all cross interactions)
        # This is expensive (25 lookups), but valuable.
        cross_wins = []
        for bc in b_team.values():
            for rc in r_team.values():
                if bc in self.counter_matrix and rc in self.counter_matrix[bc]:
                    cross_wins.append(self._get_wr(self.counter_matrix[bc][rc]))
        
        vec[start_idx + 5] = sum(cross_wins) / len(cross_wins) if cross_wins else 0.5

    def _get_wr(self, data):
        g, w = data['games'], data['wins']
        if g < 5: return 0.5 # Smoothing threshold
        return (w + 2.0) / (g + 4.0)

    # --- Boilerplate Helpers (Keep existing logic) ---
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

    def _fill_comp_stats(self, team_norm, vec, start_idx):
        if not self.ddragon_cache: return
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
            
            stats[0] += atk
            stats[1] += mag
            stats[2] += defn
            stats[3] += info.get('difficulty', 0)
            
            if "Fighter" in roles: stats[4] += 1
            if "Tank" in roles: stats[5] += 1; stats[13] += 2
            if "Mage" in roles: stats[6] += 1; stats[14] += 2
            if "Assassin" in roles: stats[7] += 1
            if "Marksman" in roles: stats[8] += 1; stats[14] += 3
            if "Support" in roles: stats[9] += 1; stats[13] += 1
        
        if count > 0:
            for i in range(4): stats[i] /= count
            total_dmg = total_atk + total_mag
            if total_dmg > 0:
                stats[10] = total_atk / total_dmg
                stats[11] = total_mag / total_dmg
        
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

    def _fill_synergy_stats(self, team_norm, vec, start_idx):
        pairs = []
        cids = [team_norm.get(r, 0) for r in ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]]
        
        for i in range(5):
            for j in range(i+1, 5):
                c1, c2 = cids[i], cids[j]
                if c1 == 0 or c2 == 0: continue
                pairs.append(self._get_synergy_score(c1, c2))
                
        avg_syn = sum(pairs) / len(pairs) if pairs else 0.5
        max_syn = max(pairs) if pairs else 0.5
        
        vec[start_idx] = avg_syn
        vec[start_idx+1] = max_syn
        vec[start_idx+2] = self._get_synergy_score(cids[3], cids[4]) # Bot
        vec[start_idx+3] = self._get_synergy_score(cids[2], cids[1]) # Mid-Jg
        vec[start_idx+4] = self._get_synergy_score(cids[0], cids[1]) # Top-Jg

    def _get_synergy_score(self, c1, c2):
        if c1 in self.synergy_matrix and c2 in self.synergy_matrix[c1]:
            game_data = self.synergy_matrix[c1][c2]
            return self._get_wr(game_data)
        return 0.5

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
             'synergy_matrix': self.synergy_matrix,
             'counter_matrix': self.counter_matrix,
             'spike_stats': self.spike_stats
         }
         joblib.dump(state, path)

    def load_state(self, path):
        if not os.path.exists(path): return False
        try:
            state = joblib.load(path)
            self.vocab = state.get('vocab', {})
            self.meta_stats = state.get('meta_stats', {})
            self.synergy_matrix = state.get('synergy_matrix', {})
            self.counter_matrix = state.get('counter_matrix', {})
            self.spike_stats = state.get('spike_stats', {})
            return True
        except: return False

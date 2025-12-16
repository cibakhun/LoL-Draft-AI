import json
import os

class TimelineEngine:
    """
    Project Chronos: The Time Lord.
    Extracts 'Temporal DNA' from Match Timelines.
    """
    def __init__(self):
        pass

    def process_timeline(self, match_id, timeline_data, participants):
        """
        Extracts metrics for each player in the match.
        participants: List of {puuid, championId, teamPosition, win, teamId}
        
        Returns: List of entry dicts for DB update.
        """
        frames = timeline_data.get('info', {}).get('frames', [])
        if not frames: return []
        
        # 1. Temporal Snapshot @ 15m
        target_frame_idx = 15
        if len(frames) <= target_frame_idx:
            target_frame_idx = len(frames) - 1 # Use last frame if game ended early
            
        snapshot = frames[target_frame_idx]
        p_frames = snapshot.get('participantFrames', {})
        
        # Map participantId (1-10) to Info
        # Participants list usually has 'participantId' inside it or we deduce it from order?
        # Riot API: participants is list, index 0 is participantId 1.
        
        entries = []
        
        # Calculate Team Totals for Normalization
        blue_gold = 0
        red_gold = 0
        
        pid_map = {} # pid -> {gold, xp}
        
        for pid_str, data in p_frames.items():
            pid = int(pid_str)
            gold = data.get('totalGold', 0)
            xp = data.get('xp', 0)
            pid_map[pid] = {'gold': gold, 'xp': xp}
            
            if pid <= 5: blue_gold += gold
            else: red_gold += gold
        
        # Global Avg
        game_avg_gold = (blue_gold + red_gold) / 10.0
        
        for i, p in enumerate(participants):
            pid = i + 1
            if pid not in pid_map: continue
            
            stats = pid_map[pid]
            cid = p.get('championId')
            role = p.get('teamPosition')
            win = p.get('win')
            team = p.get('teamId')
            
            # 2. Metrics Calculation
            
            # A. Tempo (Gold Diff from Game Avg)
            # This shows if they are richer than everyone else at 15m
            gold_diff = stats['gold'] - game_avg_gold
            
            # B. XP Tempo
            # XP diff from lane opponent would be better, but global avg is a decent proxy for "Roaming vs Farming"
            # Actually, let's just stick to raw XP for now, or Diff from Dual laner?
            # Global avg XP
            # xp_diff = stats['xp'] - (blue_xp + red_xp)/10 
            # Simplified: just raw gold_diff for persistence
            
            # C. Snowball / Comeback Context
            # Did they have a lead?
            # We define 'Lead' as > 500 gold above opponent or > 10% above game average
            opponent_pid = pid + 5 if pid <= 5 else pid - 5
            opp_stats = pid_map.get(opponent_pid, {'gold': stats['gold']})
            
            lane_diff = stats['gold'] - opp_stats['gold']
            
            is_lead = lane_diff > 500
            
            entries.append({
                'cid': cid,
                'role': role,
                'gold_diff': int(gold_diff),
                'xp_diff': int(lane_diff), # Storing Lane Diff in XP column for now (Change schema later if strictly XP needed)
                'is_lead': is_lead,
                'is_win': win
            })
            
        return entries

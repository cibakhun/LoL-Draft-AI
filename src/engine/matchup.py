class MatchupEngine:
    def __init__(self):
        pass
        
    def analyze_matchup(self, my_champ_name, enemy_champ_name, ddragon_champs):
        """
        Compares two champions mathematically.
        Returns a list of strategic tips.
        """
        tips = []
        
        my_info = ddragon_champs.get(my_champ_name)
        enemy_info = ddragon_champs.get(enemy_champ_name)
        
        if not my_info or not enemy_info:
            return tips
            
        my_stats = my_info.get('stats', {})
        enemy_stats = enemy_info.get('stats', {})
        
        # 1. Range Analysis (The most critical fundamental)
        my_range = my_stats.get('attackrange', 0)
        enemy_range = enemy_stats.get('attackrange', 0)
        
        range_delta = my_range - enemy_range
        
        if range_delta > 50:
            tips.append(f"RANGE ADVANTAGE: You have +{range_delta} range. Poke with auto-attacks safely.")
        elif range_delta < -50:
            tips.append(f"RANGE DISADVANTAGE: Enemy has +{abs(range_delta)} range. Concede CS to save HP.")
            
        # 2. Level 1 Stat Check (HP/Armor)
        my_hp = my_stats.get('hp', 0)
        enemy_hp = enemy_stats.get('hp', 0)
        
        if my_hp > enemy_hp + 60:
            tips.append(f"STAT CHECK: You have +{my_hp - enemy_hp} Base HP. You win the Level 1 all-in.")
        elif enemy_hp > my_hp + 60:
            tips.append(f"CAUTION: Enemy has significant HP advantage. Do not force trades early.")
            
        # 3. Mobility Check (Move Speed)
        my_ms = my_stats.get('movespeed', 0)
        enemy_ms = enemy_stats.get('movespeed', 0)
        
        if my_ms > enemy_ms + 5:
            tips.append(f"MOBILITY: You are faster (+{my_ms - enemy_ms} MS). Look for extended trades.")
            
        return tips

class MetaEngine:
    def __init__(self):
        self.champion_stats = {} # Populated dynamically
        self.counters = {
            "Malphite": ["Sylas", "Mordekaiser", "Ahri"],
            "Zed": ["Lissandra", "Malphite"],
            "Yasuo": ["Renekton", "Pantheon"],
            "Yone": ["Vex", "Zed"],
        }
        self.synergies = {
            ("Lee Sin", "Ahri"): 0.8,
            ("Leona", "Kaisa"): 0.9,
            ("Lulu", "Jinx"): 0.95,
        }
        
        # Advanced Synergy Clusters (The "Wombo Combos")
        self.clusters = {
            "Knockup": ["Malphite", "Yasuo", "Yone", "Alistar", "Ornn", "Lee Sin", "Rakan"],
            "Protect": ["Lulu", "Janna", "KogMaw", "Jinx", "Yuumi", "Soraka"],
            "Dive": ["Zed", "Kaisa", "Leona", "Nautilus", "Jarvan IV", "Camille"]
        }

    def get_cluster_synergy_score(self, champion, my_team):
        """
        Detects if the champion fits into an active team cluster.
        Returns a multiplier bonus (e.g. 1.2x).
        """
        bonus = 1.0
        
        # Check Knockups (Yasuo Rule)
        if champion == "Yasuo" or champion == "Yone":
            knockups = sum(1 for ally in my_team if ally in self.clusters["Knockup"])
            if knockups >= 2:
                bonus += 0.25 # Huge bonus for Yasuo + 2 Knockups
                
        # Check if Champion IS a Knockup provider for a Yasuo ally
        if champion in self.clusters["Knockup"]:
            has_yasou = any(ally in ["Yasuo", "Yone"] for ally in my_team)
            if has_yasou:
                bonus += 0.15
                
        # Check Protect (Hypercarry Rule)
        if champion in self.clusters["Protect"]:
            # If I am a protector, do I have a carry?
            # If I am a carry, do I have a protector?
            friends = sum(1 for ally in my_team if ally in self.clusters["Protect"])
            if friends >= 1:
                bonus += 0.1
                
        return bonus

    def update_meta_from_ddragon(self, ddragon_champs):
        """
        Hydrates the meta engine with all champions.
        Since we don't have a live scraper, we will simulate realistic tiers.
        """
        # 1. Default everyone to Tier B / 50% WR
        for name in ddragon_champs:
            self.champion_stats[name] = {"winrate": 0.50, "tier": "B"}
            
        # 2. Inject "Mock" Meta (Current Patch Simulation)
        op_champs = ["Ahri", "Lee Sin", "Kaisa", "Jinx", "Thresh", "Lux", "Zed", 
                     "Darius", "Mordekaiser", "Viego", "Hecarim", "Miss Fortune", 
                     "Nautilus", "Blitzcrank", "Yone", "Sylas", "Caitlyn"]
        
        for op in op_champs:
            if op in self.champion_stats:
                self.champion_stats[op] = {"winrate": 0.53, "tier": "S"}
                
        print(f"[META] Hydrated meta for {len(self.champion_stats)} champions.")
        
        self.synergies = {
            ("Lee Sin", "Ahri"): 0.8, # Jungle-Mid synergy score
            ("Leona", "Kaisa"): 0.9,
        }

    def get_meta_score(self, champion_name):
        """Returns a normalized meta score (0-100)."""
        stats = self.champion_stats.get(champion_name)
        if not stats:
            return 50 # Average if unknown
        
        # Simple formula: Winrate * 100 + Tier Bonus
        base_score = stats["winrate"] * 100
        if stats["tier"] == "S":
            base_score += 10
        elif stats["tier"] == "A":
            base_score += 5
            
        return min(100, base_score)

    def get_counter_score(self, my_pick, enemy_team):
        """
        Calculates how well my_pick counters the enemy team.
        Returns a score 0-100.
        """
        score = 50
        # If my_pick is a known counter to anyone in enemy_team, boost score
        # Ideally this uses a full matrix.
        # Check if my_pick is good vs any enemy
        # This is a simplified "Reversed" check for the MVP
        # Does my_pick appear in counters list of enemies?
        
        for enemy in enemy_team:
            enemy_counters = self.counters.get(enemy, [])
            if my_pick in enemy_counters:
                score += 20 # Hard counter bonus
        
        return min(100, score)
    
    def get_synergy_score(self, my_pick, my_team):
        """
        Calculates synergy with existing teammates.
        """
        score = 50
        for ally in my_team:
            # Check pair
            pair_score = self.synergies.get((ally, my_pick)) or self.synergies.get((my_pick, ally))
            if pair_score:
                score += (pair_score * 20) # Boost based on synergy
                
        return min(100, score)

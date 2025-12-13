from src.engine.matchup import MatchupEngine

class GameplanGenerator:
    def __init__(self):
        self.matchup_engine = MatchupEngine()

    def generate_plan(self, my_champion, enemy_team, my_role, ddragon_data=None):
        """
        Generates a text-based gameplan.
        Now uses DDragon roles to give class-specific advice + Mathematical Matchup Analysis.
        """
        plan = []
        
        # 1. Identify My Class
        my_roles = []
        if ddragon_data and my_champion in ddragon_data:
            my_roles = ddragon_data[my_champion]['roles'] # e.g. ["Mage", "Assassin"]
            
        plan.append(f"Analyzed Role: {', '.join(my_roles)} ({my_role})")
        
        # 2. Determine Lane Opponent (Heuristic)
        # We need to guess who plays the same role. 
        # Ideally, we get this from LCU, but enemy team positions aren't always clear there.
        # We scan ddragon for enemies with matching 'my_role' tag?
        # Simplified: We look for the enemy that is MOST likely to be in my lane.
        
        lane_opponent = None
        # Heuristic: Find enemy with same role tags as my_role
        target_tag = "Mage"
        if my_role == "BOTTOM": target_tag = "Marksman"
        elif my_role == "UTILITY": target_tag = "Support"
        elif my_role == "JUNGLE": target_tag = "Jungle" # Tag is tricky, check smite?
        elif my_role == "TOP": target_tag = "Fighter"
        
        if ddragon_data:
            possible_opponents = []
            for enemy in enemy_team:
                e_info = ddragon_data.get(enemy)
                if e_info and target_tag in e_info['roles']:
                    possible_opponents.append(enemy)
            
            if possible_opponents:
                lane_opponent = possible_opponents[0] # Pick first match
        
        if lane_opponent:
            plan.append(f"Targeting Lane Opponent: {lane_opponent}")
            
            # --- MATCHUP ENGINE CALL ---
            math_tips = self.matchup_engine.analyze_matchup(my_champion, lane_opponent, ddragon_data)
            for tip in math_tips:
                plan.append(f"➤ {tip}")
        
        # 3. Class-Based Logic
        if "Assassin" in my_roles:
            plan.append("CLASS: ASSASSIN")
            plan.append("- Your goal is the enemy backline (ADC/Mage).")
            plan.append("- Look for flanks. Do not engage first.")
        elif "Tank" in my_roles:
            plan.append("CLASS: TANK")
            plan.append("- You are the frontline. Peel for your carry.")
            plan.append("- Engage when you see an enemy misstep.")
        elif "Marksman" in my_roles:
            plan.append("CLASS: MARKSMAN")
            plan.append("- Survival is key. Hit the closest target.")
            plan.append("- Do not facecheck bushes.")
        elif "Support" in my_roles:
            plan.append("CLASS: SUPPORT")
            plan.append("- Ward objectives 1 minute before spawn.")
            plan.append("- Protect your win condition (Fed Ally).")
            
        # 4. Analyze Scaling
        plan.append("\nWIN CONDITION:")
        early_game_threats = ["Lee Sin", "Elise", "Pantheon", "Renekton", "Zed"]
        late_game_scalers = ["Kaisa", "Vayne", "Ornn", "Kayle", "Veigar"]
        
        is_my_team_early = any(c in early_game_threats for c in [my_champion]) # simplified
        is_enemy_late = any(c in late_game_scalers for c in enemy_team)
        
        if is_my_team_early and is_enemy_late:
            plan.append("WIN CONDITION: Close out the game early.")
            plan.append("- Force skimishes and invades before minute 20.")
            plan.append("- Do not trade farm for objectives. Take dragons on spawn.")
            
        # 5. Itemization Hints (Reactive Build)
        ap_threats = ["Ahri", "Sylas", "LeBlanc", "Karthus"]
        enemy_ap_count = sum(1 for c in enemy_team if c in ap_threats)
        
        if enemy_ap_count >= 3:
            plan.append("ITEMIZATION: Heavy Magic Damage detected.")
            plan.append("-> Consider: Maw of Malmortius / Banshee's Veil / Mercury's Treads.")
            
        if len(plan) < 5:
            plan.append("Standard Laning phase. Focus on farm and objective control.")
            
        return "\n".join(plan)

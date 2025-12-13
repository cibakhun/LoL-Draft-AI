class CompositionAnalyzer:
    def __init__(self, ddragon):
        self.ddragon = ddragon
        
    def analyze_team(self, team_ids):
        """
        Analyzes a list of champion IDs to determine team needs.
        Returns a dict of 'Needs' with Multipliers.
        """
        if not team_ids:
            return {}
            
        # 1. Map IDs to Roles/Classes
        team_roles = []
        damage_profile = {"Physical": 0, "Magic": 0, "True": 0}
        has_tank = False
        has_support = False
        
        # Simple heuristics for Damage Profile based on Class
        # Mage -> Magic, Marksman -> Physical, Assassin -> Mixed (skewed phys), Fighter -> Physical
        
        for cid in team_ids:
            cname = self.ddragon.id_map.get(int(cid))
            if not cname: continue
            
            info = self.ddragon.champions.get(cname)
            if not info: continue
            
            roles = info['roles']
            team_roles.extend(roles)
            
            if "Mage" in roles: damage_profile["Magic"] += 1
            if "Marksman" in roles: damage_profile["Physical"] += 1
            if "Fighter" in roles: damage_profile["Physical"] += 1
            if "Assassin" in roles: damage_profile["Physical"] += 0.8; damage_profile["Magic"] += 0.2
            if "Tank" in roles: has_tank = True
            if "Support" in roles: has_support = True
            
        # 2. Determine Needs
        needs = {}
        
        # Need Frontline?
        if not has_tank:
            needs["Tank"] = 1.3 # +30% Score for Tanks
            
        # Need AP?
        total_dmg = damage_profile["Physical"] + damage_profile["Magic"]
        if total_dmg > 0:
            magic_ratio = damage_profile["Magic"] / total_dmg
            if magic_ratio < 0.2:
                needs["Mage"] = 1.4 # +40% for Mages if team is full AD
                
        # Need AD?
        if total_dmg > 0:
            phys_ratio = damage_profile["Physical"] / total_dmg
            if phys_ratio < 0.2:
                needs["Marksman"] = 1.4
                needs["Fighter"] = 1.2
                
        print(f"[CORTEX] Team Analysis: Tank={has_tank}, Magic={damage_profile['Magic']:.1f}/{total_dmg:.1f}")
        return needs

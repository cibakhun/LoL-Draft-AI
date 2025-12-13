class ItemizationEngine:
    def __init__(self, ddragon):
        self.ddragon = ddragon
        
        # Knowledge Base: Threat Triggers
        # Which champions trigger which need?
        # This should ideally be fetched from tags, but hardcoded High-Value lists work best for reliability.
        self.threats = {
            "Healer": ["Soraka", "Yuumi", "Aatrox", "Warwick", "Vladimir", "Sylas", "DrMundo", "Swain"],
            "Tank": ["Ornn", "Sion", "Malphite", "ChoGath", "TahmKench", "K桑rnte", "Zac", "Rammus"],
            "BurstAP": ["Syndra", "Veigar", "LeBlanc", "Akali", "Annie", "Brand"],
            "AssassinAD": ["Zed", "Talon", "Qiyana", "KhaZix", "Rengar", "BlueKayn"]
        }
        
        # Knowledge Base: Counter Items (Simplified Map)
        # Type: {Need: Id} (We need IDs from DDragon ideally, but using names for readability layer)
        self.counters = {
            "AD": {
                "AntiHeal": "Mortal Reminder", # Exec
                "AntiTank": "Blade of the Ruined King", # or LDR
                "AntiBurst": "Maw of Malmortius",
                "AntiAssasin": "Guardian Angel" 
            },
            "AP": {
                "AntiHeal": "Morellonomicon",
                "AntiTank": "Liandry's Anguish",
                "AntiBurst": "Banshee's Veil",
                "AntiAssasin": "Zhonya's Hourglass"
            },
            "Tank": {
                "AntiHeal": "Thornmail",
                "AntiAttackSpeed": "Frozen Heart",
                "AntiCrit": "Randuin's Omen"
            }
        }

    def generate_build(self, champion, enemy_team, role="AD"):
        """
        Generates a Context-Aware Build.
        role: "AD" (Marksman/Fighter), "AP" (Mage), "Tank"
        """
        # 1. Identify Threats
        needs = []
        
        healers = sum(1 for e in enemy_team if e in self.threats["Healer"])
        tanks = sum(1 for e in enemy_team if e in self.threats["Tank"])
        burst_ap = sum(1 for e in enemy_team if e in self.threats["BurstAP"])
        assassins = sum(1 for e in enemy_team if e in self.threats["AssassinAD"])
        
        if healers >= 1: needs.append("AntiHeal")
        if tanks >= 2: needs.append("AntiTank")
        if burst_ap >= 2: needs.append("AntiBurst")
        if assassins >= 2: needs.append("AntiAssasin")
        
        print(f"[ITEM] Analysis for {champion} vs {enemy_team}: Needs={needs}")
        
        # 2. Get Core Build (Standard)
        # In a real app, successful scraping would give us "Kraken -> IE -> LDR".
        # For this demo, we mock a "Standard High Elo Build" depending on class.
        build = []
        if role == "AD":
            build = ["Kraken Slayer", "Infinity Edge", "Phantom Dancer", "Bloodthirster", "Guardian Angel"]
        elif role == "AP":
            build = ["Luden's Companion", "Shadowflame", "Rabadon's Deathcap", "Cryptbloom", "Zhonya's Hourglass"]
        elif role == "Tank":
            build = ["Sunfire Aegis", "Thornmail", "Jak'Sho", "Kaenic Rookern", "Randuin's Omen"]
            
        # 3. Inject Context Items
        # Strategy: Replace 3rd or 4th item with Counter Item.
        # If AntiHeal is needed, replace 3rd.
        # If AntiTank is needed, replace 2nd/3rd.
        
        advice = []
        
        my_counters = self.counters.get(role, {})
        
        for need in needs:
            item = my_counters.get(need)
            if item and item not in build:
                # Injection Logic
                advice.append(f"⚠ Build {item} early due to {need} threat.")
                
                # Simple swap for demo
                if len(build) > 3:
                    build[2] = item # Swap 3rd item
        
        return {
            "final_build": build,
            "advice": advice,
            "threats": needs
        }

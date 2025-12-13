import sys
from src.engine import MetaEngine, ProfileEngine, SmartDraft, GameplanGenerator
from src.config import get_riot_api_key

def main():
    print("========================================")
    print("   THE HYBRID ORACLE - CONSOLE ALPHA    ")
    print("========================================")
    
    # 1. Initialize Engines
    print("[*] Initializing Left Brain (Meta Engine)...")
    meta = MetaEngine()
    
    print("[*] Initializing Right Brain (Profile Engine)...")
    profile = ProfileEngine(summoner_name="TestUser") # Hardcoded for MVP
    
    draft_brain = SmartDraft(meta, profile)
    tactician = GameplanGenerator()
    
    # Check Config
    key = get_riot_api_key()
    if not key:
        print("[!] Warning: No Riot API Key found. Using Offline Mode with dummy data.")
    else:
        print(f"[*] Connected as Authenticated User")

    print("\n--- SIMULATION MODE ---")
    print("Scenario: You are playing Mid lane.")
    
    # 2. Input Scenario
    my_team = ["Ornn", "Lee Sin", "Kaisa", "Leona"] # 4 picks made
    enemy_team = ["Malphite", "Zed", "Jinx", "Lulu", "Viego"]
    
    print(f"Your Team: {', '.join(my_team)}")
    print(f"Enemy Team: {', '.join(enemy_team)}")
    print("Available Candidates: Ahri, Yasuo (Mastery too low), Corki (Meta bad)")
    
    candidates = ["Ahri", "Yasuo", "Corki"]
    
    print("\n[ANALYSIS]")
    best_score = -1
    best_pick = None
    
    for champ in candidates:
        score, details = draft_brain.calculate_score(champ, my_team, enemy_team)
        if score > 0:
            print(f"> {champ} Score: {score} | Meta: {details['Meta']} | Personal: {details['Personal']} | Synergy: {details['Synergy']} | Counter: {details['Counter']}")
            if score > best_score:
                best_score = score
                best_pick = champ
        else:
            print(f"> {champ} REJECTED (Score 0) - Reason: {details}")

    print("\n========================================")
    print(f"RECOMMENDED PICK: {best_pick}")
    print("========================================")
    
    # 3. Gameplan
    if best_pick:
        print("\n--- DYNAMIC GAMEPLAN ---")
        plan = tactician.generate_plan(my_team + [best_pick], enemy_team, best_pick)
        print(plan)

if __name__ == "__main__":
    main()

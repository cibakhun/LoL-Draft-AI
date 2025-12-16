
import sys
import os
import numpy as np
import torch
import json

# Adjust path to include src
sys.path.append(os.getcwd())

from src.engine.features import FeatureEngine
from src.engine.neural_brain import NeuralBrain, LeagueNet
from src.engine.ensemble_brain import EnsembleBrain

# --- 1. MOCK DDRAGON ---
class MockDDragon:
    def __init__(self):
        self.champions = {
            "Ahri": {"key": "103", "info": {"attack": 3, "magic": 8, "defense": 4, "difficulty": 5}, "roles": ["Mage", "Assassin"]},
            "LeeSin": {"key": "64", "info": {"attack": 8, "magic": 5, "defense": 5, "difficulty": 6}, "roles": ["Fighter", "Assassin"]},
            "Thresh": {"key": "412", "info": {"attack": 5, "magic": 6, "defense": 6, "difficulty": 7}, "roles": ["Support", "Tank"]},
            "Jinx": {"key": "222", "info": {"attack": 9, "magic": 2, "defense": 2, "difficulty": 6}, "roles": ["Marksman"]},
            "Ornn": {"key": "516", "info": {"attack": 5, "magic": 3, "defense": 9, "difficulty": 5}, "roles": ["Tank", "Fighter"]},
            "Zed": {"key": "238", "info": {"attack": 9, "magic": 1, "defense": 2, "difficulty": 7}, "roles": ["Assassin"]},
            "Lulu": {"key": "117", "info": {"attack": 4, "magic": 7, "defense": 5, "difficulty": 5}, "roles": ["Support", "Mage"]},
            "Ezreal": {"key": "81", "info": {"attack": 7, "magic": 6, "defense": 2, "difficulty": 7}, "roles": ["Marksman", "Mage"]},
            "Viego": {"key": "234", "info": {"attack": 6, "magic": 2, "defense": 4, "difficulty": 5}, "roles": ["Fighter", "Assassin"]},
            "Malphite": {"key": "54", "info": {"attack": 5, "magic": 7, "defense": 9, "difficulty": 2}, "roles": ["Tank", "Fighter"]},
        }

def run_xray():
    print("========================================")
    print("      DEEP BRAIN X-RAY DIAGNOSTIC       ")
    print("========================================")

    # 1. Setup Feature Engine
    print("\n[1] Initializing Cortex (Feature Engine)...")
    cortex = FeatureEngine()
    ddragon = MockDDragon()
    cortex.build_vocab(ddragon)
    
    # Mock some history
    print(" -> Injecting Synthetic Memories (Meta Stats)...")
    cortex.meta_stats = {
        103: {'total_games': 100, 'MIDDLE': {'games': 90, 'wins': 50}}, # Ahri: 55% WR
        64: {'total_games': 200, 'JUNGLE': {'games': 190, 'wins': 95}}, # Lee: 50% WR
    }
    cortex.synergy_matrix = {
        103: {64: {'games': 50, 'wins': 40}} # Ahri-Lee: 80% WR (Strong Synergy)
    }

    # 2. Vectorize a Match
    print("\n[2] Vectorizing Sample Match...")
    blue_team = {"TOP": "Ornn", "JUNGLE": "LeeSin", "MIDDLE": "Ahri", "BOTTOM": "Jinx", "UTILITY": "Thresh"}
    red_team = {"TOP": "Malphite", "JUNGLE": "Viego", "MIDDLE": "Zed", "BOTTOM": "Ezreal", "UTILITY": "Lulu"}
    
    # Convert names to IDs
    b_ids = {r: int(ddragon.champions[n]['key']) for r, n in blue_team.items()}
    r_ids = {r: int(ddragon.champions[n]['key']) for r, n in red_team.items()}
    
    start_vec = list(b_ids.values()) + list(r_ids.values())
    print(f" -> Input IDs: {start_vec}")
    
    flat_vec, (neural_b, neural_r, neural_meta) = cortex.vectorize(b_ids, r_ids, ddragon)
    
    print(f" -> Flat Vector Size: {len(flat_vec)} (Sparse: {np.sum(flat_vec[:-72] > 0)} active)")
    print(f" -> Meta Vector Size: {len(neural_meta)}")
    
    # INSPECT META VECTOR
    print("\n[3] X-Raying Meta Features (72 Dimensions):")
    labels = [
        "Blue Atk", "Blue Mag", "Blue Def", "Blue Diff", "B Fgtr", "B Tank", "B Mage", "B Assn", "B Mark", "B Supp", "B %Atk", "B %Mag", "B TankScore", "B SuppScore", "B CarryScore",
        "Red Atk", "Red Mag", "Red Def", "Red Diff", "R Fgtr", "R Tank", "R Mage", "R Assn", "R Mark", "R Supp", "R %Atk", "R %Mag", "R TankScore", "R SuppScore", "R CarryScore",
        # 30-39 Role Mastery (Freq, WR) x 5
        "B Top F", "B Top W", "B Jg F", "B Jg W", "B Mid F", "B Mid W", "B Bot F", "B Bot W", "B Sup F", "B Sup W",
        "R Top F", "R Top W", "R Jg F", "R Jg W", "R Mid F", "R Mid W", "R Bot F", "R Bot W", "R Sup F", "R Sup W",
        # 50-54 Synergy
        "B Syn Avg", "B Syn Max", "B Syn Bot", "B Syn MidJg", "B Syn TopJg",
        # 55-59 Red Synergy
        "R Syn Avg", "R Syn Max", "R Syn Bot", "R Syn MidJg", "R Syn TopJg",
        # 60-65 Spikes
        "B Early", "B Mid", "B Late", "R Early", "R Mid", "R Late",
        # 66-71 Counters
        "Top Cn", "Jg Cn", "Mid Cn", "Bot Cn", "Sup Cn", "Team Cn"
    ]
    
    for i, val in enumerate(neural_meta):
        label = labels[i] if i < len(labels) else f"Dim {i}"
        if abs(val) > 0.001:
            print(f"    [{i:02d}] {label}: {val:.4f}")
            
    # SPECIFIC CHECKS
    print("\n[!] Consistency Checks:")
    # Check Ahri-Lee Synergy (Blue Mid-Jg)
    # Ahri (103) & Lee (64) have 50 games, 40 wins -> 0.8 WR. Smoothed: (40+2)/(50+4) = 42/54 = 0.777
    syn_score = neural_meta[53] 
    print(f" -> Blue Mid-Jungle Synergy (Expected ~0.78): {syn_score:.4f}")
    if abs(syn_score - 0.777) < 0.01: print("    [PASS] Synergy Logic Correct.")
    else: print("    [FAIL] Synergy Logic Suspicious.")
    
    # Check Ahri Mid Winrate
    # 100 total, 90 mid, 50 wins -> 55.5% raw. Smoothed: (50+5)/(90+10) = 0.55
    role_wr = neural_meta[35]
    print(f" -> Blue Mid Winrate (Expected 0.55): {role_wr:.4f}")
    
    # 3. Neural Network Check
    print("\n[4] Initializing Neural Brain (LeagueNet)...")
    net = NeuralBrain()
    vocab_size = max(cortex.vocab.values()) + 1
    net.initialize(vocab_size)
    
    if net.model:
        print(" -> Model Architecture:")
        print(net.model)
        
        # Forward Pass
        print("\n[5] Running Simulation Pass...")
        prob = net.predict(neural_b, neural_r, neural_meta)
        print(f" -> Predicted Win Probability: {prob:.4f}")
        
        # Check Gradient Flow
        print(" -> Verifying Backpropagation...")
        try:
            net.train([list(neural_b)+list(neural_r)], [neural_meta], [1.0], epochs=1, batch_size=1, vocab_size=vocab_size)
            print("    [PASS] Gradients Flowing.")
        except Exception as e:
            print(f"    [FAIL] Training Error: {e}")
            
    else:
        print(" -> PyTorch not detected. Skipping Neural Check.")

if __name__ == "__main__":
    run_xray()

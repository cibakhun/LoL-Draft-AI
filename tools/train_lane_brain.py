import os
import sys
import shutil

# Add project root match
sys.path.append(os.getcwd())

from src.engine.ensemble_brain import EnsembleBrain
from src.data.ddragon import DataDragon

def main():
    print("=== LANE AWARE BRAIN TRAINING ===")
    
    # 1. Initialize
    ddragon = DataDragon()
    brain = EnsembleBrain()
    
    # 2. Reset Brain
    if os.path.exists("brain.joblib"):
        print("Removing old brain...")
        os.remove("brain.joblib")
        
    # 3. Train
    match_dir = os.path.join("src", "data", "matches")
    print(f"Training on data in {match_dir}")
    
    brain.train(match_dir, ddragon)
    
    # 4. Save
    brain.save()
    
    # 5. Evaluate
    print("\nEvaluating Performance...")
    brain.evaluate(match_dir, ddragon)

if __name__ == "__main__":
    main()

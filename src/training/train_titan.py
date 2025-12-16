import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.engine.ensemble_brain import EnsembleBrain
from src.engine.lcu_connector import DDragonInterface

def main():
    print("==============================================")
    print("      TITAN TRAINING PROTOCOL (Round 7)       ")
    print("==============================================")
    print("Target: 1 Million Matches")
    print("Architecture: 64-Dim Embeddings / 512-Layer NN")
    print("RAM Strategy: Streaming (Batch Size: 50,000)")
    print("==============================================\n")
    
    # 1. Initialize Components
    print("[TITAN] Initializing Systems...")
    brain = EnsembleBrain()
    ddragon = DDragonInterface()
    
    # 2. Update DDragon (Crucial for Vocab)
    print("[TITAN] Syncing with Riot Servers (DDragon)...")
    ddragon.update_data()
    
    # 3. Execute Training
    # Batch Size 50,000 is optimized for 32GB RAM.
    # It balances RAM usage (~2GB per batch) with GPU/CPU throughput.
    print("[TITAN] Engaging Neural Core...")
    brain.train("legacy_ignored", ddragon, batch_size=50000)
    
    # 4. Save
    print("[TITAN] Training Complete. Saving Synaptic Weights...")
    brain.save()
    print("[TITAN] Model Saved: brain.joblib")

if __name__ == "__main__":
    main()


import os
import sys
import numpy as np
import pytest

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.engine.neural_brain import NeuralBrain, HAS_TORCH

def test_titan_convergence():
    if not HAS_TORCH:
        pytest.skip("PyTorch not installed, skipping Titan test.")
        
    print("\n[TITAN] Initializing Neural Brain...")
    brain = NeuralBrain(model_path="test_titan.pt")
    
    # 1. Generate Synthetic "Easy" Data
    # Rule: If Blue Team has ID=1 (Annie) and Red Team has ID=2 (Olaf), Blue ALWAYS wins.
    # Otherwise random.
    print("[TITAN] Generating 10,000 synthetic matches (Rule: Annie beats Olaf)...")
    
    X_champs = []
    X_meta = [] # Random noise
    y = []
    
    for _ in range(10000):
        # Blue Team
        b = [0]*5
        if np.random.random() < 0.5:
             b[0] = 1 # Annie present
        else:
             b[0] = 3 # Not Annie
             
        # Red Team
        r = [0]*5
        r[0] = 2 # Olaf always present
        
        # Meta noise
        meta = np.random.rand(50).tolist()
        
        # Determine Winner
        if b[0] == 1:
            win = 1.0
        else:
            win = 0.0
            
        X_champs.append(b + r)
        X_meta.append(meta)
        y.append(win)
        
    # 2. Train using Streaming Logic (Mini-Batch SGD)
    # We simulate a "Chunk" of 5000
    chunk_size = 5000
    
    brain.initialize(vocab_size=10) # Small vocab
    
    print("[TITAN] Starting Training Phase (Expected: Loss < 0.1)...")
    
    # Chunk 1
    loss1 = brain.train_on_batch(
        X_champs[:chunk_size], 
        X_meta[:chunk_size], 
        y[:chunk_size]
    )
    print(f"[TITAN] Chunk 1 Loss: {loss1:.4f}")
    
    # Chunk 2
    loss2 = brain.train_on_batch(
        X_champs[chunk_size:], 
        X_meta[chunk_size:], 
        y[chunk_size:]
    )
    print(f"[TITAN] Chunk 2 Loss: {loss2:.4f}")
    
    # 3. Validation
    # Validate on new data
    test_champs = []
    test_meta = []
    test_y = []
    for _ in range(100):
        b = [1,0,0,0,0] # Annie
        r = [2,0,0,0,0] # Olaf
        test_champs.append(b+r)
        test_meta.append(np.random.rand(50).tolist())
        test_y.append(1.0)
        
    # Predict
    # We need to manually call model because predict_batch expects slightly different format
    # But let's use the public API
    # public API 'predict_batch' expects List of Lists for Blue/Red
    
    b_list = [x[:5] for x in test_champs]
    r_list = [x[5:] for x in test_champs]
    
    preds = brain.predict_batch(b_list, r_list, test_meta)
    avg_pred = sum(preds) / len(preds)
    print(f"[TITAN] Prediction for Annie vs Olaf (Target 1.0): {avg_pred:.4f}")
    
    # Assert
    assert loss2 < loss1, "Loss should decrease over chunks"
    assert loss2 < 0.4, "Loss should be reasonably low after 10k samples"
    assert avg_pred > 0.8, "Model should learn that Annie beats Olaf"
    
    print("[TITAN] TEST PASSWORD: GREEN")
    
if __name__ == "__main__":
    test_titan_convergence()

import sys
import os

# Fix Path (Must be before src imports)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader
from src.engine.titan_brain import TitanBrain

from src.engine.datasets import TitanMemoryDataset

def load_dataset_mmap(path):
    # Wrapper for TitanMemoryDataset
    try:
        return TitanMemoryDataset(path)
    except Exception as e:
        print(f"Failed to load dataset {path}: {e}")
        return None

def generate_hybrid_mask(size=21, context_size=11):
    """
    Generates a mask where:
    - Context (0..context_size-1) sees itself fully (0..context_size-1).
    - Future (context_size..end) sees Context fully.
    - Future sees itself Causally (Triangular).
    - Context CANNOT see Future.
    """
    # Initialize with -inf (Block All)
    mask = torch.ones(size, size) * float('-inf')
    
    # 1. Context Block (Full Visibility)
    mask[:context_size, :context_size] = 0.0
    
    # 2. Future sees Context (Full Visibility)
    mask[context_size:, :context_size] = 0.0
    
    # 3. Future sees Future (Causal)
    future_len = size - context_size
    
    # Generate sub-mask for future block (Upper Triangle = -inf)
    # We want Row i to see 0..i.
    m = torch.zeros(future_len, future_len)
    
    # Fill Upper Triangle with -inf
    for i in range(future_len):
        for j in range(i + 1, future_len):
            m[i, j] = float('-inf')
            
    mask[context_size:, context_size:] = m
    
    return mask

def main():
    print("--- TitanNet V3 Ignition Sequence (Safe Mode) ---")
    
    # 1. Load Data
    TRAIN_PATH = os.path.join("data", "titan_train_v3.pt")
    VAL_PATH = os.path.join("data", "titan_val_v3.pt")
    
    train_set = load_dataset_mmap(TRAIN_PATH)
    val_set = load_dataset_mmap(VAL_PATH)
    
    if not train_set or not val_set:
        print("Data loading failed. Run compile_dataset.py first.")
        return
        
    print(f"Train Samples: {len(train_set)}")
    print(f"Val Samples:   {len(val_set)}")
    
    train_loader = DataLoader(train_set, batch_size=128, shuffle=True)
    val_loader = DataLoader(val_set, batch_size=128, shuffle=False)
    
    # 2. Initialize Brain
    brain = TitanBrain("titan_v3_model.pt")
    brain.initialize(vocab_size=3000)
    
    # 3. Mask Setup
    # 0: Meta
    # 1-10: Bans (Index 1-10)
    # Total Context = 11 tokens.
    # 11-20: Picks (Index 11-20)
    causal_mask = generate_hybrid_mask(21, context_size=11)
    
    EPOCHS = 1
    os.makedirs("checkpoints", exist_ok=True)
    best_val_loss = float('inf')
    
    for epoch in range(1, EPOCHS+1):
        print(f"\n--- Epoch {epoch}/{EPOCHS} ---")
        
        # Train
        train_pol_loss = 0.0
        train_val_loss = 0.0
        batches = 0
        
        brain.model.train()
        for batch in train_loader:
            xp, xt, xb, xm, xmeta, y = batch
            
            # Explicit Targets: The input `xp` is [P1..P10].
            # The model internally shifts to predict [P1..P10].
            # So Target is `xp`.
            
            targets = xp.clone().long()
            
            l_pol, l_val = brain.train_step(xp, xt, xb, xm, xmeta, y, src_mask=causal_mask, y_policy=targets)
            
            train_pol_loss += l_pol
            train_val_loss += l_val
            batches += 1
            
            if batches % 100 == 0:
                print(f"\rBatch {batches} | Pol: {l_pol:.4f} | Val: {l_val:.4f}", end="")
                
        avg_pol = train_pol_loss / max(1, batches)
        avg_val = train_val_loss / max(1, batches)
        print(f"\n[Train] Avg Policy: {avg_pol:.4f} | Avg Value: {avg_val:.4f}")
        
        # Validation
        brain.model.eval()
        val_mse = 0.0
        val_batches = 0
        
        with torch.no_grad():
            for batch in val_loader:
                xp, xt, xb, xm, xmeta, y = batch
                xp = xp.to(brain.device).long()
                xt = xt.to(brain.device).long()
                xb = xb.to(brain.device).long()
                xm = xm.to(brain.device).float()
                xmeta = xmeta.to(brain.device).float()
                y = y.to(brain.device).float()
                
                # Validation without mask to test full draft understanding
                # (Peeking allows checking if Value Head works on full sequence)
                mask_val = None 
                
                out = brain.model(xp, xt, xb, xm, xmeta, src_mask=mask_val)
                loss = torch.nn.MSELoss()(out['value'], y)
                val_mse += loss.item()
                val_batches += 1
                
        avg_val_mse = val_mse / max(1, val_batches)
        print(f"[Valid] MSE Loss: {avg_val_mse:.4f}")
        
        if avg_val_mse < best_val_loss:
            best_val_loss = avg_val_mse
            print(f">>> NEW BEST MODEL (Loss: {best_val_loss:.4f}) - Saving...")
            brain.model_path = os.path.join("checkpoints", "titan_v3_best.pt")
            brain.save()
            
    print("\nTraining Complete.")
    brain.model_path = os.path.join("checkpoints", "titan_v3_final.pt")
    brain.save()

if __name__ == "__main__":
    main()

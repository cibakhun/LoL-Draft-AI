import sys
import os

# Fix Path (Must be before src imports)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader
from src.engine.titan_brain import TitanBrain, VOCAB_SIZE

from src.engine.datasets import TitanMemoryDataset

def load_dataset_mmap(path):
    # Wrapper for TitanMemoryDataset
    try:
        return TitanMemoryDataset(path)
    except Exception as e:
        print(f"Failed to load dataset {path}: {e}")
        return None


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
    brain.initialize(vocab_size=VOCAB_SIZE)
    
    # V3.5: Dynamic masking is done internally via x_times — no external mask needed
    
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
            xp, xt, xb, xm, xmeta, x_times, y = batch
            
            # Explicit Targets: Full Draft Sequence (Bans + Picks)
            # Input: Meta -> Output: Ban 1
            # Input: Ban 10 -> Output: Pick 1
            # ...
            # Input: Pick 9 -> Output: Pick 10
            
            # Target Shape: [B, 20]
            targets = torch.cat([xb, xp], dim=1).long()
            
            # TITAN V3.5: Dynamic Masking via x_times
            l_pol, l_val = brain.train_step(xp, xt, xb, xm, xmeta, y, x_times=x_times, src_mask=None, y_policy=targets)
            
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
        val_pol = 0.0
        val_batches = 0
        
        with torch.no_grad():
            for batch in val_loader:
                xp, xt, xb, xm, xmeta, x_times, y = batch
                xp = xp.to(brain.device).long()
                xt = xt.to(brain.device).long()
                xb = xb.to(brain.device).long()
                xm = xm.to(brain.device).float()
                xmeta = xmeta.to(brain.device).float()
                x_times = x_times.to(brain.device).long()
                y = y.to(brain.device).float()
                
                # Use dynamically generated causal mask within TitanNet for true predictive testing
                mask_val = None 
                
                out = brain.model(xp, xt, xb, xm, xmeta, x_times=x_times, src_mask=mask_val)
                loss_mse = torch.nn.MSELoss()(out['value'], y)
                val_mse += loss_mse.item()
                
                # Compute Policy Loss
                logits = out['policy'].reshape(-1, out['policy'].size(-1))
                t_meta = torch.zeros((xp.size(0), 1), dtype=torch.long, device=brain.device)
                raw_tokens = torch.cat([t_meta, xb, xp], dim=1)
                sort_idx = out['sort_indices']
                sorted_tokens = torch.gather(raw_tokens, 1, sort_idx)
                targets = sorted_tokens[:, 1:].contiguous().view(-1)
                
                loss_pol = torch.nn.CrossEntropyLoss()(logits, targets)
                val_pol += loss_pol.item()
                
                val_batches += 1
                
        avg_val_mse = val_mse / max(1, val_batches)
        avg_val_pol = val_pol / max(1, val_batches)
        print(f"[Valid] MSE Loss: {avg_val_mse:.4f} | Policy Loss: {avg_val_pol:.4f}")
        
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

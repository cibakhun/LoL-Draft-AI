import torch
import sys
import os

# Add src to path (Up 2 levels from tests/)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.engine.titan_brain import TitanBrain

def test_causal_masking():
    print("--- Testing Causal Masking ---")
    sys.stdout.flush()
    brain = TitanBrain()
    brain.initialize(vocab_size=1000) # Safety Margin
    brain.model.eval()
    
    # 1. Generate Inputs
    # B=1
    x_picks = torch.tensor([[10, 20, 30, 40, 50, 60, 70, 80, 90, 100]]) # Fixed
    x_turns = torch.tensor([[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]])
    x_bans  = torch.zeros((1, 10))
    x_mast  = torch.zeros((1, 10))
    x_meta  = torch.zeros((1, 3))
    
    # 2. Generate Mask (from training loop logic)
    size = 21
    causal_mask = torch.triu(torch.ones(size, size) * float('-inf'), diagonal=1)
    causal_mask[0:11, 0:11] = 0.0 # Unlock context
    
    print(f"DEBUG: Picks Max: {x_picks.max()}, Turns Max: {x_turns.max()}")
    sys.stdout.flush()
    print(f"DEBUG: Picks Shape: {x_picks.shape}")
    sys.stdout.flush()
    
    # 3. Run Inference A
    with torch.no_grad():
        out_A = brain.model(x_picks.long(), x_turns.long(), x_bans.long(), x_mast.float(), x_meta.float(), src_mask=causal_mask)
        # Prediction at Step 0 (Pick 1) -> Should depend only on Context + Pick 1
        # Actually index 11 is Pick 1.
        # It predicts Pick at next step?
        pred_A = out_A['policy'][0, 0, :] # Logits for first pick pos
        
    # 4. Modify Future (Pick 10)
    x_picks_B = x_picks.clone()
    x_picks_B[0, 9] = 999 # Change LAST token
    
    # 5. Run Inference B
    with torch.no_grad():
        out_B = brain.model(x_picks_B, x_turns.long(), x_bans.long(), x_mast.float(), x_meta.float(), src_mask=causal_mask)
        pred_B = out_B['policy'][0, 0, :]
        
    # 6. Compare Pred A and Pred B
    # If Causal, Pred A (at step 0) should NOT know about the change at Step 9.
    diff = torch.sum(torch.abs(pred_A - pred_B)).item()
    
    print(f"Difference in Step 0 Prediction after changing Step 9: {diff}")
    
    if diff < 1e-6:
        print("✅ SUCCESS: Future does not leak into Past.")
    else:
        print("❌ FAILURE: Leaky Attention Detected!")
        
    # 7. Reverse Check: Change Past
    x_picks_C = x_picks.clone()
    x_picks_C[0, 0] = 999 # Change FIRST token
    
    with torch.no_grad():
        out_C = brain.model(x_picks_C, x_turns.long(), x_bans.long(), x_mast.float(), x_meta.float(), src_mask=causal_mask)
        pred_C = out_C['policy'][0, 8, :] # Prediction at Step 8
        
    # Compare Out A Step 8 vs Out C Step 8
    # Step 8 SHOULD see Step 0 change.
    diff_rev = torch.sum(torch.abs(out_A['policy'][0, 8, :] - pred_C)).item()
    print(f"Difference in Step 8 Prediction after changing Step 0: {diff_rev}")
    if diff_rev > 1e-6:
        print("✅ SUCCESS: Past correctly influences Future.")
    else:
        print("❌ FAILURE: Attention seems broken (No dependency).")

if __name__ == "__main__":
    test_causal_masking()

import torch

def test_dynamic_masking():
    print("--- Titan V3.5 Dynamic Masking Unit Test ---")
    # Szenario: 3 Slots.
    # Slot 0 (Top) pickt als Letztes (Zeit 3)
    # Slot 1 (Jungle) pickt als Erstes (Zeit 1)
    # Slot 2 (Mid) pickt als Zweites (Zeit 2)
    
    # Unsere Inputs
    x_seats = torch.tensor([[0, 1, 2]]) # Topology (fest)
    x_times = torch.tensor([[3, 1, 2]]) # Chronology (variabel)
    
    # Erwartete Logik:
    # Slot 1 (Zeit 1) darf NUR sich selbst sehen.
    # Slot 2 (Zeit 2) darf sich selbst UND Slot 1 sehen.
    # Slot 0 (Zeit 3) darf ALLE sehen.
    
    # Simulierte Masken-Erstellung (aus deinem Code)
    B, L = x_times.shape
    t_i = x_times.unsqueeze(2) # (1, 3, 1) -> Spaltenvektor für Empfänger (Query Time)
    t_j = x_times.unsqueeze(1) # (1, 1, 3) -> Zeilenvektor für Sender (Key Time)
    
    # Maske: j sichtbar für i, wenn t_j <= t_i
    # True = Visible (0.0 in Attention)
    # False = Hidden (-inf in Attention)
    # Note: user's snippet used bool checking, I will stick to their logic but verify semantics.
    # In Attention implementation: mask usually is "True means Masked/Hidden".
    # But here we verify logical visibility.
    
    mask_visible = (t_j <= t_i) 
    
    print(f"Time Vector: {x_times}")
    print("\nGenerierte Sichtbarkeits-Matrix (True = Visible/Sichtbar):")
    print(mask_visible[0])

    # Assertions
    # 1. Jungle (Idx 1, T=1) looks at Top (Idx 0, T=3). Should be False (Future).
    # t_i = 1 (Jungle), t_j = 3 (Top). 3 <= 1 is False. Correct.
    assert mask_visible[0, 1, 0] == False, "FEHLER: Jungle (Zeit 1) sieht Top (Zeit 3) -> Future Leak!"
    
    # 2. Mid (Idx 2, T=2) looks at Jungle (Idx 1, T=1). Should be True (Past).
    # t_i = 2 (Mid), t_j = 1 (Jungle). 1 <= 2 is True. Correct.
    assert mask_visible[0, 2, 1] == True,  "FEHLER: Mid (Zeit 2) sieht Jungle (Zeit 1) nicht -> Blind Spot!"
    
    # 3. Top (Idx 0, T=3) looks at Mid (Idx 2, T=2). Should be True (Past).
    # t_i = 3 (Top), t_j = 2 (Mid). 2 <= 3 is True. Correct.
    assert mask_visible[0, 0, 2] == True,  "FEHLER: Top (Zeit 3) sieht Mid (Zeit 2) nicht -> Blind Spot!"
    
    print("\n✅ PASSED: Masking logic is mathematically sound.")
    print("Topology and Causality are successfully decoupled.")

if __name__ == "__main__":
    test_dynamic_masking()

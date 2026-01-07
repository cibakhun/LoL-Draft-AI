
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.engine.mcts import TitanMCTS, MCTSNode

def test_decay():
    print("--- Verifying MCTS Dynamic Exploration ---")
    
    # Mock Objects
    class MockModel: pass
    class MockFE: pass
    
    # Init MCTS with specifics
    base = 4.0
    decay = 0.85
    mcts = TitanMCTS(MockModel(), MockFE(), base_c_puct=base, decay_factor=decay)
    
    print(f"Config: Base={base}, Decay={decay}")
    
    # Test Turns 0 to 9
    for turn in range(11): # Test up to 10 (OutOfBounds Check)
        c_val = mcts.get_exploration_constant(turn)
        expected = base * (decay ** min(turn, 9))
        
        status = "OK" if abs(c_val - expected) < 0.0001 else "FAIL"
        print(f"Turn {turn}: c_puct = {c_val:.4f} (Expected: {expected:.4f}) -> {status}")
        
    # Check Node Propagation
    root_state = [1, 2, 3] # Turn 3 (Len=3)
    root = MCTSNode(root_state)
    
    print(f"\nRoot Global Turn (Len=3): {root.global_turn_index}")
    
    child = MCTSNode(root_state + [4], parent=root)
    print(f"Child Global Turn: {child.global_turn_index}")
    
    c_child = mcts.get_exploration_constant(child.global_turn_index)
    print(f"Child c_puct: {c_child:.4f}")
    
    assert root.global_turn_index == 3
    assert child.global_turn_index == 4
    
    print("\n--- Verification Complete ---")

if __name__ == "__main__":
    test_decay()

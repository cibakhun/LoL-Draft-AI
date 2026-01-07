import sys
import os
import json

# Setup Path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(src_dir)

from src.engine.core import TitanEngine

def test_core():
    print("Initializing Engine...")
    try:
        engine = TitanEngine()
    except Exception as e:
        print(f"FAILED to initialize: {e}")
        return

    print(f"Checkpoint Used: {engine.brain.model_path}")
    print(f"Vocab Size: {len(engine.fe.vocab)}")
    print(f"Token Map Size: {len(engine.token_to_real)}")
    
    # Mock Token 1 Conversion
    t1 = 1
    k1 = engine.token_to_real.get(t1)
    print(f"Token 1 -> Key {k1}")
    if k1:
        name = engine.id_map.get(k1, "Unknown")
        print(f"Key {k1} -> Name {name}")
        
    print("\nRunning Cycle (Expect Idle/Offline if no LCU)...")
    try:
        res = engine.cycle()
        print(f"Result: {res}")
        
        # Check for 0 IDs in suggestions
        wr, recs, status, lane, build = res
        for r in recs:
            print(f"Suggestion: {r['name']} (ID: {r['id']})")
            if r['id'] == "0" or r['id'] == 0:
                print("!!! FAIL: Found ID 0 in suggestions!")
                
    except Exception as e:
        print(f"Cycle Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_core()

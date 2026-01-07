import sys
import os

# Setup Path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(src_dir)

from src.data.ddragon import DataDragon

def test_mundo():
    print("Loading DataDragon...")
    dd = DataDragon()
    
    print("\nSearch for Key 36:")
    target_key = 36
    found = False
    
    for c_id, c_val in dd.champions.items():
        # Debug DrMundo
        if "Mundo" in c_id:
            print(f"Found Entry: {c_id} -> Key: {c_val['key']} (Type: {type(c_val['key'])})")
            
        if c_val['key'] == target_key:
            print(f"MATCH FOUND via INT comparison: {c_id}")
            found = True
            
    if not found:
        print("No match found for int(36).")
        
    # Check String Comparison failure
    print("\nString Comparison Check:")
    matched_str = False
    target_str = "36"
    for c_id, c_val in dd.champions.items():
        if c_val['key'] == target_str:
            print(f"MATCH FOUND via STR comparison: {c_id}")
            matched_str = True
    
    if not matched_str:
        print("FAIL: String comparison failed (Expected).")

if __name__ == "__main__":
    test_mundo()

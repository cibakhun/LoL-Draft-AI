import sys
import os
import time
import argparse
import traceback

# Add src to path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(os.path.dirname(current_dir)) # g:\Projects\...\
sys.path.append(src_dir)

from src.engine.core import TitanEngine

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--skill', type=float, help='Override Skill Scalar (1.0 - 10.0)', default=None)
    parser.add_argument('--debug', action='store_true', help='Enable Debug Output')
    args = parser.parse_args()

    print("--- TITAN ENGINE [LIVE CLI] ---")
    
    try:
        engine = TitanEngine(skill_level=args.skill)
        print("\n--- ENGINE ACTIVE ---")
        
        last_status = None
        
        while True:
            try:
                # Cycle returns: (win_rate, suggestions, status_msg, lane_status, build_data)
                wr, recs, status, lane, build = engine.cycle()
                
                # Print Logic
                if status != last_status:
                     # Only print status logic
                     pass

                if status == "Drafting...":
                     # Dynamic Line Update
                     filled = 0 # Need to expose more if we want details here, but core handles it.
                     
                     rec_str = ", ".join([f"{r['name']} ({r['delta']:+.1f}%)" for r in recs])
                     
                     build_str = ""
                     b_champ, b_items = build
                     if b_champ:
                          item_names = [i['name'] for i in b_items]
                          build_str = f" | Build: {' > '.join(item_names)} ({b_champ['wr']:.1f}%)"
                     
                     print(f"\r[DRAFT] Win%: {wr*100:.1f}% | {lane} | Rec: {rec_str}{build_str}      ", end="")
                     sys.stdout.flush()
                     last_status = "Drafting"
                else:
                     if status != last_status:
                         print(f"\n[IDLE] {status}")
                         last_status = status
                
                time.sleep(1)
                
            except KeyboardInterrupt:
                print("\nShutting down.")
                break
            except Exception as e:
                if args.debug:
                    print(f"\n[Error] {e}")
                    traceback.print_exc()
                time.sleep(2)
                
    except Exception as e:
        print(f"Critical Error: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()

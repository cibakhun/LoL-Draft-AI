import subprocess
import time
import os
import sys

def main():
    print("--- TITAN V3.5 LAUNCHER ---")
    
    current_dir = os.getcwd()
    print(f"[LAUNCHER] Root: {current_dir}")
    
    # 1. Start Python Native Interface
    print("[LAUNCHER] Launching TITAN NATIVE (Window Manager)...")
    app_script = os.path.join(current_dir, "src", "interface", "window_manager.py")
    
    # Using 'py' to launch directly
    backend = subprocess.Popen(["py", app_script], shell=False, cwd=current_dir)
    
    print("\n[LAUNCHER] SYSTEMS ACTIVE.")
    print("--------------------------------")
    print(f"Target: {app_script}")
    print("--------------------------------")
    print("Press Ctrl+C to shutdown.")
    
    try:
        while True:
            time.sleep(1)
            # Check if processes are alive
            if backend.poll() is not None:
                print("[LAUNCHER] Application closed.")
                break
            
    except KeyboardInterrupt:
        print("\n[LAUNCHER] Stopping systems...")
        backend.terminate()
        sys.exit(0)

if __name__ == "__main__":
    main()

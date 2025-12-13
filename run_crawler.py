import time
import signal
import sys
from src.crawler import MetaCrawler
from src.engine import MetaEngine

def signal_handler(sig, frame):
    print("\n[CRAWLER] Shutting down...")
    sys.exit(0)

def main():
    print("=== STANDALONE META CRAWLER ===")
    print("[INIT] initializing Meta Engine...")
    meta_engine = MetaEngine()
    
    print("[INIT] Starting Crawler...")
    crawler = MetaCrawler(meta_engine)
    crawler.start()
    
    signal.signal(signal.SIGINT, signal_handler)
    
    print("[RUNNING] Crawler is active in background threads.")
    print("Press Ctrl+C to stop.")
    
    # Keep main thread alive
    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()

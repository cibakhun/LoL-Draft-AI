import sys
import os
import time

# Ensure root is in path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(current_dir)
root_dir = os.path.dirname(src_dir)
if root_dir not in sys.path: sys.path.append(root_dir)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer

# Internal
from src.engine.core import TitanEngine
from src.interface.lobby_window import LobbyWindow
# We will rename the overlay or keep it as titan_app reference for now
from src.interface.titan_app import TitanOverlay, TitanWorker

class TitanWindowManager:
    """
    Orchestrates the UI States:
    1. Lobby Window (Config/Stats) - Visible when NOT in Champ Select.
    2. Draft Overlay (HUD) - Visible ONLY in Champ Select.
    """
    def __init__(self):
        self.app = QApplication(sys.argv)
        
        # --- VANTAGE GLOBAL THEME ---
        try:
            style_path = os.path.join(current_dir, "style.qss")
            if os.path.exists(style_path):
                with open(style_path, "r") as f:
                    self.app.setStyleSheet(f.read())
            else:
                print("[WARN] style.qss not found")
        except Exception as e:
            print(f"[ERROR] Loading Global Style: {e}")
        
        # 1. Initialize Engine (Shared State)
        self.engine = TitanEngine()
        
        # 2. Worker Thread (Shared)
        self.worker = TitanWorker()
        # Inject engine into worker if not already handled by its own init
        self.worker.engine = self.engine
        
        # 3. Create Windows
        self.lobby_window = LobbyWindow(self.engine)
        self.draft_overlay = TitanOverlay()
        self.draft_overlay.set_engine(self.engine)
        
        # PREVENT IMPLICIT EXIT
        self.app.setQuitOnLastWindowClosed(False)
        
        # 5. Wire Signals
        # Worker -> WindowManager (For Navigation)
        self.worker.status_update.connect(self.on_status_update)
        
        # Worker -> Overlay (For Data)
        self.worker.status_update.connect(self.draft_overlay.update_status)
        self.worker.draft_update.connect(self.draft_overlay.update_draft)
        self.worker.build_update.connect(self.draft_overlay.update_build)
        
        self.worker.start()
        
        # Initial State
        self.current_phase = "None"
        self.update_visibility()

    def on_status_update(self, status, color):
        """
        Receives Status Strings from Worker (async).
        Examples: "Drafting...", "Status: Lobby", "Status: Matchmaking"
        """
        new_phase = "Lobby"
        
        if "Drafting" in status or "Lane" in status:
            new_phase = "ChampSelect"
        elif "Status:" in status:
            # Extract phase from "Status: X"
            parts = status.split(":")
            if len(parts) > 1:
                p = parts[1].strip()
                if p == "ChampSelect": new_phase = "ChampSelect"
                else: new_phase = "Lobby"
        
        if new_phase != self.current_phase:
            print(f"[WINDOW] Phase Detect: {self.current_phase} -> {new_phase} (Msg: {status})")
            self.current_phase = new_phase
            self.update_visibility()

    def update_visibility(self):
        print(f"[WINDOW] Switching Visibility. Phase: {self.current_phase}")
        if self.current_phase == "ChampSelect":
            self.lobby_window.hide()
            self.draft_overlay.show()
            self.draft_overlay.raise_()
            self.draft_overlay.activateWindow()
        else:
            self.draft_overlay.hide()
            self.lobby_window.show()
            self.lobby_window.raise_()
            self.lobby_window.activateWindow()

    def run(self):
        sys.exit(self.app.exec())

if __name__ == "__main__":
    wm = TitanWindowManager()
    wm.run()

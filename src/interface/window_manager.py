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
        
        # 4. Wire Signals
        # Worker -> Overlay
        self.worker.status_update.connect(self.draft_overlay.update_status)
        self.worker.draft_update.connect(self.draft_overlay.update_draft)
        self.worker.build_update.connect(self.draft_overlay.update_build)
        
        # Overlay -> Engine (Clicks)
        # Delegated internally by TitanOverlay -> engine.act_on_suggestion
        pass
            
        # 5. Start State Check Timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.check_phase)
        self.timer.start(2000) # Check every 2s
        
        self.worker.start()
        
        # Initial State
        self.current_phase = "None"
        self.update_visibility()

    def check_phase(self):
        new_phase = self.engine.get_phase()
        if new_phase != self.current_phase:
            print(f"[WINDOW] Phase Change: {self.current_phase} -> {new_phase}")
            self.current_phase = new_phase
            self.update_visibility()

    def update_visibility(self):
        if self.current_phase == "ChampSelect":
            self.lobby_window.hide()
            self.draft_overlay.show()
        else:
            self.draft_overlay.hide()
            self.lobby_window.show()

    def run(self):
        sys.exit(self.app.exec())

if __name__ == "__main__":
    wm = TitanWindowManager()
    wm.run()

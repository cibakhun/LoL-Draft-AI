from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QColor, QFont, QPixmap, QPainter, QPen, QBrush

from src.interface.components import THEME, CardWidget


class PhaseTrackerWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(24)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(15)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.labels = {}
        for p in ["INTENT", "BAN", "PICK", "LOAD"]:
             lbl = QLabel(p)
             lbl.setStyleSheet(f"color: {THEME['text_dim']}; font-weight: bold; font-size: 10px;")
             self.layout.addWidget(lbl)
             self.labels[p] = lbl
             
    def set_phase(self, phase_str):
        # Map LCU phase strings to our keys
        active = "LOAD"
        if phase_str == "PLANNING": active = "INTENT"
        elif phase_str == "BAN_PICK":
             active = "BAN/PICK" 
             pass
        elif phase_str == "FINALIZATION": active = "LOAD"
        elif phase_str == "GAME_START": active = "LOAD"
        
        if phase_str in ["INTENT", "PLANNING"]: active = "INTENT"
        if phase_str == "BANNING": active = "BAN"
        if phase_str == "PICKING": active = "PICK"
        
        for k, lbl in self.labels.items():
             if k == active or (active == "BAN/PICK" and k in ["BAN", "PICK"]):
                 lbl.setStyleSheet(f"color: {THEME['accent_blue']}; font-weight: 800; font-size: 11px; text-decoration: underline;")
             else:
                 lbl.setStyleSheet(f"color: {THEME['text_dim']}; font-weight: bold; font-size: 10px;")

class DraftSlotWidget(QFrame):
    """
    Represents a single player slot in the draft (0-9).
    Mirroring the LCU client: Splash/Icon, Name, Spells.
    """
    clicked = pyqtSignal(int) # Emits cell_id

    def __init__(self, cell_id, loader):
        super().__init__()
        self.cell_id = cell_id
        self.loader = loader
        
        self.setFixedHeight(100) # Similar aspect ratio to client slot
        self.setFrameShape(QFrame.Shape.StyledPanel)
        
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {THEME['bg_main']};
                border: 1px solid {THEME['border_norm']};
                border-radius: 4px;
            }}
            QFrame:hover {{
                border: 1px solid {THEME['border_active']};
            }}
        """)
        
        # Layout: [Icon/Splash] [Name/Role/Spells]
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.layout.setSpacing(10)
        
        # 1. Champion Icon
        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(60, 60)
        self.icon_lbl.setStyleSheet(f"background-color: #000; border-radius: 30px; border: 2px solid {THEME['border_norm']};")
        self.layout.addWidget(self.icon_lbl)
        
        # 2. Info Stack
        self.info_layout = QVBoxLayout()
        self.layout.addLayout(self.info_layout)
        
        self.name_lbl = QLabel("Summoner")
        self.name_lbl.setStyleSheet(f"color: {THEME['text_main']}; font-weight: bold; font-size: 11px;")
        self.info_layout.addWidget(self.name_lbl)
        
        self.status_lbl = QLabel("Picking...")
        self.status_lbl.setStyleSheet(f"color: {THEME['text_dim']}; font-size: 10px;")
        self.info_layout.addWidget(self.status_lbl)
        
        # Active State
        self.is_active = False
        
    def update_state(self, champ_id, summoner_name, is_active, is_self=False):
        self.is_active = is_active
        if is_active:
             self.setStyleSheet(f"""
                QFrame {{
                    background-color: {THEME['bg_glass']};
                    border: 1px solid {THEME['accent_blue'] if is_self else THEME['border_active']};
                    border-radius: 4px;
                }}
             """)
        else:
             self.setStyleSheet(f"""
                QFrame {{
                    background-color: {THEME['bg_main']};
                    border: 1px solid {THEME['border_norm']};
                    border-radius: 4px;
                }}
             """)
             
        self.name_lbl.setText(summoner_name if summoner_name else f"Summoner {self.cell_id}")
        
        # Icon
        if champ_id:
            pix = self.loader.circular_mask(self.loader.get_champ_icon_path(str(champ_id)), 60)
            self.icon_lbl.setPixmap(pix)
            self.status_lbl.setText("LOCKED" if not is_active else "PICKING")
            self.status_lbl.setStyleSheet(f"color: {THEME['success'] if not is_active else THEME['text_main']}; font-size: 10px;")
        else: # None/0
            # Default empty/ban icon or role
            self.icon_lbl.clear()
            self.status_lbl.setText("PICKING..." if is_active else "WAITING")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.cell_id)

class BanSlotWidget(QLabel):
    def __init__(self, loader):
        super().__init__()
        self.loader = loader
        self.setFixedSize(32, 32)
        self.setStyleSheet(f"background-color: #111; border: 1px solid {THEME['border_norm']}; border-radius: 16px;")
        
    def set_champ(self, champ_id):
        if champ_id:
            pix = self.loader.circular_mask(self.loader.get_champ_icon_path(str(champ_id)), 32)
            self.setPixmap(pix)
        else:
            self.clear()

class DraftMirrorWidget(QWidget):
    """
    Main Container.
    Layout:
    [ Bans L ] [ TIMER ] [ Bans R ]
    [ Slot 0 ]           [ Slot 5 ]
    [ Slot 1 ]  CENTER   [ Slot 6 ]
    [ Slot 2 ]  PANEL    [ Slot 7 ]
    [ Slot 3 ]           [ Slot 8 ]
    [ Slot 4 ]           [ Slot 9 ]
    """
    suggestion_clicked = pyqtSignal(str) # Propagate up

    def __init__(self, loader, engine):
        super().__init__()
        self.loader = loader
        self.engine = engine # Need engine for settings/roles if needed
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(5)
        
        # Background
        self.setObjectName("DraftMirrorWidget")
        
        # Background
        self.setObjectName("DraftMirrorWidget")
        self.setStyleSheet("#DraftMirrorWidget { background: transparent; }")
        
        # --- Top Bar (Bans & Header) ---
        self.top_frame = QFrame()
        self.top_frame.setFixedHeight(50)
        tf_layout = QHBoxLayout(self.top_frame)


        
        # Left Bans
        self.bans_l = [BanSlotWidget(loader) for _ in range(5)]
        for b in self.bans_l: tf_layout.addWidget(b)
        
        tf_layout.addStretch()
        tf_layout.addStretch()
        
        # Middle Stack: Header + Phase Tracker
        mid_layout = QVBoxLayout()
        mid_layout.setSpacing(2)
        mid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.header_lbl = QLabel("CHAMPION SELECT")
        self.header_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.header_lbl.setStyleSheet(f"color: {THEME['border_active']}; font-weight: bold; font-size: 14px;")
        mid_layout.addWidget(self.header_lbl)
        
        self.phase_tracker = PhaseTrackerWidget()
        mid_layout.addWidget(self.phase_tracker)
        
        tf_layout.addLayout(mid_layout)
        tf_layout.addStretch()
        
        # Right Bans
        self.bans_r = [BanSlotWidget(loader) for _ in range(5)]
        for b in self.bans_r: tf_layout.addWidget(b)
        
        self.main_layout.addWidget(self.top_frame)
        
        # --- Main Body (Columns) ---
        self.body_layout = QHBoxLayout()
        self.main_layout.addLayout(self.body_layout)
        
        # Left Column (Blue/Order 0-4)
        self.left_col = QVBoxLayout()
        self.left_col.setSpacing(2)
        self.slots_l = []
        for i in range(5):
            s = DraftSlotWidget(i, loader)
            self.slots_l.append(s)
            self.left_col.addWidget(s)
        self.body_layout.addLayout(self.left_col, 1) # Stretch 1
        
        # Center Panel (Suggestions/Context)
        self.center_frame = QFrame()
        self.center_frame.setFixedWidth(300) # Fixed width for suggestions
        self.center_frame.setStyleSheet(f"background-color: {THEME['bg_glass']}; border-radius: 12px;")
        self.center_layout = QVBoxLayout(self.center_frame)
        
        self.center_header = QLabel("TITAN AI")
        self.center_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.center_header.setStyleSheet(f"color: {THEME['success']}; font-weight: 800; font-size: 16px;")
        self.center_layout.addWidget(self.center_header)

        from PyQt6.QtWidgets import QPushButton
        self.btn_lock = QPushButton("LOCK IN")
        self.btn_lock.setFixedHeight(30)
        self.btn_lock.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_lock.setStyleSheet(f"""
            QPushButton {{
                background-color: {THEME['border_active']};
                color: {THEME['bg_main']};
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-family: {THEME['font_main']};
            }}
            QPushButton:hover {{
                background-color: {THEME['accent_blue']};
            }}
            QPushButton:pressed {{
                background-color: {THEME['success']};
            }}
        """)
        self.btn_lock.clicked.connect(self.on_lock_click)
        self.center_layout.addWidget(self.btn_lock)
        
        # Suggestion Cards Container
        self.suggestion_cards = []
        badges = ["★ OPTIMAL", "⚔️ AGGRO", "🛡️ SAFE"]
        for b in badges:
            cw = CardWidget(loader, {"id": "0", "name":"", "wr":50.0}, b)
            cw.setVisible(False)
            cw.clicked.connect(self.on_card_click)
            self.center_layout.addWidget(cw)
            self.suggestion_cards.append(cw)
            
        self.center_layout.addStretch()
        self.body_layout.addWidget(self.center_frame, 0)
        
        # Right Column (Red/Order 5-9)
        self.right_col = QVBoxLayout()
        self.right_col.setSpacing(2)
        self.slots_r = []
        for i in range(5, 10):
            s = DraftSlotWidget(i, loader)
            self.slots_r.append(s)
            self.right_col.addWidget(s)
        self.body_layout.addLayout(self.right_col, 1)

        # Cache Map
        self.id_cache = {}

    def on_card_click(self, champ_id):
        self.suggestion_clicked.emit(champ_id)

    def on_lock_click(self):
        self.suggestion_clicked.emit("LOCK") # Use special code or new signal?
        # Re-using suggestion_clicked with "LOCK" string is hacky but might work if handled upstream
        # But wait, suggestion_clicked passes a string "champ_id". 
        # Better to add a dedicated signal.





    def _resolve_id(self, cid):
         if not self.engine or not self.engine.ddragon: return str(cid)
         if cid in self.id_cache: return self.id_cache[cid]
         
         # Build Cache if empty
         if not self.id_cache:
              for k, v in self.engine.ddragon.champions.items():
                   try:
                       self.id_cache[int(v['key'])] = k
                   except: pass
         
         return self.id_cache.get(cid, str(cid))

    def update_gamestate(self, snapshot, my_cell, is_banning=False, has_action=False, phase="UNKNOWN"):
         if not snapshot: return

         # Update Button State
         if not has_action:
              self.btn_lock.setVisible(False)
         else:
              self.btn_lock.setVisible(True)
              if is_banning:
                   self.btn_lock.setText("BAN CHAMPION")
                   # Replace Green with Red
                   self.btn_lock.setStyleSheet(self.btn_lock.styleSheet().replace(THEME['border_active'], THEME['accent_red']))
              else:
                   self.btn_lock.setText("LOCK IN")
                   # Replace Red with Green
                   self.btn_lock.setStyleSheet(self.btn_lock.styleSheet().replace(THEME['accent_red'], THEME['border_active']))
        
         # Derive specific phase for tracker
         tracker_phase = phase
         if phase == "BAN_PICK":
             if is_banning: tracker_phase = "BANNING" 
             else: tracker_phase = "PICKING"
         
         if tracker_phase == "BAN_PICK":
             picks = snapshot[0]
             has_picks = any(p > 0 for p in picks)
             if not has_picks: tracker_phase = "BANNING"
             else: tracker_phase = "PICKING"
             
         self.phase_tracker.set_phase(tracker_phase)
        


         picks = snapshot[0]
         bans = snapshot[1]
         
         # Update Picks
         for i, pid in enumerate(picks):
             if i < 5: slot = self.slots_l[i]
             else: slot = self.slots_r[i - 5]
             
             is_self = (i == my_cell)
             
             asset_id = 0
             if pid > 0:
                  asset_id = self._resolve_id(pid)
             
             # Pass Asset ID (String) if > 0, else 0
             # update_state expects champ_id. If passed string, we need to handle "if > 0" check.
             # DraftSlotWidget: "if champ_id > 0". Strings are > 0? No, TypeError in Py3.
             # We should change DraftSlotWidget to check validity or pass explicit ID and Name separately?
             # Or just pass the Asset String as champ_id and change check to `if champ_id:`
             
             # Let's fix loop to pass asset_id
             slot.update_state(asset_id if pid > 0 else 0, "", False, is_self) 
             
         # Update Bans
         for i, bid in enumerate(bans):
             b_asset = 0
             if bid > 0: b_asset = self._resolve_id(bid)
             
             if i < 5: self.bans_l[i].set_champ(b_asset)
             elif i < 10: self.bans_r[i-5].set_champ(b_asset)

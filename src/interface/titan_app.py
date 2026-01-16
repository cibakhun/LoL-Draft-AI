
import sys
import os
import time
import json
import traceback

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QFrame, QGraphicsDropShadowEffect, QToolTip, QSlider, QPushButton)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPoint, QSize, QRectF, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QColor, QFont, QCursor, QPixmap, QPainter, QPen, QBrush, QConicalGradient

# Imports from parallel structure (assuming running from root or similar context via WindowManager)
# WindowManager sets up path, but safe to re-assert
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(os.path.dirname(current_dir))
if src_dir not in sys.path: sys.path.append(src_dir)

from src.infrastructure.lcu_connector import TitanLCU
from src.engine.core import TitanEngine
from src.interface.asset_loader import AssetLoader
from src.interface.draft_mirror import DraftMirrorWidget
from src.interface.components import THEME, CardWidget

# Re-using constants from original titan_app, but we might move to config
WINDOW_WIDTH = 1000 # Wider for Timeline/Bans
WINDOW_HEIGHT = 220 

THEME = {
    "bg_main": "#010A13",  
    "bg_glass": "rgba(9, 20, 40, 0.90)", 
    "border_norm": "#463714",
    "border_active": "#C8AA6E", 
    "text_main": "#F0E6D2",
    "text_dim": "#A09B8C",
    "accent_blue": "#0AC8B9", 
    "accent_red": "#E84057",
    "success": "#0AC8B9",
    "font_main": "Segoe UI",
    "font_data": "Consolas"
}

# --- Shared Worker (Can be imported or re-defined, kept here for self-containment/simplicity if running standalone) ---
# In WindowManager architecture, we import TitanWorker from titan_app or define it centrally.
# Per plan, we reused titan_app.TitanWorker. 
# So we need to ensure this file purely defines widgets if possible, OR acts as the module.
# To avoid circular imports or confusion, I will redefine Widgets here and let WindowManager import them.
# Wait, WindowManager imports TitanOverlay from titan_app.py. 
# So I should EDIT titan_app.py, not create a new one, OR replace titan_app.py logic entirely.
# I will REPLACE titan_app.py content with this enhanced version.

class TitanWorker(QThread):
    # Signals
    status_update = pyqtSignal(str, str) 
    draft_update = pyqtSignal(list, float, str, dict) 
    build_update = pyqtSignal(dict, list) 
    
    def run(self):
        try:
            self.status_update.emit("Initializing...", THEME["border_active"])
            # Engine is injected by WindowManager usually, or created here if standalone
            if not hasattr(self, 'engine'):
                 self.engine = TitanEngine()

            # Initialize Downloader 
            from src.interface.asset_loader import AssetDownloader
            self.downloader = AssetDownloader() 

            self.status_update.emit("Online - Idle", THEME["success"])
            
            last_msg = ""
            while True:
                try:
                    res = self.engine.cycle()
                    if len(res) == 6:
                         wr, recs, status, lane, build, context = res
                    else:
                         wr, recs, status, lane, build = res
                         context = {}
                    
                    if recs:
                         for r in recs:
                              _ = self.downloader.get_champ_icon_path(r['id'])
                    
                    # Also download bans/picks from context snapshot? 
                    # context['snapshot'] = (picks, bans...)
                    # We can parse them for timeline visualization later
                    
                    if status != last_msg:
                        color = THEME["success"] if "Drafting" in status or "Lane" in status else THEME["border_active"]
                        if "Drafting" in status: color = THEME["accent_blue"]
                        self.status_update.emit(status, color)
                        last_msg = status
                        
                    if "Drafting" in status:
                        self.draft_update.emit(recs, wr, lane, context)
                        self.build_update.emit(build[0], build[1])
                    else:
                        if "Connected" not in status: 
                             self.draft_update.emit([], 0.5, "Waiting...", {})
                             self.build_update.emit({}, [])
                    
                    time.sleep(1)
                except Exception as e:
                    print(f"Loop Error: {e}")
                    time.sleep(2)
        except Exception:
            traceback.print_exc()
            
    def process_click(self, champion_id):
         try:
             self.engine.act_on_suggestion(champion_id)
         except Exception as e:
             print(f"Click Error: {e}")

# --- WIDGETS ---

class StatBar(QWidget):
    def __init__(self, label, value, color, parent=None):
        super().__init__(parent)
        self.setFixedHeight(4)
        self.val = value
        self.col = color
        
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor("#1E2328"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(0, 0, self.width(), self.height(), 2, 2)
        p.setBrush(QColor(self.col))
        w = int(self.width() * (self.val / 100))
        p.drawRoundedRect(0, 0, w, self.height(), 2, 2)

class OracleGauge(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(100, 100) # Slightly smaller
        self._value = 0.50
        
    def set_value(self, val):
        self._value = val
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(10, 10, 80, 80)
        
        pen_track = QPen(QColor("#1A1A1A"), 6)
        pen_track.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen_track)
        painter.drawArc(rect, -90 * 16, 360 * 16)
        
        val = self._value
        if val > 0.55: color = QColor(THEME["success"])
        elif val < 0.45: color = QColor(THEME["accent_red"])
        else: color = QColor(THEME["text_dim"])
        
        pen = QPen(color, 6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        angle = int(-360 * val * 16)
        painter.drawArc(rect, 90 * 16, angle)
        
        painter.setPen(QColor(THEME["text_main"]))
        painter.setFont(QFont(THEME["font_data"], 18, QFont.Weight.Bold))
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, f"{val*100:.0f}%")
        
        painter.setFont(QFont(THEME["font_main"], 7, QFont.Weight.Bold))
        painter.setPen(QColor(THEME["border_active"]))
        r_lbl = QRectF(10, 65, 80, 20)
        painter.drawText(r_lbl, Qt.AlignmentFlag.AlignCenter, "WIN")

# CardWidget moved to src.interface.components

class TeamAnalysisWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedWidth(140)
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(4)
        
        self.lbl_title = QLabel("ANALYSIS")
        self.lbl_title.setStyleSheet(f"color: {THEME['border_active']}; font-size: 9px; font-weight: bold;")
        self.layout.addWidget(self.lbl_title)
        
        self.ad_bar = StatBar("AD", 50, "#FF6B6B")
        self.ap_bar = StatBar("AP", 50, "#4D96FF")
        
        self.layout.addWidget(QLabel("PHY", styleSheet="color:#888; font-size:8px;"))
        self.layout.addWidget(self.ad_bar)
        self.layout.addWidget(QLabel("MAG", styleSheet="color:#888; font-size:8px;"))
        self.layout.addWidget(self.ap_bar)
        self.layout.addStretch()
        
    def update_stats(self, stats, title_override=None):
        ad = stats.get('ad', 50)
        ap = stats.get('ap', 50)
        self.ad_bar.val = ad
        self.ap_bar.val = ap
        self.ad_bar.update()
        self.ap_bar.update()
        if title_override: self.lbl_title.setText(title_override)

class DraftHeaderWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(30)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        
        self.lbl_phase = QLabel("PHASE: LOADING")
        self.lbl_phase.setStyleSheet(f"color: {THEME['text_main']}; font-weight: bold; font-family: {THEME['font_data']};")
        layout.addWidget(self.lbl_phase)
        layout.addStretch()
        
        self.lbl_turn = QLabel("TURN: --")
        self.lbl_turn.setStyleSheet(f"color: {THEME['accent_blue']}; font-weight: bold;")
        layout.addWidget(self.lbl_turn)

    def update_info(self, phase, turn):
        self.lbl_phase.setText(f"PHASE: {phase}")
        self.lbl_turn.setText(f"TURN: {turn}")

class TimelineWidget(QWidget):
    def __init__(self, loader):
        super().__init__()
        self.loader = loader
        self.setFixedHeight(50)
        self._picks = [] # List of (champ_id, is_blue)
        
    def set_picks(self, picks_data):
        """picks_data: list of champ_ids. We infer side by index (Snake Draft: 1-6-7-12... logic or just simple 0-4 blue, 5-9 red if sorted).
           Actually, the snapshot is ordered chronologically by pick turn.
           Blue: 1, 4, 5, 8, 9
           Red: 2, 3, 6, 7, 10
        """
        self._picks = picks_data
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Draw background strip
        r = self.rect()
        p.setBrush(QColor("#091428"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(r, 4, 4)
        
        if not self._picks:
             p.setPen(QColor(THEME['text_dim']))
             p.drawText(r, Qt.AlignmentFlag.AlignCenter, "WAITING FOR DRAFT...")
             return

        # Visualize 10 slots
        slot_w = self.width() / 10
        
        # Standard Snake Draft Order mapping to visualize Left (Blue) vs Right (Red) or just Linear Time?
        # Linear Time is clearer for "History".
        # 1 -> Blue, 2 -> Red, 3 -> Red, 4 -> Blue...
        blue_turns = {0, 3, 4, 7, 8}
        
        for i in range(10):
            x = int(i * slot_w)
            y = 5
            sz = 40
            
            # Slot BG
            is_blue = i in blue_turns
            color = "#0AC8B9" if is_blue else "#E84057"
            p.setPen(QPen(QColor(color), 1, Qt.PenStyle.DashLine))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(x + 2, y, sz, sz)
            
            if i < len(self._picks):
                cid = self._picks[i]
                if cid != 0:
                    # Draw Icon
                    pix = self.loader.circular_mask(self.loader.get_champ_icon_path(str(cid)), 38)
                    p.drawPixmap(x + 3, y + 1, pix)

# --- OVERLAY WINDOW ---
class DraftConfigPopup(QWidget):
    """
    Mini-window for live settings adjustment during draft.
    """
    def __init__(self, engine, parent=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.engine = engine
        self.setFixedSize(250, 150)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: {THEME['bg_main']};
                border: 1px solid {THEME['border_active']};
                border-radius: 8px;
            }}
            QLabel {{ color: {THEME['text_main']}; }}
        """)
        
        layout = QVBoxLayout(self)
        
        # Mastery
        layout.addWidget(QLabel("Mastery Bias"))
        self.sl_mastery = QSlider(Qt.Orientation.Horizontal)
        self.sl_mastery.setRange(50, 200)
        self.sl_mastery.setValue(int(self.engine.settings.get("mastery_bias") * 100))
        self.sl_mastery.valueChanged.connect(self.update_mastery)
        layout.addWidget(self.sl_mastery)
        
        # Risk
        layout.addWidget(QLabel("Risk / Creativity"))
        self.sl_risk = QSlider(Qt.Orientation.Horizontal)
        self.sl_risk.setRange(0, 100)
        self.sl_risk.setValue(int(self.engine.settings.get("risk_level") * 100))
        self.sl_risk.valueChanged.connect(self.update_risk)
        layout.addWidget(self.sl_risk)
        
    def update_mastery(self, val):
        self.engine.settings.set("mastery_bias", val / 100.0)
    
    def update_risk(self, val):
        self.engine.settings.set("risk_level", val / 100.0)

class TitanOverlay(QMainWindow):
    def __init__(self):
        super().__init__()
        self.loader = AssetLoader()
        self.engine = None 
        
        # --- VANTAGE UI CONFIGURATION ---
        # Remove Tool flag to ensure it appears as a proper window
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        
        self.resize(1280, 250) # Ensure valid size
        print("[OVERLAY] Initialized TitanOverlay")
        
        # Load VANTAGE Theme
        try:
            style_path = os.path.join(current_dir, "style.qss")
            if os.path.exists(style_path):
                with open(style_path, "r") as f:
                    self.setStyleSheet(f.read())
            else:
                print("[WARN] style.qss not found")
        except Exception as e:
            print(f"[ERROR] Loading Style: {e}")

        screen_geo = QApplication.primaryScreen().geometry()
        w = 1100
        h = 700 
        x = (screen_geo.width() - w) // 2
        y = (screen_geo.height() - h) // 2
        self.setGeometry(x, y, w, h)
        
        # Background handled by QSS/PaintEvent, keeping pixmap logic for safety
        bg_path = os.path.join(current_dir, "assets", "background.png")
        self.bg_pixmap = QPixmap(bg_path)
        
        self.mousePos = None
        
        # --- MAIN CONTAINER ---
        # Wrap everything in a frame for QSS styling (borders/radius)
        self.main_frame = QFrame(self)
        self.main_frame.setObjectName("MainFrame")
        self.setCentralWidget(self.main_frame)
        
        layout = QVBoxLayout(self.main_frame)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # HEADER (Custom Title Bar)
        self.header = QFrame()
        self.header.setFixedHeight(40)
        self.header.setObjectName("HeaderFrame") # Styling hook
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(15, 0, 15, 0)
        
        title = QLabel("VANTAGE // TITAN v3.5")
        title.setObjectName("TitleLabel")
        header_layout.addWidget(title)
        header_layout.addStretch()
        
        btn_close = QPushButton("✕")
        btn_close.setObjectName("CloseButton")
        btn_close.setFixedSize(30, 30)
        btn_close.clicked.connect(self.close)
        header_layout.addWidget(btn_close)
        
        layout.addWidget(self.header)

        # CONTENT AREA
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        layout.addWidget(self.content_area)

        # --- MIRROR UI ---
        # Reparent Mirror to Content Area
        self.mirror = DraftMirrorWidget(self.loader, None)
        self.mirror.suggestion_clicked.connect(self.on_recommendation_clicked)
        self.content_layout.addWidget(self.mirror)
        
    def set_engine(self, engine):
        self.engine = engine
        self.mirror.engine = engine # Propagate to Mirror
        self.mirror.engine = engine # Propagate
        
    def update_draft(self, suggestions, winrate, lane_status, context):
        """
        Delegates updates to the Mirror Widget.
        Auto-shows suggestions if it is the user's turn.
        """
        snapshot = context.get('snapshot')
        my_cell = context.get('my_cell', -1)
        is_banning = context.get('is_banning', False)
        has_action = context.get('has_action', False) # New context
        
        if snapshot:

            phase = context.get('phase', 'UNKNOWN')
            self.mirror.update_gamestate(snapshot, my_cell, is_banning, has_action, phase)
            
        # Check if it's my turn to show suggestions
        # lane_status usually contains "Picking..." or similar.
        # But we can check specifically if our slot is active?
        # Since 'suggestions' are only generated if it IS our turn (mostly),
        # or if we are shadow-unpicking.
        
        # Update Suggestions in Center Panel
        if suggestions:
             # Show them (Mirror widget handles visibility)
             self.mirror.center_header.setText("SUGGESTED PICK")
             for i, cw in enumerate(self.mirror.suggestion_cards):
                  if i < len(suggestions):
                      cw.update_data(suggestions[i])
                      cw.setVisible(True)
                  else:
                      cw.setVisible(False)
        else:
             # Hide cards if no suggestions (e.g. locked in)
             self.mirror.center_header.setText("TITAN AI")
             for cw in self.mirror.suggestion_cards: cw.setVisible(False)

    def on_recommendation_clicked(self, champ_id):
        if champ_id == "LOCK":
            print(f"[OVERLAY] Lock Request")
            if self.engine: self.engine.lock_in()
            return
            
        print(f"[OVERLAY] Card Clicked: {champ_id}")
        if self.engine:
            self.engine.act_on_suggestion(champ_id)
            
    def update_status(self, text, color):
        # We can pass this to mirror header if needed
        pass
        
    def update_build(self, b_champ, b_items): pass
    
    def paintEvent(self, event):
        painter = QPainter(self)
        if hasattr(self, 'bg_pixmap') and not self.bg_pixmap.isNull():
             scaled = self.bg_pixmap.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
             # Center crop
             x = (scaled.width() - self.width()) // 2
             y = (scaled.height() - self.height()) // 2
             painter.drawPixmap(0, 0, scaled, x, y, self.width(), self.height())
        else:
             painter.fillRect(self.rect(), QColor(THEME['bg_main']))
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.mousePos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if self.mousePos is not None:
            delta = event.globalPosition().toPoint() - self.mousePos
            self.move(self.pos() + delta)
            self.mousePos = event.globalPosition().toPoint()

    def mouseReleaseEvent(self, event):
        self.mousePos = None

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = TitanOverlay()
    win.show()
    sys.exit(app.exec())

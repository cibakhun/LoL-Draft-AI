

from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTabWidget, QFrame, QCheckBox, QSlider, QComboBox, QGraphicsDropShadowEffect)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt6.QtGui import QFont, QColor, QLinearGradient, QPalette, QBrush

class GenericButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setFixedHeight(40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton {
                background-color: #1E2328;
                color: #C8AA6E;
                border: 1px solid #463714;
                font-weight: bold;
                font-size: 12px;
                padding: 0 20px;
            }
            QPushButton:hover {
                background-color: #1E282D;
                border: 1px solid #C8AA6E;
                color: #F0E6D2;
            }
            QPushButton:pressed {
                background-color: #091428;
                border: 1px solid #0AC8B9;
            }
        """)

class HextechFrame(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("HexFrame")
        self.setStyleSheet("""
            QFrame#HexFrame {
                background-color: rgba(1, 10, 19, 0.85);
                border: 1px solid #463714;
                border-radius: 2px;
            }
        """)
        # Glow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(15)
        shadow.setColor(QColor(0, 0, 0, 150))
        shadow.setOffset(0, 0)
        self.setGraphicsEffect(shadow)

class LobbyWindow(QMainWindow):
    """
    The Main Menu Window (Hextech Theme).
    Visible when NOT in Champion Select.
    """
    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self.setWindowTitle("Titan AI Coach - Lobby")
        self.resize(1100, 700)
        
        # Background Styling
        self.central = QWidget()
        self.setCentralWidget(self.central)
        self.layout = QVBoxLayout(self.central)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
        # Header
        self.top_bar = QFrame()
        self.top_bar.setFixedHeight(80)
        self.top_bar.setStyleSheet("background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #091428, stop:1 #010A13); border-bottom: 2px solid #C8AA6E;")
        header_layout = QHBoxLayout(self.top_bar)
        
        self.title_lbl = QLabel("TITAN AI PROTOCOL")
        self.title_lbl.setStyleSheet("font-family: 'Segoe UI'; font-size: 28px; font-weight: 800; color: #F0E6D2; letter-spacing: 2px;")
        header_layout.addWidget(self.title_lbl)
        header_layout.addStretch()
        
        self.status_pill = QLabel("STATUS: ONLINE")
        self.status_pill.setStyleSheet("color: #0AC8B9; font-weight: bold; font-family: 'Consolas'; border: 1px solid #0AC8B9; padding: 4px 10px; border-radius: 4px;")
        header_layout.addWidget(self.status_pill)
        
        self.layout.addWidget(self.top_bar)
        
        # Body
        self.body_layout = QHBoxLayout()
        self.body_layout.setContentsMargins(40, 40, 40, 40)
        self.layout.addLayout(self.body_layout)
        
        # LEFT: Navigation
        self.nav_frame = HextechFrame()
        self.nav_frame.setFixedWidth(250)
        nav_layout = QVBoxLayout(self.nav_frame)
        nav_layout.setSpacing(10)
        
        self.btn_dash = GenericButton("DASHBOARD")
        self.btn_dash.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        nav_layout.addWidget(self.btn_dash)
        
        self.btn_sett = GenericButton("SETTINGS")
        self.btn_sett.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        nav_layout.addWidget(self.btn_sett)
        
        nav_layout.addStretch()
        self.body_layout.addWidget(self.nav_frame)
        
        # RIGHT: Content Stack
        self.stack = QTabWidget()
        self.stack.setStyleSheet("QTabWidget::pane { border: none; }")
        
        # Page 1: Dashboard
        self.page_dash = QWidget()
        self.init_dashboard()
        self.stack.addTab(self.page_dash, "Dash")
        
        # Page 2: Settings
        self.page_sett = QWidget()
        self.init_settings()
        self.stack.addTab(self.page_sett, "Sett")
        
        # Hide default tab bar
        self.stack.tabBar().hide()
        
        self.body_layout.addWidget(self.stack)
        
        # Style
        self.apply_style()
        
        # Poll Timer
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_dashboard)
        self.timer.start(3000) 
        QTimer.singleShot(500, self.update_dashboard)

    def update_dashboard(self):
        if not self.isVisible(): return
        
        data = self.engine.get_profile_data()
        if data:
            name = f"{data['name']} #{data['tag']}"
            self.lbl_summ_name.setText(name.upper())
            self.lbl_summ_lvl.setText(f"LEVEL {data['level']}")
            self.lbl_rank_main.setText(data['rank_solo'])
            
            t = data['tier_solo']
            c = "#F0E6D2"
            if "EMERALD" in t: c = "#0AC8B9"
            elif "DIAMOND" in t: c = "#5765F2"
            elif "MASTER" in t or "GRAND" in t: c = "#C8AA6E"
            elif "CHALLENGER" in t: c = "#F0E6D2" # Chal is usually shiny gold/blue
            
            self.lbl_rank_main.setStyleSheet(f"font-size: 32px; font-weight: bold; color: {c};")
        else:
            self.lbl_summ_name.setText("CONNECTING TO LCU...")

    def init_dashboard(self):
        layout = QVBoxLayout(self.page_dash)
        # We wrap content in a frame
        frame = HextechFrame()
        frame_lo = QVBoxLayout(frame)
        frame_lo.setContentsMargins(40, 40, 40, 40)
        
        self.lbl_summ_name = QLabel("LOADING...")
        self.lbl_summ_name.setStyleSheet("font-size: 24px; font-weight: bold; color: #F0E6D2; letter-spacing: 1px;")
        frame_lo.addWidget(self.lbl_summ_name)
        
        self.lbl_summ_lvl = QLabel("LEVEL --")
        self.lbl_summ_lvl.setStyleSheet("font-size: 14px; font-weight: bold; color: #A09B8C;")
        frame_lo.addWidget(self.lbl_summ_lvl)
        
        frame_lo.addSpacing(40)
        
        start_lbl = QLabel("RANKED SOLO/DUO")
        start_lbl.setStyleSheet("color: #C8AA6E; font-size: 10px; font-weight: bold; letter-spacing: 2px;")
        frame_lo.addWidget(start_lbl)
        
        self.lbl_rank_main = QLabel("UNRANKED")
        self.lbl_rank_main.setStyleSheet("font-size: 32px; font-weight: bold; color: #F0E6D2;")
        frame_lo.addWidget(self.lbl_rank_main)
        
        frame_lo.addStretch()
        layout.addWidget(frame)

    def init_settings(self):
        layout = QVBoxLayout(self.page_sett)
        frame = HextechFrame()
        flo = QVBoxLayout(frame)
        flo.setSpacing(30)
        flo.setContentsMargins(40, 40, 40, 40)
        
        # Header
        hl = QLabel("CONFIGURATION")
        hl.setStyleSheet("color: #C8AA6E; font-size: 18px; font-weight: bold; border-bottom: 1px solid #463714; padding-bottom: 10px;")
        flo.addWidget(hl)
        
        # Note
        note = QLabel("Draft Protocols (Mastery/Risk) are now located in the Draft Overlay for live adjustment.")
        note.setWordWrap(True)
        note.setStyleSheet("color: #888; font-style: italic; font-size: 11px;")
        flo.addWidget(note)
        
        # 3. Auto Hover
        self.chk_hover = QCheckBox("Enable Click-to-Hover (Interactive Draft)")
        self.chk_hover.setStyleSheet("color: #F0E6D2; font-weight: bold; spacing: 10px;")
        self.chk_hover.setChecked(self.engine.settings.get("auto_hover"))
        self.chk_hover.stateChanged.connect(self.save_settings)
        flo.addWidget(self.chk_hover)
        
        flo.addStretch()
        layout.addWidget(frame)

    def save_settings(self):
        # Update settings manager
        # Only saving global settings here. Draft settings handled by Overlay.
        self.engine.settings.set("auto_hover", self.chk_hover.isChecked())
        print("[UI] Settings Saved")
 
    def apply_style(self):
        self.setStyleSheet("""
            QMainWindow { background-color: #010A13; }
        """)

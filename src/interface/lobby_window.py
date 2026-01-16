
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTabWidget, QFrame, QCheckBox, QGraphicsDropShadowEffect, QApplication)
from PyQt6.QtCore import Qt, QTimer, QSize
from PyQt6.QtGui import QIcon, QAction

class LobbyWindow(QMainWindow):
    """
    VANTAGE//TITAN V3.5
    Main Dashboard (Lobby State)
    """
    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self.setWindowTitle("VANTAGE // TITAN v3.5")
        
        # Geometry & Centering
        screen_geo = QApplication.primaryScreen().geometry()
        w = 1100
        h = 700 
        x = (screen_geo.width() - w) // 2
        y = (screen_geo.height() - h) // 2
        self.setGeometry(x, y, w, h)
        
        # VANTAGE Styling is loaded via WindowManager globall (style.qss)
        # We just need to set ObjectNames for specific styling hooks
        
        # Central Widget
        self.central = QFrame()
        self.central.setObjectName("MainFrame") # Uses the global gradient/border
        self.setCentralWidget(self.central)
        
        self.layout = QVBoxLayout(self.central)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # --- HEADER ---
        self.header = QFrame()
        self.header.setFixedHeight(60)
        self.header.setStyleSheet("background-color: rgba(20, 20, 30, 0.4); border-bottom: 1px solid rgba(255, 255, 255, 0.05);")
        
        hl = QHBoxLayout(self.header)
        hl.setContentsMargins(20, 0, 20, 0)
        
        title = QLabel("VANTAGE // TITAN")
        title.setProperty("class", "Header")
        title.setStyleSheet("font-size: 18px; letter-spacing: 2px; color: #fff;")
        hl.addWidget(title)
        
        hl.addStretch()
        
        self.status = QLabel("SYSTEM ONLINE")
        self.status.setProperty("class", "SubHeader")
        self.status.setStyleSheet("color: #0AC8B9;")
        hl.addWidget(self.status)
        
        self.layout.addWidget(self.header)
        
        # --- BODY: Sidebar + Content ---
        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(20, 20, 20, 20)
        body_layout.setSpacing(20)
        
        # SIDEBAR
        sidebar = QFrame()
        sidebar.setFixedWidth(200)
        sidebar.setProperty("class", "GlassPanel") # Defined in style.qss
        sidebar.setStyleSheet("background-color: rgba(20,20,30,0.3); border-radius: 8px;")
        
        sl = QVBoxLayout(sidebar)
        sl.setSpacing(10)
        
        btn_dash = QPushButton("DASHBOARD")
        btn_dash.setCheckable(True)
        btn_dash.setChecked(True)
        btn_dash.clicked.connect(lambda: self.switch_tab(0, btn_dash))
        sl.addWidget(btn_dash)
        
        btn_sett = QPushButton("SETTINGS")
        btn_sett.setCheckable(True)
        btn_sett.clicked.connect(lambda: self.switch_tab(1, btn_sett))
        sl.addWidget(btn_sett)
        
        sl.addStretch()
        
        ver = QLabel("v3.5.0-stable")
        ver.setProperty("class", "SubHeader")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sl.addWidget(ver)
        
        body_layout.addWidget(sidebar)
        self.nav_btns = [btn_dash, btn_sett]
        
        # CONTENT STACK
        self.stack = QTabWidget()
        self.stack.tabBar().hide()
        self.stack.setStyleSheet("QTabWidget::pane { border: none; } background: transparent;")
        
        # Tab 1: Dashboard
        self.page_dash = QWidget()
        self.init_dashboard()
        self.stack.addTab(self.page_dash, "")
        
        # Tab 2: Settings
        self.page_sett = QWidget()
        self.init_settings()
        self.stack.addTab(self.page_sett, "")
        
        body_layout.addWidget(self.stack)
        
        self.layout.addWidget(body)
        
        # Poll Timer for Data
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_data)
        self.timer.start(3000)

    def switch_tab(self, idx, btn_sender):
        self.stack.setCurrentIndex(idx)
        for b in self.nav_btns:
            b.setChecked(False)
        btn_sender.setChecked(True)

    def init_dashboard(self):
        l = QVBoxLayout(self.page_dash)
        l.setContentsMargins(0, 0, 0, 0)
        l.setSpacing(20)
        
        # Profile Card
        card = QFrame()
        card.setProperty("class", "GlassPanel")
        card.setFixedHeight(200)
        
        cl = QVBoxLayout(card)
        cl.setContentsMargins(30, 30, 30, 30)
        
        self.lbl_name = QLabel("CONNECTING...")
        self.lbl_name.setStyleSheet("font-size: 32px; font-weight: bold; color: #fff;")
        cl.addWidget(self.lbl_name)
        
        self.lbl_rank = QLabel("Unranked")
        self.lbl_rank.setStyleSheet("font-size: 18px; color: #A0A0B0;")
        cl.addWidget(self.lbl_rank)
        
        l.addWidget(card)
        l.addStretch()

    def init_settings(self):
        l = QVBoxLayout(self.page_sett)
        l.setContentsMargins(0, 0, 0, 0)
        
        card = QFrame()
        card.setProperty("class", "GlassPanel")
        
        cl = QVBoxLayout(card)
        cl.setContentsMargins(30, 30, 30, 30)
        cl.setSpacing(20)
        
        hdr = QLabel("CONFIGURATION")
        hdr.setProperty("class", "Header")
        cl.addWidget(hdr)
        
        self.chk_hover = QCheckBox("Enable Click-to-Hover")
        self.chk_hover.setStyleSheet("font-size: 14px;")
        self.chk_hover.setChecked(self.engine.settings.get("auto_hover", False))
        self.chk_hover.stateChanged.connect(self.save_settings)
        cl.addWidget(self.chk_hover)
        
        cl.addStretch()
        l.addWidget(card)
        l.addStretch()

    def save_settings(self):
        self.engine.settings.set("auto_hover", self.chk_hover.isChecked())

    def update_data(self):
        if not self.isVisible(): return
        
        data = self.engine.get_profile_data()
        if data:
            self.lbl_name.setText(f"{data['name']} #{data['tag']}")
            self.lbl_rank.setText(data['rank_solo'])
            self.status.setText("SYSTEM ONLINE")
            self.status.setStyleSheet("color: #0AC8B9;")
        else:
            self.status.setText("WAITING FOR CLIENT")
            self.status.setStyleSheet("color: #E84057;")

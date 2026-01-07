
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget
from PyQt6.QtCore import Qt, pyqtSignal, QRectF
from PyQt6.QtGui import QColor, QFont, QPainter, QPen

THEME = {
    "bg_main": "#010A13",  
    "bg_glass": "rgba(9, 20, 40, 0.95)", 
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

class CardWidget(QFrame):
    clicked = pyqtSignal(str)

    def __init__(self, loader, data, badge=None):
        super().__init__()
        self.loader = loader
        self.data = data
        self.setFixedSize(130, 170)
        self.setObjectName("Card")
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(1, 1, 1, 1)
        self.layout.setSpacing(0)
        
        # Header
        self.top_bar = QFrame()
        self.top_bar.setFixedHeight(20)
        tb_layout = QHBoxLayout(self.top_bar)
        tb_layout.setContentsMargins(5, 0, 5, 0)
        
        self.badge_lbl = QLabel(badge if badge else "")
        self.badge_lbl.setStyleSheet(f"color: {THEME['border_active']}; font-size: 8px; font-weight: 800;")
        self.delta_lbl = QLabel()
        tb_layout.addWidget(self.badge_lbl)
        tb_layout.addStretch()
        tb_layout.addWidget(self.delta_lbl)
        self.layout.addWidget(self.top_bar)
        
        # Icon
        self.icon_cont = QWidget()
        ic_layout = QVBoxLayout(self.icon_cont)
        ic_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(64, 64)
        ic_layout.addWidget(self.icon_lbl)
        self.layout.addWidget(self.icon_cont)
        
        # Info
        self.name_lbl = QLabel(data['name'])
        self.name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.name_lbl.setStyleSheet(f"color: {THEME['text_main']}; font-weight: bold; font-size: 12px; text-transform: uppercase;")
        self.layout.addWidget(self.name_lbl)
        
        self.wr_lbl = QLabel("--%")
        self.wr_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.wr_lbl.setStyleSheet(f"color: {THEME['text_dim']}; font-family: {THEME['font_data']}; font-size: 10px;")
        self.layout.addWidget(self.wr_lbl)
        
        self.layout.addStretch()
        self.bar_bg = QFrame()
        self.bar_bg.setFixedHeight(4)
        self.bar_bg.setStyleSheet("background: #1E2328; border-radius: 2px; margin: 0 10px;")
        self.fill = QFrame(self.bar_bg)
        self.fill.setStyleSheet(f"background: {THEME['success']}; border-radius: 2px;")
        self.fill.setFixedHeight(4)
        self.layout.addWidget(self.bar_bg)
        self.layout.addSpacing(10)
        
        self.update_data(data)
        self.apply_style()

    def update_data(self, data):
        self.data = data
        self.name_lbl.setText(data['name'])
        # Require loader to handle None safety if logic differs
        if self.loader and data.get('id'):
            pix = self.loader.circular_mask(self.loader.get_champ_icon_path(str(data['id'])), 64)
            self.icon_lbl.setPixmap(pix)
        
        delta = data.get('delta', 0.0)
        txt = f"{delta:+.1f}%"
        color = THEME['success'] if delta >= 0 else THEME['accent_red']
        self.delta_lbl.setText(txt)
        self.delta_lbl.setStyleSheet(f"color: {color}; font-family: {THEME['font_data']}; font-size: 9px; font-weight: bold;")
        
        wr = data.get('wr', 50.0)
        self.wr_lbl.setText(f"{wr:.1f}% WR")
        
        norm = max(0, min(1, (wr - 45) / 10))
        self.fill.setFixedWidth(int(110 * norm))
        
        rsn = data.get('reasoning', '')
        tt = (
            f"<div style='background-color: {THEME['bg_main']}; color: {THEME['text_main']}; padding: 8px;'>"
            f"<b style='color: {THEME['border_active']}'>{data['name']}</b><hr>"
            f"Impact: {rsn}</div>"
        )
        self.setToolTip(tt)

    def apply_style(self):
        self.setStyleSheet(f"""
            QFrame#Card {{
                background-color: {THEME['bg_glass']};
                border: 1px solid {THEME['border_norm']};
                border-radius: 6px;
            }}
            QFrame#Card:hover {{
                border: 1px solid {THEME['border_active']};
                background-color: rgba(9, 20, 40, 0.95);
            }}
        """)
        
    def mousePressEvent(self, event):
        if self.data and 'id' in self.data:
            self.clicked.emit(str(self.data['id']))
        super().mousePressEvent(event)

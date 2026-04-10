
import random
import math
import os
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTabWidget, QFrame, QCheckBox, QSlider, QComboBox, 
                             QGraphicsDropShadowEffect, QScrollArea)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize, QDateTime, QPoint, QPointF, QRectF, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QFont, QColor, QLinearGradient, QPalette, QBrush, QPainter, QPen, QRadialGradient, QConicalGradient

# Import Premium Components
from src.interface.components import GlassPanel, HexFrame, CardWidget, HexButton, THEME
from src.interface.asset_loader import AssetLoader

# Obsoleted PulseNavButton in favor of global HexButton.


class TimelineItem(QWidget):
    """
    A single node in the Match History Timeline.
    Interactive: Expands on hover.
    """
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.data = data
        self.setFixedHeight(120) # Taller for timeline feel
        self._hovered = False
        self._hover_progress = 0.0
        
        self.anim = QPropertyAnimation(self, b"hover_progress")
        self.anim.setDuration(200)
        
        self.setMouseTracking(True)
        
    @pyqtProperty(float)
    def hover_progress(self): return self._hover_progress
    @hover_progress.setter
    def hover_progress(self, val):
        self._hover_progress = val
        self.update()

    def enterEvent(self, event):
        self._hovered = True
        self.anim.stop()
        self.anim.setStartValue(self._hover_progress)
        self.anim.setEndValue(1.0)
        self.anim.start()
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        self._hovered = False
        self.anim.stop()
        self.anim.setStartValue(self._hover_progress)
        self.anim.setEndValue(0.0)
        self.anim.start()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w, h = self.width(), self.height()
        cx = 40 # Timeline line X position
        
        # 1. Draw Timeline Line
        painter.setPen(QPen(QColor(THEME['border_norm']), 2))
        painter.drawLine(cx, 0, cx, h)
        
        # 2. Draw Node (Orb)
        is_win = self.data['win']
        base_color = QColor(THEME['success']) if is_win else QColor(THEME['accent_red'])
        
        node_size = 14 + (6 * self._hover_progress)
        node_y = h / 2
        
        # Glow
        if self._hover_progress > 0.01:
            glow_r = node_size * 1.5
            grad = QRadialGradient(cx, node_y, glow_r)
            grad.setColorAt(0, base_color)
            grad.setColorAt(1, QColor(0,0,0,0))
            painter.setBrush(grad)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPointF(cx, node_y), glow_r, glow_r)
        
        # Core Orb
        painter.setBrush(base_color)
        painter.setPen(QPen(QColor("#FFF"), 1.5))
        painter.drawEllipse(QPointF(cx, node_y), node_size/2, node_size/2)
        
        # 3. Content Panel (Slide out from line)
        panel_x = cx + 30
        panel_w = w - panel_x - 20
        panel_h = 80
        panel_y = (h - panel_h) / 2
        
        panel_rect = QRectF(panel_x, panel_y, panel_w, panel_h)
        
        # Panel BG
        bg_c = QColor(THEME['bg_glass'])
        if is_win:
            bg_c = QColor(THEME['success'])
            bg_c.setAlpha(15)
        else:
            bg_c = QColor(THEME['accent_red'])
            bg_c.setAlpha(15)
            
        # Hover brightness
        if self._hovered:
            bg_c.setAlpha(40)
            
        painter.setBrush(bg_c)
        painter.setPen(QPen(base_color, 1))
        painter.drawRoundedRect(panel_rect, 4, 4)
        
        # Text
        painter.setPen(QColor(THEME['text_main']))
        font_res = QFont(THEME['font_main'], 14, QFont.Weight.Bold)
        painter.setFont(font_res)
        
        res_text = "VICTORY" if is_win else "DEFEAT"
        painter.drawText(int(panel_x + 15), int(panel_y + 25), res_text)
        
        # KDA
        painter.setPen(QColor(THEME['text_data']))
        painter.setFont(QFont(THEME['font_data'], 12))
        kda = self.data.get('kda', '0/0/0')
        painter.drawText(int(panel_x + 15), int(panel_y + 50), f"KDA: {kda}")
        
        # Mode & Date
        painter.setPen(QColor(THEME['text_dim']))
        painter.setFont(QFont(THEME['font_main'], 9))
        
        ts = self.data.get('timestamp', 0) / 1000
        dt = QDateTime.fromSecsSinceEpoch(int(ts))
        date_str = dt.toString("MMM d - HH:mm")
        mode = self.data.get('mode', 'CLASSIC')
        
        align_r = int(panel_x + panel_w - 15)
        painter.drawText(QRectF(panel_x, panel_y + 15, panel_w - 15, 20), Qt.AlignmentFlag.AlignRight, mode)
        painter.drawText(QRectF(panel_x, panel_y + 55, panel_w - 15, 20), Qt.AlignmentFlag.AlignRight, date_str)


class LobbyWindow(QMainWindow):
    """
    The Divine Terminal - Main Lobby Interface.
    """
    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self.loader = AssetLoader() # For champion icons
        self.debug_override_tier = None # Init debug state
        
        self.setWindowTitle("Titan AI - Divine Terminal")
        self.resize(1280, 800)
        
        # Window Entry Animation
        self._intro_progress = 0.0
        self.anim_intro = QPropertyAnimation(self, b"intro_progress")
        self.anim_intro.setDuration(1200)
        self.anim_intro.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # Central Setup
        self.central = QWidget()
        self.setCentralWidget(self.central)
        self.layout = QVBoxLayout(self.central)
        self.layout.setContentsMargins(40, 40, 40, 40)
        self.layout.setSpacing(20)
        
        # === 1. TOP NAVBAR (Floating HUD Dock) ===
        self.nav_dock = QWidget()
        self.nav_dock.setFixedHeight(70)
        nav_layout = QHBoxLayout(self.nav_dock)
        nav_layout.setContentsMargins(20, 0, 20, 0)
        nav_layout.setSpacing(30)
        
        # Logo Area
        lbl_tit = QLabel("TITAN PROTOCOL")
        lbl_tit.setStyleSheet(f"font-family: '{THEME['font_main']}'; font-size: 20px; font-weight: 900; color: {THEME['border_active']}; letter-spacing: 4px;")
        nav_layout.addWidget(lbl_tit)
        
        nav_layout.addStretch()
        
        # Nav Buttons
        self.btn_prof = HexButton("COMMANDER")
        self.btn_prof.setFixedWidth(160)
        self.btn_prof.clicked.connect(lambda: getattr(self, 'set_page', lambda x: None)(0))
        nav_layout.addWidget(self.btn_prof)
        
        self.btn_hist = HexButton("TIMELINE")
        self.btn_hist.setFixedWidth(160)
        self.btn_hist.clicked.connect(lambda: getattr(self, 'set_page', lambda x: None)(1))
        nav_layout.addWidget(self.btn_hist)
        
        self.btn_sett = HexButton("SYSTEM CONFIG")
        self.btn_sett.setFixedWidth(160)
        self.btn_sett.clicked.connect(lambda: getattr(self, 'set_page', lambda x: None)(2))
        nav_layout.addWidget(self.btn_sett)
        
        self.layout.addWidget(self.nav_dock)
        
        # === 2. MAIN CONTENT AREA (Transparent for Background) ===
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        
        self.stack = QTabWidget()
        self.stack.setStyleSheet("QTabWidget::pane { border: none; background: transparent; } QTabWidget { background: transparent; }")
        
        # Pages
        self.page_prof = QWidget()
        self.init_profile()
        self.stack.addTab(self.page_prof, "Profile")
        
        self.page_hist = QWidget()
        self.init_history()
        self.stack.addTab(self.page_hist, "History")
        
        self.page_sett = QWidget()
        self.init_settings()
        self.stack.addTab(self.page_sett, "Sett")
        
        self.stack.tabBar().hide()
        self.content_layout.addWidget(self.stack)
        
        self.layout.addWidget(self.content_area)
        
        # === 3. BACKGROUND ANIMATION SYSTEM ===
        self._ambient_phase = 0.0
            
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.game_loop)
        self.timer.start(32) # Lower update rate for smooth background drift (no particles)
        
        self.sync_timer = QTimer(self)
        self.sync_timer.timeout.connect(self.sync_data)
        self.sync_timer.start(3000)
        
        self.set_page(0)
        QTimer.singleShot(500, self.sync_data)
        
        # Run Intro Animation
        self.anim_intro.setStartValue(0.0)
        self.anim_intro.setEndValue(1.0)
        self.anim_intro.start()
        
    @pyqtProperty(float)
    def intro_progress(self):
        return self._intro_progress
        
    @intro_progress.setter
    def intro_progress(self, val):
        self._intro_progress = val
        self.update()
        # Slide content area up
        offset = int(40 * (1.0 - val))
        self.central.setFixedSize(self.width(), self.height())
        self.central.move(0, offset)
        self.central.setWindowOpacity(val)
        
    def set_page(self, idx):
        self.stack.setCurrentIndex(idx)
        # Highlight the active TacticalButton by adjusting color keys.
        btns = [self.btn_prof, self.btn_hist, self.btn_sett]
        for i, b in enumerate(btns):
            if i == idx:
                b.color_key = 'accent_blue'
                b.update()
            else:
                b.color_key = 'border_active'
                b.update()
            
    def game_loop(self):
        """Update animations (Background drift)."""
        self._ambient_phase += 0.005
        self.update() # Triggers paintEvent
       

    def sync_data(self):
        if not self.isVisible(): return
        
        # Profile Data
        data = self.engine.get_profile_data()
        if data:
            self.lbl_summ_name.setText(data['name'].upper())
            self.lbl_tag.setText(f"#{data['tag']}")
            
            # Formatting Rank - Check Debug Override
            if self.debug_override_tier:
                # In debug mode, we skip overwriting the rank frame
                pass 
            else:
                # Normal Live Data Flow
                t = data.get('tier_solo', 'UNRANKED')
                
                rank_str = data.get('rank_solo')
                # Fix for "None" or empty rank
                r_text = ""
                if not rank_str or "NONE" in str(rank_str).upper() or "UNRANKED" in str(rank_str).upper() or rank_str.strip() == "":
                     t = "UNRANKED"
                     r_text = "PROVISIONAL"
                else:
                    parts = rank_str.split(' ') 
                    if len(parts) >= 2:
                        r_text = ' '.join(parts[2:]) # LP part
                    else:
                        r_text = ""
                
                self.update_rank_display(t, r_text)
            
            # Update Top Mastery
            top_m = data.get('top_mastery', [])
            for i, card in enumerate(self.mastery_cards):
                if i < len(top_m):
                    m = top_m[i]
                    card.setVisible(True)
                    card.update_data({
                        "id": m['id'],
                        "name": m['name'],
                        "subtitle": f"{m['points']} HRS" # Points as subtitle
                    })
                else:
                    card.setVisible(False)
        
        # Match History Data
        matches_data = self.engine.get_match_history_data()
        if matches_data:
            analytics = matches_data.get('analytics', {})
            # Update Analytics widgets...
            pass
            
            # Update List if needed
            if self.timeline_layout.count() < 1 and matches_data.get('matches'):
                for m in matches_data['matches']:
                    item = TimelineItem(m)
                    self.timeline_layout.addWidget(item)
                self.timeline_layout.addStretch()

    def init_profile(self):
        layout = QVBoxLayout(self.page_prof)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # --- TOP ROW: IDENTITY & RANKED TYPOGRAPHY ---
        top_row = QHBoxLayout()
        top_row.setSpacing(60)
        top_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 1. Identity Box
        id_frame = GlassPanel() 
        id_frame.setFixedSize(380, 220)
        id_lo = QVBoxLayout(id_frame)
        id_lo.setContentsMargins(40, 40, 40, 40)
        
        lbl_head = QLabel("COMMANDER")
        lbl_head.setStyleSheet(f"color: {THEME['text_dim']}; font-size: 10px; font-weight: bold; letter-spacing: 3px;")
        id_lo.addWidget(lbl_head)
        
        self.lbl_summ_name = QLabel("LOADING...")
        self.lbl_summ_name.setStyleSheet(f"font-size: 36px; font-weight: 900; color: {THEME['text_main']}; letter-spacing: 1px;")
        id_lo.addWidget(self.lbl_summ_name)
        
        self.lbl_tag = QLabel("#TAG")
        self.lbl_tag.setStyleSheet(f"font-size: 18px; color: {THEME['border_active']}; font-weight: bold;")
        id_lo.addWidget(self.lbl_tag)
        id_lo.addStretch()
        
        top_row.addWidget(id_frame)
        
        # 2. Ranked Typography Box (Monolithic)
        self.rank_frame = GlassPanel()
        self.rank_frame.setFixedSize(450, 220)
        r_lo = QVBoxLayout(self.rank_frame)
        r_lo.setContentsMargins(40, 40, 40, 40)
        r_lo.setAlignment(Qt.AlignmentFlag.AlignTop) # Align to top for cleaner layout
        
        lbl_rt = QLabel("SOLO / DUO QUEUE")
        lbl_rt.setStyleSheet(f"color: {THEME['text_dim']}; font-size: 10px; font-weight: bold; letter-spacing: 4px;")
        r_lo.addWidget(lbl_rt)
        r_lo.addSpacing(10)
        
        self.lbl_rank_main = QLabel("UNRANKED")
        r_lo.addWidget(self.lbl_rank_main)
        
        self.lbl_rank_sub = QLabel("")
        self.lbl_rank_sub.setStyleSheet(f"color: {THEME['text_dim']}; font-size: 14px; font-weight: bold; letter-spacing: 1.5px;")
        r_lo.addWidget(self.lbl_rank_sub)
        r_lo.addStretch()
        
        top_row.addWidget(self.rank_frame)
        
        layout.addLayout(top_row)
        layout.addSpacing(50)
        
        # --- MASTERY SHOWCASE (3 Cards) ---
        m_label = QLabel("MASTERY SHOWCASE")
        m_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        m_label.setStyleSheet(f"color: {THEME['border_glow']}; font-size: 16px; font-weight: 800; letter-spacing: 4px; padding-bottom: 20px;")
        layout.addWidget(m_label)
        
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(30)
        cards_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.mastery_cards = []
        for i in range(3):
            # Placeholders
            card = CardWidget(self.loader, {"id": 0, "name": "...", "subtitle": "-- PTS"}, badge=f"#{i+1}" if i==0 else None)
            card.setVisible(False) # Hide until data
            cards_layout.addWidget(card)
            self.mastery_cards.append(card)
            
        layout.addLayout(cards_layout)
        
        # --- DEBUG: RANK SELECTOR ---
        debug_lo = QHBoxLayout()
        debug_lo.addStretch()
        lbl_dbg = QLabel("DEBUG VISUALS:")
        lbl_dbg.setStyleSheet(f"color: {THEME['text_dim']}; font-size: 10px; font-weight: bold;")
        debug_lo.addWidget(lbl_dbg)
        
        self.combo_debug_rank = QComboBox()
        self.combo_debug_rank.addItems(["AUTO (LIVE DATA)", "IRON", "BRONZE", "SILVER", "GOLD", "PLATINUM", "EMERALD", "DIAMOND", "MASTER", "GRANDMASTER", "CHALLENGER"])
        self.combo_debug_rank.setFixedWidth(150)
        self.combo_debug_rank.setStyleSheet(f"""
            QComboBox {{ 
                background: {THEME['bg_glass']}; 
                color: {THEME['accent_blue']}; 
                border: 1px solid {THEME['border_norm']};
                padding: 5px;
            }}
            QComboBox:hover {{ border: 1px solid {THEME['border_active']}; }}
        """)
        self.combo_debug_rank.currentTextChanged.connect(self.on_debug_rank_changed)
        debug_lo.addWidget(self.combo_debug_rank)
        
        layout.addSpacing(10)
        layout.addLayout(debug_lo)
        
        layout.addStretch()

    def on_debug_rank_changed(self, text):
        if "AUTO" in text:
            self.debug_override_tier = None
            self.sync_data() # Force immediate resync
        else:
            self.debug_override_tier = text
            self.update_rank_display(text, "DEBUG MODE")

    # Refactored update logic to be reusable
    def update_rank_display(self, tier, rank_text):
         # Update Armor Style & Text Color
        if hasattr(self.rank_frame, 'set_tier'):
            self.rank_frame.set_tier(tier)
        
        t_str = str(tier).upper()
        c = "#F0E6D2" # Default Gold/Bone
        if "EMERALD" in t_str: c = "#0AC8B9"
        elif "DIAMOND" in t_str: c = "#5765F2"
        elif "MASTER" in t_str: c = "#C855F2"
        elif "GRAND" in t_str: c = "#C83232"
        elif "CHALLENGER" in t_str: c = "#F0E6D2" 
        elif "PLATINUM" in t_str: c = "#4FB9B3"
        elif "GOLD" in t_str: c = "#D4AF37"
        elif "SILVER" in t_str: c = "#9EBAC4"
        elif "BRONZE" in t_str: c = "#CD8032"
        elif "IRON" in t_str: c = "#727272"
        
        self.lbl_rank_main.setText(t_str)
        self.lbl_rank_sub.setText(rank_text)
        self.lbl_rank_main.setStyleSheet(f"font-size: 36px; font-weight: 900; color: {c}; letter-spacing: 2px; margin-top: 5px;")

    def init_history(self):
        layout = QVBoxLayout(self.page_hist)
        
        # Header
        hl = QLabel("TIMELINE LOG")
        hl.setStyleSheet(f"color: {THEME['border_active']}; font-size: 14px; font-weight: bold; padding-bottom: 20px;")
        layout.addWidget(hl)
        
        # Scroll Area for Timeline
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: transparent; }
            QScrollBar:vertical { background: rgba(0,0,0,0.2); width: 8px; }
            QScrollBar::handle:vertical { background: #463714; border-radius: 4px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { background: none; }
        """)
        
        self.timeline_container = QWidget()
        self.timeline_container.setStyleSheet("background: transparent;")
        self.timeline_layout = QVBoxLayout(self.timeline_container)
        self.timeline_layout.setSpacing(0) # Connected line
        self.timeline_layout.setContentsMargins(10, 0, 10, 0)
        
        scroll.setWidget(self.timeline_container)
        layout.addWidget(scroll)

    def init_settings(self):
        layout = QVBoxLayout(self.page_sett)
        frame = HexFrame()
        flo = QVBoxLayout(frame)
        flo.setSpacing(30)
        flo.setContentsMargins(40, 40, 40, 40)
        
        hl = QLabel("SYSTEM CONFIGURATION")
        hl.setStyleSheet(f"color: {THEME['border_active']}; font-size: 18px; font-weight: bold; border-bottom: 1px solid {THEME['border_norm']}; padding-bottom: 10px;")
        flo.addWidget(hl)
        
        self.chk_hover = QCheckBox("Enable Click-to-Hover (Interactive Draft)")
        self.chk_hover.setStyleSheet(f"color: {THEME['text_main']}; font-weight: bold; spacing: 10px; font-size: 14px;")
        self.chk_hover.setChecked(self.engine.settings.get("auto_hover"))
        self.chk_hover.stateChanged.connect(self.save_settings)
        flo.addWidget(self.chk_hover)
        
        flo.addStretch()
        layout.addWidget(frame)
        
        layout.addStretch()

    def save_settings(self):
        self.engine.settings.set("auto_hover", self.chk_hover.isChecked())

    def paintEvent(self, event):
        """
        Draw the sleek Obsidian Grid background gradient.
        No godrays, no messy particles.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        w, h = rect.width(), rect.height()
        
        intro_alpha = getattr(self, '_intro_progress', 1.0)
        
        # 1. Deep Void BG
        grad = QLinearGradient(0, 0, 0, h)
        main_c = QColor(THEME['bg_main'])
        
        top_c = main_c.lighter(120)
        top_c.setAlpha(int(255 * intro_alpha))
        main_c.setAlpha(int(255 * intro_alpha))
        
        grad.setColorAt(0, top_c)
        grad.setColorAt(1, main_c)
        painter.fillRect(rect, grad)
        
        # 2. Sleek Tactical Grid Overlay Minimal
        if intro_alpha > 0.1:
            painter.setPen(QPen(QColor(255, 255, 255, int(5 * intro_alpha)), 1))
            grid_spacing = 80
            
            # Drift grid slowly based on ambient phase
            shift_x = (self._ambient_phase * 150) % grid_spacing
            
            # Vertical lines
            for x in range(int(-shift_x), w, grid_spacing):
                painter.drawLine(x, 0, x, h)
                
            # Horizontal lines
            for y in range(0, h, grid_spacing):
                painter.drawLine(0, y, w, y)
                
        # 3. Soft Top Edge Glow (Minimalist lighting)
        glow_grad = QLinearGradient(0, 0, 0, 80)
        c_glow = QColor(THEME['border_active'])
        c_glow.setAlpha(int(15 * intro_alpha))
        glow_grad.setColorAt(0, c_glow)
        glow_grad.setColorAt(1, QColor(0,0,0,0))
        painter.fillRect(0, 0, w, 80, glow_grad)

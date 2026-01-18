
import random
import math
import os
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTabWidget, QFrame, QCheckBox, QSlider, QComboBox, 
                             QGraphicsDropShadowEffect, QScrollArea)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QSize, QDateTime, QPoint, QPointF, QRectF, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QFont, QColor, QLinearGradient, QPalette, QBrush, QPainter, QPen, QRadialGradient, QConicalGradient

# Import Premium Components
from src.interface.components import AnimatedHexFrame, HexFrame, CardWidget, THEME
from src.interface.asset_loader import AssetLoader

class PulseNavButton(QPushButton):
    """
    Holographic Navigation Button with Hover Pulse and Active Glow.
    """
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setFixedHeight(50)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._hover_progress = 0.0
        self._active = False
        
        # Font settings
        font = QFont(THEME['font_main'], 10, QFont.Weight.Bold)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.5)
        self.setFont(font)
        
        self.anim_hover = QPropertyAnimation(self, b"hover_progress")
        self.anim_hover.setDuration(300)
        self.anim_hover.setEasingCurve(QEasingCurve.Type.OutCubic)
        
    @pyqtProperty(float)
    def hover_progress(self):
        return self._hover_progress
        
    @hover_progress.setter
    def hover_progress(self, val):
        self._hover_progress = val
        self.update()
        
    def set_active(self, active):
        self._active = active
        self.update()

    def enterEvent(self, event):
        self.anim_hover.stop()
        self.anim_hover.setStartValue(self._hover_progress)
        self.anim_hover.setEndValue(1.0)
        self.anim_hover.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.anim_hover.stop()
        self.anim_hover.setStartValue(self._hover_progress)
        self.anim_hover.setEndValue(0.0)
        self.anim_hover.start()
        super().leaveEvent(event)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        w, h = rect.width(), rect.height()
        
        # Background
        bg_color = QColor(THEME['bg_glass'])
        border_color = QColor(THEME['border_norm'])
        text_color = QColor(THEME['text_dim'])
        
        if self._active:
            bg_color = QColor(THEME['bg_glass_dark'])
            border_color = QColor(THEME['border_active'])
            text_color = QColor(THEME['border_active'])
        elif self._hover_progress > 0.01:
            # Lerp towards hover state
            text_color = QColor(THEME['text_main'])
            bg_color = QColor(20, 40, 60, 150)
            
        # Draw Background Plate
        painter.setBrush(bg_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(rect)
        
        # Draw Border (Left Accent)
        if self._active:
            painter.setBrush(QColor(THEME['border_active']))
            painter.drawRect(0, 0, 4, h)
            
            # Glow rect
            grad = QLinearGradient(0, 0, w, 0)
            grad.setColorAt(0, QColor(212, 175, 55, 50))
            grad.setColorAt(1, QColor(0,0,0,0))
            painter.setBrush(grad)
            painter.drawRect(4, 0, w, h)
        
        if self._hover_progress > 0.01:
            # Hover Line slide in
            line_w = w * self._hover_progress
            painter.setBrush(QColor(THEME['accent_blue']))
            painter.drawRect(0, h-2, int(line_w), 2)
            
        # Draw Text
        painter.setPen(text_color)
        # Offset text slightly on hover
        tx_off = 5 * self._hover_progress
        painter.drawText(QRectF(20 + tx_off, 0, w-20, h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())


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
            bg_c = QColor(10, 200, 185, 20)
        else:
            bg_c = QColor(200, 50, 50, 20)
            
        # Hover brightness
        if self._hovered:
            bg_c.setAlpha(50)
            
        painter.setBrush(bg_c)
        painter.setPen(QPen(base_color, 1))
        painter.drawRoundedRect(panel_rect, 6, 6)
        
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
        
        self.setWindowTitle("Titan AI - Divine Terminal")
        self.resize(1280, 800)
        
        # Enable Transparent Attributes for particles to look good if we overlaid, 
        # but pure QMainWindow usually has opaque BG. We will draw BG in paintEvent.
        
        # Central Setup
        self.central = QWidget()
        self.setCentralWidget(self.central)
        self.layout = QHBoxLayout(self.central)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # === 1. LEFT SIDEBAR (Holographic Nav) ===
        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(260)
        self.sidebar.setStyleSheet("background-color: rgba(5, 10, 20, 0.9); border-right: 1px solid #333;")
        
        side_layout = QVBoxLayout(self.sidebar)
        side_layout.setContentsMargins(0, 0, 0, 0)
        side_layout.setSpacing(0)
        
        # Logo Area
        logo_box = QFrame()
        logo_box.setFixedHeight(100)
        lb_lo = QVBoxLayout(logo_box)
        lbl_tit = QLabel("TITAN\nPROTOCOL")
        lbl_tit.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_tit.setStyleSheet(f"font-family: '{THEME['font_main']}'; font-size: 24px; font-weight: 900; color: {THEME['border_active']}; letter-spacing: 4px;")
        lb_lo.addWidget(lbl_tit)
        side_layout.addWidget(logo_box)
        
        # Nav Buttons
        self.btn_prof = PulseNavButton("  COMMANDER")
        self.btn_prof.clicked.connect(lambda: self.set_page(0))
        side_layout.addWidget(self.btn_prof)
        
        self.btn_hist = PulseNavButton("  TIMELINE")
        self.btn_hist.clicked.connect(lambda: self.set_page(1))
        side_layout.addWidget(self.btn_hist)
        
        self.btn_sett = PulseNavButton("  CONFIG")
        self.btn_sett.clicked.connect(lambda: self.set_page(2))
        side_layout.addWidget(self.btn_sett)
        
        side_layout.addStretch()
        
        # Status Footer
        ft_box = QFrame()
        ft_box.setFixedHeight(60)
        ft_lo = QVBoxLayout(ft_box)
        self.lbl_status = QLabel("SYSTEM ONLINE")
        self.lbl_status.setStyleSheet("color: #0AC8B9; font-family: 'Consolas'; font-size: 10px; letter-spacing: 1px;")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ft_lo.addWidget(self.lbl_status)
        side_layout.addWidget(ft_box)
        
        self.layout.addWidget(self.sidebar)
        
        # === 2. MAIN CONTENT AREA (Transparent for Background) ===
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(40, 40, 40, 40)
        
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
        self._particles = []
        for _ in range(50):
            self._particles.append({
                'x': random.uniform(0, 1280),
                'y': random.uniform(0, 800),
                'vx': random.uniform(-0.2, 0.2),
                'vy': random.uniform(-0.5, -0.1), # Upward drift
                'size': random.uniform(1, 3.5),
                'alpha': random.uniform(0.2, 0.6),
                'color': random.choice([(10, 180, 160), (200, 170, 100), (180, 200, 250)])
            })
            
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.game_loop)
        self.timer.start(16) # 60 FPS
        
        # Sync Timer (LCU Data)
        self.sync_timer = QTimer(self)
        self.sync_timer.timeout.connect(self.sync_data)
        self.sync_timer.start(3000)
        
        self.set_page(0)
        QTimer.singleShot(500, self.sync_data)
        
    def set_page(self, idx):
        self.stack.setCurrentIndex(idx)
        # Update Nav Buttons
        btns = [self.btn_prof, self.btn_hist, self.btn_sett]
        for i, b in enumerate(btns):
            b.set_active(i == idx)
            
    def game_loop(self):
        """Update animations (Background, Particles)."""
        self._ambient_phase += 0.01
        
        w, h = self.width(), self.height()
        
        # Particle Physics
        for p in self._particles:
            p['x'] += p['vx']
            p['y'] += p['vy']
            
            # Wrap
            if p['y'] < -10: p['y'] = h + 10; p['x'] = random.uniform(0, w)
            if p['x'] < -10: p['x'] = w + 10
            if p['x'] > w + 10: p['x'] = -10
            
        self.update() # Triggers paintEvent
       

    def sync_data(self):
        if not self.isVisible(): return
        
        # Profile Data
        data = self.engine.get_profile_data()
        if data:
            self.lbl_summ_name.setText(data['name'].upper())
            self.lbl_tag.setText(f"#{data['tag']}")
            
            # Formatting Rank
            t = data['tier_solo']
            c = "#F0E6D2"
            if "EMERALD" in t: c = "#0AC8B9"
            elif "DIAMOND" in t: c = "#5765F2"
            elif "MASTER" in t: c = "#C855F2"
            elif "GRAND" in t: c = "#C83232"
            elif "CHALLENGER" in t: c = "#F0E6D2"
            
            # Update Armor Color
            self.rank_frame.color_key = c # Hacky, but assuming HexFrame reads color? No, we need to subclass or methods.
            # AnimatedHexFrame uses 'active=True' to pulse. 
            # We can override paintEvent via style or rebuild. 
            # Actually AnimatedHexFrame hardcodes gold. 
            # For now let's just update the TEXT color which is effective enough combined with gold frame.
            
            rank_str = data.get('rank_solo')
            # Fix for "None" or empty rank
            if not rank_str or "NONE" in str(rank_str).upper() or "UNRANKED" in str(rank_str).upper() or rank_str.strip() == "":
                self.lbl_rank_main.setText("UNRANKED")
                self.lbl_rank_sub.setText("PROVISIONAL")
            else:
                parts = rank_str.split(' ') # e.g. EMERALD IV (44 LP)
                if len(parts) >= 2:
                    self.lbl_rank_main.setText(f"{parts[0]} {parts[1]}")
                    self.lbl_rank_sub.setText(' '.join(parts[2:]))
                else:
                    self.lbl_rank_main.setText(rank_str)
                    self.lbl_rank_sub.setText("")
            
            self.lbl_rank_main.setStyleSheet(f"font-size: 36px; font-weight: 900; color: {c}; letter-spacing: 2px; margin-top: 5px;")
            
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
        
        # --- TOP ROW: IDENTITY & RANKED ARMOR ---
        top_row = QHBoxLayout()
        top_row.setSpacing(40)
        
        # 1. Identity Box
        id_frame = HexFrame() 
        id_frame.setFixedSize(350, 200)
        id_lo = QVBoxLayout(id_frame)
        id_lo.setContentsMargins(30, 30, 30, 30)
        
        lbl_head = QLabel("COMMANDER")
        lbl_head.setStyleSheet(f"color: {THEME['border_active']}; font-size: 10px; font-weight: bold; letter-spacing: 2px;")
        id_lo.addWidget(lbl_head)
        
        self.lbl_summ_name = QLabel("LOADING...")
        self.lbl_summ_name.setStyleSheet(f"font-size: 32px; font-weight: 800; color: {THEME['text_main']};")
        id_lo.addWidget(self.lbl_summ_name)
        
        self.lbl_tag = QLabel("#TAG")
        self.lbl_tag.setStyleSheet(f"font-size: 18px; color: {THEME['text_dim']}; font-weight: bold;")
        id_lo.addWidget(self.lbl_tag)
        id_lo.addStretch()
        
        top_row.addWidget(id_frame)
        
        # 2. Ranked Armor (Animated)
        # Using AnimatedHexFrame for the "Armor" feel
        self.rank_frame = AnimatedHexFrame()
        self.rank_frame.setFixedSize(400, 200)
        r_lo = QVBoxLayout(self.rank_frame)
        r_lo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        lbl_rt = QLabel("SOLO / DUO QUEUE")
        lbl_rt.setStyleSheet(f"color: {THEME['border_active']}; font-size: 12px; font-weight: bold; letter-spacing: 3px;")
        r_lo.addWidget(lbl_rt)
        
        self.lbl_rank_main = QLabel("UNRANKED")
        r_lo.addWidget(self.lbl_rank_main)
        
        self.lbl_rank_sub = QLabel("")
        self.lbl_rank_sub.setStyleSheet(f"color: {THEME['text_main']}; font-size: 14px; font-weight: bold;")
        r_lo.addWidget(self.lbl_rank_sub)
        
        top_row.addWidget(self.rank_frame)
        top_row.addStretch()
        
        layout.addLayout(top_row)
        layout.addSpacing(30)
        
        # --- MASTERY SHOWCASE (3 Cards) ---
        m_label = QLabel("MASTERY SHOWCASE")
        m_label.setStyleSheet(f"color: {THEME['border_active']}; font-size: 14px; font-weight: bold; letter-spacing: 2px; padding-left: 10px;")
        layout.addWidget(m_label)
        
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(20)
        cards_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.mastery_cards = []
        for i in range(3):
            # Placeholders
            card = CardWidget(self.loader, {"id": 0, "name": "...", "subtitle": "-- PTS"}, badge=f"#{i+1}" if i==0 else None)
            card.setVisible(False) # Hide until data
            cards_layout.addWidget(card)
            self.mastery_cards.append(card)
            
        layout.addLayout(cards_layout)
        
        layout.addStretch()

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
        Draw the Divine Void background.
        """
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        w, h = rect.width(), rect.height()
        
        # 1. Deep Void BG
        grad = QLinearGradient(0, 0, 0, h)
        grad.setColorAt(0, QColor(2, 5, 10))
        grad.setColorAt(1, QColor(5, 10, 20))
        painter.fillRect(rect, grad)
        
        # 2. Godrays
        cx = w * 0.7
        painter.setPen(Qt.PenStyle.NoPen)
        
        # Ray 1
        ray1 = QRadialGradient(cx, -100, h)
        ray1.setColorAt(0, QColor(20, 40, 80, 80))
        ray1.setColorAt(1, QColor(0,0,0,0))
        painter.setBrush(ray1)
        painter.drawRect(rect)
        
        # 3. Ambient Particles
        for p in self._particles:
            alpha = int(255 * p['alpha'])
            c = p['color']
            painter.setBrush(QColor(c[0], c[1], c[2], alpha))
            painter.drawEllipse(QPointF(p['x'], p['y']), p['size'], p['size'])
            
        # 4. Vignette
        painter.setBrush(Qt.BrushStyle.NoBrush)
        pen_vig = QPen()
        # Complex to do smooth vignette with rects, skip for performance or use image if needed.
        # Simple corner gradients:
        
        # Bottom Fade
        bot_grad = QLinearGradient(0, h, 0, h-200)
        bot_grad.setColorAt(0, QColor(0,0,0,200))
        bot_grad.setColorAt(1, QColor(0,0,0,0))
        painter.fillRect(0, h-200, w, 200, bot_grad)

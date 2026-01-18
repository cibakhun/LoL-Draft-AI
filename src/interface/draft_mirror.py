from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QGridLayout, QPushButton, QGraphicsDropShadowEffect)
from PyQt6.QtCore import Qt, pyqtSignal, QSize, QPropertyAnimation, QEasingCurve, QTimer, pyqtProperty, QPointF
from PyQt6.QtGui import QColor, QFont, QPixmap, QPainter, QPen, QBrush, QPainterPath, QLinearGradient
import math

from src.interface.components import THEME, CardWidget, HexFrame, HexEffect, AnimatedHexFrame

class PhaseTrackerWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(30)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(20)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.labels = {}
        for p in ["INTENT", "BAN", "PICK", "LOAD"]:
             lbl = QLabel(p)
             lbl.setStyleSheet(f"color: {THEME['text_dim']}; font-weight: bold; font-size: 11px; letter-spacing: 1px;")
             self.layout.addWidget(lbl)
             self.labels[p] = lbl
             
    def set_phase(self, phase_str):
        active = "LOAD"
        if phase_str == "PLANNING": active = "INTENT"
        elif phase_str == "BAN_PICK": active = "BAN/PICK" 
        elif phase_str == "FINALIZATION": active = "LOAD"
        elif phase_str == "GAME_START": active = "LOAD"
        
        if phase_str in ["INTENT", "PLANNING"]: active = "INTENT"
        if phase_str == "BANNING": active = "BAN"
        if phase_str == "PICKING": active = "PICK"
        
        for k, lbl in self.labels.items():
            if k == active or (active == "BAN/PICK" and k in ["BAN", "PICK"]):
                lbl.setStyleSheet(f"color: {THEME['accent_blue']}; font-weight: 800; font-size: 12px; text-decoration: none;")
                # Glow effect (HexEffect sets offset to 0,0)
                glow = HexEffect(THEME['accent_blue'], 15)
                lbl.setGraphicsEffect(glow)
            else:
                lbl.setStyleSheet(f"color: {THEME['text_dim']}; font-weight: bold; font-size: 11px;")
                lbl.setGraphicsEffect(None)



class DraftSlotWidget(HexFrame):
    """
    Represents a single player slot in the draft (0-9).
    """
    clicked = pyqtSignal(int)

    def __init__(self, cell_id, loader):
        # Determine color key based on side
        side_color = 'accent_blue' if cell_id < 5 else 'accent_red'
        super().__init__(active=False, color_key="border_norm") 
        
        self.cell_id = cell_id
        self.loader = loader
        self.side_color = side_color
        self._is_active_turn = False  # Track if this is the active player's turn
        
        self.setFixedHeight(85)  # Taller slots for premium feel
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Hover animation
        self._hover_progress = 0.0
        self.anim_hover = QPropertyAnimation(self, b"hover_progress")
        self.anim_hover.setDuration(200)
        self.anim_hover.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        # Pulsing glow animation
        self._glow_phase = 0.0
        self._glow_timer = QTimer(self)
        self._glow_timer.timeout.connect(self._tick_glow)
        self._glow_timer.setInterval(25)  # 40 FPS for smoother breathing
        
        # Layout: [Icon] [Name/Status]
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(15, 8, 15, 8)
        self.layout.setSpacing(15)
        
        # 1. Champion Icon
        self.icon_lbl = QLabel()
        self.icon_lbl.setFixedSize(52, 52)
        self.icon_lbl.setStyleSheet(f"background-color: rgba(0,0,0,0.5); border-radius: 26px; border: 2px solid {THEME['border_norm']};")
        self.layout.addWidget(self.icon_lbl)
        
        # 2. Info Stack
        self.info_layout = QVBoxLayout()
        self.info_layout.setSpacing(4)
        self.info_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        self.layout.addLayout(self.info_layout)
        
        self.name_lbl = QLabel("SUMMONER")
        self.name_lbl.setStyleSheet(f"color: {THEME['text_main']}; font-weight: 700; font-size: 12px; letter-spacing: 1px;")
        self.info_layout.addWidget(self.name_lbl)
        
        self.status_lbl = QLabel("WAITING")
        self.status_lbl.setStyleSheet(f"color: {THEME['text_dim']}; font-size: 10px; font-weight: 600;")
        self.info_layout.addWidget(self.status_lbl)
        
        self.layout.addStretch()

        # Selection Glow
        self.glow = HexEffect(THEME['border_active'], 25)
        self.glow.setEnabled(False)
        self.setGraphicsEffect(self.glow)
    
    @pyqtProperty(float)
    def hover_progress(self):
        return self._hover_progress
    
    @hover_progress.setter
    def hover_progress(self, val):
        self._hover_progress = val
        brightness = 1.0 + (0.2 * val)
        self.setStyleSheet(f"background-color: rgba({int(15 * brightness)}, {int(25 * brightness)}, {int(40 * brightness)}, {int(200 + 40 * val)});")
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
    
    def _tick_glow(self):
        """Breathing glow without particles."""
        self._glow_phase += 0.08
        intensity = 0.5 + 0.5 * math.sin(self._glow_phase)
        self.glow.setBlurRadius(18 + 18 * intensity)
        
        base_color = QColor(THEME['border_active'])
        bright_color = QColor(THEME['accent_blue'])
        r = int(base_color.red() + (bright_color.red() - base_color.red()) * intensity)
        g = int(base_color.green() + (bright_color.green() - base_color.green()) * intensity)
        b = int(base_color.blue() + (bright_color.blue() - base_color.blue()) * intensity)
        self.glow.setColor(QColor(r, g, b))
        
        self.update()
    
    def paintEvent(self, event):
        super().paintEvent(event)  # Draw base HexFrame
        
        if self._is_active_turn:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
            w, h = self.width(), self.height()
            intensity = 0.5 + 0.5 * math.sin(self._glow_phase)
            
            # Spotlight gradient from bottom
            spotlight_grad = QLinearGradient(0, h, 0, 0)
            spotlight_alpha = int(40 + 30 * intensity)
            spotlight_grad.setColorAt(0, QColor(10, 200, 180, spotlight_alpha))
            spotlight_grad.setColorAt(0.5, QColor(10, 200, 180, int(spotlight_alpha * 0.3)))
            spotlight_grad.setColorAt(1, QColor(10, 200, 180, 0))
            
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(spotlight_grad))
            painter.drawRoundedRect(self.rect(), 6, 6)
            
            # "YOUR TURN" text (right side)
            text_alpha = int(200 + 55 * intensity)
            painter.setPen(QColor(THEME['accent_blue'].replace('#', ''), text_alpha))
            font = QFont(THEME['font_main'], 9, QFont.Weight.Bold)
            font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 2)
            painter.setFont(font)
            painter.drawText(self.rect().adjusted(0, 0, -15, 0), 
                           Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, 
                           "YOUR TURN")

    def update_state(self, champ_id, summoner_name, is_active, is_self=False, is_banning=False):
        self.set_active(is_active or is_self)
        self.glow.setEnabled(is_active or is_self)
        self._is_active_turn = is_active
        
        # Start/stop pulsing glow timer
        if is_active or is_self:
            self._glow_timer.start()
        else:
            self._glow_timer.stop()
        
        # Update colors based on activity
        if is_active:
             self.glow.setColor(QColor(THEME['border_active']))
             self.status_lbl.setText("BANNING" if is_banning else "PICKING")
             text_color = THEME['accent_red'] if is_banning else THEME['border_active']
             self.status_lbl.setStyleSheet(f"color: {text_color}; font-size: 10px; font-weight: bold;")
        elif is_self:
             self.glow.setColor(QColor(THEME['accent_blue']))
        else:
             self.status_lbl.setText("LOCKED" if champ_id else "WAITING")
             self.status_lbl.setStyleSheet(f"color: {THEME['text_dim']}; font-size: 10px;")

        self.name_lbl.setText(summoner_name if summoner_name else f"SUMMONER {self.cell_id}")
        
        # Icon
        if champ_id:
            pix = self.loader.hexagon_mask(self.loader.get_champ_icon_path(str(champ_id)), 48, THEME['border_active'] if is_active or is_self else THEME['border_norm'], 2)
            self.icon_lbl.setPixmap(pix)
            self.icon_lbl.setStyleSheet(f"background-color: transparent; border: none;")
            if not is_active: self.status_lbl.setText("LOCKED")
        else:
            self.icon_lbl.clear()
            self.icon_lbl.setStyleSheet(f"background-color: #000; border-radius: 4px; border: 2px solid {THEME['border_norm']};")

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.cell_id)

class BanSlotWidget(QWidget):
    """Ban slot with premium vortex→shatter→settle animation."""
    def __init__(self, loader, cell_id):
        super().__init__()
        self.loader = loader
        self.cell_id = cell_id
        self.setFixedSize(44, 44)  # Slightly larger for effects
        
        self._champ_pixmap = None
        self._anim_progress = 0.0
        self._is_banned = False
        
        # Animation (0->1)
        self.anim_ban = QPropertyAnimation(self, b"anim_progress")
        self.anim_ban.setDuration(600) # Faster, snappier
        self.anim_ban.setEasingCurve(QEasingCurve.Type.OutBack)
        
        # Continuous update timer for glow pulse (optional, reuse or simple)
        self._glow_timer = QTimer(self)
        self._glow_timer.timeout.connect(self.update)
        self._glow_timer.setInterval(40)
    
    @pyqtProperty(float)
    def anim_progress(self):
        return self._anim_progress
    
    @anim_progress.setter
    def anim_progress(self, val):
        self._anim_progress = val
        self.update()
    

        
    def set_champ(self, champ_id):
        if champ_id:
            path = self.loader.get_champ_icon_path(str(champ_id))
            if path:
                orig = QPixmap(path)
                self._champ_pixmap = orig.scaled(36, 36, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            
            if not self._is_banned:
                self._is_banned = True
                self.anim_ban.stop()
                self.anim_ban.setStartValue(0.0)
                self.anim_ban.setEndValue(1.0)
                self.anim_ban.start()
                self._glow_timer.start()
            
            effect = HexEffect(THEME['accent_red'], 15)
            self.setGraphicsEffect(effect)
        else:
            self._champ_pixmap = None
            self._anim_progress = 0.0
            self._is_banned = False
            self._glow_timer.stop()
            self.setGraphicsEffect(None)
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        radius = 17
        
        # 1. Background Placeholder if empty
        if not self._champ_pixmap:
             painter.setPen(QPen(QColor(THEME['text_dim']), 1, Qt.PenStyle.DashLine))
             painter.setBrush(QColor(0, 0, 0, 80))
             painter.drawEllipse(QPointF(cx, cy), radius, radius)
             return

        # 2. Champion Icon
        p = self._anim_progress
        red = QColor(THEME['accent_red'])
        
        painter.save()
        path = QPainterPath()
        path.addEllipse(QPointF(cx, cy), radius, radius)
        painter.setClipPath(path)
        
        # Scale/Bounce on entry
        scale = 1.0
        if p < 0.5:
             # Little pop
             scale = 1.0 + 0.2 * math.sin(p * 3.14 * 2) 
        
        painter.translate(cx, cy)
        painter.scale(scale, scale)
        painter.translate(-cx, -cy)
        
        painter.drawPixmap(int(cx - 18), int(cy - 18), self._champ_pixmap)
        
        # Desaturation overlay (Ban state)
        if self._is_banned:
             painter.setBrush(QColor(0, 0, 0, 150))
             painter.setPen(Qt.PenStyle.NoPen)
             painter.drawRect(0, 0, w, h)
             
        painter.restore()
        
        # 3. The "X" Slash Animation
        if self._is_banned:
             # Draw the X marks
             # Line 1: Top-Left to Bottom-Right
             if p > 0.2:
                  l1_p = min(1.0, (p - 0.2) / 0.3) # 0.2 -> 0.5
                  painter.setPen(QPen(red, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                  
                  p1_start = QPointF(cx - 10, cy - 10)
                  p1_end   = QPointF(cx + 10, cy + 10)
                  
                  current_end = p1_start + (p1_end - p1_start) * l1_p
                  painter.drawLine(p1_start, current_end)
                  
             # Line 2: Top-Right to Bottom-Left
             if p > 0.5:
                  l2_p = min(1.0, (p - 0.5) / 0.3) # 0.5 -> 0.8
                  painter.setPen(QPen(red, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                  
                  p2_start = QPointF(cx + 10, cy - 10)
                  p2_end   = QPointF(cx - 10, cy + 10)
                  
                  current_end = p2_start + (p2_end - p2_start) * l2_p
                  painter.drawLine(p2_start, current_end)
            
        # 4. Border Ring
        painter.setBrush(Qt.BrushStyle.NoBrush)
        border_col = red if self._is_banned else QColor(THEME['border_norm'])
        painter.setPen(QPen(border_col, 2))
        painter.drawEllipse(QPointF(cx, cy), radius, radius)

class DraftMirrorWidget(QWidget):
    suggestion_clicked = pyqtSignal(str)

    def __init__(self, loader, engine):
        super().__init__()
        self.loader = loader
        self.engine = engine
        
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(10)
        
        self.setObjectName("DraftMirrorWidget")
        self.setStyleSheet("#DraftMirrorWidget { background: transparent; }")
        
        # --- Top Bar (Bans & Header) ---
        self.top_frame = QFrame()
        self.top_frame.setFixedHeight(60)
        tf_layout = QHBoxLayout(self.top_frame)
        
        # Left Bans (Blue Team)
        self.bans_l = [BanSlotWidget(loader, i) for i in range(5)]
        for b in self.bans_l: tf_layout.addWidget(b)
        
        tf_layout.addStretch()
        
        # Middle Stack
        mid_layout = QVBoxLayout()
        mid_layout.setSpacing(2)
        mid_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.header_lbl = QLabel("CHAMPION SELECT")
        self.header_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.header_lbl.setStyleSheet(f"color: {THEME['border_active']}; font-weight: 800; font-size: 16px; letter-spacing: 2px;")
        
        # Header Glow
        h_glow = HexEffect(THEME['border_active'], 20)
        self.header_lbl.setGraphicsEffect(h_glow)
        
        mid_layout.addWidget(self.header_lbl)
        
        self.phase_tracker = PhaseTrackerWidget()
        mid_layout.addWidget(self.phase_tracker)
        

        
        tf_layout.addLayout(mid_layout)
        
        tf_layout.addStretch()
        
        # Right Bans (Red Team)
        self.bans_r = [BanSlotWidget(loader, i+5) for i in range(5)]
        for b in self.bans_r: tf_layout.addWidget(b)
        
        self.main_layout.addWidget(self.top_frame)
        
        # --- Main Body ---
        self.body_layout = QHBoxLayout()
        self.main_layout.addLayout(self.body_layout)
        
        # Left Column
        self.left_col = QVBoxLayout()
        self.left_col.setSpacing(12) # Increased spacing
        self.slots_l = []
        for i in range(5):
            s = DraftSlotWidget(i, loader)
            self.slots_l.append(s)
            self.left_col.addWidget(s)
        self.body_layout.addLayout(self.left_col, 1)
        
        # Center Panel (with animated rotating border)
        self.center_frame = AnimatedHexFrame(active=True, color_key='border_active')
        self.center_frame.setFixedWidth(320)
        self.center_layout = QVBoxLayout(self.center_frame)
        self.center_layout.setContentsMargins(10, 20, 10, 20)
        self.center_layout.setSpacing(10)
        
        self.center_header = QLabel("TITAN AI")
        self.center_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.center_header.setStyleSheet(f"color: {THEME['success']}; font-weight: 900; font-size: 20px; letter-spacing: 3px;")
        self.center_header.setGraphicsEffect(HexEffect(THEME['success'], 25))
        self.center_layout.addWidget(self.center_header)

        self.btn_lock = QPushButton("LOCK IN")
        self.btn_lock.setFixedHeight(48)
        self.btn_lock.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_lock.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {THEME['bg_glass']}, stop:1 rgba(20, 40, 60, 220));
                color: {THEME['border_active']};
                border: 2px solid {THEME['border_active']};
                border-radius: 8px;
                font-weight: 900;
                font-size: 16px;
                letter-spacing: 2px;
                padding: 10px 20px;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {THEME['border_active']}, stop:1 {THEME['accent_blue']});
                color: #FFFFFF;
                border-color: {THEME['accent_blue']};
            }}
            QPushButton:pressed {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 {THEME['success']}, stop:1 {THEME['accent_blue']});
                border-color: {THEME['success']};
                color: #FFFFFF;
            }}
        """)
        self.btn_lock.setGraphicsEffect(HexEffect(THEME['border_active'], 20))
        self.btn_lock.clicked.connect(self.on_lock_click)
        self.center_layout.addWidget(self.btn_lock)
        
        # Cards
        self.suggestion_cards = []
        badges = ["★ OPTIMAL", "⚔️ AGGRO", "🛡️ SAFE"]
        for b in badges:
            cw = CardWidget(loader, {"id": "0", "name":"", "wr":50.0}, b)
            cw.setVisible(False)
            cw.clicked.connect(self.on_card_click)
            self.center_layout.addWidget(cw, alignment=Qt.AlignmentFlag.AlignCenter) # Center cards
            self.suggestion_cards.append(cw)
            
        self.center_layout.addStretch()
        
        # Add a subtle footer or deco

        
        self.body_layout.addWidget(self.center_frame, 0)
        
        # Right Column
        self.right_col = QVBoxLayout()
        self.right_col.setSpacing(12) # Increased spacing
        self.slots_r = []
        for i in range(5, 10):
            s = DraftSlotWidget(i, loader)
            self.slots_r.append(s)
            self.right_col.addWidget(s)
        self.body_layout.addLayout(self.right_col, 1)

        self.id_cache = {}

    def on_card_click(self, champ_id):
        self.suggestion_clicked.emit(champ_id)

    def on_lock_click(self):
        self.suggestion_clicked.emit("LOCK")

    def _resolve_id(self, cid):
         if not self.engine or not self.engine.ddragon: return str(cid)
         if cid in self.id_cache: return self.id_cache[cid]
         if not self.id_cache:
              for k, v in self.engine.ddragon.champions.items():
                   try: self.id_cache[int(v['key'])] = k
                   except: pass
         return self.id_cache.get(cid, str(cid))

    def update_gamestate(self, snapshot, my_cell, is_banning=False, has_action=False, phase="UNKNOWN"):
         if not snapshot: return
         
         # Button State
         if has_action:
              self.btn_lock.setVisible(True)
              if is_banning:
                   self.btn_lock.setText("BAN CHAMPION")
                   self.btn_lock.setStyleSheet(f"""
                        QPushButton {{
                            background-color: {THEME['bg_glass']};
                            color: {THEME['accent_red']};
                            border: 2px solid {THEME['accent_red']};
                            border-radius: 4px; font-weight: 800; font-size: 14px;
                        }}
                        QPushButton:hover {{ background-color: {THEME['accent_red']}; color: black; }}
                   """)
                   self.center_header.setStyleSheet(f"color: {THEME['accent_red']}; font-weight: 900; font-size: 20px; letter-spacing: 3px;")
                   self.center_header.setGraphicsEffect(HexEffect(THEME['accent_red'], 25))
              else:
                   self.btn_lock.setText("LOCK IN")
                   self.btn_lock.setStyleSheet(f"""
                        QPushButton {{
                            background-color: {THEME['bg_glass']};
                            color: {THEME['success']};
                            border: 2px solid {THEME['success']};
                            border-radius: 4px; font-weight: 800; font-size: 14px;
                        }}
                        QPushButton:hover {{ background-color: {THEME['success']}; color: black; }}
                   """)
                   self.center_header.setStyleSheet(f"color: {THEME['success']}; font-weight: 900; font-size: 20px; letter-spacing: 3px;")
                   self.center_header.setGraphicsEffect(HexEffect(THEME['success'], 25))
         else:
              self.btn_lock.setVisible(False)
              self.center_header.setStyleSheet(f"color: {THEME['border_active']}; font-weight: 900; font-size: 20px; letter-spacing: 3px;")
              self.center_header.setGraphicsEffect(HexEffect(THEME['border_active'], 25))

         # Tracker
         tracker = phase
         if phase == "BAN_PICK":
             tracker = "BANNING" if is_banning else "PICKING"
         self.phase_tracker.set_phase(tracker)
         
         picks = snapshot[0]
         bans = snapshot[1]
         
         # Picks
         for i, pid in enumerate(picks):
             slot = self.slots_l[i] if i < 5 else self.slots_r[i-5]
             is_self = (i == my_cell)
             
             asset_id = 0
             if pid > 0: asset_id = self._resolve_id(pid)
             
             # Highlight if active turn?
             # Snapshot doesn't track "is_active_turn" directly for every cell, 
             # but we can infer or pass it. For now, rely on pid==0 meaning "not picked".
             # Actually, we need to know who is picking NOW.
             # The engine logic knows `lane_status`. 
             # For now, simplistic: if pid == 0 and previous are filled... hard to guess.
             # Just set Active for SELF if has_action and pid==0.
             
             is_picking = False
             if i == my_cell and has_action and pid == 0: is_picking = True
             
             slot.update_state(asset_id, "", is_picking, is_self, is_banning)
             
         # Bans
         for i, bid in enumerate(bans):
             b_asset = 0
             if bid > 0: b_asset = self._resolve_id(bid)
             if i < 5: self.bans_l[i].set_champ(b_asset)
             elif i < 10: self.bans_r[i-5].set_champ(b_asset)

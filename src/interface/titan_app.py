
import sys
import os
import time
import json
import traceback

from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QFrame, QGraphicsDropShadowEffect, QToolTip, QSlider)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QPoint, QPointF, QSize, QRectF, QPropertyAnimation, QEasingCurve, pyqtProperty, QTimer
from PyQt6.QtGui import QColor, QFont, QCursor, QPixmap, QPainter, QPen, QBrush, QConicalGradient, QLinearGradient, QRadialGradient, QPainterPath
import random
import math

# Imports
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(os.path.dirname(current_dir))
if src_dir not in sys.path: sys.path.append(src_dir)

from src.infrastructure.lcu_connector import TitanLCU
from src.engine.core import TitanEngine
from src.interface.asset_loader import AssetLoader
from src.interface.draft_mirror import DraftMirrorWidget
from src.interface.components import THEME, CardWidget

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

class TitanOverlay(QMainWindow):
    def __init__(self):
        super().__init__()
        self.loader = AssetLoader()
        self.engine = None 
        
        self.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint)
        # self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground) # Disabled per user request 
        
        screen_geo = QApplication.primaryScreen().geometry()
        w = 1150
        h = 750 
        x = (screen_geo.width() - w) // 2
        y = (screen_geo.height() - h) // 2
        self.setGeometry(x, y, w, h)
        
        # Background
        bg_path = os.path.join(current_dir, "assets", "background.png")
        self.bg_pixmap = QPixmap(bg_path)
        if self.bg_pixmap.isNull():
            # If no BG, we will rely on paintEvent drawing a glass rect
            pass
        
        self.mousePos = None
        self.last_selected_id = None
        
        # --- NEW MIRROR UI ---
        # Engine is None here, so we must set it later
        self.mirror = DraftMirrorWidget(self.loader, None)
        self.mirror.suggestion_clicked.connect(self.on_recommendation_clicked)
        self.setCentralWidget(self.mirror)
        
        self.last_interaction_time = 0 # Timestamp of last internal user click
        self.last_snapshot_selection = 0 # To track state changes from Client side
        
        # Lock-In Flash Effect
        self._flash_opacity = 0.0
        self.anim_flash = QPropertyAnimation(self, b"flash_opacity")
        self.anim_flash.setDuration(300)
        self.anim_flash.setEasingCurve(QEasingCurve.Type.OutQuad)
        
        # Ambient Background Animation
        self._ambient_phase = 0.0
        
        # Volumetric Nebula Data
        self._nebula_blobs = []
        for _ in range(4):
            self._nebula_blobs.append({
                'x': random.uniform(0.1, 0.9),
                'y': random.uniform(0.1, 0.9),
                'vx': random.uniform(-0.0005, 0.0005),
                'vy': random.uniform(-0.0005, 0.0005),
                'r': random.uniform(0.5, 0.8),
                'color': random.choice([THEME['void_purple'], THEME['accent_blue'], THEME['radiant_gold'], "#003366"])
            })
        
        # Rotating Border Phase
        self._border_rotation = 0.0
        
        self._ambient_timer = QTimer(self)
        self._ambient_timer.timeout.connect(self._tick_ambient)
        self._ambient_timer.setInterval(16)  # 60 FPS for smoother animations
        self._ambient_timer.start()
    
    def _tick_ambient(self):
        """Update ambient background logic."""
        self._ambient_phase += 0.02
        
        # Drift Nebula Blobs
        for b in self._nebula_blobs:
             b['x'] += b['vx']
             b['y'] += b['vy']
             if b['x'] < -0.2 or b['x'] > 1.2: b['vx'] *= -1
             if b['y'] < -0.2 or b['y'] > 1.2: b['vy'] *= -1
             
        self.update()
    
    @pyqtProperty(float)
    def flash_opacity(self):
        return self._flash_opacity
        
    @flash_opacity.setter
    def flash_opacity(self, val):
        self._flash_opacity = val
        self.update()
        
    def set_engine(self, engine):
        self.engine = engine
        self.mirror.engine = engine 
        
    def update_draft(self, suggestions, winrate, lane_status, context):
        snapshot = context.get('snapshot')
        my_cell = context.get('my_cell', -1)
        is_banning = context.get('is_banning', False)
        has_action = context.get('has_action', False) # New context
        phase = context.get('phase', 'UNKNOWN')
        
        if snapshot:
            self.mirror.update_gamestate(snapshot, my_cell, is_banning, has_action, phase)
            
            # --- SYNC SELECTION FROM SNAPSHOT ---
            # --- SYNC SELECTION FROM SNAPSHOT ---
            # Correct Logic: "Change-Based Sync"
            # Only update local state if the external state (Client) has CHANGED.
            # This allows local clicks to persist even if Client lags, 
            # but if User actively changes champ in Client, we catch it.
            
            try:
                # snapshot is (picks, bans, ...)
                picks = snapshot[0]
                bans = snapshot[1]
                
                # Check for active selection in my cell
                current_selection = 0
                if is_banning:
                     if len(bans) > my_cell: current_selection = bans[my_cell]
                else:
                     if len(picks) > my_cell: current_selection = picks[my_cell]
                     
                # Check for State Change
                if current_selection != self.last_snapshot_selection:
                     # Client state changed! We should respect this update.
                     if current_selection > 0:
                          self.last_selected_id = current_selection
                          # print(f"[OVERLAY] Synced to Client Selection: {current_selection}")
                     
                     self.last_snapshot_selection = current_selection
                     
            except Exception as e:
                print(f"[OVERLAY] Sync Error: {e}")
            
        # Update Suggestions in Center Panel
        if suggestions:
             header_text = "SUGGESTED BAN" if is_banning else "SUGGESTED PICK"
             self.mirror.center_header.setText(header_text)
             for i, cw in enumerate(self.mirror.suggestion_cards):
                  if i < len(suggestions):
                      cw.update_data(suggestions[i])
                      cw.setVisible(True)
                  else:
                      cw.setVisible(False)
        else:
             self.mirror.center_header.setText("TITAN AI")
             for cw in self.mirror.suggestion_cards: cw.setVisible(False)

    def on_recommendation_clicked(self, champ_id):
        self.last_interaction_time = time.time()
        print(f"[OVERLAY] Interaction Event: {champ_id}")
        
        if champ_id == "LOCK":
            print(f"[OVERLAY] Lock Request. ID: {self.last_selected_id}")
            try:
                if self.engine: 
                     self.mirror.btn_lock.setText("...")
                     self.mirror.btn_lock.repaint() # Force redraw
                     
                     print(f"[OVERLAY] Calling Engine Lock In...")
                     res = self.engine.lock_in(self.last_selected_id)
                     
                     if res:
                          self.mirror.btn_lock.setText("LOCKED")
                          # Trigger Flash Effect
                          self._trigger_flash()
                     else:
                          self.mirror.btn_lock.setText("FAILED")
                          # Reset text after delay (handled by next update loop anyway)
                else:
                     print(f"[OVERLAY] Engine not connected!")
                     self.mirror.btn_lock.setText("NO LINK")
            except Exception as e:
                print(f"[OVERLAY] Lock In Exception: {e}")
                self.mirror.btn_lock.setText("ERROR")
            return
            
        # Normal Card Click
        print(f"[OVERLAY] Card Clicked: {champ_id}")
        self.last_selected_id = champ_id
        if self.engine:
            self.engine.act_on_suggestion(champ_id)
            
    def update_status(self, text, color):
        pass
        
    def update_build(self, b_champ, b_items): pass
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        rect = self.rect()
        w, h = rect.width(), rect.height()
        cx, cy = w / 2, h / 2
        radius = 16
        
        # === 1. DEEP VOID BACKGROUND (Radial Depth) ===
        # Deep space feel that gets darker at the edges
        bg_grad = QRadialGradient(cx, cy, w * 0.8)
        bg_grad.setColorAt(0, QColor(8, 15, 25))   # Center: Deep Navy
        bg_grad.setColorAt(1, QColor(THEME['bg_main'])) # Edges: Void
        painter.fillRect(rect, bg_grad)
        
        # === 1.b. LIVING NEBULA (Volumetric Drift & Parallax) ===
        cursor_pos = self.mapFromGlobal(self.cursor().pos())
        mx = cursor_pos.x() / w if w > 0 else 0.5
        my = cursor_pos.y() / h if h > 0 else 0.5
        
        for i, b in enumerate(self._nebula_blobs):
            # Calculate parallax offset based on depth index `i`
            px = b['x'] * w + (0.5 - mx) * (60 * (i + 1))
            py = b['y'] * h + (0.5 - my) * (60 * (i + 1))
            pr = b['r'] * w
            
            nebula_grad = QRadialGradient(px, py, pr)
            c = QColor(b['color'])
            # Soft pulsing alpha
            base_alpha = 12 + 6 * math.sin(self._ambient_phase + i)
            c.setAlpha(int(base_alpha))
            nebula_grad.setColorAt(0, c)
            nebula_grad.setColorAt(1, QColor(0, 0, 0, 0))
            
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(nebula_grad))
            painter.drawRect(rect)
        
        # === 2. VIGNETTE (Soft Royal Fade) ===
        vig_color = QColor(2, 4, 10, 200) # Deep dark shadow
        
        # Top gradient
        v_top = QLinearGradient(0, 0, 0, h * 0.15)
        v_top.setColorAt(0, vig_color)
        v_top.setColorAt(1, QColor(0,0,0,0))
        painter.fillRect(0, 0, w, int(h*0.15), v_top)
        
        # Bottom gradient
        v_bot = QLinearGradient(0, h, 0, h * 0.15)
        v_bot.setColorAt(0, vig_color)
        v_bot.setColorAt(1, QColor(0,0,0,0))
        painter.fillRect(0, int(h*0.85), w, int(h*0.15), v_bot)
        
        # === 3. SLEEK OUTER GLASS BORDER ===
        frame_rect = rect.adjusted(1, 1, -1, -1)
        
        # Very subtle inner shimmer
        pulse = 0.5 + 0.5 * math.sin(self._ambient_phase * 1.5)
        shimmer_c = QColor(THEME['border_active'])
        shimmer_c.setAlpha(int(30 + 30 * pulse))
        
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(shimmer_c, 1))
        painter.drawRoundedRect(frame_rect, radius, radius)
        
        # Thicker structural border in dark grey
        painter.setPen(QPen(QColor(THEME['border_norm']), 2))
        painter.drawRoundedRect(rect.adjusted(3, 3, -3, -3), radius, radius)
        
        # === FLASH OVERLAY (Radial Burst) ===
        if self._flash_opacity > 0.01:
            # Radial gradient burst from center
            flash_grad = QConicalGradient(cx, cy, 0)
            for i in range(8):
                pos = i / 8
                alpha = int(200 * self._flash_opacity * (0.5 + 0.5 * math.sin(pos * 6.28 + self._border_rotation * 0.1)))
                flash_grad.setColorAt(pos, QColor(255, 255, 255, alpha))
            
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(flash_grad))
            
            # Expanding circle flash
            flash_radius = self._flash_opacity * max(w, h) * 0.8
            painter.drawEllipse(QPointF(cx, cy), flash_radius, flash_radius)
            
            # Additional white overlay
            painter.setBrush(QColor(255, 255, 255, int(100 * self._flash_opacity)))
            painter.drawRoundedRect(rect, radius, radius)
    
    def _trigger_flash(self):
        """Trigger the lock-in flash animation smoothly."""
        self.anim_flash.stop()
        self.anim_flash.setStartValue(1.0)
        self.anim_flash.setEndValue(0.0)
        self.anim_flash.start()
    
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

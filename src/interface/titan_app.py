
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
        self._bg_particles = []
        # Color variants: teal, gold, white
        particle_colors = [
            (10, 180, 160),   # Hextech Teal
            (200, 170, 100),  # Gold
            (180, 200, 220),  # Cool White
            (100, 220, 200),  # Bright Teal
            (220, 180, 80),   # Warm Gold
        ]
        for _ in range(40):  # More particles
            color = random.choice(particle_colors)
            self._bg_particles.append({
                'x': random.uniform(0, 1150),
                'y': random.uniform(0, 750),
                'vx': random.uniform(-0.3, 0.3),
                'vy': random.uniform(-0.5, 0.15),
                'size': random.uniform(1.5, 4),
                'alpha': random.uniform(0.3, 0.7),
                'color': color,
                'trail': [],  # Store previous positions for trail effect
                'is_comet': random.random() < 0.15,  # 15% are larger comets
            })
        
        # Energy Wave Ripples
        self._energy_waves = []  # List of {cx, cy, radius, alpha, max_radius}
        
        # Rotating Border Phase
        self._border_rotation = 0.0
        
        self._ambient_timer = QTimer(self)
        self._ambient_timer.timeout.connect(self._tick_ambient)
        self._ambient_timer.setInterval(16)  # 60 FPS for smoother animations
        self._ambient_timer.start()
    
    def _tick_ambient(self):
        """Update ambient background animation."""
        self._ambient_phase += 0.025
        self._border_rotation += 0.8  # Degrees per frame
        if self._border_rotation >= 360:
            self._border_rotation = 0
            
        w, h = self.width(), self.height()
        
        for p in self._bg_particles:
            # Store trail position before moving
            if p.get('is_comet') or p['size'] > 2.5:
                p['trail'].append((p['x'], p['y']))
                if len(p['trail']) > 8:  # Keep last 8 positions
                    p['trail'].pop(0)
            
            p['x'] += p['vx']
            p['y'] += p['vy']
            
            # Wrap around
            if p['x'] < 0: p['x'] = w; p['trail'] = []
            if p['x'] > w: p['x'] = 0; p['trail'] = []
            if p['y'] < 0: p['y'] = h; p['trail'] = []
            if p['y'] > h: p['y'] = 0; p['trail'] = []
        
        # Update energy waves
        new_waves = []
        for wave in self._energy_waves:
            wave['radius'] += 4  # Expand speed
            wave['alpha'] -= 0.02  # Fade speed
            if wave['alpha'] > 0 and wave['radius'] < wave['max_radius']:
                new_waves.append(wave)
        self._energy_waves = new_waves
        
        self.update()
    
    def spawn_energy_wave(self, cx=None, cy=None):
        """Spawn a new energy wave ripple from the given center."""
        if cx is None:
            cx = self.width() / 2
        if cy is None:
            cy = self.height() / 2
        self._energy_waves.append({
            'cx': cx, 'cy': cy,
            'radius': 10,
            'alpha': 0.8,
            'max_radius': max(self.width(), self.height()) * 0.6
        })
    
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
        
        # === 1. DEEP VOID BACKGROUND ===
        bg_color = QColor(1, 10, 19) # Deepest Blue
        painter.fillRect(rect, bg_color)
        
        # === 2. DEMACIAN ATMOSPHERE (Godrays & Radiance) ===
        # Top-Center Godray (Holy Light)
        godray_grad = QRadialGradient(cx, -h * 0.2, h * 1.2)
        godray_grad.setColorAt(0, QColor(20, 40, 80, 100)) # Royal Blue Glow
        godray_grad.setColorAt(0.5, QColor(10, 20, 40, 50))
        godray_grad.setColorAt(1, QColor(0, 0, 0, 0))
        
        painter.setBrush(QBrush(godray_grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(rect)
        
        # Bottom-Up Reflection (Ground glow)
        ground_grad = QLinearGradient(0, h, 0, h - 150)
        ground_grad.setColorAt(0, QColor(30, 30, 60, 80)) # Dark Blue/Navy
        ground_grad.setColorAt(1, QColor(0, 0, 0, 0))
        painter.setBrush(QBrush(ground_grad))
        painter.drawRect(rect)
        
        # === 3. VIGNETTE (Soft Royal Fade) ===
        vig_color = QColor(2, 5, 12, 180) # Very Dark Navy
        
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
        
        # === ENERGY RIPPLES -> RADIANT PULSE RINGS (Gold/White) ===
        for wave in self._energy_waves:
            alpha = int(255 * wave['alpha'] * 0.2)
            # Gold/White rings
            wave_color = QColor(255, 250, 220, alpha)
            pen = QPen(wave_color, 1.5)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            
            # Perfect Circles for "Divine" look (instead of Hexagons)
            r = wave['radius']
            painter.drawEllipse(QPointF(wave['cx'], wave['cy']), r, r)
            
            if r > 20:
                inner_alpha = int(255 * wave['alpha'] * 0.1)
                painter.setPen(QPen(QColor(100, 200, 255, inner_alpha), 1))
                painter.drawEllipse(QPointF(wave['cx'], wave['cy']), r * 0.8, r * 0.8)
        
        # === AMBIENT PARTICLES WITH TRAILS ===
        for p in self._bg_particles:
            color = p.get('color', (10, 180, 160))
            base_alpha = int(255 * p['alpha'] * (0.5 + 0.5 * math.sin(self._ambient_phase + p['x'] / 80)))
            
            # Draw trail first (behind particle)
            trail = p.get('trail', [])
            if len(trail) > 1:
                for i, (tx, ty) in enumerate(trail):
                    trail_alpha = int(base_alpha * (i / len(trail)) * 0.5)
                    trail_size = p['size'] * (0.3 + 0.5 * (i / len(trail)))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QColor(color[0], color[1], color[2], trail_alpha))
                    painter.drawEllipse(QPointF(tx, ty), trail_size, trail_size)
            
            # Draw main particle
            particle_color = QColor(color[0], color[1], color[2], base_alpha)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(particle_color)
            size = p['size'] * 1.5 if p.get('is_comet') else p['size']
            painter.drawEllipse(QPointF(p['x'], p['y']), size, size)
            
            # Bright core for comets
            if p.get('is_comet'):
                painter.setBrush(QColor(255, 255, 255, int(base_alpha * 0.8)))
                painter.drawEllipse(QPointF(p['x'], p['y']), size * 0.4, size * 0.4)
        
        # === ROTATING CONICAL GRADIENT BORDER ===
        border_pulse = 0.6 + 0.4 * math.sin(self._ambient_phase * 0.8)
        
        # Outer glow layer
        for i, thickness in enumerate([6, 3]):
            alpha = int(30 * border_pulse) if i == 0 else int(80 * border_pulse)
            glow_color = QColor(10, 180, 160, alpha)
            pen = QPen(glow_color, thickness)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(2, 2, -2, -2), radius, radius)
        
        # === DEMACIAN BORDER (DOUBLE GOLD PLATE) ===
        # 1. Outer Frame (Dark Bronze/Gold, Thicker)
        outer_rect = rect.adjusted(4, 4, -4, -4)
        
        # Metallic Gradient for Outer Frame
        outer_grad = QLinearGradient(0, 0, w, h)
        outer_grad.setColorAt(0.0, QColor("#504020")) # Dark Bronze
        outer_grad.setColorAt(0.4, QColor("#997530")) # Mid Gold
        outer_grad.setColorAt(0.5, QColor("#F0E6D2")) # Shine
        outer_grad.setColorAt(0.6, QColor("#997530")) 
        outer_grad.setColorAt(1.0, QColor("#504020"))
        
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QBrush(outer_grad), 3)) 
        painter.drawRoundedRect(outer_rect, radius, radius)
        
        # 2. Inner Frame (Bright Polished Gold, Thinner)
        # Gap of 6px
        inner_rect = outer_rect.adjusted(6, 6, -6, -6)
        
        # Bright Gold Gradient
        inner_grad = QLinearGradient(w, 0, 0, h) # Opposing angle
        inner_grad.setColorAt(0.0, QColor("#D4AF37"))
        inner_grad.setColorAt(0.5, QColor("#FFFFFF")) # White Hot Shine
        inner_grad.setColorAt(1.0, QColor("#D4AF37"))
        
        painter.setPen(QPen(QBrush(inner_grad), 1.5))
        painter.drawRoundedRect(inner_rect, radius-4, radius-4)
        
        # 3. Corner Brackets (Connecting the two frames)
        # We draw L-shapes at the corners that bridge the gap
        bracket_len = 25
        bracket_c = QColor("#D4AF37") # Pure Gold
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bracket_c)
        
        # Helper to draw L-shape
        def draw_corner(cx, cy, rotation):
            painter.save()
            painter.translate(cx, cy)
            painter.rotate(rotation)
            # Draw L-shape connecting outer (0,0) towards inner
            # Simple thick bracket style
            path = QPainterPath()
            path.moveTo(0, 0)
            path.lineTo(bracket_len, 0)
            path.lineTo(bracket_len, 4) # Thickness
            path.lineTo(4, 4)
            path.lineTo(4, bracket_len)
            path.lineTo(0, bracket_len)
            path.closeSubpath()
            painter.drawPath(path)
            painter.restore()
            
        # Top-Left
        draw_corner(outer_rect.left()-1, outer_rect.top()-1, 0)
        # Top-Right
        draw_corner(outer_rect.right()+1, outer_rect.top()-1, 90)
        # Bottom-Right
        draw_corner(outer_rect.right()+1, outer_rect.bottom()+1, 180)
        # Bottom-Left
        draw_corner(outer_rect.left()-1, outer_rect.bottom()+1, 270)
        
        # 4. "Breathing" Light in the Gap (Optional subtle pulse)
        pulse = 0.5 + 0.5 * math.sin(self._ambient_phase * 2)
        if pulse > 0.01:
            glow_c = QColor(THEME['accent_blue'])
            glow_c.setAlpha(int(30 * pulse)) # Very subtle
            painter.setPen(QPen(glow_c, 4))
            gap_rect = outer_rect.adjusted(3,3,-3,-3)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(gap_rect, radius-2, radius-2)

        # Corner accent diamonds (Fixed)
        accent_alpha = int(200 + 55 * border_pulse)
        accent_color = QColor(255, 255, 255, accent_alpha) # White diamonds
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(accent_color)
        
        # Top-left corner accent
        painter.save()
        painter.translate(12, 12)
        painter.rotate(45)
        painter.drawRect(-3, -3, 6, 6)
        painter.restore()
        
        # Bottom-right corner accent
        painter.save()
        painter.translate(w - 12, h - 12)
        painter.rotate(45)
        painter.drawRect(-3, -3, 6, 6)
        painter.restore()
        
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
        """Trigger the lock-in flash animation with energy wave burst."""
        self.anim_flash.stop()
        self.anim_flash.setStartValue(1.0)
        self.anim_flash.setEndValue(0.0)
        self.anim_flash.start()
        
        # Spawn multiple energy waves for dramatic effect
        cx, cy = self.width() / 2, self.height() / 2
        self.spawn_energy_wave(cx, cy)
        QTimer.singleShot(100, lambda: self.spawn_energy_wave(cx, cy))
        QTimer.singleShot(200, lambda: self.spawn_energy_wave(cx, cy))
    
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

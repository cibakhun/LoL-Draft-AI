from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QPointF, QSize, QPropertyAnimation, QEasingCurve, pyqtProperty, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QLinearGradient, QPolygonF, QPixmap, QPainterPath, QConicalGradient, QRadialGradient
import random
import math

THEME = {
    "bg_main": "#050A14", # Deep Navy
    "bg_glass": "rgba(240, 245, 255, 0.10)", # White/Blue Tinted Glass (Brighter)
    "bg_glass_dark": "rgba(10, 20, 40, 0.85)", # Deep Royal Blue
    "border_norm": "#786E55", # Muted Bronze
    "border_active": "#D4AF37", # True Gold
    "border_glow": "#FFFDF0", # Radiant White-Gold
    "text_main": "#F0F5FF", # Ice White
    "text_dim": "#8CA6C8", # Muted Steel Blue
    "accent_blue": "#E6FFFF", # Radiance (White-Blue)
    "accent_blue_dim": "rgba(230, 255, 255, 0.2)",
    "accent_red": "#FF4455", # Vivid Red
    "success": "#0AC8B9",
    "font_main": "Segoe UI",
    "font_data": "Consolas",
}

class HexEffect(QGraphicsDropShadowEffect):
    def __init__(self, color=THEME['accent_blue'], blur=15, parent=None):
        super().__init__(parent)
        self.setBlurRadius(blur)
        self.setColor(QColor(color))
        self.setOffset(0, 0)

class HexFrame(QFrame):
    """
    Base class for Hextech-styled frames with angled corners and borders.
    """
    def __init__(self, parent=None, active=False, color_key="border_norm"):
        super().__init__(parent)
        self.active = active
        self.color_key = color_key
        self.hovered = False
        
        # Enable mouse tracking for hover effects
        self.setMouseTracking(True)

    def set_active(self, active):
        self.active = active
        self.update()

    def enterEvent(self, event):
        self.hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.hovered = False
        self.update()
        super().leaveEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        w, h = rect.width(), rect.height()
        
        # Determine Base Colors
        c_active = QColor(THEME['border_active'])
        c_norm = QColor(THEME['border_norm'])
        c_blue = QColor(THEME['accent_blue'])
        
        base_border = c_active if (self.active or self.hovered) else c_norm
        if self.active: base_border = c_blue
        
        # Background Gradient - LINEAR to match angles
        grad = QLinearGradient(0, 0, w, h)
        if hasattr(self, 'active') and self.active:
            grad.setColorAt(0, QColor(THEME['bg_glass']))
            grad.setColorAt(1, QColor(THEME['bg_glass_dark']))
        elif hasattr(self, 'hovered') and self.hovered:
            grad.setColorAt(0, QColor(THEME['bg_glass']))
            grad.setColorAt(1, QColor(0, 0, 0, 150))
        else:
            grad.setColorAt(0, QColor(0, 0, 0, 100))
            grad.setColorAt(1, QColor(0, 0, 0, 200))
            
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        
        # Draw Angled Background
        cut = 15 
        poly = QPolygonF([
            QPointF(0, 0), QPointF(w - cut, 0),
            QPointF(w, cut), QPointF(w, h),
            QPointF(cut, h), QPointF(0, h - cut)
        ])
        painter.drawPolygon(poly)
        
        # --- DEMACIAN REGAL BORDER DESIGN (POLISHED GOLD) ---
        
        # 0. Shadow/Glow behind
        if (hasattr(self, 'active') and self.active) or (hasattr(self, 'hovered') and self.hovered):
             painter.setPen(Qt.PenStyle.NoPen)
             glow_c = QColor(THEME['border_active'])
             glow_c.setAlpha(40)
             painter.setBrush(glow_c)
             painter.drawPolygon(poly.translated(0, 2))
        
        # 1. Base Structure - Metallic Gold Gradient
        # Create a gradient brush for the pen (PyQt6 requires QPen with QBrush)
        gold_grad = QLinearGradient(0, 0, w, h)
        c_dark = QColor("#785A28") # Dark Bronze
        c_mid  = QColor("#D4AF37") # Classic Gold
        c_lite = QColor("#FFFDF0") # Highlight
        
        gold_grad.setColorAt(0.0, c_dark)
        gold_grad.setColorAt(0.2, c_mid)
        gold_grad.setColorAt(0.4, c_lite) # Shine
        gold_grad.setColorAt(0.6, c_mid)
        gold_grad.setColorAt(1.0, c_dark)
        
        # --- DEMACIAN BORDER (DOUBLE GOLD PLATE - HEXAGONAL) ---
        
        # 1. Outer Frame (Dark Bronze/Gold, Thicker)
        # Gradient Brush defined above (lines 109-118) remains useful
        pen_outer = QPen(QBrush(gold_grad), 3)
        pen_outer.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        painter.setPen(pen_outer)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPolygon(poly)
        
        # 2. Inner Frame (Bright Polished Gold, Thinner)
        # Calculate inner polygon with gap
        gap = 5
        poly_inner = QPolygonF([
            QPointF(gap, gap), QPointF(w - cut - gap/2, gap),
            QPointF(w - gap, cut + gap/2), QPointF(w - gap, h - gap),
            QPointF(cut + gap/2, h - gap), QPointF(gap, h - cut - gap/2)
        ])
        
        # Bright Gold Gradient for Inner
        inner_grad = QLinearGradient(w, 0, 0, h)
        inner_grad.setColorAt(0.0, c_mid)
        inner_grad.setColorAt(0.5, c_lite) # White Hot
        inner_grad.setColorAt(1.0, c_mid)
        
        pen_inner = QPen(QBrush(inner_grad), 1.5)
        painter.setPen(pen_inner)
        painter.drawPolygon(poly_inner)
        
        # 3. Corner Brackets (Connecting the plates)
        # Gold L-shapes at the corners
        painter.setPen(Qt.PenStyle.NoPen)
        b_col = QColor(THEME['border_active']) 
        painter.setBrush(b_col)
        
        # We'll use small rects or paths to bridge the gap at specific points
        # Top-Left Vertical
        painter.drawRect(0, 0, 3, 20)
        # Top-Left Horizontal
        painter.drawRect(0, 0, 20, 3)
        
        # Top-Right
        painter.drawRect(int(w-20), 0, 20, 3)
        painter.drawRect(int(w-3), 0, 3, 20)
        
        # Bottom-Left
        painter.drawRect(0, int(h-20), 3, 20)
        painter.drawRect(0, int(h-3), 20, 3)
        
        # Bottom-Right
        painter.drawRect(int(w-20), int(h-3), 20, 3)
        painter.drawRect(int(w-3), int(h-20), 3, 20)
        
        # Top Center Diamond (Regal Accent)
        if hasattr(self, 'active') and self.active:
            painter.save()
            painter.translate(w/2, 0)
            painter.rotate(45)
            painter.setBrush(QColor("#FFFDF0")) # White Gold
            painter.drawRect(-4, -4, 8, 8)
            painter.restore()
            
            # Top-Right "Wing" Accent
            tr_wings = QPolygonF([
                 QPointF(w+2, -2), 
                 QPointF(w-25, -2), 
                 QPointF(w-5, 18),
                 QPointF(w+2, 18)
            ])
            painter.drawPolygon(tr_wings)
            
            # Bottom-Left "Wing" Accent
            bl_wings = QPolygonF([
                 QPointF(-2, h+2),
                 QPointF(-2, h-25),
                 QPointF(18, h-5),
                 QPointF(18, h+2)
            ])
            painter.drawPolygon(bl_wings)
            
            # Corner Gems (Blue Radiance)
            painter.setBrush(QColor(THEME['accent_blue']))
            painter.drawEllipse(QPointF(w-8, 8), 2, 2)
            painter.drawEllipse(QPointF(8, h-8), 2, 2)


class AnimatedHexFrame(HexFrame):
    """
    Premium animated frame with layered glow effects.
    """
    def __init__(self, parent=None, active=True, color_key="border_active"):
        super().__init__(parent, active, color_key)
        self._pulse_phase = 0.0
        
        self._border_timer = QTimer(self)
        self._border_timer.timeout.connect(self._tick_border)
        self._border_timer.setInterval(25)  # 40 FPS for smoother animation
        self._border_timer.start()
    
    def _tick_border(self):
        self._pulse_phase += 0.06
        if self._pulse_phase >= 6.28:
            self._pulse_phase = 0
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        w, h = self.width(), self.height()
        
        # --- DEMACIAN "DOUBLE GOLD PLATE" BORDER ---
        
        # 1. Outer Frame (Dark Bronze/Gold, Thicker)
        # 3px solid frame
        outer_rect = QRectF(3, 3, w-6, h-6)
        
        # Metallic Gradient
        outer_grad = QLinearGradient(0, 0, w, h)
        outer_grad.setColorAt(0.0, QColor("#504020")) # Dark Bronze
        outer_grad.setColorAt(0.4, QColor("#997530")) # Mid Gold
        outer_grad.setColorAt(0.5, QColor("#F0E6D2")) # Shine
        outer_grad.setColorAt(0.6, QColor("#997530")) 
        outer_grad.setColorAt(1.0, QColor("#504020"))
        
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QBrush(outer_grad), 3)) 
        painter.drawRect(outer_rect)
        
        # 2. Inner Frame (Bright Polished Gold, Thinner)
        # Gap of 5px
        inner_rect = outer_rect.adjusted(5, 5, -5, -5)
        
        # Bright Gold Gradient
        inner_grad = QLinearGradient(w, 0, 0, h)
        inner_grad.setColorAt(0.0, QColor("#D4AF37"))
        inner_grad.setColorAt(0.5, QColor("#FFFFFF")) # White Hot Shine
        inner_grad.setColorAt(1.0, QColor("#D4AF37"))
        
        painter.setPen(QPen(QBrush(inner_grad), 1.5))
        painter.drawRect(inner_rect)
        
        # 3. "Breathing" Light in the Gap
        pulse = 0.5 + 0.5 * math.sin(self._pulse_phase)
        if pulse > 0.1:
            glow_c = QColor(THEME['accent_blue'])
            glow_c.setAlpha(int(30 * pulse)) # Very subtle sheen
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(glow_c)
            # Draw rect in the gap
            gap_rect = outer_rect.adjusted(2, 2, -2, -2)
            painter.drawRect(gap_rect)
            
        # 4. Corner Brackets (Connecting the two frames)
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
        draw_corner(outer_rect.left(), outer_rect.top(), 0)
        # Top-Right
        draw_corner(outer_rect.right(), outer_rect.top(), 90)
        # Bottom-Right
        draw_corner(outer_rect.right(), outer_rect.bottom(), 180)
        # Bottom-Left
        draw_corner(outer_rect.left(), outer_rect.bottom(), 270)


class CardWidget(HexFrame):
    clicked = pyqtSignal(str)
    
    def __init__(self, loader, data, badge=None):
        super().__init__(active=False)
        self.loader = loader
        self.data = data
        self.badge_text = badge
        
        self.setFixedSize(140, 200)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        # Animation Properties
        self._hover_progress = 0.0
        self._click_scale = 1.0
        self._intro_progress = 0.0
        self._shimmer_offset = -0.5  # Shimmer light position
        self._shimmer_hue = 0.0  # For rainbow effect
        self._particles = []  # List of particle dicts
        
        # NEW: Levitation/Float Effect
        self._float_phase = 0.0
        self._float_offset = 0.0  # Vertical offset in pixels
        
        # NEW: Tilt toward cursor
        self._tilt_x = 0.0  # -1 to 1 based on cursor position
        self._tilt_y = 0.0
        
        # NEW: Winrate-based glow pulse speed
        self._wr_pulse_speed = 1.0  # Modified based on winrate
        
        # NEW: Badge animation
        self._badge_progress = 0.0
        
        # Animations
        self.anim_hover = QPropertyAnimation(self, b"hover_progress")
        self.anim_hover.setDuration(250)
        self.anim_hover.setEasingCurve(QEasingCurve.Type.OutCubic)
        
        self.anim_click = QPropertyAnimation(self, b"click_scale")
        self.anim_click.setDuration(120)
        
        self.anim_intro = QPropertyAnimation(self, b"intro_progress")
        self.anim_intro.setDuration(500)
        self.anim_intro.setEasingCurve(QEasingCurve.Type.OutBack)
        
        # Timer for continuous effects (shimmer, particles, float)
        self._effect_timer = QTimer(self)
        self._effect_timer.timeout.connect(self._tick_effects)
        self._effect_timer.setInterval(16)  # ~60 FPS
        
        # Cache for expensive pixmaps
        self._icon_pixmap = None
        self._cached_id = None
        
        # Initial update
        self.update_data(data)
    
    def _tick_effects(self):
        """Update shimmer, particles, and float each frame."""
        # Shimmer sweep with rainbow hue rotation
        if self._hover_progress > 0.1:
            self._shimmer_offset += 0.025
            self._shimmer_hue += 3.0  # Rotate hue for rainbow
            if self._shimmer_hue >= 360:
                self._shimmer_hue = 0
            if self._shimmer_offset > 1.5:
                self._shimmer_offset = -0.5
        
        # Floating levitation effect
        if self._hover_progress > 0.3:
            self._float_phase += 0.08 * self._wr_pulse_speed
            self._float_offset = 3 * math.sin(self._float_phase) * self._hover_progress
        else:
            self._float_offset *= 0.9  # Ease back down
        
        # Badge slide-in animation
        if self._badge_progress < 1.0:
            self._badge_progress += 0.05
        
        # Particle physics
        new_particles = []
        for p in self._particles:
            p['life'] -= 0.015 * self._wr_pulse_speed
            p['x'] += p['vx']
            p['y'] += p['vy']
            p['vy'] += 0.015  # Lighter gravity
            
            # Trail effect - store history
            if 'trail' not in p:
                p['trail'] = []
            p['trail'].append((p['x'], p['y']))
            if len(p['trail']) > 5:
                p['trail'].pop(0)
                
            if p['life'] > 0:
                new_particles.append(p)
        self._particles = new_particles
        
        # Spawn particles - burst on hover start, then continuous
        if self._hover_progress > 0.5 and len(self._particles) < 20:
            spawn_chance = 0.4 if len(self._particles) < 5 else 0.15
            if random.random() < spawn_chance:
                self._spawn_particle()
        
        self.update()
    
    def _spawn_particle(self, burst=False):
        """Create a new sparkle particle near the icon."""
        cx, cy = self.width() / 2, 80
        
        # Star-shaped particles have rotation
        angle = random.uniform(0, 360)
        speed = random.uniform(0.3, 1.2) if burst else random.uniform(0.3, 0.8)
        
        self._particles.append({
            'x': cx + random.uniform(-35, 35),
            'y': cy + random.uniform(-35, 35),
            'vx': math.cos(math.radians(angle)) * speed,
            'vy': math.sin(math.radians(angle)) * speed - 0.8,
            'life': 1.0,
            'size': random.uniform(2.5, 6),
            'rotation': angle,
            'is_star': random.random() < 0.4,  # 40% are star-shaped
            'hue': random.uniform(160, 200),  # Teal to cyan range
            'trail': []
        })
    
    def spawn_particle_burst(self, count=8):
        """Spawn a burst of particles for dramatic effect."""
        for _ in range(count):
            self._spawn_particle(burst=True)

    @pyqtProperty(float)
    def intro_progress(self):
        return self._intro_progress
        
    @intro_progress.setter
    def intro_progress(self, val):
        self._intro_progress = val
        self.update()

    @pyqtProperty(float)
    def hover_progress(self):
        return self._hover_progress
        
    @hover_progress.setter
    def hover_progress(self, val):
        self._hover_progress = val
        self.update()
        
    @pyqtProperty(float)
    def click_scale(self):
        return self._click_scale
        
    @click_scale.setter
    def click_scale(self, val):
        self._click_scale = val
        self.update()

    def enterEvent(self, event):
        self.anim_hover.stop()
        self.anim_hover.setStartValue(self._hover_progress)
        self.anim_hover.setEndValue(1.0)
        self.anim_hover.start()
        self._effect_timer.start()  # Start shimmer/particle timer
        
        # Spawn burst of particles on hover start
        self.spawn_particle_burst(6)
        
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.anim_hover.stop()
        self.anim_hover.setStartValue(self._hover_progress)
        self.anim_hover.setEndValue(0.0)
        self.anim_hover.start()
        # Don't stop timer immediately - let particles fade out
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.anim_click.stop()
            self.anim_click.setStartValue(1.0)
            self.anim_click.setEndValue(0.95)
            self.anim_click.setEasingCurve(QEasingCurve.Type.OutQuad)
            self.anim_click.start()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            # Spring back
            self.anim_click.stop()
            self.anim_click.setStartValue(self._click_scale)
            self.anim_click.setEndValue(1.0)
            self.anim_click.setEasingCurve(QEasingCurve.Type.OutElastic) # Juicy bounce
            self.anim_click.start()
            
            if self.data and 'id' in self.data:
                self.clicked.emit(str(self.data['id']))
        super().mouseReleaseEvent(event)

    def update_data(self, data):
        self.data = data
        cid = data.get('id')
        wr = data.get('wr', 50.0)
        
        # Set winrate-based pulse speed (high WR = faster pulse)
        if wr > 52.0:
            self._wr_pulse_speed = 1.5 + (wr - 52) * 0.1  # Faster for higher WR
        elif wr < 48.0:
            self._wr_pulse_speed = 0.7  # Slower for low WR
        else:
            self._wr_pulse_speed = 1.0
        
        # Update Icon only if changed
        if cid != self._cached_id and self.loader and cid:
            path = self.loader.get_champ_icon_path(str(cid))
            if path:
                original = QPixmap(path)
                self._icon_pixmap = original.scaled(100, 100, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self._cached_id = cid
            
            # Trigger Entry Animation
            self.anim_intro.stop()
            self.anim_intro.setStartValue(0.0)
            self.anim_intro.setEndValue(1.0)
            self.anim_intro.start()
        
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        rect = self.rect()
        w, h = rect.width(), rect.height()
        cut = 15
        
        # --- 0. Entry Animation Transform ---
        if self._intro_progress < 1.0:
            painter.setOpacity(self._intro_progress)
            slide_off = 15 * (1.0 - self._intro_progress)
            painter.translate(0, slide_off)
        
        # --- 0.5 Float/Levitation Effect ---
        if abs(self._float_offset) > 0.1:
            painter.translate(0, -self._float_offset)
        
        # --- 1. Apply Click Scale Transform ---
        painter.translate(w/2, h/2)
        painter.scale(self._click_scale, self._click_scale)
        painter.translate(-w/2, -h/2)
        
        # --- 2. BASE GLASS BACKGROUND (Royal Blue) ---
        poly = QPolygonF([
            QPointF(0, 0), QPointF(w - cut, 0),
            QPointF(w, cut), QPointF(w, h),
            QPointF(cut, h), QPointF(0, h - cut),
            QPointF(0, cut * 2)
        ])
        
        grad_bg = QLinearGradient(0, 0, 0, h)
        
        # Hover logic: Brighten significantly for "Holy" feel
        if self._hover_progress > 0.01:
            # Radiant Blue/Gold tint on hover
            grad_bg.setColorAt(0, QColor(20, 40, 80, 240))
            grad_bg.setColorAt(1, QColor(10, 20, 50, 250))
        else:
            # Deep Navy default
            grad_bg.setColorAt(0, QColor(10, 20, 30, 240))
            grad_bg.setColorAt(1, QColor(5, 8, 12, 250))
            
        painter.setBrush(QBrush(grad_bg))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(poly)
        
        # --- 3. RADIANT GODRAY (The "Sweeping Beam") ---
        # A vertical beam of light that appears on hover
        if self._hover_progress > 0.01:
            painter.save()
            path = QPainterPath()
            path.addPolygon(poly)
            painter.setClipPath(path)
            
            # Beam width and position
            beam_w = w * 0.8
            beam_x = (w - beam_w) / 2
            
            beam_grad = QLinearGradient(0, h, 0, 0) # Bottom to Top
            c_beam = QColor(THEME['accent_blue'])
            # Alpha based on hover
            beam_alpha = int(80 * self._hover_progress) 
            
            beam_grad.setColorAt(0, QColor(255, 255, 255, 0))
            beam_grad.setColorAt(0.5, QColor(c_beam.red(), c_beam.green(), c_beam.blue(), beam_alpha))
            beam_grad.setColorAt(1, QColor(255, 255, 255, 0))
            
            painter.setBrush(QBrush(beam_grad))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(int(beam_x), 0, int(beam_w), h)
            
            painter.restore()
        
        # --- 4. CHAMPION VISUALS (Lift & Halo) ---
        if self._icon_pixmap:
            painter.save()
            path = QPainterPath()
            path.addPolygon(poly)
            painter.setClipPath(path)
            
            cx, cy = w/2, 70
            
            # --- ANIMATION: LIFT & SCALE ---
            progress = self._hover_progress
            # Smooth ease-out for scale: 1.0 -> 1.15
            scale_factor = 1.0 + (0.15 * progress)
            # Lift up: 0 -> -10 pixels
            lift_y = -10 * progress
            
            # --- A. HOLY HALO (Backglow) ---
            if progress > 0.01:
                halo_r = 70 * scale_factor
                halo_grad = QRadialGradient(cx, cy + lift_y, halo_r)
                halo_grad.setColorAt(0.5, QColor(255, 255, 255, 0))
                halo_grad.setColorAt(0.8, QColor(255, 220, 100, int(150 * progress))) # Gold/White Halo
                halo_grad.setColorAt(1.0, QColor(255, 255, 255, 0))
                
                painter.setBrush(QBrush(halo_grad))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawRect(0,0,w,h)
            
            # --- B. BACKGROUND ICON (Faded, Static) ---
            painter.setOpacity(0.15)
            # Static background version for depth
            painter.drawPixmap(int(cx - 60), int(cy - 60), 120, 120, self._icon_pixmap)
            
            # --- C. MAIN ICON (Animated) ---
            painter.setOpacity(1.0)
            icon_s = 85 * scale_factor
            
            # Draw lifting icon
            painter.drawPixmap(
                int(cx - icon_s/2), 
                int(cy - icon_s/2 + lift_y), 
                int(icon_s), 
                int(icon_s), 
                self._icon_pixmap
            )
            
            # --- D. INNER SHADOW (Vignette) ---
            painter.setBrush(Qt.BrushStyle.NoBrush)
            grad_vig = QRadialGradient(cx, cy + lift_y, icon_s * 0.9)
            grad_vig.setColorAt(0.8, QColor(0,0,0,0))
            grad_vig.setColorAt(1.0, QColor(5, 10, 20, 150))
            painter.setBrush(QBrush(grad_vig))
            painter.drawRect(0,0,w,h)
            
            painter.restore()
            
        # --- 5. DATA HUD (Gold Details) ---
        mid_y = 130
        
        # Divider Line (Metallic Gold)
        c_gold = QColor(THEME['border_active'])
        painter.setPen(QPen(c_gold, 1))
        painter.drawLine(10, mid_y, int(w/2 - 5), mid_y)
        painter.drawLine(int(w/2 + 5), mid_y, w-10, mid_y)
        
        # Center Diamond
        painter.setBrush(c_gold)
        painter.drawRect(int(w/2 - 2), int(mid_y - 2), 4, 4)
        
        # Champion Name
        painter.setPen(QColor(THEME['text_main']))
        font_name = QFont(THEME['font_main'], 11, QFont.Weight.Bold)
        font_name.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.2)
        painter.setFont(font_name)
        
        name = self.data.get('name', 'Unknown').upper()
        # Text also lifts slightly on hover? No, keep text stable for readability
        painter.drawText(QRectF(0, 135, w, 25), Qt.AlignmentFlag.AlignCenter, name)
        
        # Winrate Pill
        wr = self.data.get('wr', 50.0)
        wr_rect = QRectF(w/2 - 25, 165, 50, 18)
        painter.setBrush(QColor(20, 30, 50))
        painter.setPen(QPen(QColor(THEME['border_norm']), 1))
        painter.drawRoundedRect(wr_rect, 4, 4)
        
        delta = self.data.get('delta', 0.0)
        c_wr = QColor(THEME['success']) if delta >= 0 else QColor(THEME['accent_red'])
        
        painter.setFont(QFont(THEME['font_data'], 9, QFont.Weight.Bold))
        painter.setPen(c_wr)
        painter.drawText(wr_rect, Qt.AlignmentFlag.AlignCenter, f"{wr:.1f}%")
        
        # --- 6. PARTICLES (Rising Motes Only) ---
        # Filter particles to only show simple ones, remove complex trails 
        for p in self._particles:
            alpha = int(200 * p['life'] * self._hover_progress)
            if alpha > 0:
                # Gold/White sparkles
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor(255, 230, 150, alpha))
                
                # Apply lift effect to particles too
                py = p['y'] - (20 * self._hover_progress)
                painter.drawEllipse(QPointF(p['x'], py), p['size'], p['size'])
        
        # --- 7. BORDER (Polished Gold Transition) ---
        # Base Bronze 
        c_base = QColor("#785A28")
        
        if self._hover_progress > 0.01:
            # Transition to Polished Gold Gradient
            # Draw metallic gold border
            gold_grad = QLinearGradient(0, 0, w, h)
            gold_grad.setColorAt(0.0, QColor("#997530"))
            gold_grad.setColorAt(0.3, QColor("#F0E6D2")) # Shine
            gold_grad.setColorAt(0.6, QColor("#D4AF37"))
            gold_grad.setColorAt(1.0, QColor("#785A28"))
            
            painter.setPen(QPen(QBrush(gold_grad), 2))
        else:
            # Flat Bronze
            painter.setPen(QPen(c_base, 1.5))
            
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPolygon(poly)
        
        # Corner Wing Accents (Only on Hover)
        if self._hover_progress > 0.1:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#D4AF37"))
            
            # Simple wing tips
            tip_h = 8 * self._hover_progress
            # BL
            painter.drawPolygon(QPolygonF([QPointF(0, h), QPointF(8, h), QPointF(0, h-tip_h)]))
            # TR
            painter.drawPolygon(QPolygonF([QPointF(w, 0), QPointF(w-8, 0), QPointF(w, tip_h)]))
                    


    def _lerp_color(self, c1, c2, t):
        r = c1.red() + (c2.red() - c1.red()) * t
        g = c1.green() + (c2.green() - c1.green()) * t
        b = c1.blue() + (c2.blue() - c1.blue()) * t
        a = c1.alpha() + (c2.alpha() - c1.alpha()) * t
        return QColor(int(r), int(g), int(b), int(a))


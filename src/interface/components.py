from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QPointF, QSize, QPropertyAnimation, QEasingCurve, pyqtProperty, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QLinearGradient, QPolygonF, QPixmap, QPainterPath, QConicalGradient, QRadialGradient, QTransform
import random
import math
import os

THEME = {
    "bg_main": "#080A0E",           # Deep obsidian background
    "bg_glass": "rgba(12, 16, 24, 0.6)", # Frosted glass
    "bg_glass_dark": "rgba(8, 10, 16, 0.8)",
    "border_norm": "rgba(255, 255, 255, 0.08)", # Very subtle 1px white border
    "border_active": "#00E5FF",     # Electric Cyan accent
    "border_glow": "#FFFFFF",       # Pure white flash
    "text_main": "#F4F5F8",         # Off-white for high readability
    "text_dim": "#6A7A90",          # Muted slate/steel blue for secondary text
    "accent_blue": "#00E5FF",
    "accent_blue_dim": "rgba(0, 229, 255, 0.15)",
    "accent_red": "#FF2A55",        # Sharp tactical red
    "success": "#00FFAA",           # Mint green for optimal stats
    "font_main": "Inter",           # Assuming a clean modern sans (or Segoe UI fallback)
    "font_data": "Consolas",
    "text_data": "#8A9BAA",
    "radiant_gold": "#FFD700",       # Rich, glowing gold for mastery/locked picks
    "void_purple": "#7B00FF",        # Ethereal purple for AI processing/bans
    "diamond_frost": "#00BFFF",      # Celestial frost for high rank indicators
}

class HexEffect(QGraphicsDropShadowEffect):
    def __init__(self, color=THEME['accent_blue'], blur=15, parent=None):
        super().__init__(parent)
        self.setBlurRadius(blur)
        self.setColor(QColor(color))
        self.setOffset(0, 0)

class TacticalButton(QWidget):
    """
    Ultra-minimalist interactive button. Thin neon accent line, pure typography.
    """
    clicked = pyqtSignal()
    
    def __init__(self, text="", color_key='border_active', parent=None):
        super().__init__(parent)
        self.text = text
        self.color_key = color_key
        self.setFixedHeight(40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self._hover_progress = 0.0
        self._mouse_x = 0
        self._mouse_y = 0
        
        self.anim_hover = QPropertyAnimation(self, b"hover_progress")
        self.anim_hover.setDuration(300)
        self.anim_hover.setEasingCurve(QEasingCurve.Type.OutExpo)

    @pyqtProperty(float)
    def hover_progress(self):
        return self._hover_progress
        
    @hover_progress.setter
    def hover_progress(self, val):
        self._hover_progress = val
        self.update()

    def mouseMoveEvent(self, event):
        self._mouse_x = event.position().x()
        self._mouse_y = event.position().y()
        self.update()
        super().mouseMoveEvent(event)

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

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        rect = self.rect()
        w, h = rect.width(), rect.height()
        
        # Magnetic Hover Translation
        painter.save()
        if self._hover_progress > 0.01:
            mag_x = (self._mouse_x - w/2) * 0.1 * self._hover_progress
            mag_y = (self._mouse_y - h/2) * 0.15 * self._hover_progress
            painter.translate(mag_x, mag_y)
        
        # 1. Background Fill (Fade in on hover)
        bg_color = QColor(THEME['border_active']) if self.color_key == 'border_active' else QColor(THEME[self.color_key])
        bg_alpha = int(40 * self._hover_progress)
        bg_color.setAlpha(bg_alpha)
        
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg_color)
        painter.drawRect(rect)
        
        # 2. Left Accent Line
        line_w = 2 + (2 * self._hover_progress)
        line_color = QColor(THEME[self.color_key])
        line_color.setAlpha(int(50 + 205 * self._hover_progress))
        painter.setBrush(line_color)
        painter.drawRect(0, int((h - h*self._hover_progress)/2), int(line_w), int(h * self._hover_progress))
        
        # 3. Typography
        text_color = QColor(THEME['text_main']) if self._hover_progress > 0.1 else QColor(THEME['text_dim'])
        painter.setPen(QPen(text_color))
        font = QFont(THEME['font_main'], 10, QFont.Weight.Bold if self._hover_progress > 0.5 else QFont.Weight.Medium)
        font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.5)
        painter.setFont(font)
        
        # Slide text slightly right on hover
        offset = int(6 * self._hover_progress)
        painter.drawText(QRectF(15 + offset, 0, w - 15 - offset, h), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text)
        
        painter.restore()

# Alias for backwards compatibility
HexButton = TacticalButton

class HexFrame(QFrame):
    """
    Base class for Hextech-styled frames with angled corners and borders.
    """
    def __init__(self, parent=None, active=False, color_key="border_norm"):
        super().__init__(parent)
        self.active = active
        self.color_key = color_key
        self._hover_progress = 0.0
        
        # Enable mouse tracking for hover effects
        self.setMouseTracking(True)
        
        self.anim_hover = QPropertyAnimation(self, b"hover_progress")
        self.anim_hover.setDuration(400)
        self.anim_hover.setEasingCurve(QEasingCurve.Type.OutCubic)

    @pyqtProperty(float)
    def hover_progress(self):
        return self._hover_progress
        
    @hover_progress.setter
    def hover_progress(self, val):
        self._hover_progress = val
        self.update()

    def set_active(self, active):
        self.active = active
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
        
        # State checks
        is_active = getattr(self, 'active', False)
        h_prog = self._hover_progress
        
        # Background Gradient
        grad = QLinearGradient(0, 0, w, h)
        if is_active:
            grad.setColorAt(0, QColor(THEME['bg_glass']))
            grad.setColorAt(1, QColor(THEME['bg_glass_dark']))
        elif h_prog > 0.01:
            bg_h = QColor(THEME['bg_glass'])
            bg_h.setAlpha(int(60 + 60 * h_prog))
            grad.setColorAt(0, bg_h)
            grad.setColorAt(1, QColor(THEME['bg_main']))
        else:
            grad.setColorAt(0, QColor(0, 0, 0, 120))
            grad.setColorAt(1, QColor(0, 0, 0, 200))
            
        # Draw Angled Background Path (Seamless Chamfered Rectangle)
        cut = 12 
        path = QPainterPath()
        path.moveTo(cut, 0)
        path.lineTo(w - cut, 0)
        path.lineTo(w, cut)
        path.lineTo(w, h - cut)
        path.lineTo(w - cut, h)
        path.lineTo(cut, h)
        path.lineTo(0, h - cut)
        path.lineTo(0, cut)
        path.closeSubpath()
        
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPath(path)
        
        # Inner Path for Double Border
        gap = 4
        inner_path = QPainterPath()
        inner_path.moveTo(cut + gap/2, gap)
        inner_path.lineTo(w - cut - gap/2, gap)
        inner_path.lineTo(w - gap, cut + gap/2)
        inner_path.lineTo(w - gap, h - cut - gap/2)
        inner_path.lineTo(w - cut - gap/2, h - gap)
        inner_path.lineTo(cut + gap/2, h - gap)
        inner_path.lineTo(gap, h - cut - gap/2)
        inner_path.lineTo(gap, cut + gap/2)
        inner_path.closeSubpath()

        # Shadows & Glow behind the border
        if is_active or h_prog > 0.01:
            glow_c = QColor(THEME['border_active']) if h_prog < 0.1 else QColor(THEME['accent_blue'])
            if h_prog > 0.01 and not is_active:
                glow_c = QColor(THEME['border_active'])
            glow_c.setAlpha(int(50 * max(h_prog, 1.0 if is_active else 0.0)))
            painter.setPen(QPen(glow_c, 6))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(inner_path)

        # Outer Frame - Sleek Metallic
        outer_grad = QLinearGradient(0, 0, w, h)
        if is_active or h_prog > 0.01:
            outer_base = QColor(THEME['border_active'])
            outer_base.setAlpha(int(255 * max(h_prog, 1.0 if is_active else 0.0)))
            outer_grad.setColorAt(0.0, outer_base)
            outer_grad.setColorAt(0.5, QColor(THEME['border_glow'])) # Shine
            outer_grad.setColorAt(1.0, outer_base)
        else:
            outer_grad.setColorAt(0.0, QColor(THEME['border_norm']))
            outer_grad.setColorAt(0.5, QColor("#506070"))
            outer_grad.setColorAt(1.0, QColor(THEME['border_norm']))
            
        pen_outer = QPen(QBrush(outer_grad), 2.0)
        pen_outer.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        painter.setPen(pen_outer)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(path)
        
        # Inner Frame
        inner_grad = QLinearGradient(0, h, w, 0)
        if is_active:
            inner_grad.setColorAt(0.0, QColor(THEME['border_glow']))
            inner_grad.setColorAt(0.5, QColor(THEME['border_active']))
            inner_grad.setColorAt(1.0, QColor(THEME['border_glow']))
        else:
            inner_grad.setColorAt(0.0, QColor("#203040"))
            inner_grad.setColorAt(0.5, QColor("#405060"))
            inner_grad.setColorAt(1.0, QColor("#203040"))
            
        pen_inner = QPen(QBrush(inner_grad), 1.0)
        painter.setPen(pen_inner)
        painter.drawPath(inner_path)
        
        # Elegant Corner Accents
        if is_active or h_prog > 0.01:
            accent_color = THEME['accent_blue'] if is_active else THEME['border_active']
            pen_c = QColor(accent_color)
            pen_c.setAlpha(int(255 * max(h_prog, 1.0 if is_active else 0.0)))
            painter.setPen(QPen(pen_c, 2.0))
            
            # Top-left and Top-right glowing edges
            painter.drawLine(QPointF(cut, 0), QPointF(cut + 15, 0))
            painter.drawLine(QPointF(w - cut - 15, 0), QPointF(w - cut, 0))
            
            # Subtle glowing dots at the chamfer vertices
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(pen_c)
            sz = 3.5
            for pt in [QPointF(w, cut), QPointF(w, h - cut), QPointF(cut, h), QPointF(0, h - cut)]:
                painter.drawEllipse(pt, sz/2.0, sz/2.0)
                
        # Glass Shimmer Overlay (The "Juice")
        if h_prog > 0.01 and h_prog < 0.99:
            # Sweep a white sheen across the diagonal
            shimmer_x = -w + (w * 2.5 * h_prog)
            shimmer_grad = QLinearGradient(shimmer_x, 0, shimmer_x + w, h)
            shimmer_grad.setColorAt(0, QColor(255, 255, 255, 0))
            
            pulse = math.sin(h_prog * math.pi) # 0 to 1 to 0
            shimmer_grad.setColorAt(0.5, QColor(255, 255, 255, int(60 * pulse)))
            shimmer_grad.setColorAt(1, QColor(255, 255, 255, 0))
            
            painter.setBrush(QBrush(shimmer_grad))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawPath(path)

# Alias for backwards compatibility and clean naming
GlassPanel = HexFrame

class TacticalDataCard(GlassPanel):
    """
    Sleek, minimalist data readout. Clean typography and sharp accent lines.
    Replaces the massive 7-layer CardWidget.
    """
    clicked = pyqtSignal(str)
    
    def __init__(self, loader, data, badge=None):
        super().__init__(active=False)
        self.loader = loader
        self.data = data
        self.badge_text = badge
        
        self.setFixedSize(140, 200)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self._click_scale = 1.0
        self._intro_progress = 0.0
        
        # Override hover duration for snappier cards
        self.anim_hover.setDuration(250)
        
        self.anim_click = QPropertyAnimation(self, b"click_scale")
        self.anim_click.setDuration(120)
        
        self.anim_intro = QPropertyAnimation(self, b"intro_progress")
        self.anim_intro.setDuration(400)
        self.anim_intro.setEasingCurve(QEasingCurve.Type.OutQuart) # Smooth, snapping drop-in
        
        self._icon_pixmap = None
        self._cached_id = None
        self.update_data(data)

    @pyqtProperty(float)
    def intro_progress(self):
        return self._intro_progress
        
    @intro_progress.setter
    def intro_progress(self, val):
        self._intro_progress = val
        self.update()
        
    @pyqtProperty(float)
    def click_scale(self):
        return self._click_scale
        
    @click_scale.setter
    def click_scale(self, val):
        self._click_scale = val
        self.update()



    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.anim_click.stop()
            self.anim_click.setStartValue(1.0)
            self.anim_click.setEndValue(0.97)
            self.anim_click.start()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.anim_click.stop()
            self.anim_click.setStartValue(self._click_scale)
            self.anim_click.setEndValue(1.0)
            self.anim_click.setEasingCurve(QEasingCurve.Type.OutBack)
            self.anim_click.start()
            
            if self.data and 'id' in self.data:
                self.clicked.emit(str(self.data['id']))
        super().mouseReleaseEvent(event)

    def update_data(self, data):
        self.data = data
        cid = data.get('id')
        
        if cid != self._cached_id and self.loader and cid:
            path = self.loader.get_champ_icon_path(str(cid))
            if path:
                original = QPixmap(path)
                self._icon_pixmap = original.scaled(80, 80, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self._cached_id = cid
            
            # Restart Intro
            self.anim_intro.stop()
            self.anim_intro.setStartValue(0.0)
            self.anim_intro.setEndValue(1.0)
            self.anim_intro.start()
        
        self.update()

    def paintEvent(self, event):
        # We handle Base Panel via GlassPanel's paintEvent, but
        # wait, we're doing a total custom render using GlassPanel's style internally
        # so we'll call super() to draw the glass base!
        
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        
        w, h = self.width(), self.height()
        
        # Determine overall opacity / translation (Intro Animation)
        c_scale = self._click_scale
        h_prog = self._hover_progress
        intro_alpha = self._intro_progress
        
        if intro_alpha <= 0: return
        
        painter.setOpacity(intro_alpha)
        # Y-Drop
        drop_y = (1.0 - self._intro_progress) * 15
        
        painter.translate(w/2, h/2 + drop_y)
        painter.scale(c_scale, c_scale)
        painter.translate(-w/2, -h/2 - drop_y)
        
        # 1. Base Glass
        bg_c = QColor(12, 16, 24, 160)
        if h_prog > 0.01:
            bg_c = QColor(18, 24, 32, 210)
        painter.setBrush(bg_c)
        painter.setPen(QPen(QColor(255, 255, 255, 10 + int(30 * h_prog)), 1))
        painter.drawRoundedRect(0, 0, w-1, h-1, 4, 4)
        
        # 2. Top Accent Line (Minimal Neon)
        if h_prog > 0.01:
            line_w = w * h_prog
            painter.setBrush(QColor(THEME['border_active']))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRect(int(w/2 - line_w/2), 0, int(line_w), 2)
            
        # 3. Champion Image (Desaturated unless hovered)
        cx, cy = w/2, 60
        if self._icon_pixmap:
            if h_prog > 0.1:
                # Add a subtle glowing ring
                ring_c = QColor(THEME['border_active'])
                ring_c.setAlpha(int(60 * h_prog))
                painter.setPen(QPen(ring_c, 1))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(QPointF(cx, cy), 44, 44)
                
            # Fake Desaturation: We'll draw image with lower opacity, then a white/grey blend
            # Or just draw it full if hovered, semi-transparent otherwise.
            img_alpha = 0.6 + (0.4 * h_prog)
            painter.setOpacity(intro_alpha * img_alpha)
            painter.drawPixmap(int(cx - 40), int(cy - 40), self._icon_pixmap)
            painter.setOpacity(intro_alpha)
        
        # 4. Typography Layout
        wr = self.data.get('wr', 0.0)
        name = self.data.get('name', 'UNKNOWN').upper()
        games = self.data.get('games', 0)
        
        # Champion Name
        text_c = QColor(THEME['text_main']) if h_prog > 0.5 else QColor(THEME['text_dim'])
        painter.setPen(text_c)
        font_name = QFont(THEME['font_main'], 11, QFont.Weight.Bold)
        font_name.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.2)
        painter.setFont(font_name)
        painter.drawText(QRectF(0, 115, w, 20), Qt.AlignmentFlag.AlignCenter, name)
        
        # Win Rate Readout
        is_success = wr >= 50.0
        wr_color = QColor(THEME['success']) if is_success else QColor(THEME['accent_red'])
        if h_prog < 0.1:
            wr_color.setAlpha(180) # Dim slightly when not hovered
            
        painter.setPen(wr_color)
        font_data = QFont(THEME['font_data'], 16, QFont.Weight.Bold)
        painter.setFont(font_data)
        painter.drawText(QRectF(0, 140, w, 25), Qt.AlignmentFlag.AlignCenter, f"{wr:.1f}%")
        
        # Sub-stats (Games Played)
        painter.setPen(QColor(THEME['text_data']))
        font_sub = QFont(THEME['font_main'], 8)
        font_sub.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.5)
        painter.setFont(font_sub)
        painter.drawText(QRectF(0, 168, w, 15), Qt.AlignmentFlag.AlignCenter, f"{games} MATCHES")

# Alias for backwards compatibility
CardWidget = TacticalDataCard


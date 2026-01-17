
import os
import requests
from PyQt6.QtGui import QPixmap, QPainter, QBrush, QBitmap, QColor
from PyQt6.QtCore import Qt, QSize

# Configuration
DDRAGON_VER = "15.24.1" # Could fetch dynamically, but fixed for stability/speed
BASE_URL_CHAMP = f"https://ddragon.leagueoflegends.com/cdn/{DDRAGON_VER}/img/champion/"
BASE_URL_ITEM = f"https://ddragon.leagueoflegends.com/cdn/{DDRAGON_VER}/img/item/"

class AssetDownloader:
    """Thread-Safe Asset Management (IO Only, No PyQt6)"""
    def __init__(self, asset_dir="assets"):
        self.asset_dir = asset_dir
        self.champ_dir = os.path.join(asset_dir, "champs")
        self.item_dir = os.path.join(asset_dir, "items")
        
        # Ensure directories
        os.makedirs(self.champ_dir, exist_ok=True)
        os.makedirs(self.item_dir, exist_ok=True)

    def get_champ_icon_path(self, champ_id_name):
        """
        Retrieves path locally. Downloads strictly if missing.
        Blocking (Network IO). Run this in Worker Thread!
        """
        if not champ_id_name: return None
        if str(champ_id_name) == "0": return None # Padding Check
        
        filename = f"{champ_id_name}.png"
        path = os.path.join(self.champ_dir, filename)
        
        if os.path.exists(path):
            return path
            
        # Download
        url = f"{BASE_URL_CHAMP}{filename}"
        return self._download_file(url, path)

    def get_item_icon_path(self, item_id):
        if not item_id: return None
        
        filename = f"{item_id}.png"
        path = os.path.join(self.item_dir, filename)
        
        if os.path.exists(path):
            return path
            
        url = f"{BASE_URL_ITEM}{filename}"
        return self._download_file(url, path)

    def _download_file(self, url, save_path):
        try:
            print(f"[ASSETS] Downloading: {url}")
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                with open(save_path, 'wb') as f:
                    f.write(r.content)
                return save_path
            else:
                print(f"[ASSETS] Failed to download {url}: Status {r.status_code}")
                return None
        except Exception as e:
            print(f"[ASSETS] Error downloading {url}: {e}")
            return None

class AssetLoader(AssetDownloader):
    """UI Asset Manager (PyQt6 Dependent)"""
    def __init__(self, asset_dir="assets"):
        super().__init__(asset_dir)
        self.memory_cache = {}

    def get_champ_icon(self, champ_id_name):
        """UI Convenience Wrapper"""
        return self.get_champ_icon_path(champ_id_name)
    
    def get_item_icon(self, item_id):
        """UI Convenience Wrapper"""
        return self.get_item_icon_path(item_id)

    def circular_mask(self, image_path, size=64):
        """
        Loads an image, scales it, and masks it to a circle.
        Returns QPixmap. Cached in memory.
        """
        if not image_path:
             # Return placeholder
             pixmap = QPixmap(size, size)
             pixmap.fill(Qt.GlobalColor.transparent)
             return pixmap

        # FAST PATH: Check Cache
        cache_key = f"{image_path}_{size}"
        if cache_key in self.memory_cache:
            return self.memory_cache[cache_key]
            
        if not os.path.exists(image_path):
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.GlobalColor.transparent)
            return pixmap
            
        # Load
        src = QPixmap(image_path)
        src = src.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        
        # Create Output
        dest = QPixmap(size, size)
        dest.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(dest)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Brush
        brush = QBrush(src)
        painter.setBrush(brush)
        painter.setPen(Qt.PenStyle.NoPen)
        
        # Draw Circle
        painter.drawEllipse(0, 0, size, size)
        painter.end()
        
        # Store in Cache
        self.memory_cache[cache_key] = dest
        return dest

    def hexagon_mask(self, image_path, size=64, border_color=None, border_width=2):
        """
        Loads an image, scales it, and masks it to a pointy-topped hexagon.
        Returns QPixmap. Cached in memory.
        """
        if not image_path:
             pixmap = QPixmap(size, size)
             pixmap.fill(Qt.GlobalColor.transparent)
             return pixmap

        cache_key = f"{image_path}_{size}_hex_{border_color}"
        if cache_key in self.memory_cache:
            return self.memory_cache[cache_key]
            
        if not os.path.exists(image_path):
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.GlobalColor.transparent)
            return pixmap
            
        # Load
        src = QPixmap(image_path)
        src = src.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
        center_x = (src.width() - size) // 2
        center_y = (src.height() - size) // 2
        src = src.copy(center_x, center_y, size, size)
        
        # Create Output
        dest = QPixmap(size, size)
        dest.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(dest)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Create Hexagon Polygon (Pointy-topped)
        import math
        from PyQt6.QtCore import QPointF
        from PyQt6.QtGui import QPolygonF, QPainterPath, QPen, QColor
        
        points = []
        r = size / 2 - border_width # Padding
        cx, cy = size/2, size/2
        
        for i in range(6):
            angle_deg = 60 * i - 30 
            angle_rad = math.radians(angle_deg)
            x = cx + r * math.cos(angle_rad)
            y = cy + r * math.sin(angle_rad)
            points.append(QPointF(x, y))
            
        poly = QPolygonF(points)
        
        # Draw Image Masked
        path = QPainterPath()
        path.addPolygon(poly)
        painter.setClipPath(path)
        painter.drawPixmap(0, 0, src)
        
        # Draw Border
        if border_color:
             painter.setClipping(False) 
             pen = QPen(QColor(border_color), border_width)
             painter.setPen(pen)
             painter.setBrush(Qt.BrushStyle.NoBrush)
             painter.drawPolygon(poly)
             
        painter.end()
        
        self.memory_cache[cache_key] = dest
        return dest

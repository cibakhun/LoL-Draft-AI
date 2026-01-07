import json
import os

CONFIG_PATH = "config.json"

DEFAULT_CONFIG = {
    "theme": "Pro Esports",
    "mastery_bias": 1.0, # 1.0 = Standard, >1.0 = Prefer High Mastery
    "risk_level": 0.5, # 0.0 = Safe, 1.0 = Aggro/Risky (Exploration)
    "auto_hover": True,
    "show_probability": True,
    "ui_scale": 1.0
}

class SettingsManager:
    """
    Manages persistent user configuration.
    """
    def __init__(self, path=CONFIG_PATH):
        self.path = path
        self.config = DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        if not os.path.exists(self.path):
            self.save()
            return
            
        try:
            with open(self.path, 'r') as f:
                data = json.load(f)
                # Merge with defaults (handling new keys)
                for k, v in DEFAULT_CONFIG.items():
                    if k not in data:
                        data[k] = v
                self.config = data
        except Exception as e:
            print(f"[SETTINGS] Load Error: {e}, using defaults.")
            self.config = DEFAULT_CONFIG.copy()

    def save(self):
        try:
            with open(self.path, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
             print(f"[SETTINGS] Save Error: {e}")

    def get(self, key, default=None):
        val = self.config.get(key)
        if val is None:
             val = DEFAULT_CONFIG.get(key)
        if val is None:
             val = default
        return val

    def set(self, key, value):
        self.config[key] = value
        self.save()

from typing import List, Dict, Tuple, Optional
from pydantic import BaseModel, Field, validator
import numpy as np

# --- 1. The Contract (Feature Layout) ---
class FeatureConfig:
    """
    Central Authority on Feature Indices.
    Prevents "Magic Number" drift between Training (Polars) and Inference (Python).
    Total Dimensions: 82 (Titan V1)
    """
    # Dimensions
    TOTAL_DIM = 82

    # Queue IDs
    QUEUE_COOP_VS_AI = 830
    
    # Blocks (Start Indices)
    # Blue Team (15 dims each)
    BLUE_COMP_START = 0
    # Red Team (15 dims each)
    RED_COMP_START = 15
    
    # Context (10 dims each)
    BLUE_CONTEXT_START = 30
    RED_CONTEXT_START = 40
    
    # Synergy (5 dims each)
    BLUE_SYNERGY_START = 50
    RED_SYNERGY_START = 55
    
    # Spikes (3 dims each)
    BLUE_SPIKE_START = 60
    RED_SPIKE_START = 63
    
    # Counters (5 dims + 1 Team Score)
    COUNTER_START = 66
    
    # Timeline / Temporality (10 dims)
    # 5 Blue + 5 Red
    BLUE_TIMELINE_START = 72
    RED_TIMELINE_START = 77
    
    # Sub-Indices (Relative to Block Start)
    # Comp Stats (0-14)
    IDX_ATK = 0
    IDX_MAG = 1
    IDX_DEF = 2
    IDX_DIFF = 3
    IDX_FIGHTER = 4
    IDX_TANK = 5
    IDX_MAGE = 6
    IDX_ASSASSIN = 7
    IDX_MARKSMAN = 8
    IDX_SUPPORT = 9
    IDX_DMG_PHYS = 10 # Ratio
    IDX_DMG_MAGIC = 11 # Ratio
    # 12 is unused?
    IDX_TANKINESS = 13
    IDX_CARRY_SCORE = 14
    
    # Timeline Sub-Indices
    IDX_TEMPO = 0    # Gold Diff
    IDX_SNOWBALL = 1 # Winrate in Short Games
    IDX_COMEBACK = 2 # Winrate in Long Games
    IDX_EARLY_LEAD = 3 # Unused / Placeholder
    IDX_LANE_DOM = 4   # Unused / Placeholder

    @classmethod
    def get_indices(cls, block_start: int) -> List[int]:
        return list(range(block_start, block_start + 5)) # Generic helper

# --- 2. The Input Schema (Type Safety) ---
class TeamInput(BaseModel):
    """
    Represents one team (5 players). 
    Keys: Role (TOP/JUNGLE/...), Values: Champion ID (int)
    """
    TOP: int = 0
    JUNGLE: int = 0
    MIDDLE: int = 0
    BOTTOM: int = 0
    UTILITY: int = 0

    @validator('*', pre=True)
    def sanitize_int(cls, v):
        try: return int(v)
        except: return 0

class MatchInput(BaseModel):
    """
    The strictly typed input for the Brain.
    """
    blue: TeamInput
    red: TeamInput
    
    # Optional Context
    timestamp: Optional[int] = None
    
    def to_dict(self):
        return {
            'blue': self.blue.dict(),
            'red': self.red.dict()
        }

# --- 3. The Scaler (Fixed Limits) ---
class RomanScaler:
    """
    'Roman' Scaler: Fixed limits based on game knowledge.
    Replaces 'Dynamic' scaling which is fragile to outliers.
    """
    # Max Theoretical Values (Roughly)
    MAX_ATK = 50.0  # 5 champs * 10
    MAX_DEF = 50.0
    MAX_MAG = 50.0
    MAX_DIFF = 50.0 # Difficulty
    MAX_COUNT = 5.0 # Max 5 of one role
    MAX_SCORE = 20.0 # Heuristic scores
    
    MAX_GOLD_DIFF = 3000.0 # Cap gold diff at 3k/player avg (15k total)
    
    @staticmethod
    def scale(vec: np.ndarray) -> np.ndarray:
        """
        In-place scaling using fixed constants.
        """
        cfg = FeatureConfig
        
        # Helper to scale block
        def scale_block(start):
            # 0-3: Stats
            vec[start + cfg.IDX_ATK] /= RomanScaler.MAX_ATK
            vec[start + cfg.IDX_MAG] /= RomanScaler.MAX_MAG
            vec[start + cfg.IDX_DEF] /= RomanScaler.MAX_DEF
            vec[start + cfg.IDX_DIFF] /= RomanScaler.MAX_DIFF
            
            # 4-9: Counts
            for i in range(4, 10):
                vec[start + i] /= RomanScaler.MAX_COUNT
                
            # 13-14: Scores
            vec[start + 13] /= RomanScaler.MAX_SCORE
            vec[start + 14] /= RomanScaler.MAX_SCORE
            
        scale_block(cfg.BLUE_COMP_START)
        scale_block(cfg.RED_COMP_START)
        
        # Timeline Scaling (Gold Diff)
        # We assume input is Average Gold Diff per player
        vec[cfg.BLUE_TIMELINE_START + cfg.IDX_TEMPO] /= RomanScaler.MAX_GOLD_DIFF
        vec[cfg.RED_TIMELINE_START + cfg.IDX_TEMPO] /= RomanScaler.MAX_GOLD_DIFF
        
        # Clamp to [-1, 1] or [0, 1] just in case
        np.clip(vec, -5.0, 5.0, out=vec) 
        
        return vec

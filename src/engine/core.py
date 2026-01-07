import os
import sys
import time
import torch
import traceback
import json

# Internal Imports
from src.infrastructure.lcu_connector import TitanLCU
from src.engine.titan_brain import TitanBrain
from src.engine.features import FeatureEngine
from src.engine.mcts import SpatialMCTS
from src.data.ddragon import DataDragon
from src.engine.config import SettingsManager

class TitanEngine:
    """
    TitanEngine: The Central Cortex.
    Single Source of Truth for:
    - LCU Synchronization
    - Neural Inference (TitanNet)
    - Draft Search (MCTS)
    - State Management
    """
    def __init__(self, role_filter=None, skill_level=None):
        self.role_filter = role_filter
        self.skill_level = skill_level # Manual override, or None to auto-detect
        
        print("[TITAN] Initializing Engine Core...")
        
        # 0. Load Configuration
        self.settings = SettingsManager()
        
        # 1. Connect Components
        self.lcu = TitanLCU()
        
        # 2. Load Data
        print("[TITAN] Loading DataDragon...")
        self.ddragon = DataDragon()
        self.id_map = self.ddragon.get_id_map()
        
        # 3. Initialize Feature Cortex
        print("[TITAN] initializing Cortex...")
        self.fe = FeatureEngine()
        self.fe.build_vocab(self.ddragon)
        self.fe._build_ddragon_cache(self.ddragon)
        
        # 4. Initialize Brain (TitanNet)
        print("[TITAN] Loading Neural Network...")
        self.brain = TitanBrain()
        self.brain.initialize(vocab_size=3000)
        
        # Checkpoints
        current_dir = os.path.dirname(os.path.abspath(__file__)) # src/engine
        src_dir = os.path.dirname(current_dir) # src
        root_dir = os.path.dirname(src_dir) # root
        
        # Look in root/checkpoints first, then src/checkpoints
        ckpt_candidates = [
            os.path.join(root_dir, "checkpoints", "titan_v3_best.pt"),
            os.path.join(root_dir, "checkpoints", "titan_v3_final.pt"),
            os.path.join(src_dir, "checkpoints", "titan_v3_best.pt")
        ]
        
        found_ckpt = None
        for c in ckpt_candidates:
            if os.path.exists(c):
                found_ckpt = c
                break
             
        if found_ckpt:
            self.brain.model_path = found_ckpt
            self.brain.load()
            print(f"[TITAN] Loaded Checkpoint: {found_ckpt}")
        else:
            print("[TITAN] WARNING: No checkpoint found. Using random weights.")
            
        self.brain.model.eval()
        
        # 5. Load Auxiliary Metrics
        self.lane_data = {}
        lane_path = os.path.join(src_dir, "data", "lane_metrics.json")
        if os.path.exists(lane_path):
             with open(lane_path, 'r') as f: self.lane_data = json.load(f)
             
        self.item_data = {}
        item_path = os.path.join(src_dir, "data", "item_metrics.json")
        if os.path.exists(item_path):
             with open(item_path, 'r') as f: self.item_data = json.load(f)
             
        # Build Inverse Vocab (Token ID -> Real ID INT)
        # fe.vocab is {RealID: TokenID}
        self.token_to_real = {v: k for k, v in self.fe.vocab.items()}

        # 6. Initialize Strategist (The Brain's Executive Function)
        from src.engine.strategist import DraftStrategist
        self.strategist = DraftStrategist(self.brain, self.fe, self.ddragon, self.lane_data)

        # 7. State
        self.last_hash = None
        self.cached_recs = []
        self.cached_winrate = 0.5
        self.cached_lane_status = "Observing"
        self.cached_build = ({}, [])
        
    def set_skill(self, level):
        self.skill_level = level
        
    def get_skill(self):
        # Return manual override or detect from LCU
        if self.skill_level: return self.skill_level
        # Fallback to logic (duplicated for now until utility moved)
        return self._detect_rank_scalar()
        
    def cycle(self):
        """
        Runs one tick of the engine.
        Delegates to Strategist for decision making.
        """
        if not self.lcu.connected:
            if self.lcu.connect():
                 return 0.5, [], "Connected", "System", ({}, [])
            return 0.0, [], "Waiting for Client...", "Offline", ({}, [])
            
        phase = self.lcu.get_gameflow_phase()
        
        if phase != "ChampSelect":
            # Reset Caches
            self.last_hash = None
            self.cached_recs = []
            return 0.5, [], f"Status: {phase}", "Idle", ({}, [])
            
        # --- CHAMP SELECT ACTIVE ---
        session = self.lcu.get_champ_select()
        if not session: return 0.5, [], "Syncing...", "Loading", ({}, [])
        
        # 1. Parse Environment
        current_patch = 14.23 # Fallback
        if self.ddragon.version:
             try:
                 parts = self.ddragon.version.split('.')
                 current_patch = float(f"{parts[0]}.{parts[1]}")
             except: pass
        
        skill = self.get_skill()
        
        # 2. Check for State Change (Simple Hash)
        # We can do a quick check before invoking Strategist to save compute
        # But Strategist handle's Logic.
        # Let's invoke Strategist to "Analyze"
        # 2. Analyze
        # We need to fetch mastery if bias is active
        mastery = None
        if self.settings.get("mastery_bias") != 1.0:
             # Check cache or fetch
             # Simplification: Only fetch once per session or if missing
             # For now, let's try to get profile data to get PUUID
             prof = self.get_profile_data() # This caches internally? No.
             if prof and prof.get('puuid'):
                  mastery = self.lcu.get_champion_mastery(prof['puuid'])

        suggestions, win_prob, lane_status, context = self.strategist.analyze(
            session, 
            skill=self.get_skill(),
            patch=current_patch,
            settings=self.settings,
            mastery=mastery
        )
        
        # Context allows us to hash checks
        current_snapshot = context['snapshot'] # (xp, xb, my_pos, enemy_champ, my_champ_id)
        # Snapshot is tuple of lists/data
        # Include settings in hash to force re-calc on slider change
        s_bias = self.settings.get("mastery_bias")
        s_risk = self.settings.get("risk_level")
        current_hash = hash(str(current_snapshot) + f"_{s_bias}_{s_risk}")
        
        if current_hash == self.last_hash and self.cached_recs:
             # Return cached
             return self.cached_winrate, self.cached_recs, "Drafting...", self.cached_lane_status, self.cached_build
             
        # New State
        self.last_hash = current_hash
        self.cached_winrate = win_prob
        self.cached_recs = suggestions
        self.cached_lane_status = lane_status
        
        # Build Data
        champ_build = {}
        item_list = []
        
        my_champ_id = context['my_champ_id']
        
        if my_champ_id > 0:
             metrics = self.item_data.get(str(my_champ_id))
             if metrics:
                  cname = self.id_map.get(my_champ_id, "Unknown")
                  champ_build = {
                      "name": cname,
                      "score": 100,
                      "wr": metrics.get('winrate', 0.0) * 100,
                      "delta": 0.0
                  }
                  
                  for iid in metrics.get('core_items', []):
                       idata = self.ddragon.items.get(str(iid))
                       iname = idata['name'] if idata else str(iid)
                       item_list.append({"id": str(iid), "name": iname})
                       
        self.cached_build = (champ_build, item_list)
        
        # 6. Expose Hover Context if available
        # Return: win, recs, status, lane_str, build, context
        return self.cached_winrate, self.cached_recs, "Drafting...", self.cached_lane_status, self.cached_build, context

    def act_on_suggestion(self, champion_id):
        """
        Triggers an action in the LCU to hover the specified champion.
        """
        if not self.lcu.connected: return False
        
        session = self.lcu.get_champ_select()
        if not session: return False
        
        # Find active action
        local_cell = session.get('localPlayerCellId', -1)
        actions = session.get('actions', [])
        
        target_action_id = -1
        
        for turn in actions:
            for action in turn:
                if action.get('actorCellId') == local_cell and action.get('isInProgress', False):
                     # Found active action
                     target_action_id = action.get('id')
                     break
            if target_action_id != -1: break
            
        if target_action_id != -1:
             try:
                 # Ensure proper ID Mapping.
                 
                 real_id = 0
                 # Try direct int conversion (if it's "266")
                 if str(champion_id).isdigit():
                      real_id = int(champion_id)
                 else:
                      # It's an Asset Name (e.g. "Aatrox")
                      for c_key, c_val in self.ddragon.champions.items():
                           if c_key == champion_id:
                                real_id = int(c_val['key'])
                                break
                                
                 if real_id > 0:
                     return self.lcu.hover_champion(target_action_id, real_id)
             except Exception as e:
                 print(f"Action Error: {e}")
                 traceback.print_exc()
                  
        return False



    def get_phase(self):
        """Returns the current GameFlow phase from LCU."""
        return self.lcu.get_gameflow_phase()

    def get_profile_data(self):
        """Fetches current summoner profile and rank from LCU."""
        if not self.lcu.connected: 
            return None
            
        summ = self.lcu.get_current_summoner()
        if not summ: 
            return None
            
        data = {
            "name": summ.get('gameName', summ.get('displayName', 'Unknown')),
            "tag": summ.get('tagLine', ''),
            "level": summ.get('summonerLevel', 0),
            "puuid": summ.get('puuid', ''),
            "rank_solo": "Unranked",
            "tier_solo": ""
        }
        
        # Get Rank
        if data['puuid']:
            ranked = self.lcu.get_ranked_stats(data['puuid'])
            if ranked and 'queues' in ranked:
                # Find Solo Queue (420)
                for q in ranked['queues']:
                    if q.get('queueType') == 'RANKED_SOLO_5x5':
                        data['tier_solo'] = q.get('tier', '')
                        data['rank_solo'] = f"{q.get('tier')} {q.get('rank')} ({q.get('leaguePoints')} LP)"
                        break
        return data

    # --- HELPERS ---
    def _detect_player_role(self, session):
         # Legacy: Strategist handles this internally now.
         # Kept as simple wrapper if external tools call it, but ideally we deprecate.
         return self.strategist.detect_player_role(session)


    def _detect_rank_scalar(self):
         try:
              summ = self.lcu.get_current_summoner()
              if not summ: return 3.0
              puuid = summ['puuid']
              stats = self.lcu.get_ranked_stats(puuid)
              
              tier = "UNRANKED"
              division = "IV"
              
              if stats and 'queues' in stats:
                   for q in stats['queues']:
                        if q.get('queueType') == "RANKED_SOLO_5x5":
                             tier = q.get('tier', 'UNRANKED')
                             division = q.get('division', 'IV')
                             break
                             
              tiers = {"IRON":1.0, "BRONZE":2.0, "SILVER":3.0, "GOLD":4.0, "PLATINUM":5.0, "EMERALD":6.0, "DIAMOND":7.0, "MASTER":8.0, "GRANDMASTER":9.0, "CHALLENGER":10.0}
              divs = {"IV":0.0, "III":0.25, "II":0.50, "I":0.75}
              
              base = tiers.get(tier, 3.0)
              offset = divs.get(division, 0.0)
              if base >= 8.0: offset = 0.0
              return base + offset
         except: return 3.0

if __name__ == "__main__":
    # Self-Test
    engine = TitanEngine()
    print("Cycle Test...")
    res = engine.cycle()
    print(res)


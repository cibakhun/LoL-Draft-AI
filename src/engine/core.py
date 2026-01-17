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
        
        # Detect Phase for UI Button
        timer = session.get('timer', {})
        phase = timer.get('phase', 'UNKNOWN')
        
        is_banning = False
        has_action = False
        local_cell = session.get('localPlayerCellId', -1)
        actions = session.get('actions', [])
        
        # Logic: If phase is PLANNING (Intent), we do NOT have an action button (can't lock intent in LCU API usually)
        # Even if LCU says action isInProgress, it's just intent declaration.
        
        if phase != 'PLANNING':
            for turn in actions:
                 for action in turn:
                      if action.get('actorCellId') == local_cell and action.get('isInProgress', False):
                           has_action = True
                           if action.get('type') == 'ban':
                                is_banning = True
                           break
                 if has_action: break
        
        context['is_banning'] = is_banning
        context['has_action'] = has_action
        context['phase'] = phase # Pass phase to UI for Tracker
        
        # Context allows us to hash checks
        current_snapshot = context['snapshot'] # (xp, xb, my_pos, enemy_champ, my_champ_id)
        # Snapshot is tuple of lists/data
        # Include settings in hash to force re-calc on slider change
        s_bias = self.settings.get("mastery_bias")
        s_risk = self.settings.get("risk_level")
        # Include has_action/is_banning in hash to update button state immediately
        current_hash = hash(str(current_snapshot) + f"_{s_bias}_{s_risk}_{has_action}_{is_banning}")
        
        if current_hash == self.last_hash and self.cached_recs:
             # Return cached
             return self.cached_winrate, self.cached_recs, "Drafting...", self.cached_lane_status, self.cached_build, context
             
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
        
        # Resolve Real ID
        real_id = 0
        if str(champion_id).isdigit():
             real_id = int(champion_id)
        else:
             for c_key, c_val in self.ddragon.champions.items():
                  if c_key == champion_id:
                        real_id = int(c_val['key'])
                        break
        if real_id == 0: return False

        phase = self.lcu.get_gameflow_phase()
        
        # PLANNING PHASE (Intent)
        if phase == 'ChampSelect':
            # Check specifically for Planning sub-phase via timer or just try intent if no actions
            session = self.lcu.get_champ_select()
            if not session: return False
            
            timer = session.get('timer', {})
            phase_internal = timer.get('phase', '')
            
            if phase_internal == 'PLANNING':
                 print(f"[TITAN] Declaring Intent: {real_id}")
                 return self.lcu.declare_intent(real_id)
            
            # Normal Action Loop
            local_cell = session.get('localPlayerCellId', -1)
            actions = session.get('actions', [])
            target_action_id = -1
            
            for turn in actions:
                for action in turn:
                    if action.get('actorCellId') == local_cell and action.get('isInProgress', False):
                         target_action_id = action.get('id')
                         break
                if target_action_id != -1: break
            
            if target_action_id != -1:
                 print(f"[TITAN] Hovering Champion {real_id} on Action {target_action_id}")
                 return self.lcu.hover_champion(target_action_id, real_id)
                 
        return False

    def lock_in(self, champion_id=None): # Added champion_id parameter
        """
        Locks in the current selection (Pick or Ban).
        """
        if not self.lcu.connected: 
            print("[TITAN] Cannot Lock In: LCU Disconnected")
            return False
        
        session = self.lcu.get_champ_select()
        if not session: 
            print("[TITAN] Cannot Lock In: No Session")
            return False
        
        # Find active action
        local_cell = session.get('localPlayerCellId', -1)
        actions = session.get('actions', [])
        
        target_action_id = -1
        found_action = None
        
        print(f"[TITAN] Lock In Request - Cell: {local_cell}")
        
        # Debug: List ALL actions for this turn/local player
        potential_actions = []
        for turn in actions:
            for action in turn:
                if action.get('actorCellId') == local_cell and action.get('isInProgress', False):
                     print(f"[DEBUG] Active Action Found: ID={action.get('id')} Type={action.get('type')} CID={action.get('championId')}")
                     potential_actions.append(action)
                     
        # Priority Selection: BAN > PICK > Other
        for action in potential_actions:
             if action.get('type') == 'ban':
                  found_action = action
                  target_action_id = action.get('id')
                  break
        
        if target_action_id == -1:
             for action in potential_actions:
                  if action.get('type') == 'pick':
                       found_action = action
                       target_action_id = action.get('id')
                       break
                       
        # Fallback to any active action if no specific type match
        if target_action_id == -1 and potential_actions:
             found_action = potential_actions[0]
             target_action_id = found_action.get('id')
            
        if target_action_id != -1 and found_action:
             print(f"[TITAN] Target Action ID: {target_action_id} Type: {found_action.get('type')}")
             
             # Determine Content ID (CID)
             # Priority 1: Explicit Argument from UI (e.g. user clicked card then clicked lock)
             # Priority 1: Explicit Argument from UI (e.g. user clicked card then clicked lock)
             cid = 0
             if champion_id:
                  if str(champion_id).isdigit():
                       cid = int(champion_id)
                  else:
                       # Attempt to resolve name to ID
                       for c_key, c_val in self.ddragon.champions.items():
                            if c_key == champion_id:
                                  cid = int(c_val['key'])
                                  break
                  print(f"[TITAN] Using Explicit Champion ID: {cid} (from {champion_id})")

             # Priority 2: Action's existing selection (e.g. user clicked lock without card, but hovered in client)
             if cid == 0:
                 cid = found_action.get('championId', 0)
                 if cid > 0: print(f"[TITAN] Using Action's Champion ID: {cid}")

             # Priority 3: MyTeam Selection (only for picks, if action not updated yet)
             if cid == 0 and found_action.get('type') == 'pick':
                 my_selection = next((p for p in session.get('myTeam', []) if p.get('cellId') == local_cell), None)
                 if my_selection: 
                     cid = my_selection.get('championId', 0)
                     if cid > 0: print(f"[TITAN] Using MyTeam Champion ID ({cid})")
                 else:
                     print(f"[TITAN] No MyTeam entry found for cell {local_cell}")
                 
             print(f"[TITAN] Final Lock ID: {cid}")
             
             if cid == 0:
                  print("[TITAN] ERROR: Champion ID is 0. Cannot Lock In.")
                  return False

             # Force Hover First (Double Tap to be safe)
             self.lcu.hover_champion(target_action_id, cid)
             time.sleep(0.25)
                  
             # Payload: Ensure we send EVERYTHING potentially needed
             data = {"championId": cid, "completed": True}
                  
             # Try completion
             print(f"[TITAN] Sending Lock Request for Action {target_action_id} with {data}")
             res = self.lcu.complete_action(target_action_id, data=data)
             
             if res:
                  print(f"[TITAN] Lock In SUCCESS for Action {target_action_id}")
             else:
                  print(f"[TITAN] Lock In FAILED. LCU returned False. Check LCU logs.")

             return res
             
        print(f"[TITAN] No active action found to lock in. Potential actions found: {len(potential_actions)}")
        for pa in potential_actions:
             print(f" - ID:{pa.get('id')} Type:{pa.get('type')} InProg:{pa.get('isInProgress')} Actor:{pa.get('actorCellId')}")
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


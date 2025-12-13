from lcu_driver import Connector
import threading
import asyncio
import time

# Reference to the global state in server (circular import avoidance needed usually, 
# but for this script we will treat this as a standalone worker that updates a shared dict 
# or we pass the state object to it).
# For simplicity, we will define the connector here and import it in server, 
# OR run it as a separate process. 
# Better: Make this a class we can instantiate in server.py.

class LCUWorker:
    def __init__(self, state_ref, on_update=None):
        self.state = state_ref
        self.on_update = on_update
        self.connector = None # Initialize in _run to ensure loop exists
        
    def start(self):
        # Run in a separate thread because connector.start() is blocking
        t = threading.Thread(target=self._run)
        t.daemon = True
        t.start()
        
    def _run(self):
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Initialize connector with this loop
        self.connector = Connector(loop=loop)
        
        @self.connector.ready
        async def connect(connection):
            print(f"[LCU] Connected to League Client.")
            self.state['status'] = "Connected to Client"
            
            # Fetch Current Summoner
            summoner = await connection.request('get', '/lol-summoner/v1/current-summoner')
            if summoner.status == 200:
                data = await summoner.json()
                self.state['summoner_name'] = data['gameName']
                self.state['tag_line'] = data['tagLine']
                self.state['puuid'] = data['puuid']
                self.state['summoner_id'] = data['summonerId'] # Needed for finding self in team
            print(f"[LCU] Logged in as: {data['gameName']}#{data['tagLine']}")
            
            # Check for existing Champ Select Session (Mid-Game Startup)
            try:
                session = await connection.request('get', '/lol-champ-select/v1/session')
                if session.status == 200:
                    data = await session.json()
                    print("[LCU] Found active Champ Select session! Syncing state...")
                    # Manually trigger handler with a mock event object
                    class MockEvent:
                        def __init__(self, d): self.data = d
                    await champ_select_handler(connection, MockEvent(data))
            except Exception as e:
                print(f"[LCU] Session Check Error: {e}") 
            
        @self.connector.close
        async def disconnect(connection):
            print(f"[LCU] Disconnected.")
            self.state['status'] = "Disconnected"
            
        @self.connector.ws.register('/lol-gameflow/v1/gameflow-phase', event_types=('UPDATE',))
        async def gameflow_handler(connection, event):
            phase = event.data
            print(f"[LCU] Gameflow Phase: {phase}")
            if phase != "ChampSelect":
                # RESET STATE
                print("[LCU] Left Champ Select. Resetting State.")
                self.state['status'] = "Waiting..."
                self.state['my_team'] = []
                self.state['enemy_team'] = []
                self.state['my_team_roles'] = {}
                self.state['enemy_team_roles'] = {}
                self.state['my_pick'] = None
                self.state['recommendations'] = []
                self.state['assigned_position'] = ""
                # Trigger update to clear UI
                if self.on_update:
                    threading.Thread(target=self.on_update).start()

        @self.connector.ws.register('/lol-champ-select/v1/session', event_types=('UPDATE',))
        async def champ_select_handler(connection, event):
            data = event.data
            
            # Identify Me and My Position
            my_cell_id = data.get('localPlayerCellId') 
            
            my_team = data.get('myTeam', [])
            enemy_team = data.get('theirTeam', [])

            # NEW: Parse Actions for everyone (find active hovers)
            cell_actions = {}
            actions = data.get('actions', [])
            for action_group in actions:
                for action in action_group:
                    if action['type'] == 'pick' and action['championId'] != 0:
                        cell_actions[action['actorCellId']] = str(action['championId'])
            
            # Helper to get best ID (Lock > Action > Intent)
            def resolve_champ_id(p):
                # 1. Locked Pick
                cid = p.get('championId', 0)
                if cid != 0: return str(cid)
                
                # 2. Active Hover (from Actions)
                if p['cellId'] in cell_actions:
                    return cell_actions[p['cellId']]

                # 3. Intent (Legacy/Fallback)
                cid = p.get('championPickIntent', 0)
                if cid != 0: return str(cid)
                return "0"

            # Store full list for engine (Only picked/hovered champs)
            print(f"[DEBUG] My Team Raw Sample: {my_team[0] if my_team else 'Empty'}")
            
            # Use resolved ID for the list
            self.state['my_team'] = []
            for p in my_team:
                cid = resolve_champ_id(p)
                if cid != "0": self.state['my_team'].append(cid)
                
            self.state['enemy_team'] = [str(p['championId']) for p in enemy_team if p['championId'] != 0]

            self.state['my_team_roles'] = {}
            for p in my_team:
                role = p.get('assignedPosition', '')
                if role:
                    role = role.upper() # Normalize to UPPERCASE
                    cid = resolve_champ_id(p)
                    if cid != "0":
                        self.state['my_team_roles'][role] = cid
                    else:
                        # Mark as picking so UI shows slot
                        self.state['my_team_roles'][role] = "Picking..."

            self.state['enemy_team_roles'] = {}
            for p in enemy_team:
                if p['championId'] != 0:
                     role = p.get('assignedPosition', '')
                     if role: self.state['enemy_team_roles'][role.upper()] = str(p['championId'])

            
            # Find Assigned Position
            for p in my_team:
                # Match by CellId OR SummonerId
                is_me = (p['cellId'] == my_cell_id)
                if not is_me and self.state.get('summoner_id') and p.get('summonerId') == self.state['summoner_id']:
                    is_me = True
                    
                if is_me:
                    raw_role = p.get('assignedPosition', '')
                    self.state['assigned_position'] = raw_role.upper() if raw_role else ""
                    
                    # Pick in progress?
                    cid = resolve_champ_id(p)
                    if cid != "0":
                        self.state['my_pick'] = cid
                    else:
                        # Check actions for Hover (Still useful for animation or very early hover)
                        # Structure: actions = [ [action1, action2], [action3, action4] ... ]
                        actions = data.get('actions', [])
                        for action_group in actions:
                            for action in action_group:
                                if action['actorCellId'] == p['cellId'] and action['championId'] != 0 and action['type'] == 'pick':
                                    # Found Hover!
                                    hovered_id = str(action['championId'])
                                    self.state['my_pick'] = hovered_id
                                    # Temporarily add to my_team list for prediction context
                                    # (Only if not already there)
                                    if hovered_id not in self.state['my_team']:
                                        self.state['my_team'].append(hovered_id)
                                    break
                    break
                    
            self.state['status'] = "Champion Select Active"
            print(f"[LCU] Role: {self.state.get('assigned_position')} | Allies: {len(self.state['my_team'])}")
            
            if self.on_update:
                try:
                    # Run analysis in a separate thread to not block the WebSocket loop
                    # Only run if meaningful change (optimization)? 
                    # For now run always to be safe.
                    t = threading.Thread(target=self.on_update)
                    t.daemon = True
                    t.start()
                except Exception as e:
                    print(f"[LCU] Analysis Error: {e}")
            
        self.connector.start()

# Standalone test
if __name__ == "__main__":
    dummy_state = {}
    worker = LCUWorker(dummy_state)
    worker.start()
    while True:
        time.sleep(1)

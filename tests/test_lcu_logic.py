
import asyncio
import unittest

# Mock State
class MockState:
    def __init__(self):
        self.data = {
            'my_team': [],
            'enemy_team': [],
            'my_team_roles': {},
            'enemy_team_roles': {},
            'assigned_position': '',
            'my_pick': None,
            'status': 'Waiting...'
        }
    
    def __getitem__(self, key):
        return self.data[key]
    
    def __setitem__(self, key, value):
        self.data[key] = value
        
    def get(self, key, default=None):
        return self.data.get(key, default)

# Simplified logic from lcu_connector.py to test
class LCUParser:
    def __init__(self, state):
        self.state = state

    def resolve_champ_id(self, p):
        cid = p.get('championId', 0)
        if cid != 0: return str(cid)
        # Fallback to intent (Hover)
        cid = p.get('championPickIntent', 0)
        if cid != 0: return str(cid)
        return "0"

    def parse_session(self, data):
        my_cell_id = data.get('localPlayerCellId')
        my_team = data.get('myTeam', [])
        enemy_team = data.get('theirTeam', [])
        
        # NEW: Parse Actions
        cell_actions = {}
        actions = data.get('actions', [])
        for action_group in actions:
            for action in action_group:
                if action['type'] == 'pick' and action['championId'] != 0:
                    cell_actions[action['actorCellId']] = str(action['championId'])
        
        # 1. Team List
        self.state['my_team'] = []
        for p in my_team:
            cid = self.resolve_champ_id(p, cell_actions)
            if cid != "0": 
                self.state['my_team'].append(cid)
            
        # 2. Roles
        self.state['my_team_roles'] = {}
        for p in my_team:
            role = p.get('assignedPosition', '')
            if role:
                role = role.upper() # emulate fix
                cid = self.resolve_champ_id(p, cell_actions)
                if cid != "0":
                    self.state['my_team_roles'][role] = cid
                else:
                    self.state['my_team_roles'][role] = "Picking..."
        
        # 3. My Position
        for p in my_team:
            is_me = (p['cellId'] == my_cell_id)
            if is_me:
                self.state['assigned_position'] = p.get('assignedPosition', '')

    def resolve_champ_id(self, p, cell_actions):
        cid = p.get('championId', 0)
        if cid != 0: return str(cid)
        
        if p['cellId'] in cell_actions:
            return cell_actions[p['cellId']]
            
        # Fallback to intent (Hover)
        cid = p.get('championPickIntent', 0)
        if cid != 0: return str(cid)
        return "0"

class TestLCUParsing(unittest.TestCase):
    def test_actions_parsing(self):
        """Test that actions are parsed correctly for hovers"""
        state = MockState()
        parser = LCUParser(state)
        
        data = {
            'localPlayerCellId': 0,
            'myTeam': [
                {'cellId': 0, 'assignedPosition': 'MIDDLE', 'championId': 0, 'championPickIntent': 0},
                {'cellId': 1, 'assignedPosition': 'TOP', 'championId': 0, 'championPickIntent': 0},
            ],
            'actions': [
                [
                    {'actorCellId': 0, 'championId': 103, 'type': 'pick'}, # Ahri Hover
                    {'actorCellId': 1, 'championId': 86, 'type': 'pick'}   # Garen Hover
                ]
            ]
        }
        
        parser.parse_session(data)
        
        self.assertEqual(state['my_team_roles']['MIDDLE'], '103')
        self.assertEqual(state['my_team_roles']['TOP'], '86')

                
class TestLCUParsing(unittest.TestCase):
    def test_standard_lobby(self):
        """Test a standard lobby with assigned roles"""
        state = MockState()
        parser = LCUParser(state)
        
        data = {
            'localPlayerCellId': 0,
            'myTeam': [
                {'cellId': 0, 'assignedPosition': 'MIDDLE', 'championId': 0, 'championPickIntent': 103}, # Ahri Hover
                {'cellId': 1, 'assignedPosition': 'TOP', 'championId': 86, 'championPickIntent': 0}, # Garen Locked
                {'cellId': 2, 'assignedPosition': 'JUNGLE', 'championId': 0, 'championPickIntent': 0}, # Empty
                {'cellId': 3, 'assignedPosition': 'BOTTOM', 'championId': 0, 'championPickIntent': 81}, # Ezreal Hover
                {'cellId': 4, 'assignedPosition': 'UTILITY', 'championId': 0, 'championPickIntent': 0} # Empty
            ]
        }
        
        parser.parse_session(data)
        
        print("\nTest Result Data:", state.data)
        
        # Assertions
        self.assertEqual(state['assigned_position'], 'MIDDLE')
        self.assertEqual(state['my_team_roles']['TOP'], '86')
        self.assertEqual(state['my_team_roles']['MIDDLE'], '103') # Should resolve intent
        self.assertEqual(state['my_team_roles']['BOTTOM'], '81') # Should resolve intent
        self.assertEqual(state['my_team_roles']['JUNGLE'], 'Picking...') 
        
        # KEY CHECK: Does my_team list contain the picking/intent ones?
        # Current logic says "if cid != 0 append". 
        # resolve_champ_id returns intent if champId is 0. 
        # So Middle and Bottom should be in list.
        self.assertIn('103', state['my_team'])
        self.assertIn('86', state['my_team'])
        self.assertIn('81', state['my_team'])
        
        # What about Jungle? It returns "0". So it is NOT in 'my_team'.
        # server.py uses 'my_team' (list) for prediction.
        # But 'my_team_roles' (dict) for UI display (via enrich).
        
    def test_blind_pick_no_roles(self):
        """Test a blind pick scenario or missing roles"""
        state = MockState()
        parser = LCUParser(state)
        
        data = {
            'localPlayerCellId': 0,
            'myTeam': [
                {'cellId': 0, 'assignedPosition': '', 'championId': 103, 'championPickIntent': 0}, 
                {'cellId': 1, 'assignedPosition': '', 'championId': 86, 'championPickIntent': 0}, 
            ]
        }
        
        parser.parse_session(data)
        
        # Roles should be empty
        self.assertEqual(len(state['my_team_roles']), 0)
        # But list should be full
        self.assertEqual(len(state['my_team']), 2)


if __name__ == '__main__':
    unittest.main()

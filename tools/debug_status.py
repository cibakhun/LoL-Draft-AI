import requests
import json
try:
    r = requests.get('http://127.0.0.1:5000/status')
    data = r.json()
    print("MY TEAM:", data.get('my_team'))
    print("ROLES:", data.get('my_team_roles'))
    print("ASSIGNMENTS:", data.get('my_team_assignments'))
except Exception as e:
    print(e)

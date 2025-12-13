import requests

# HARDCODED KEY FROM USER
KEY = "RGAPI-0a29ef38-9b42-430a-b6b6-0684b1ad5047"
REGION = "euw1"

print(f"--- TESTING KEY: {KEY} ---")

def test_url(name, url, headers=None, params=None):
    print(f"\n[TEST] {name}")
    print(f"URL: {url}")
    try:
        r = requests.get(url, headers=headers, params=params)
        print(f"Status: {r.status_code}")
        print(f"Body: {r.text}")
        return r.status_code == 200
    except Exception as e:
        print(f"EXCEPTION: {e}")
        return False

# 1. Standard Header Method
url = f"https://{REGION}.api.riotgames.com/lol/platform/v3/champion-rotations"
test_url("Method 1: Header (Standard)", url, headers={"X-Riot-Token": KEY})

# 2. Query Param Method (Alternative)
test_url("Method 2: Query Param", url, params={"api_key": KEY})

# 3. Status Endpoint (Low Security)
url_status = f"https://{REGION}.api.riotgames.com/lol/status/v4/platform-data"
test_url("Method 3: Status Endpoint", url_status, headers={"X-Riot-Token": KEY})

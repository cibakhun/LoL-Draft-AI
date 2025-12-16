import os
from dotenv import load_dotenv
import requests

load_dotenv()

key = os.getenv("RIOT_API_KEY", "").strip()
region = os.getenv("RIOT_REGION", "euw1")

print(f"Testing Key: {key[:5]}*****")
print(f"Region: {region}")

url = f"https://{region}.api.riotgames.com/lol/platform/v3/champion-rotations"
headers = {"X-Riot-Token": key}

print(f"Requesting: {url}")
r = requests.get(url, headers=headers)

print(f"Status: {r.status_code}")
print(f"Body: {r.text}")

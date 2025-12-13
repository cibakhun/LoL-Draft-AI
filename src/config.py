import os
from dotenv import load_dotenv

# Load environment variables from .env file
def load_config():
    load_dotenv(override=True)

load_config()

def get_riot_api_key():
    """Retrieves the Riot API Key from environment variables."""
    api_key = os.getenv("RIOT_API_KEY")
    if not api_key:
        print("WARNING: RIOT_API_KEY not found in environment variables.")
        print("Please create a .env file with RIOT_API_KEY=your_key_here")
        return []
        
    # Support multiple keys comma separated
    keys = [k.strip() for k in api_key.split(',') if k.strip()]
    return keys

def get_region():
    """Default region."""
    return os.getenv("RIOT_REGION", "euw1")

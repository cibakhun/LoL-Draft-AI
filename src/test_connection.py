from src.riot_client import RiotClient

def main():
    print("Testing Riot API Connection...")
    client = RiotClient()
    
    if not client.api_key:
        print("ERROR: No API Key found. Please check your .env file.")
        return

    print("API Key found. (Masked: " + client.api_key[:4] + "..." + client.api_key[-4:] + ")")
    print("Region:", client.region)
    
    # Simple test request (e.g., get status or a summoner)
    # Since we haven't implemented methods yet, just printing config.
    print("Setup seems correct!")

if __name__ == "__main__":
    main()

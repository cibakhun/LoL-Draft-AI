import json
import csv

print("--- CSV HEADERS ---")
try:
    with open(r'g:\Projects\Lol Ai Coach - profiling & meta\idea\games.csv', 'r') as f:
        reader = csv.reader(f)
        headers = next(reader)
        print(headers)
        print("--- FIRST ROW ---")
        print(next(reader))
except Exception as e:
    print(e)

print("\n--- CHAMPION INFO ---")
try:
    with open(r'g:\Projects\Lol Ai Coach - profiling & meta\idea\champion_info.json', 'r') as f:
        data = json.load(f)
        # Print a sample item
        if isinstance(data, dict):
            k = list(data.keys())[0]
            print(f"Key: {k}, Value: {data[k]}")
        elif isinstance(data, list):
            print(data[0])
except Exception as e:
    print(e)

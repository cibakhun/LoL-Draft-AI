import os
import sys
import threading
import time
import json
import logging
from flask import Flask, jsonify, request
from flask_cors import CORS

# Add src to path
current_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(os.path.dirname(current_dir))
sys.path.append(src_dir)

from src.engine.core import TitanEngine

app = Flask(__name__)
CORS(app) # Allow React to talk to us

# Global State
engine = None
engine_lock = threading.Lock()
latest_state = {
    "status": "Initializing...",
    "recommendations": [],
    "win_rate": 0.5,
    "lane_status": "Idle",
    "my_team_names": ["", "", "", "", ""],
    "enemy_team_names": ["", "", "", "", ""],
    "my_team_assignments": {}, # {ROLE: ChampName}
    "enemy_team_assignments": {},
    "my_pick_name": None,
    "assigned_position": None,
    "selection_stats": None
}

# --- Background Worker ---
def engine_loop():
    global engine, latest_state
    print("[SERVER] Starting Engine Loop...")
    
    # Initialize Engine
    try:
        engine = TitanEngine()
        print("[SERVER] Engine Initialized.")
    except Exception as e:
        print(f"[SERVER] CRITICAL ENGINE FAILURE: {e}")
        latest_state["status"] = f"Error: {str(e)}"
        return

    while True:
        try:
            # Run Cycle
            # Returns: (win_rate, suggestions, status_msg, lane_status, build, context)
            with engine_lock:
                cycle_res = engine.cycle()
            
            # Unpack
            if len(cycle_res) == 6:
                wr, recs, status, lane, build, context = cycle_res
            else:
                wr, recs, status, lane, build = cycle_res
                context = {}

            # Process Data for Frontend
            
            # Assignments (From Snapshot if available)
            # context['snapshot'] = (xp, xb, my_pos, enemy_champ, my_champ_id)
            # This logic is a bit reduced in core.py, let's extract what we can from 'context' or 'session'
            # Ideally core.py should return structured team data. 
            # For now, we trust 'recs' and 'status'.
            
            # Map Recommendations to simplified format
            # Recs is list of {id, name, score, delta, details}
            clean_recs = []
            selection_stats = None
            
            my_champ_id = context.get('my_champ_id', 0)
            
            for r in recs:
                # If this is our current selection, separate it
                is_selected = (r['id'] == my_champ_id)
                
                item = {
                    "champion": r['name'],
                    "score": r['score'],
                    "win": 50.0 + r['delta'], # Approx
                    "tier": "S" if r['score'] > 95 else "A",
                    "details": r.get('details', {})
                }
                
                if is_selected:
                    selection_stats = item
                else:
                    clean_recs.append(item)

            # Update Global State
            state_update = {
                "status": status,
                "recommendations": clean_recs,
                "selection_stats": selection_stats,
                "win_rate": wr,
                "lane_status": lane,
                "assigned_position": engine.role_filter, # If manually set
                # "build": build # TODO: expose build endpoint?
            }
            
            # Fill Team Names (Placeholder Logic - Core needs to expose this better)
            # For V1, we just send empty lists if core doesn't provide.
            # We can try to extract from LCU if we access engine.lcu direclty?
            # Better to keep it safe.
            
            latest_state.update(state_update)
            
            time.sleep(1.0)
            
        except Exception as e:
            print(f"[SERVER] Loop Error: {e}")
            time.sleep(2)

# --- Routes ---

@app.route('/status', methods=['GET'])
def get_status():
    return jsonify(latest_state)

@app.route('/predict', methods=['GET'])
def get_predict():
    return jsonify({
        "probability": round(latest_state["win_rate"] * 100, 1),
        "text": "Winning" if latest_state["win_rate"] > 0.5 else "Losing"
    })

@app.route('/gameplan', methods=['GET'])
def get_gameplan():
    champ_name = request.args.get('champion')
    if not champ_name: return jsonify({"error": "No champion specified"})
    
    # Generate Gameplan (Mock/Logic)
    # In V3.5, this should come from Strategist
    # For now, simplistic return
    
    gp = f"Play aggressive with {champ_name}. Control wave early."
    
    # Get Build
    build = {"final_build": ["item1", "item2"]}
    if engine:
        # We can ask engine for specific champ metrics
        # engine.item_data is keyed by ID. We need ID from name.
        cid = 0
        for k,v in engine.ddragon.champions.items():
            if v['name'] == champ_name:
                cid = int(v['key'])
                break
        
        if cid > 0 and str(cid) in engine.item_data:
            metrics = engine.item_data[str(cid)]
            core = metrics.get('core_items', [])
            names = []
            for i in core:
                idata = engine.ddragon.items.get(str(i))
                if idata: names.append(idata['name'])
            build["final_build"] = names

    return jsonify({"gameplan": gp, "build": build})

@app.route('/setup_override', methods=['POST'])
def setup_override():
    data = request.json
    if not engine: return jsonify({"status": "Engine not ready"}), 503
    
    if 'assigned_position' in data:
        role = data['assigned_position']
        print(f"[SERVER] Override Role: {role}")
        engine.role_filter = role
        # Trigger immediate re-calc?
        
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    # Start Engine Thread
    t = threading.Thread(target=engine_loop, daemon=True)
    t.start()
    
    print("[SERVER] Starting Flask on port 5000...")
    app.run(port=5000, debug=False, use_reloader=False)

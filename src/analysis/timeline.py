import json
import os
from collections import defaultdict, Counter

class TimelineAnalyzer:
    def __init__(self, match_dir):
        self.match_dir = match_dir
        
    def analyze_timeline(self, timeline_file, participant_id, champion_name):
        """
        Extracts skill order and early item builds for a specific participant.
        """
        try:
            with open(timeline_file, 'r') as f:
                data = json.load(f)
                
            frames = data.get("info", {}).get("frames", [])
            if not frames:
                return None
                
            skill_order = []
            item_build = []
            
            # Helper to check if event belongs to our participant
            def is_me(event):
                return event.get("participantId") == participant_id
                
            for frame in frames:
                for event in frame.get("events", []):
                    if not is_me(event):
                        continue
                        
                    # 1. Skill Order (First 9 levels typically define the maxing order)
                    if event["type"] == "SKILL_LEVEL_UP":
                        if len(skill_order) < 9:
                            skill_slot = event.get("skillSlot")
                            # Map 1->Q, 2->W, 3->E, 4->R
                            slot_map = {1: "Q", 2: "W", 3: "E", 4: "R"}
                            if skill_slot in slot_map:
                                skill_order.append(slot_map[skill_slot])
                                
                    # 2. Item Purchases (First 10 mins = 600000ms) - Core Build indicators
                    # We focus on completed items or significant components? 
                    # For simplicity, let's just log ALL purchases in first 12 mins
                    # Then we can frequency count them later.
                    if event["type"] == "ITEM_PURCHASED" and event.get("timestamp", 0) < 720000: # 12 mins
                        item_id = event.get("itemId")
                        item_build.append(item_id)
                        
            return {
                "skill_order": skill_order,
                "early_items": item_build
            }
            
        except Exception as e:
            print(f"[ANALYZER] Failed to parse {timeline_file}: {e}")
            return None

    def aggregate_stats(self, matches_to_analyze):
        """
        matches_to_analyze: list of (match_id, participant_id, champion_name)
        Returns a dict of aggregated stats per champion.
        """
        agg_data = defaultdict(lambda: {"skill_orders": [], "item_counts": Counter()})
        
        for match_id, pid, champ in matches_to_analyze:
            timeline_path = os.path.join(self.match_dir, f"{match_id}_timeline.json")
            if not os.path.exists(timeline_path):
                continue
                
            result = self.analyze_timeline(timeline_path, pid, champ)
            if result:
                # Store skill order as tuple to be hashable later if needed, or just list
                agg_data[champ]["skill_orders"].append(result["skill_order"])
                agg_data[champ]["item_counts"].update(result["early_items"])
                
        return agg_data

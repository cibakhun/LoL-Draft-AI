class SmartDraft:
    def __init__(self, meta_engine, profile_engine, comp_analyzer, learning_engine, ensemble_brain=None):
        self.meta = meta_engine
        self.profile = profile_engine
        self.comp = comp_analyzer
        self.learning = learning_engine
        self.brain = ensemble_brain # The 3 AI System
        
    def calculate_score(self, champion, my_team, enemy_team, needs=None, my_team_roles=None, enemy_team_roles=None, my_role="MIDDLE", ddragon=None):
        """
        New AI-Driven Scoring.
        Returns:
            Score (0-100) representing Win Probability.
            Details (Dict) explaining the AI confidence.
        """
        if not self.brain or not self.brain.is_trained:
            return 0, "AI Learning..."
            
        # 1. Create Hypothetical Team
        # precise team construction for the AI
        
        # Default to empty dicts if not provided (e.g. from tests)
        if my_team_roles is None: my_team_roles = {}
        if enemy_team_roles is None: enemy_team_roles = {}
        
        # Construct Blue Team (Us)
        # We need to construct a dictionary {ROLE: ID}
        # We start with the known roles from LCU
        hypothetical_blue = my_team_roles.copy()
        
        # Inject the candidate into our assigned role
        hypothetical_blue[my_role] = champion
        
        # Construct Red Team (Enemy)
        # We use what we know. If roles are missing, the AI handles it (0 padding).
        hypothetical_red = enemy_team_roles.copy()
        
        # 2. Predict Win Probability
        # Brain expects Dicts or Lists. Dicts are safer now that we support them.
        try:
            # We must pass the ddragon instance for vectorization
            ddragon_ref = ddragon or self.comp.ddragon
            
            # PREDICT
            prob = self.brain.predict(hypothetical_blue, hypothetical_red, ddragon_ref)
            
            # Calibration: Trust the Neural/Ensemble Output directly.
            # No arbitrary clamping.
            score = prob * 100
            
            synergy_score = 0
            if self.comp:
                synergy_score = self.comp.analyze_comp_impact(
                    champion, hypothetical_blue, hypothetical_red, ddragon_ref
                )
                score += synergy_score
                
            # Clamp final score
            score = max(0, min(100, score))
            
            # 3. Details
            # 3. Details
            details = {
                "WinProbability": f"{score:.1f}%",
                "AI_Confidence": "High" if score > 55 else "Low"
            }
            if synergy_score != 0:
                 details["Synergy"] = f"{synergy_score:+.1f}%"
            
            # 4. Optional: Explain Decision (Why?)
            # This is expensive, maybe only do it for top picks?
            # Or just return basic info. 
            # Ideally we call brain.explain() separately if user clicks.
            
            return round(score, 1), details
            
        except Exception as e:
            print(f"[SMART DRAFT] AI Error for {champion}: {e}")
            return 0, "AI Error"

    def batch_rank(self, candidates, my_team_roles, enemy_team_roles, my_role, ddragon):
        """
        Optimized Batch Processing.
        Generates scenarios for ALL candidates and predicts in one go.
        """
        if not self.brain or not self.brain.is_trained:
            return []

        # 1. Prepare Batch Vectors
        blue_teams = []
        red_teams = [] 
        
        # FIX: Ensure Team Roles are Integers (LCU sends strings)
        def clean_roles(role_dict):
            cleaned = {}
            for r, cid in role_dict.items():
                try: cleaned[r] = int(cid)
                except: pass
            return cleaned

        base_blue = clean_roles(my_team_roles)
        clean_red = clean_roles(enemy_team_roles)
        
        # Cache Name->ID lookup for candidates
        # candidates contains Names (e.g. "Ahri")
        valid_candidates = []
        
        for name in candidates:
            # Resolve Name -> ID
            # ddragon.champions[name]['key']
            try:
                c_data = ddragon.champions.get(name)
                if not c_data: continue
                
                cid = int(c_data['key'])
                
                # Construct scenario
                scenario_blue = base_blue.copy()
                scenario_blue[my_role] = cid
                
                blue_teams.append(scenario_blue)
                red_teams.append(clean_red)
                valid_candidates.append(name) 
            except Exception as e: 
                print(f"[SMART DRAFT] Error processing candidate '{name}': {e}")
                pass
            
        if not blue_teams:
            print(f"[SMART DRAFT] CRITICAL: No valid teams generated from {len(candidates)} candidates.")
            return []
            
        # 2. Bulk Predict
        probs = self.brain.predict_batch(blue_teams, red_teams, ddragon)
        
        results = []
        for i, name in enumerate(valid_candidates):
            raw_prob = probs[i]
            
            # --- GOLD STANDARD: HYBRID INTELLIGENCE ---
            # We pass the raw probability to the hybrid scorer
            final_prob = self._calculate_hybrid_score(raw_prob, name, my_role, ddragon)
            
            score = final_prob * 100
            # REMOVED FILTER to debug 0 results
            # if score > -1:
            # Determine Confidence Label
            if score >= 60: conf_label = "High"
            elif score >= 53: conf_label = "Medium"
            else: conf_label = "Low"
            
            results.append({
                "champion": name,
                "score": round(score, 1),
                "details": {"WinProbability": f"{score:.1f}%", "AI_Confidence": conf_label}
            })
                
        return results

    def _calculate_hybrid_score(self, neural_prob, champ_name, role, ddragon):
        """
        Combines Neural Dreams with Statistical Reality.
        New Logic: Neural is Truth. Stats provide Uncertainty Scaling.
        """
        # 1. The Dreamer (Neural Net / Ensemble)
        score = neural_prob
        
        # 2. The Realist (Sample Size Check)
        role_games = 0
        
        if self.brain and hasattr(self.brain, 'meta_stats'):
            try:
                c_data = ddragon.champions.get(champ_name)
                if c_data:
                    cid = int(c_data['key'])
                    champ_stats = self.brain.meta_stats.get(cid, {})
                    role_stats = champ_stats.get(role, {})
                    role_games = role_stats.get('games', 0)
                    print(f"[DEBUG] Cid: {cid} Role: {role} Games: {role_games}")
            except: pass
            
        # UNCERTAINTY DAMPENING
        # If we have very few games on this champ in this role, we trust the model LESS.
        # We pull the score towards 50%.
        
        if role_games < 10:
            # High Uncertainty
            # factor = 0.8 (Trust model 80%, Prior 20%)
            uncertainty_factor = 0.8
            score = (score * uncertainty_factor) + (0.5 * (1 - uncertainty_factor))
            
        elif role_games > 50:
            # High Confidence boost
            # If the model is timid (0.55) but winrate is high, we might want to boost?
            # actually, let's just leave it pure. The dampening is enough safety.
            pass

        return max(0.01, min(0.99, score))


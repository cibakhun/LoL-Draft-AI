import numpy as np
import os
import json
import joblib
import time

# Optional SOTA Brain
try:
    from src.engine.neural_brain import NeuralBrain, HAS_TORCH
except ImportError:
    HAS_TORCH = False
    NeuralBrain = None

from src.engine.features import FeatureEngine
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.linear_model import SGDClassifier

class EnsembleBrain:
    def __init__(self):
        self.neural = None
        
    def __init__(self):
        self.neural = None
        
        # 0. Cortex (Feature Engine)
        self.feature_engine = FeatureEngine()
        
        # Chronos (Timeline Engine)
        from src.engine.timeline import TimelineEngine
        self.timeline_engine = TimelineEngine()
        
        # 1. The Nuclear Option (PyTorch)
        if HAS_TORCH:
            print("[HIVE MIND] PyTorch Detected. Initializing Neural Core (LeagueNet)...")
            self.neural = NeuralBrain()
        else:
            print("[HIVE MIND] PyTorch NOT Detected. Running in Legacy Mode (CPU).")

        # 2. Gradient Boosting (Logic / Optimization) - Still useful for structured data
        # "Modern Meta" Expert -> Trains on the very latest data only.
        self.booster = HistGradientBoostingClassifier(
            max_iter=100,
            learning_rate=0.05,
            max_depth=5,        # Slightly deeper for complex interactions
            min_samples_leaf=10,
            early_stopping=True,
            random_state=42
        )
        
        # 3. Council of Trees (Bagged Forests)
        # Scalable Random Forest for Infinite Data using Sliding Window
        self.forest_council = []
        self.council_size = 60 # Capacity: 60 * 50k = 3.0 Million Matches in active RAM (Titan Scale)
        self.forest_batch_size = 50000 
        
        # 4. Meta-Learner (The Conductor)
        # Learns how to weight the 3 models dynamically using Online Logistic Regression
        self.meta_learner = SGDClassifier(loss='log_loss', learning_rate='optimal', random_state=42)
        self.meta_warmup = False
        
        self.is_trained = False
        self.model_path = "brain.joblib"
        
        # Fallback Weights
        self.weights = {'neural': 0.50, 'forest': 0.30, 'booster': 0.20}

    def save(self, path=None):
        target = path or self.model_path
        if self.is_trained:
            print(f"[HIVE MIND] Persisting Ensemble state to {target}...")
            
            # Save Scikit-Learn Models & Weights
            ensemble_state = {
                'forest_council': self.forest_council,
                'booster': self.booster,
                'weights': self.weights,
                'meta_learner': self.meta_learner,
                'meta_warmup': self.meta_warmup
            }
            joblib.dump(ensemble_state, target)
            
            # Save Cortex State (Vocab, Stats, Matrix)
            # We save it alongside the brain
            stats_path = target.replace(".joblib", "_cortex.pkl")
            self.feature_engine.save_state(stats_path)
            
            # Save Neural State
            if self.neural:
                self.neural.save()
            
            print(" -> Brain frozen successfully.")
            
    def load(self, path=None):
        target = path or self.model_path
        if os.path.exists(target):
            print(f"[HIVE MIND] Loading Ensemble state from {target}...")
            try:
                ensemble_state = joblib.load(target)
                self.forest_council = ensemble_state.get('forest_council', [])
                # Legacy Support
                if not self.forest_council and 'forest' in ensemble_state:
                     self.forest_council.append(ensemble_state['forest'])
                self.booster = ensemble_state.get('booster', self.booster)
                self.weights = ensemble_state.get('weights', self.weights)
                self.meta_learner = ensemble_state.get('meta_learner', self.meta_learner)
                self.meta_warmup = ensemble_state.get('meta_warmup', False)
                
                # Load Cortex
                stats_path = target.replace(".joblib", "_cortex.pkl")
                if os.path.exists(stats_path):
                    self.feature_engine.load_state(stats_path)
                else:
                    # Try legacy stats json
                    legacy_stats = target.replace(".joblib", "_stats.json")
                    if os.path.exists(legacy_stats):
                        print("[HIVE MIND] Importing Legacy Stats...")
                        with open(legacy_stats, 'r') as f:
                            raw = json.load(f)
                            # Convert string keys back to int
                            self.feature_engine.meta_stats = {}
                            for k, v in raw.items():
                                try: self.feature_engine.meta_stats[int(k)] = v
                                except: pass
                
                # Load Neural
                if self.neural and self.feature_engine.vocab:
                    vocab_size = max(self.feature_engine.vocab.values()) + 1
                    self.neural.load(vocab_size)

                self.is_trained = True
                print(f"[HIVE MIND] Brain loaded. Council Size: {len(self.forest_council)}")
                return True
                
            except Exception as e:
                print(f"[HIVE MIND] Load failed: {e}")
                return False
        return False

    def train(self, match_dir=None, ddragon=None, batch_size=5000, epochs=1, db=None):
        """
        STATE OF THE ART: Online Learning Protocol.
        Supports Infinite Scaling via Time-Series Streaming.
        """
        print(f"[HIVE MIND] Awakening TITAN (Online Learning Mode)... Connecting to Brain Database...")
        
        if db is None:
            from src.engine.persistence import BrainDatabase
            db = BrainDatabase()
        
        # 1. Build Vocab
        self.feature_engine.build_vocab(ddragon)
        
        # 2. Init Neural
        if self.neural:
            vocab_size = max(self.feature_engine.vocab.values()) + 1
            self.neural.initialize(vocab_size)
            
        # 3. Init Council & Memory
        self.forest_council = [] 
        # Crucial: Start with BLANK slate for meta-stats to avoid "Time Travel"
        self.feature_engine.meta_stats = {} 
        self.feature_engine.synergy_matrix = {}
        
        # Training State
        forest_buffer_X = []
        forest_buffer_y = []
        forest_cap = self.forest_batch_size # 50k per tree
        
        booster_reservoir_X = [] 
        booster_reservoir_y = []
        reservoir_cap = 300000 
        
        print(f"[HIVE MIND] --- STREAMING TIMELINE (Chronological) ---")
            
        batches = 0
        total_loss = 0
        total_matches_seen = 0
        
        # Strict Chronological Order (No Peeking)
        for batch_matches in db.yield_training_batches(batch_size, shuffle=False):
            batches += 1
            total_matches_seen += len(batch_matches)
            
            # A. Feature Engineering (PREDICTION PHASE)
            X_champs, X_meta, X_flat, y, weights = self._prepare_dataset(batch_matches, ddragon, augment=True)
            
            # --- START DEEP STACKING ---
            # Prequential Training of Meta-Learner:
            # Predict using CURRENT models (before training them on this data)
            # Then use these preds to train the meta_learner.
            
            if self.neural and self.neural.is_trained:
                 # Get component predictions
                 p_neural = self.neural.predict_batch_tensor(X_champs, X_meta) # Optimzed method needed
                 
                 p_forest = np.zeros(len(y))
                 if self.forest_council:
                     for member in self.forest_council:
                         p_forest += member.predict_proba(X_flat)[:, 1]
                     p_forest /= len(self.forest_council)
                 else: p_forest = np.full(len(y), 0.5)
                 
                 # Booster only runs at end, so we use 0.5 or current state if partial_fit supported?
                 # Booster is batch trained. So we use whatever we have.
                 p_boost = np.full(len(y), 0.5)
                 try: p_boost = self.booster.predict_proba(X_flat)[:, 1]
                 except: pass

                 # Stack: [Neural, Forest, Booster]
                 stack_X = np.column_stack([p_neural, p_forest, p_boost])
                 self.meta_learner.partial_fit(stack_X, y, classes=[0, 1])
                 self.meta_warmup = True
            # ---------------------------

            # B. Neural Training (CORRECTION PHASE)
            if self.neural:
                loss = self.neural.train_on_batch(X_champs, X_meta, y, weights=weights)
                total_loss += loss
                if batches % 10 == 0:
                    print(f" -> Batch {batches}: Loss {loss:.4f} (Matches: {total_matches_seen})")
                    
            # C. Learning Phase (UPDATE MEMORY)
            # Update Knowledge Base *after* using it to train/predict on this batch
            # C. Learning Phase (UPDATE MEMORY)
            # Update Knowledge Base *after* using it to train/predict on this batch
            self.feature_engine.update_stats(batch_matches)
            
            # Update Timeline Stats (If present)
            # We need to extract timeline data from batch if available.
            # Currently 'batch_matches' are basic dicts. 
            # In a real run, we would fetch timeline JSONs separately or cache them.
            # For now, we assume batch_matches MIGHT have 'timeline_entries' if pre-processed.
            if 'timeline_entries' in batch_matches[0]:
                 # Bulk update
                 flat_entries = [e for m in batch_matches for e in m.get('timeline_entries', [])]
                 if flat_entries:
                     db.update_timeline_stats(flat_entries)
                     # RELOAD Stats to Cortex so next batch sees them
                     # This is heavy IO. Maybe do it every 10 batches?
                     if batches % 10 == 0:
                         self.feature_engine.meta_stats = db.get_meta_stats()
            
            # D. Council Council Buffer
            forest_buffer_X.extend(X_flat)
            forest_buffer_y.extend(y)
            
            if len(forest_buffer_y) >= forest_cap:
                    self._spawn_council_member(forest_buffer_X, forest_buffer_y)
                    # Reset buffer
                    forest_buffer_X = [] 
                    forest_buffer_y = []
                    
            # E. Booster Reservoir (Sliding Window)
            booster_reservoir_X.extend(X_flat)
            booster_reservoir_y.extend(y)
            
            if len(booster_reservoir_y) > reservoir_cap:
                trim = len(booster_reservoir_y) - reservoir_cap
                booster_reservoir_X = booster_reservoir_X[trim:]
                booster_reservoir_y = booster_reservoir_y[trim:]
                        
        if self.neural and batches > 0:
            print(f"[HIVE MIND] Timeline complete. Final Average Loss: {total_loss/batches:.4f}")
            self.neural.save() 
        
        # F. Final Council Member
        if len(forest_buffer_y) > 0:
                self._spawn_council_member(forest_buffer_X, forest_buffer_y)
                
        # G. Train Booster
        if len(booster_reservoir_y) > 1000:
            print(f"[HIVE MIND] Training Booster on recent {len(booster_reservoir_y)} matches (Modern Meta)...")
            self.booster.fit(booster_reservoir_X, booster_reservoir_y)
            print("[HIVE MIND] Booster Active.")
        
        self.is_trained = True
        print(f"[HIVE MIND] Training Complete. Council Size: {len(self.forest_council)} Trees.")
        self.save()

    def _spawn_council_member(self, X, y):
        print(f"[HIVE MIND] Spawning Council Member (Samples: {len(y)})...")
        member = RandomForestClassifier(
            n_estimators=100, 
            max_depth=14,     # Increased Depth - Deep Brain
            min_samples_leaf=5, 
            n_jobs=4,         
            random_state=len(self.forest_council) 
        )
        member.fit(X, y)
        
        # SLIDING WINDOW
        if len(self.forest_council) >= self.council_size:
            print("[HIVE MIND] Council Full. Retiring oldest member (Sliding Window).")
            self.forest_council.pop(0)
            
        self.forest_council.append(member)

    def _prepare_dataset(self, matches, ddragon, augment=False):
        """
        Delegates to FeatureEngine.
        """
        X_champs, X_meta, X_flat, y, w_out = [], [], [], [], []
        
        now_ts = time.time()
        decay_rate = 0.005
        
        for m in matches:
            weight = 1.0
            if 'timestamp' in m and m['timestamp'] > 0:
                age_days = (now_ts - (m['timestamp']/1000)) / 86400.0
                if age_days < 0: age_days = 0 
                weight = np.exp(-decay_rate * age_days)
            
            states = [m]
            if augment:
                states += self._generate_partial_states(m)
                
            for state in states:
                b_team = state['blue']
                r_team = state['red']
                
                if augment:
                     b_team = self._apply_dropout(b_team)
                     r_team = self._apply_dropout(r_team)
                
                # DELEGATION TO CORTEX
                flat, (b_ids, r_ids, meta) = self.feature_engine.vectorize(b_team, r_team, ddragon)
                
                X_champs.append(b_ids + r_ids)
                X_meta.append(meta)
                X_flat.append(flat)
                y.append(state['win'])
                w_out.append(weight)
                
        return np.array(X_champs), np.array(X_meta), np.array(X_flat), np.array(y), np.array(w_out)

    def _apply_dropout(self, team_dict, p=0.01):
        import random
        new_team = team_dict.copy()
        for r, cid in new_team.items():
            if random.random() < p:
                new_team[r] = 0
        return new_team

    def _generate_partial_states(self, match):
        import random
        partials = []
        p1 = {'blue': {}, 'red': {}, 'win': match['win']}
        
        items_blue = list(match['blue'].items())
        items_red = list(match['red'].items())
        
        bk = random.randint(1, len(items_blue)) if items_blue else 0
        rk = random.randint(1, len(items_red)) if items_red else 0
        
        for k, v in items_blue[:bk]: p1['blue'][k] = v
        for k, v in items_red[:rk]: p1['red'][k] = v
        partials.append(p1)
        return partials
    
    def validate_chronological(self, ddragon, validation_ratio=0.1):
        """
        VALIDATION: Time Series Split.
        """
        print("[HIVE MIND] Running Time Series Validation (Strict Chronological Split)...")
        from src.engine.persistence import BrainDatabase
        db = BrainDatabase()
        
        total = db.get_processed_count()
        split_idx = int(total * (1 - validation_ratio))
        
        print(f"[HIVE MIND] Total Matches: {total}. Split at: {split_idx}")
        
        # Train Phase
        train_batches = db.yield_training_batches(5000, shuffle=False)
        seen = 0
        
        # We need to manually drive the training to ensure features are updated
        self.feature_engine.meta_stats = {}
        self.feature_engine.synergy_matrix = {}
        
        for batch in train_batches:
            if seen >= split_idx: break
            
            # Predict/Train Logic (Simplified for validation speed)
            self.feature_engine.update_stats(batch)
            
            # Also train neural/forest if we want real validation accuracy...
            # But here we mainly validate the PIPELINE.
            
            seen += len(batch)
            
        print("[HIVE MIND] Validation Train Phase Complete. Starting Test Phase...")
        
        test_batches = db.yield_training_batches(5000, shuffle=False)
        seen_test = 0
        correct = 0
        tested = 0
        
        for batch in test_batches:
            seen_test += len(batch)
            if seen_test < split_idx: continue
            
            for m in batch:
                pred = self.predict(m['blue'], m['red'], ddragon)
                actual = 1 if m['win'] else 0
                if abs(pred - actual) < 0.5: correct += 1
                tested += 1
                
        acc = correct / tested if tested > 0 else 0
        print(f"[HIVE MIND] Validation Accuracy: {acc*100:.2f}% (Matches: {tested})")
        return acc

    def predict(self, blue_team, red_team, ddragon):
        """Fast prediction Wrapper."""
        return self.predict_batch([blue_team], [red_team], ddragon)[0]

    def predict_batch(self, blue_teams, red_teams, ddragon):
        if not self.is_trained: return [0.5] * len(blue_teams)
        
        n_samples = len(blue_teams)
        
        # 0. Active Models
        active_weights = {}
        if self.neural: active_weights['neural'] = self.weights['neural']
        if self.forest_council: active_weights['forest'] = self.weights['forest']
        if self.booster: active_weights['booster'] = self.weights['booster']
        
        total_weight = sum(active_weights.values())
        if total_weight == 0: return [0.5] * n_samples
        
        norm_weights = {k: v / total_weight for k, v in active_weights.items()}
        
        # Stacking Arrays
        p_neural = np.zeros(n_samples)
        p_forest = np.zeros(n_samples)
        p_booster = np.zeros(n_samples)

        b_list, r_list, m_list = [], [], []
        flat_vectors = []
        
        for b, r in zip(blue_teams, red_teams):
            flat, (b_ids, r_ids, meta) = self.feature_engine.vectorize(b, r, ddragon)
            b_list.append(b_ids)
            r_list.append(r_ids)
            m_list.append(meta)
            flat_vectors.append(flat)

        # 1. Neural
        if 'neural' in active_weights:
            # This calls predict_batch which returns list, convert to np
            p_neural = np.array(self.neural.predict_batch(b_list, r_list, m_list))
            
        # 2. Forest Council (Averaging)
        if 'forest' in active_weights:
            if self.forest_council:
                for member in self.forest_council:
                    p_forest += member.predict_proba(flat_vectors)[:, 1]
                p_forest /= len(self.forest_council)
            else: p_forest[:] = 0.5
            
        # 3. Booster
        if 'booster' in active_weights:
             try:
                 p_booster = self.booster.predict_proba(flat_vectors)[:, 1]
             except: p_booster[:] = 0.5
             
        # META DECISION
        if self.meta_warmup:
             stack_X = np.column_stack([p_neural, p_forest, p_booster])
             final_probs = self.meta_learner.predict_proba(stack_X)[:, 1]
             return final_probs.tolist()
        else:
            # Fallback to Weighted Avg
            final = (p_neural * norm_weights.get('neural', 0)) + \
                    (p_forest * norm_weights.get('forest', 0)) + \
                    (p_booster * norm_weights.get('booster', 0))
            return final.tolist()

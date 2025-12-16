import json
import os
import time
import numpy as np
import joblib

# Optional Import (Handled Gracefully)
try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import Dataset, DataLoader
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

class LeagueNet(nn.Module if HAS_TORCH else object):
    # TITAN ARCHITECTURE (Round 9 - Deep SOTA)
    def __init__(self, num_champions, embedding_dim=128):
        super(LeagueNet, self).__init__()
        
        # 1. Champion Embeddings: 128-Dimensions
        # Captures deep stylistic nuances (Early vs Late, Micro vs Macro, Poke vs All-in)
        self.embedding = nn.Embedding(num_champions + 1, embedding_dim, padding_idx=0)
        
        # Input: (10 * 128) + 82 Meta (Temporal DNA Upgrade) = 1362 Input Features
        input_dim = (10 * embedding_dim) + 82 
        
        # 2. Titan Network (5 Layers Deep + GELU)
        # Replacing LeakyReLU with GELU (State of the Art for large models)
        self.layers = nn.Sequential(
            # Layer 1: Expansion
            nn.Linear(input_dim, 1024),
            nn.BatchNorm1d(1024),
            nn.GELU(),
            nn.Dropout(0.2),
            
            # Layer 2: Abstraction
            nn.Linear(1024, 512),
            nn.BatchNorm1d(512),
            nn.GELU(),
            nn.Dropout(0.2),
            
            # Layer 3: Reasoning
            nn.Linear(512, 256),
            nn.BatchNorm1d(256),
            nn.GELU(),
            nn.Dropout(0.2),
            
            # Layer 4: Distillation
            nn.Linear(256, 128),
            nn.BatchNorm1d(128),
            nn.GELU(),
            nn.Dropout(0.1),

            # Layer 5: Output Logic
            nn.Linear(128, 64),
            nn.BatchNorm1d(64),
            nn.GELU(),
            
            nn.Linear(64, 1),
            nn.Sigmoid()
        )
        
    def forward(self, blue_ids, red_ids, meta_features):
        # blue_ids: [Batch, 5]
        # red_ids: [Batch, 5]
        # meta_features: [Batch, 50]
        
        b_emb = self.embedding(blue_ids) # [Batch, 5, Emb]
        r_emb = self.embedding(red_ids)
        
        b_flat = b_emb.view(b_emb.size(0), -1) # [Batch, 5*Emb]
        r_flat = r_emb.view(r_emb.size(0), -1)
        
        # Concatenate everything
        x = torch.cat([b_flat, r_flat, meta_features], dim=1)
        
        return self.layers(x)

class NeuralBrain:
    def __init__(self, model_path="lol_neural_v1.pt"):
        self.model = None
        self.optimizer = None
        self.criterion = None
        self.model_path = model_path
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.is_trained = False
        
        # For Partial Fit state
        self.epochs_per_batch = 1 
        
        if not HAS_TORCH:
            print("[NEURAL BRAIN] CRITICAL: PyTorch not found. Brain is dormant.")

    def initialize(self, vocab_size):
        if not HAS_TORCH: return
        print(f"[NEURAL BRAIN] Initializing Titan Architecture (Vocab: {vocab_size}, Device: {self.device})...")
        self.model = LeagueNet(vocab_size).to(self.device)
        self.criterion = nn.BCELoss()
        # AdamW is better for regularization
        self.optimizer = optim.AdamW(self.model.parameters(), lr=0.001, weight_decay=1e-4) 

    def train_on_batch(self, X_champs, X_meta, y_batch, weights=None):
        """
        Performs "Deep Learning" on a data stream chunk.
        Instead of 1 gradient step per 5000 matches, we run a full Epoch (Mini-Batch SGD)
        over this chunk.
        
        Args:
            X_champs: [N, 10] list/array of IDs
            X_meta: [N, 50] list/array of floats
            y_batch: [N] list/array of targets
            weights: [N] list/array of sample weights
        """
        if not HAS_TORCH: return 0.0
        if not self.model: return 0.0
            
        self.model.train()
        
        # 1. Convert to Tensors
        t_champs = torch.LongTensor(np.array(X_champs)).to(self.device)
        t_meta = torch.FloatTensor(np.array(X_meta)).to(self.device)
        t_y = torch.FloatTensor(np.array(y_batch)).view(-1, 1).to(self.device)
        
        if weights is not None:
             t_w = torch.FloatTensor(np.array(weights)).view(-1, 1).to(self.device)
        else:
             t_w = torch.ones_like(t_y).to(self.device)
             
        # 2. Create Mini-Batches (Batch Size 128 is good stability/speed compromise)
        dataset = torch.utils.data.TensorDataset(t_champs, t_meta, t_y, t_w)
        # Shuffle ensures we don't learn order-dependent bias within the chunk
        loader = DataLoader(dataset, batch_size=128, shuffle=True) 
        
        total_loss = 0
        steps = 0
        
        # 3. Mini-Batch Descent
        # We perform ~40 updates for a 5000-size chunk
        for b_champs, b_meta, b_y, b_w in loader:
            self.optimizer.zero_grad()
            
            blue = b_champs[:, :5]
            red = b_champs[:, 5:]
            
            outputs = self.model(blue, red, b_meta)
            
            # Weighted Loss Calculation
            criterion = nn.BCELoss(reduction='none')
            loss_elements = criterion(outputs, b_y)
            loss = (loss_elements * b_w).mean()
            
            loss.backward()
            self.optimizer.step()
            
            total_loss += loss.item()
            steps += 1
        
        self.is_trained = True
        return total_loss / steps if steps > 0 else 0.0

    def train(self, X_champs, X_meta, y, epochs=20, batch_size=64, vocab_size=None):
        """
        X_champs: [N, 10] (Blue 0-4, Red 5-9)
        X_meta: [N, 50]
        y: [N]
        vocab_size: Total number of champions (indices) in the universe.
        """
        if not HAS_TORCH: return
        
        # Determine Embedding Size
        # If vocab_size is provided, use it. Otherwise guess from data (risky for small data).
        if not self.model: 
            size = vocab_size if vocab_size else (X_champs.max() + 1)
            self.initialize(vocab_size=size)
        
        print(f"[NEURAL BRAIN] Training on {len(y)} matches for {epochs} epochs...")
        
        # Convert to Tensors
        t_champs = torch.LongTensor(X_champs).to(self.device)
        t_meta = torch.FloatTensor(X_meta).to(self.device)
        t_y = torch.FloatTensor(y).view(-1, 1).to(self.device)
        
        dataset = torch.utils.data.TensorDataset(t_champs, t_meta, t_y)
        loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
        
        self.model.train()
        start = time.time()
        
        self.losses = [] # Re-initialize losses for each train call
        for epoch in range(epochs):
            epoch_loss = 0
            count = 0
            for b_champs, b_meta, b_y in loader:
                self.optimizer.zero_grad()
                
                # Split champs into Blue/Red
                blue = b_champs[:, :5]
                red = b_champs[:, 5:]
                
                pred = self.model(blue, red, b_meta)
                loss = self.criterion(pred, b_y)
                
                loss.backward()
                self.optimizer.step()
                
                epoch_loss += loss.item()
                count += 1
            
            avg_loss = epoch_loss / count
            self.losses.append(avg_loss)
            if epoch % 5 == 0:
                print(f" -> Epoch {epoch}: Loss {avg_loss:.4f}")
                
        duration = time.time() - start
        print(f"[NEURAL BRAIN] Training complete in {duration:.2f}s. Final Loss: {self.losses[-1]:.4f}")
        self.is_trained = True
        self.save()

    def predict(self, blue_ids, red_ids, meta_features):
        if not HAS_TORCH or not self.model: return 0.5
        
        self.model.eval()
        with torch.no_grad():
            b = torch.LongTensor([blue_ids]).to(self.device) # [1, 5]
            r = torch.LongTensor([red_ids]).to(self.device)
            m = torch.FloatTensor([meta_features]).to(self.device)
            
            prob = self.model(b, r, m).item()
            return prob

    def predict_batch(self, blue_ids_list, red_ids_list, meta_list):
        """
        Optimized Batch Inference (GPU Friendly).
        blue_ids_list: List of [id1, id2, id3, id4, id5]
        """
        if not HAS_TORCH or not self.model: return [0.5] * len(blue_ids_list)
        
        self.model.eval()
        with torch.no_grad():
            # Convert entire batch to one Tensor
            # Optimization: If input is already np.array, it's faster.
            # But we accept lists for flexibility.
            
            b = torch.LongTensor(blue_ids_list).to(self.device) # [N, 5]
            r = torch.LongTensor(red_ids_list).to(self.device) # [N, 5]
            m = torch.FloatTensor(meta_list).to(self.device)   # [N, 50]
            
            probs = self.model(b, r, m) # [N, 1]
            
            # Move to CPU and listify
            return probs.cpu().view(-1).tolist()

    def predict_batch_tensor(self, X_champs, X_meta):
        """
        Hyper-fast prediction for Online Stacking.
        Accepts numpy arrays directly.
        X_champs: [N, 10]
        X_meta: [N, 72]
        Returns: [N] numpy array
        """
        if not HAS_TORCH or not self.model: return np.full(len(X_champs), 0.5)
        
        self.model.eval()
        with torch.no_grad():
            t_champs = torch.LongTensor(X_champs).to(self.device)
            t_meta = torch.FloatTensor(X_meta).to(self.device)
            
            blue = t_champs[:, :5]
            red = t_champs[:, 5:]
            
            probs = self.model(blue, red, t_meta)
            return probs.cpu().view(-1).numpy()

    def save(self):
        if not HAS_TORCH or not self.model: return
        torch.save(self.model.state_dict(), self.model_path)
        
    def load(self, num_champions):
        if not HAS_TORCH: return False
        if os.path.exists(self.model_path):
            try:
                # We interpret 'num_champions' as the Vocab Size from the saved metadata
                self.initialize(num_champions)
                
                state_dict = torch.load(self.model_path, map_location=self.device)
                
                # STRICT=False allows loading if we slightly changed architecture (risky but useful during dev)
                # But here we want strict, unless we are debugging.
                # If architecture changed, improved safety:
                self.model.load_state_dict(state_dict)
                
                self.is_trained = True
                print("[NEURAL BRAIN] Synaptic weights restored.")
                return True
            except RuntimeError as e:
                print(f"[NEURAL BRAIN] Architecture Mismatch (Retrain Required): {e}")
            except Exception as e:
                print(f"[NEURAL BRAIN] Load failed: {e}")
        return False

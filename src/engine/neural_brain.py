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
    def __init__(self, num_champions, embedding_dim=16):
        super(LeagueNet, self).__init__()
        
        # 1. Champion Embeddings: The "DNA" of the game
        # We learn a vector for every champion. 0 is padding.
        self.embedding = nn.Embedding(num_champions + 1, embedding_dim, padding_idx=0)
        
        # Input: (Blue Team 5 * Emb) + (Red Team 5 * Emb) + (Meta Features 30)
        # 10 * 16 = 160
        # + 30 Meta + 20 Context = 210
        input_dim = (10 * embedding_dim) + 50 
        
        # 2. The Deep Brain (Feed Forward)
        self.layers = nn.Sequential(
            nn.Linear(input_dim, 512),
            nn.BatchNorm1d(512),
            nn.ReLU(),
            nn.Dropout(0.3),
            
            nn.Linear(512, 256),
            nn.BatchNorm1d(256),
            nn.ReLU(),
            nn.Dropout(0.2),
            
            nn.Linear(256, 128),
            nn.ReLU(),
            
            nn.Linear(128, 1),
            nn.Sigmoid() # Win Probability
        )
        
    def forward(self, blue_ids, red_ids, meta_features):
        # blue_ids: [Batch, 5]
        # red_ids: [Batch, 5]
        # meta_features: [Batch, 50]
        
        b_emb = self.embedding(blue_ids).view(blue_ids.size(0), -1) # Flatten [Batch, 5*16]
        r_emb = self.embedding(red_ids).view(red_ids.size(0), -1)
        
        # Concatenate everything
        x = torch.cat([b_emb, r_emb, meta_features], dim=1)
        
        return self.layers(x)

class NeuralBrain:
    def __init__(self, model_path="neural_brain.pt"):
        self.model_path = model_path
        self.model = None
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu") if HAS_TORCH else None
        self.is_trained = False
        self.losses = []
        
        if not HAS_TORCH:
            print("[NEURAL BRAIN] CRITICAL: PyTorch not found. Brain is dormant.")

    def initialize(self, num_champions):
        if not HAS_TORCH: return
        print(f"[NEURAL BRAIN] Initializing LeagueNet on {self.device}...")
        self.model = LeagueNet(num_champions).to(self.device)
        self.optimizer = optim.AdamW(self.model.parameters(), lr=0.001, weight_decay=1e-5)
        self.criterion = nn.BCELoss()

    def train(self, X_champs, X_meta, y, epochs=20, batch_size=64):
        """
        X_champs: [N, 10] (Blue 0-4, Red 5-9)
        X_meta: [N, 50]
        y: [N]
        """
        if not HAS_TORCH: return
        if not self.model: self.initialize(num_champions=X_champs.max() + 1)
        
        print(f"[NEURAL BRAIN] Training on {len(y)} matches for {epochs} epochs...")
        
        # Convert to Tensors
        t_champs = torch.LongTensor(X_champs).to(self.device)
        t_meta = torch.FloatTensor(X_meta).to(self.device)
        t_y = torch.FloatTensor(y).view(-1, 1).to(self.device)
        
        dataset = torch.utils.data.TensorDataset(t_champs, t_meta, t_y)
        loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)
        
        self.model.train()
        start = time.time()
        
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

    def save(self):
        if not HAS_TORCH or not self.model: return
        torch.save(self.model.state_dict(), self.model_path)
        
    def load(self, num_champions):
        if not HAS_TORCH: return False
        if os.path.exists(self.model_path):
            try:
                self.initialize(num_champions)
                self.model.load_state_dict(torch.load(self.model_path, map_location=self.device))
                self.is_trained = True
                print("[NEURAL BRAIN] Weights restored from disk.")
                return True
            except Exception as e:
                print(f"[NEURAL BRAIN] Load failed: {e}")
        return False

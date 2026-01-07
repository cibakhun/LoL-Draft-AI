import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import os

try:
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

class TitanNet(nn.Module if HAS_TORCH else object):
    """
    TitanNet V3: The God Schema Model.
    A Multi-Input Transformer optimized for "Big Data" draft emulation.
    
    Inputs:
    1. Picks (Shape 10): Champion IDs (Int16)
    2. Turns (Shape 10): Pick Order 1-10 (Int8)
    3. Bans  (Shape 10): Champion IDs (Int16)
    4. Mast  (Shape 10): Log-Normalized Mastery/XP (Float16)
    5. Meta  (Shape 3):  [Cs/Min, Patch, Side] (Float16)
    
    Architecture:
    - Shared Champion Embedding (Picks & Bans)
    - Turn Embedding
    - Mastery Encoder (Linear)
    - Meta Encoder (Linear -> Global Context)
    - Transformer Backbone (Encoder)
    - Heads: Policy (Next Pick), Value (Win Probability)
    """
    def __init__(self, vocab_size=2000, d_model=256, nhead=8, num_layers=6):
        super(TitanNet, self).__init__()
        
        self.d_model = d_model
        
        # --- Embeddings & Encoders ---
        
        # 1. Champion Embedding (Shared for Picks and Bans)
        # Vocab Size safe upper bound ~2000. 0 is padding/empty.
        self.champ_embedding = nn.Embedding(vocab_size, d_model, padding_idx=0)
        
        # 2. Pick Turn Embedding (Positions 1-10, plus 0 for unknown/pad)
        self.turn_embedding = nn.Embedding(16, d_model, padding_idx=0)
        
        # 3. Mastery Encoder (Scalar -> Vector)
        self.mastery_encoder = nn.Sequential(
            nn.Linear(1, d_model),
            nn.GELU()
        )
        
        # 4. Meta Encoder (Vector 3 -> Vector)
        self.meta_encoder = nn.Sequential(
            nn.Linear(3, d_model),
            nn.GELU()
        )
        
        # --- Backbone ---
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, 
            nhead=nhead, 
            dim_feedforward=1024, 
            dropout=0.1, 
            batch_first=True, 
            norm_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        
        # --- Heads ---
        
        # 1. Policy Head (Draft Reconstruction / Suggestion)
        # Predicts logits for ALL champions.
        self.policy_head = nn.Sequential(
            nn.Linear(d_model, d_model),
            nn.GELU(),
            nn.LayerNorm(d_model),
            nn.Linear(d_model, vocab_size)
        )
        
        # 2. Value Head (Win Probability)
        # pooled_output -> Scalar
        self.value_head = nn.Sequential(
            nn.Linear(d_model, 128),
            nn.GELU(),
            nn.Linear(128, 1),
            nn.Sigmoid()
        )
        
    def forward(self, x_picks, x_turns, x_bans, x_mast, x_meta, src_mask=None):
        """
        x_picks: [B, 10] (Int)
        x_turns: [B, 10] (Int)
        x_bans:  [B, 10] (Int)
        x_mast:  [B, 10] (Float)
        x_meta:  [B, 3]  (Float)
        src_mask: [21, 21] (Bool/Float) - Optional Causal Mask for Transformer
        """
        B = x_picks.size(0)
        
        # --- Feature Engineering ---
        
        # 1. Player Features (Pick + Turn + Mastery)
        e_picks = self.champ_embedding(x_picks) # [B, 10, D]
        e_turns = self.turn_embedding(x_turns)  # [B, 10, D]
        e_mast  = self.mastery_encoder(x_mast.unsqueeze(-1)) # [B, 10, 1] -> [B, 10, D]
        
        # Sum Player Features
        player_feats = e_picks + e_turns + e_mast # [B, 10, D]
        
        # 2. Ban Features (Just Champ Embedding)
        # We might want to add a 'Ban' positional embedding, but simple bag-of-bans or ordered bans is fine.
        ban_feats = self.champ_embedding(x_bans) # [B, 10, D]
        
        # 3. Global Context (Meta)
        meta_feat = self.meta_encoder(x_meta).unsqueeze(1) # [B, 1, D]
        
        # --- Fusion ---
        # Sequence: [Meta(1), Bans(10), Picks(10)]
        # Total Length: 21
        # Indices:
        # 0: Meta
        # 1-10: Bans (Usually we don't need causal mask for bans, they are pre-game context)
        # 11-20: Picks (We NEED causal mask here)
        
        x = torch.cat([meta_feat, ban_feats, player_feats], dim=1) # [B, 21, D]
        
        # --- Masking ---
        # Create Key Padding Mask (True where value is 0/Padding) to ignore empty slots
        # Sequence: [Meta(1), Bans(10), Picks(10)]
        
        # 1. Meta is never padding
        mask_meta = torch.zeros((B, 1), dtype=torch.bool, device=x_picks.device)
        
        # 2. Bans Padding
        mask_bans = (x_bans == 0) # [B, 10]
        
        # 3. Picks Padding
        mask_picks = (x_picks == 0) # [B, 10]
        
        # Concatenate: [Meta, Bans, Picks]
        padding_mask = torch.cat([mask_meta, mask_bans, mask_picks], dim=1) # [B, 21]

        # --- Transformer Pass ---
        # If src_mask is provided, pass it.
        # Note: TransformerEncoder takes 'mask' as (S, S) or (B*H, S, S).
        
        x_trans = self.transformer(x, mask=src_mask, src_key_padding_mask=padding_mask)
        
        # --- Heads ---
        
        # 1. Output Policy (Autoregressive Prediction)
        # Sequence Indices:
        # 0: Meta
        # 1-10: Bans (Last Ban is Index 10)
        # 11-20: Picks (Pick 1 is Index 11, Pick 10 is Index 20)
        #
        # Logic:
        # We want to predict [Pick 1, Pick 2 ... Pick 10].
        # Prediction for Pick K comes from state *before* Pick K.
        # Pred(Pick 1) comes from Index 10 (Last Ban).
        # Pred(Pick 2) comes from Index 11 (Pick 1).
        # ...
        # Pred(Pick 10) comes from Index 19 (Pick 9).
        #
        # Slice [10:20] selects Indices {10, 11... 19}.
        # Length = 10.
        # This aligns perfectly with Target [Pick 1... Pick 10].
        
        pick_tokens = x_trans[:, 10:20, :] # [B, 10, D]
        policy_logits = self.policy_head(pick_tokens) # [B, 10, Vocab]
        
        # 2. Value Output (Win Probability)
        # We want the probability of winning given the FULL draft so far.
        # The most informed token is the LAST token (Index 20).
        # Assuming Causal Mask allows Index 20 to see 0..20.
        cls_token = x_trans[:, -1, :] # [B, D]
        value = self.value_head(cls_token) # [B, 1]
        
        return {
            'policy': policy_logits,
            'value': value
        }


class TitanBrain:
    def __init__(self, model_path="titan_v3.pt"):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self.model_path = model_path
        self.optimizer = None
        
    def initialize(self, vocab_size=2000):
        if not HAS_TORCH: return
        print(f"[TITAN] Initializing V3 Architecture... Device: {self.device}")
        self.model = TitanNet(vocab_size=vocab_size).to(self.device)
        self.optimizer = optim.AdamW(self.model.parameters(), lr=0.0005, weight_decay=1e-5)
        
    def train_step(self, x_picks, x_turns, x_bans, x_mast, x_meta, y_win, src_mask=None, y_policy=None):
        if not self.model: return 0.0, 0.0
        
        self.model.train()
        self.optimizer.zero_grad()
        
        # To Device
        x_picks = x_picks.to(self.device).long()
        x_turns = x_turns.to(self.device).long()
        x_bans  = x_bans.to(self.device).long()
        x_mast  = x_mast.to(self.device).float()
        x_meta  = x_meta.to(self.device).float()
        y_win   = y_win.to(self.device).float()
        
        if src_mask is not None:
             src_mask = src_mask.to(self.device)
        
        # Forward Pass
        out = self.model(x_picks, x_turns, x_bans, x_mast, x_meta, src_mask=src_mask)
        
        # 1. Value Loss (MSE)
        loss_val = nn.MSELoss()(out['value'], y_win)
        
        # 2. Policy Loss (Reconstruction / CrossEntropy)
        # logits: [B, 10, Vocab]
        logits = out['policy'].reshape(-1, out['policy'].size(-1))
        
        if y_policy is not None:
             # Use explicit targets (Shifted outside)
             # y_policy should be [B, 10]
             targets = y_policy.to(self.device).long().view(-1)
        else:
             # Fallback (Auto-Encoder / Denoising)
             targets = x_picks.view(-1)
        
        loss_pol = nn.CrossEntropyLoss()(logits, targets)
        
        # Total Loss
        loss = loss_val + loss_pol
        
        loss.backward()
        self.optimizer.step()
        
        return loss_pol.item(), loss_val.item()

    def save(self):
        if self.model:
            torch.save(self.model.state_dict(), self.model_path)
            
    def load(self):
        if not os.path.exists(self.model_path): return False
        try:
            # Assume init called
            # weights_only=True to fix Security Warning
            self.model.load_state_dict(torch.load(self.model_path, map_location=self.device, weights_only=True))
            return True
        except: return False

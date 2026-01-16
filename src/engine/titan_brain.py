import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import os

try:
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

    """
    TitanNet V3.5: The God Schema Model (Audited).
    A Multi-Input Transformer optimized for "Big Data" draft emulation.
    
    Inputs:
    1. Picks (Shape 10): Champion IDs (Int16)
    2. Turns (Shape 10): Spatial Seat IDs (1-10) -> Used for Spatial Identity
    3. Bans  (Shape 10): Champion IDs (Int16)
    4. Mast  (Shape 10): Log-Normalized Mastery/XP (Float16)
    5. Meta  (Shape 3):  [Cs/Min, Patch, Side] (Float16)
    6. Times (Shape 10): Pick Order (1-10)
    
    Architecture:
    - Shared Champion Embedding (Picks & Bans)
    - Positional Embedding (Temporal: 1-21)
    - Spatial Embedding (Sequence/Seat: 1-10)
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
        self.champ_embedding = nn.Embedding(vocab_size, d_model, padding_idx=0)
        
        # 2. Positional Embedding (Temporal)
        # Covers 0 (Meta), 1-10 (Bans), 11-20 (Picks)
        self.pos_embedding = nn.Embedding(32, d_model, padding_idx=0)
        
        # 3. Spatial/Seat Embedding (1-10)
        # Preserves "Blue Top" vs "Red Top" identity regardless of pick order.
        self.seat_embedding = nn.Embedding(16, d_model, padding_idx=0)
        
        # 4. Mastery Encoder (Scalar -> Vector)
        self.mastery_encoder = nn.Sequential(
            nn.Linear(1, d_model),
            nn.GELU()
        )
        
        # 5. Meta Encoder (Vector 3 -> Vector)
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
        self.policy_head = nn.Sequential(
            nn.Linear(d_model, d_model),
            nn.GELU(),
            nn.LayerNorm(d_model),
            nn.Linear(d_model, vocab_size)
        )
        
        # 2. Value Head (Win Probability)
        self.value_head = nn.Sequential(
            nn.Linear(d_model, 128),
            nn.GELU(),
            nn.Linear(128, 1),
            nn.Sigmoid()
        )
        
    def _get_schedule(self, B, device, mode="SOLO"):
        """
        Returns time indices for Bans and offsets for Picks.
        
        SOLO (Default):
        - Bans 1-10 (Times 1-10)
        - Picks 1-10 (Times 11-20)
        
        TOURNAMENT:
        - Bans 1-6 (Times 1-6)
        - Picks 1-6 (Times 7-12)
        - Bans 7-10 (Times 13-16)
        - Picks 7-10 (Times 17-20)
        """
        t_bans = torch.zeros((B, 10), device=device)
        pick_offset_func = None
        
        if mode == "TOURNAMENT":
             # Phase 1
             t_bans[:, 0:6] = torch.arange(1, 7, device=device)
             # Phase 2
             t_bans[:, 6:10] = torch.arange(13, 17, device=device)
             
             def tournament_offset(pick_times):
                  # pick_times input is 1..10
                  pt = pick_times.float()
                  mask_p2 = (pt > 6)
                  pt[~mask_p2] += 6.0   # 1..6 -> 7..12
                  pt[mask_p2] += 10.0   # 7..10 -> 17..20
                  return pt.long()
             pick_offset_func = tournament_offset
             
        else: # SOLO (Ranked)
             t_bans = torch.arange(1, 11, device=device).expand(B, 10)
             
             def solo_offset(pick_times):
                  # Input 1..10 -> Output 11..20
                  return pick_times.long() + 10
             pick_offset_func = solo_offset
             
        return t_bans, pick_offset_func

    def forward(self, x_picks, x_turns, x_bans, x_mast, x_meta, x_times=None, src_mask=None, mode="SOLO"):
        """
        x_picks: [B, 10] (Int) - Champion IDs
        x_turns: [B, 10] (Int) - Spatial Seat IDs (1-10)
        x_bans:  [B, 10] (Int)
        x_mast:  [B, 10] (Float)
        x_meta:  [B, 3]  (Float)
        x_times: [B, 10] (Int) - Pick Order (1..10)
        mode:    "SOLO" (Default) or "TOURNAMENT"
        """
        B = x_picks.size(0)
        device = x_picks.device
        
        # --- Feature Engineering ---
        
        # 1. Times & Scheduling
        if x_times is None:
             x_times = torch.arange(1, 11, device=device).expand(B, 10) # 1..10 input
             
        ban_times, pick_map_func = self._get_schedule(B, device, mode=mode)
        
        # Apply mapping to Pick Times
        # We clone to avoid modifying input tensor in place if it's reused
        pick_times_global = pick_map_func(x_times.clone())
        
        # 2. Player Features
        e_picks_id = self.champ_embedding(x_picks) 
        e_picks_pos = self.pos_embedding(pick_times_global) 
        e_picks_seat = self.seat_embedding(x_turns) 
        e_mast  = self.mastery_encoder(x_mast.unsqueeze(-1)) 
        
        player_feats = e_picks_id + e_picks_pos + e_picks_seat + e_mast
        
        # 3. Ban Features
        e_bans_id = self.champ_embedding(x_bans)
        e_bans_pos = self.pos_embedding(ban_times.long())
        ban_feats = e_bans_id + e_bans_pos
        
        # 4. Global Meta (Time 0)
        meta_feat = self.meta_encoder(x_meta).unsqueeze(1)
        e_meta_pos = self.pos_embedding(torch.zeros((B, 1), dtype=torch.long, device=device))
        meta_feat = meta_feat + e_meta_pos
        
        # --- Physical Sorting (Interleaving) ---
        raw_seq = torch.cat([meta_feat, ban_feats, player_feats], dim=1) # [B, 21, D]
        
        t_meta = torch.zeros((B, 1), device=device)
        t_bans = ban_times
        t_picks = pick_times_global.float()
        
        all_times = torch.cat([t_meta, t_bans.float(), t_picks], dim=1) # [B, 21]
        sort_indices = torch.argsort(all_times, dim=1)
        
        idx_expanded = sort_indices.unsqueeze(-1).expand_as(raw_seq)
        x_sorted = torch.gather(raw_seq, 1, idx_expanded)
        
        # --- Dynamic Causal Mask (On Sorted Sequence) ---
        sorted_times = torch.gather(all_times, 1, sort_indices)
        
        if src_mask is None:
             T_i = sorted_times.unsqueeze(2) 
             T_j = sorted_times.unsqueeze(1) 
             causal_mask = (T_j > T_i)
             src_mask = causal_mask

        # --- Padding Mask (Reordered) ---
        mask_meta = torch.zeros((B, 1), dtype=torch.bool, device=device)
        mask_bans = (x_bans == 0) 
        mask_picks = (x_picks == 0) 
        raw_pad = torch.cat([mask_meta, mask_bans, mask_picks], dim=1)
        sorted_pad = torch.gather(raw_pad, 1, sort_indices)

        # --- Transformer Pass ---
        x_trans = self.transformer(x_sorted, mask=src_mask, src_key_padding_mask=sorted_pad)
        
        # --- Heads ---
        # 1. Policy Head
        policy_input = x_trans[:, :-1, :] 
        policy_logits = self.policy_head(policy_input) # [B, 20, Vocab], Sorted Order!
        
        # 2. Value Output
        cls_token = x_trans[:, -1, :] 
        value = self.value_head(cls_token) # [B, 1]
        
        return {
            'policy': policy_logits,
            'value': value,
            'sort_indices': sort_indices,
            'times': sorted_times
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
        
    def train_step(self, x_picks, x_turns, x_bans, x_mast, x_meta, y_win, src_mask=None, y_policy=None, x_times=None):
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
        
        if x_times is not None:
             x_times = x_times.to(self.device).long()
        
        if src_mask is not None:
             src_mask = src_mask.to(self.device)
        
        # Forward Pass
        out = self.model(x_picks, x_turns, x_bans, x_mast, x_meta, x_times=x_times, src_mask=src_mask)
        
        # 1. Value Loss (MSE)
        loss_val = nn.MSELoss()(out['value'], y_win)
        
        # 2. Policy Loss
        logits = out['policy'].reshape(-1, out['policy'].size(-1))
        
        if y_policy is not None:
             # Rebuild Raw Sequence of Tokens (IDs only)
             t_meta = torch.zeros((x_picks.size(0), 1), dtype=torch.long, device=self.device)
             
             # Fallback if y_policy is just [xb, xp]
             # We assume y_policy contains Targets for Bans and Picks.
             # If user passed x_bans and x_picks as targets, we can reuse x_bans/x_picks or y_policy.
             # Ideally re-construct 'raw_tokens' from inputs to handle reordering.
             raw_tokens = torch.cat([t_meta, x_bans, x_picks], dim=1) # [B, 21]
             
             # Sort using the Model's sort_indices
             sort_idx = out['sort_indices']
             sorted_tokens = torch.gather(raw_tokens, 1, sort_idx) # [B, 21]
             
             # Targets are simply the Next Tokens in the Sorted Sequence
             # Input: sorted[0..19] -> Target: sorted[1..20]
             targets = sorted_tokens[:, 1:].contiguous().view(-1)
        else:
             targets = x_picks.view(-1)
        
        loss_pol = nn.CrossEntropyLoss()(logits, targets)
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

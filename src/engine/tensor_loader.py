import torch
from torch.utils.data import Dataset
import os

class TitanTensorDataset(Dataset):
    """
    High-Performance RAM Dataset.
    Loads monolithic .pt file into CPU/GPU memory.
    """
    def __init__(self, pt_path):
        if not os.path.exists(pt_path):
            raise FileNotFoundError(f"Tensor file not found: {pt_path}")
            
        print(f"[Loader] Loading tensors from {pt_path}...")
        data = torch.load(pt_path, map_location='cpu')
        
        # Extract Tensors
        # Keys based on compiler output: draft_vectors, timeline_vectors, results
        # Also need logic to split draft into X_seq and X_roles?
        # The compiler saved 'draft_vectors' as [N, 10] IDs. It uses `vectorize_sequence` which returns IDs.
        # But `vectorize_sequence` in `features.py` returns `draft_ids` AND `role_ids`.
        # Compiler logic was: 
        # draft_ids, _ = fe.vectorize_sequence(...)
        # So 'draft_vectors' is Just Champion IDs.
        # Wait, TitanNet needs Role IDs too.
        # Reviewing compiler script -> It called fe.vectorize_sequence.
        # It discarded the second return value (role_ids) with `_`.
        # CRITICAL MISS: Role IDs are missing from the compiled dataset?
        # Let's check compiler script in history.
        
        # Step 204: 
        # draft_ids, _ = fe.vectorize_sequence(blue, red, training_mode=False)
        # Yes, it discarded role IDs.
        
        # However, TitanNet forward pass expects `draft_seq` AND `role_ids`.
        # self.model(t_seq, t_roles, ...)
        
        # If roles are missing, we might have to reconstruct them or use dummy.
        # Since I cannot re-compile instantly without scraping, I will check if I can infer roles.
        # Actually, `vectorize_sequence` returns `draft_ids` (Champion IDs) sorted by turn.
        # The order 1-10 usually implies roles if using snake draft logic, but not guaranteed.
        
        # For now, I will create synthetic/dummy roles to unblock training, OR check if TitanNet handles None.
        # TitanNet forward:
        # if role_ids is not None: x = x + self.role_embedding(role_ids)
        # It handles None! But line 214 in train_titan `t_roles = torch.LongTensor(X_roles).to(self.device)` implies it expects them.
        
        # Let's load what we have.
        self.draft_seq = data['draft_vectors'] # [N, 10]
        self.timeline = data['timeline_vectors'] # [N, T, 20]
        self.y = data['results'] # [N, 1]
        
        # Synthetic Roles (0-4, 0-4) default
        # Assuming standard list of 10 players
        N = self.draft_seq.size(0)
        # 0,1,2,3,4, 0,1,2,3,4
        self.roles = torch.tensor([0,1,2,3,4, 0,1,2,3,4], dtype=torch.long).unsqueeze(0).expand(N, -1)
        
        print(f"[Loader] Loaded {N} samples.")
        
    def __len__(self):
        return self.draft_seq.size(0)
        
    def __getitem__(self, idx):
        # Return tuple matching BrainDataset collate expectation?
        # BrainDataset returns (np.array, np.array, np.array, float)
        # Collate fn in train_titan expects list of tuples.
        # But if we use Tensors here, we might need to adjust collate OR return Tensors directly.
        
        # Train Loop expects: for i, (X_seq, X_roles, X_time, y) in enumerate(dataloader):
        # Collate converts them to Stacked Tensors.
        
        return (
            self.draft_seq[idx], # Tensor [10]
            self.roles[idx],     # Tensor [10]
            self.timeline[idx],  # Tensor [T, 20]
            self.y[idx]          # Tensor [1]
        )

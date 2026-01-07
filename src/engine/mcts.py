
import math
import random
import torch
import copy
import time
import numpy as np

class MCTSNode:
    def __init__(self, state_tensors, parent=None, action=None, slot_idx=0):
        self.state = state_tensors # (picks, turns, bans, mast, meta)
        self.parent = parent
        self.action = action # Champion ID picked to reach this state
        self.slot_idx = slot_idx # The slot (0-9) that was just filled
        
        self.children = {} # Action -> Node
        self.visits = 0
        self.value_sum = 0.0
        self.prior = 0.0 # From Policy Head
        
    def is_fully_expanded(self):
        return len(self.children) > 0

class SpatialMCTS:
    """
    AlphaZero-Lite MCTS for Spatial TitanNet V3.5.
    
    Logic:
    1. Root Expansion: Only considers moves for the User's Active Slot.
    2. Simulation: Fills remaining slots sequentially (0->9) using Policy Head hints.
    3. Evaluation: Uses Value Head on the final 10-slot board.
    """
    def __init__(self, model, feature_engine, c_puct=1.0, n_sims=50):
        self.model = model
        self.fe = feature_engine
        self.c_puct = c_puct
        self.n_sims = n_sims
        self.device = next(model.parameters()).device if model else 'cpu'

    def search(self, initial_tensors, active_slot_id, valid_actions=None):
        """
        initial_tensors: The starting board state.
        active_slot_id: The specific slot (0-9) the USER is filling.
        valid_actions: List of valid ChampIDs.
        """
        root = MCTSNode(initial_tensors, slot_idx=active_slot_id)
        
        # Expansion (Root)
        # We only expand moves for active_slot_id
        # We need to ensure we are predicting for the right slot.
        # But TitanNet predicts ALL slots.
        # We assume the model's output at index 'active_slot_id' is the prediction?
        # WAIT. TitanNet V3 output is [B, 10, Vocab].
        # Index 0 corresponds to Picks 0.
        # So yes, we look at policy_logits[:, active_slot_id, :]
        
        policy_logits, _ = self.evaluate(root.state)
        # policy_logits is [10, Vocab] after squeeze
        
        # Valid Mask
        # We pass the logits for the *specific slot*
        slot_logits = policy_logits[active_slot_id]
        
        valid_probs = self.mask_logits(slot_logits, initial_tensors, valid_actions)
        
        # Create children for top moves (Optimization: Don't create 160 children)
        top_k = 20
        # Convert valid_probs (numpy) to tensor
        top_vals, top_indices = torch.topk(torch.tensor(valid_probs), top_k)
        
        for i in range(top_k):
            action = top_indices[i].item()
            prob = top_vals[i].item()
            if prob <= 0: continue
            
            # Create Child State
            next_state = self.apply_move(root.state, action, active_slot_id)
            child = MCTSNode(next_state, parent=root, action=action, slot_idx=active_slot_id)
            child.prior = prob
            root.children[action] = child
            
        # Simulations
        for _ in range(self.n_sims):
            node = root
            
            # 1. Selection
            while node.is_fully_expanded() and not self.is_terminal(node.state):
                node = self.select_child(node)
                
            # 2. Expansion (if not terminal)
            if not self.is_terminal(node.state):
                # Identify NEXT empty slot
                next_slot = self.get_next_empty_slot(node.state)
                if next_slot != -1:
                    pol, _ = self.evaluate(node.state)
                    # For simulation, we just pick top moves for the CLONE
                    # Expand Top 5
                    
                    slot_logits = pol[next_slot]
                    sub_valid = self.mask_logits(slot_logits, node.state, None) # All valid
                    top_v, top_i = torch.topk(torch.tensor(sub_valid), 5)
                    
                    for i in range(5):
                        a = top_i[i].item()
                        if a not in node.children:
                            ns = self.apply_move(node.state, a, next_slot)
                            c = MCTSNode(ns, parent=node, action=a, slot_idx=next_slot)
                            c.prior = top_v[i].item()
                            node.children[a] = c
                            
                    # Pick one to proceed
                    if node.children:
                        # Greedy pick for simulation expansion or random based on priors?
                        # Let's just pick the first one (highest prob)
                        node = list(node.children.values())[0]
            
            # 3. Rollout / Evaluation (The Judge)
            if self.is_terminal(node.state):
                value = self.get_value(node.state)
            else:
                final_state = self.fast_rollout(node.state)
                value = self.get_value(final_state)
            
            # 4. Backprop
            curr = node
            while curr:
                curr.visits += 1
                curr.value_sum += value
                curr = curr.parent

        return root

    def get_move(self, root):
        if not root.children: return None
        best_action = max(root.children.items(), key=lambda item: item[1].visits)[0]
        return best_action

    # --- Helpers ---

    def select_child(self, node):
        best_score = -float('inf')
        best_child = None
        
        # Determine perspective
        next_slot = self.get_next_empty_slot(node.state)
        # If filling a Blue Slot (0-4), we maximize Blue Win (Value).
        # If filling Red Slot (5-9), we minimize Blue Win (Value).
        is_blue_picking = (0 <= next_slot <= 4)
        
        for action, child in node.children.items():
            avg_val = child.value_sum / (child.visits + 1e-5)
            
            # If the child represents a state after "Blue Picked",
            # The value is "Win Prob". Blue wants High Win Prob.
            # Wait. select_child uses UCT.
            # If current node is "Blue to Move", we want argmax(Q + U).
            # Q should be "Goodness for Blue".
            # avg_val IS Blue Win Prob. So Q = avg_val.
            
            # If current node is "Red to Move", we want argmax(Q' + U).
            # Q' should be "Goodness for Red".
            # Goodness for Red = 1.0 - avg_val.
            
            if is_blue_picking:
                q_score = avg_val
            else:
                q_score = 1.0 - avg_val
                
            u_val = self.c_puct * child.prior * math.sqrt(node.visits) / (1 + child.visits)
            score = q_score + u_val
            
            if score > best_score:
                best_score = score
                best_child = child
                
        return best_child

    def apply_move(self, state, action, slot_idx):
        picks = state[0].clone()
        picks[0][slot_idx] = action
        return (picks, state[1], state[2], state[3], state[4])

    def get_next_empty_slot(self, state):
        picks = state[0][0]
        for i in range(10):
            if picks[i] == 0: return i
        return -1

    def is_terminal(self, state):
        return self.get_next_empty_slot(state) == -1

    def evaluate(self, state):
        self.model.eval()
        with torch.no_grad():
            out = self.model(state[0], state[1], state[2], state[3], state[4])
        # Returns [10, Vocab], Value
        return out['policy'][0].cpu().numpy(), out['value'].item()

    def get_value(self, state):
        _, val = self.evaluate(state)
        return val

    def mask_logits(self, logits, state, valid_actions):
        # logits is numpy array [Vocab]
        probs = np.exp(logits - np.max(logits)) # Stability
        probs /= np.sum(probs)
        
        # Mask already picked
        picked = set(state[0][0].tolist())
        for i in range(len(probs)):
            if i in picked or i == 0:
                probs[i] = 0.0
                
        if valid_actions:
            for i in range(len(probs)):
                if i not in valid_actions:
                    probs[i] = 0.0
                    
        s = np.sum(probs)
        if s > 0: probs /= s
        return probs

    def fast_rollout(self, state):
        curr = state
        while True:
            slot = self.get_next_empty_slot(curr)
            if slot == -1: break
            
            pol, _ = self.evaluate(curr)
            # Use policy for THAT slot
            slot_logits = pol[slot]
            probs = self.mask_logits(slot_logits, curr, None)
            action = np.argmax(probs)
            
            curr = self.apply_move(curr, action, slot)
        return curr

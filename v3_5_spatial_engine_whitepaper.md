# Titan V3.5 Spatial Engine: Mathematical Formalism
## A Rigorous Derivation of the "God Schema" Architecture

**Version:** 3.5.0
**Date:** 2026-01-13
**Status:** Theoretical Specification

---

## Part I: The Vector Space (Input Representation)

The input consisting of a draft state $S$ is mapped into a continuous latent vector space $\mathbb{R}^{D}$.

**Definitions:**
Let $D \in \mathbb{N}$ be the model dimension ($D=256$).
Let $V \in \mathbb{N}$ be the vocabulary size of generic entities ($V=2000$).
Let $T_{seq} \in \mathbb{N}$ be the total sequence length ($T_{seq}=21$).

### 1.1 Input Tensors
The discrete input state is factorized into five independent tensors to account for the full draft phases:

1.  **Context Vector** $X_{meta} \in \mathbb{R}^{3}$: Global state [CS/Min, Patch, Side].
2.  **Ban Identity Vector** $X_{bans} \in \{0, ..., V\}^{10}$: IDs of banned champions.
3.  **Pick Identity Vector** $X_{picks} \in \{0, ..., V\}^{10}$: IDs of picked champions.
4.  **Position Vector** $X_{pos} \in \{1, ..., 21\}^{21}$: Temporal index of the draft sequence.
5.  **Spatial Seat Vector** $X_{seat} \in \{1, ..., 10\}^{10}$: Topological identity of the player seat (Maps to `x_turns`).
6.  **Mastery Vector** $X_{mast} \in \mathbb{R}^{10}$: Log-normalized mastery for picks (Padding $0$ for Bans/Context).

### 1.2 Embedding Injection
We define learnable embedding matrices:
$$W_C \in \mathbb{R}^{V \times D}, \quad W_P \in \mathbb{R}^{32 \times D}, \quad W_S \in \mathbb{R}^{16 \times D}$$

And linear projection functions:
$$f_{mast}: \mathbb{R}^1 \rightarrow \mathbb{R}^D, \quad f_{meta}: \mathbb{R}^3 \rightarrow \mathbb{R}^D$$
$$f_{mast}(x) = \text{GELU}(x W_{mast} + b_{mast}), \quad f_{meta}(x) = \text{GELU}(x W_{meta} + b_{meta})$$

The composite player embedding $E_{player}^{(i)}$ for the $i$-th slot is the vector sum of its semantic, topological, and skill components:
$$E_{player}^{(i)} = W_C[X_{picks}^{(i)}] + W_P[X_{pos}^{(i)}] + W_S[X_{seat}^{(i)}] + f_{mast}(X_{mast}^{(i)})$$

### 1.3 Sequence Construction
To align dimensions for the Transformer ($D$), we project bans and picks differently (bans lack mastery and seat info):
$$H_{bans} = W_C[X_{bans}] + W_P[X_{pos}^{1:10}]$$
$$H_{picks} = W_C[X_{picks}] + W_P[X_{pos}^{11:20}] + W_S[X_{seat}] + f_{mast}(X_{mast})$$

The full transformer input sequence $H_0 \in \mathbb{R}^{B \times 21 \times D}$ is a concatenation of context, bans, and picks:
$$H_0 = \text{Concat}\left( f_{meta}(X_{meta}) + W_P[X_{pos}^0], \; H_{bans}, \; H_{picks} \right)$$


---

## Part II: The Transformation (Neural Network Dynamics)

The core processor is a Transformer Encoder stack operating on $H_0$.

### 2.1 Self-Attention Mechanism
Let $H_l$ be the input to layer $l$. We recall the standard attention function:
$$\text{Attention}(Q, K, V) = \text{Softmax}\left(\frac{QK^T}{\sqrt{d_k}} + M\right) V$$

Where $Q = H_l W_Q, K = H_l W_K, V = H_l W_V$ are linear projections.

**Dynamic Spatial Masking $M$:**
The masking matrix $M \in \mathbb{R}^{21 \times 21}$ enforces temporal causality within the spatial draft.
Let $T \in \mathbb{N}^{21}$ be the time-index vector derived from `x_times`.
$$M_{ij} = \begin{cases} 
0 & \text{if } T_j \leq T_i \quad (\text{Visible}) \\
-\infty & \text{if } T_j > T_i \quad (\text{Future Hidden})
\end{cases}$$

Integration into Softmax:
The term $M_{ij}$ behaves as a hard constraint. If $M_{ij} = -\infty$, then $\exp(\cdot + M_{ij}) \rightarrow 0$, preventing information flow from future to past.

### 2.2 Encoder Block Dynamics
The architecture employs a **Pre-LayerNorm** design (`norm_first=True`) for enhanced training stability.
For each layer $l \in \{1, ..., L\}$:
$$H'_{l} = H_{l-1} + \text{MHA}(\text{LayerNorm}(H_{l-1}))$$
$$H_l = H'_{l} + \text{FFN}(\text{LayerNorm}(H'_{l}))$$

Where $\text{FFN}(x) = \text{GeLU}(x W_1 + b_1) W_2 + b_2$.

The final output is $H_L \in \mathbb{R}^{B \times 21 \times D}$.

---

## Part III: The Stochastic Process (MCTS Inference)

We model the draft as a Markov Decision Process (MDP).

### 3.1 MDP Definition
*   **State Space $S$:** The set of all valid draft configurations (Pick/Ban/Turn).
*   **Action Space $A$:** The set of available Champion IDs $\{1, ..., V\} \setminus \text{Picked}$.
*   **Transition $P$:** Deterministic transition $S_{t+1} = \text{Apply}(S_t, a_t)$.
*   **Reward $R$:** Binary outcome (1 for Win, 0 for Loss), observed only at terminal state $S_T$.

### 3.2 UCB1 Tree Search Equation
The selection phase maximizes the Upper Confidence Bound. For a node $s$ and action $a$:
$$a_t = \text{argmax}_{a \in A(s)} \left( Q(s,a) + U(s,a) \right)$$

**Exploitation Term ($Q$):**
$$Q(s,a) = \begin{cases} 
\bar{v}_{child} & \text{if Player = Blue} \\
1 - \bar{v}_{child} & \text{if Player = Red}
\end{cases}$$
Where $\bar{v}_{child}$ is the mean value of the child node (visits $\cdot$ value\_sum).

**Exploration Term ($U$):**
$$U(s,a) = C_{puct} \cdot P(s,a) \cdot \frac{\sqrt{\sum_b N(s,b)}}{1 + N(s,a)}$$

*   $P(s,a)$: The prior probability from the Policy Head $\pi_\theta(a|s)$.
*   $N(s,a)$: Visit count of edge $(s,a)$.
*   $C_{puct}$: Exploration constant balancing width vs. depth.

### 3.3 Network Prior Integration
The Policy Head projects the latent state of the *full sequence* (Meta + Bans + Picks 1-9) to a probability distribution over the vocabulary for the *next* token (Bans 1-10 + Picks 1-10):

$$z_{policy} = H_L[0:20]$$
$$\text{Logits} = \text{LayerNorm}(\text{GELU}(z_{policy} W_p)) W_{vocab}$$
$$\pi(a|s_t) = \text{Softmax}(\text{Logits}_t)$$

This $\pi(a|s)$ initializes the prior $P(s,a)$ in the MCTS graph, enabling prediction of both Bans and Picks over the entire draft lifecycle.

---

## Part IV: The Optimization (Training Landscape)

The network parameters $\theta$ are optimized to minimize a dual-objective loss function $L_{total}$.

### 4.1 Loss Function
$$L_{total} = L_{policy} + L_{value}$$

**Policy Loss (Cross-Entropy) with Label Shift:**
To prevent identity mapping, we strictly enforce auto-regressive prediction. The model sees input $x_t$ and must predict $x_{t+1}$.
Given the target sequence $Y = \text{Concat}(\text{Bans}, \text{Picks}) \in \{1, ..., V\}^{20}$:
$$L_{policy} = -\sum_{t=0}^{19} \log(P(Y_{t+1} | H_t))$$
Where $H_t$ is the latent representation at step $t$ (Meta or Previous Token), and $Y_{t+1}$ is the actual next token.

**Value Loss (Mean Squared Error):**
Given the actual game outcome $z \in \{0, 1\}$ and predicted win probability $\hat{v}$:
$$L_{value}(z, \hat{v}) = (z - \hat{v})^2$$

### 4.2 Gradient Flow
The gradients $\nabla_\theta L_{total}$ are computed via Backpropagation Through Time (BPTT, implicit in Transformer attention) and applied using the AdamW optimizer.
$$\theta_{t+1} = \theta_t - \eta \frac{\hat{m}_t}{\sqrt{\hat{v}_t} + \epsilon}$$

---

## Part V: The Probabilistic Prediction (Win Probability)

The system transforms the aggregate draft state into a scalar win probability.

### 5.1 Value Head Projection
We utilize the spatial context of the entire sequence, pooled primarily into the [CLS] or final token representation $h_{final} = H_L^{(last)}$.

$$\hat{v} = \sigma(W_2 \cdot \text{GELU}(W_1 \cdot h_{final} + b_1) + b_2)$$

Where $\sigma(x) = \frac{1}{1 + e^{-x}}$ is the Sigmoid activation function, constraining the output to $[0, 1]$.
This scalar $\hat{v}$ represents $P(\text{Blue Win} | S_{partial})$, guiding the MCTS "intuition" for leaf node evaluation.

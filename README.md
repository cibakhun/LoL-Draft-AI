# DraftDiff: Titan V3.5 Spatial Engine

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-ee4c2c.svg)](https://pytorch.org/)
[![Status: Developer Beta](https://img.shields.io/badge/Status-Developer_Beta-0ac8b9.svg)]()

**DraftDiff** (powered internally by the **Titan V3.5 Engine**) is a heavy-duty, offline coaching and drafting client for competitive *League of Legends*. 

We don't guess the meta—we calculate it. Utilizing extensive Riot API pipelines, local deep neural networks (PyTorch), and Monte Carlo Tree Search, DraftDiff is designed for analysts, coaches, and high-ELO players to calculate optimal draft paths, detect win-conditions, and leverage item gold curves.

> **Note:** DraftDiff is a local, offline environment. It relies wholly on public API endpoints and offline simulation logic to comply fully with Riot Games Developer terms.

---

## ⚡ Core Features & Claims

### 1. Data Pipeline: Gold Curve & Timeline Ingestion
Win rates lie. Item spikes don't. We rely heavily on the **Riot Games Match-V5 API** to ingest millions of high-ELO matches.
*   **Gold at 15 Analysis:** We rip timeline frames directly from endpoints to calculate differential xp/gold states at 15 minutes, mapping actual champion influence over the game.
*   **Local SQL Storage:** All data is parsed, compressed via zlib, and stored locally in `brain_v2.db` to act as the massive offline training ground for the neural network. 

### 2. TitanNet: The Neural Engine
The core innovation of Titan V3.5 is the **Spatial Draft Representation**, factorizing draft sequences into causal tensors to understand "Top Lane Blue" versus "Top Lane Red" not just as a pick order, but as a topological identity.
*   **Type**: Causal Transformer Encoder (Pre-LN, 6 Layers, 8 Heads, $d_{model}=256$).
*   **Inputs**: Spatial Seat IDs, Temporal Index, Champion Identity, and Patch Metadata.
*   **Mechanism**: Uses **Dynamic Spatial Masking** to enforce strict temporal causality during training.

### 3. Spatial MCTS (Inference Engine)
Calculating the optimal draft isn't a simple heuristic. DraftDiff uses extensive **Monte Carlo Tree Search** permutations to traverse potential pick/ban states.
*   **Algorithm**: MCTS with UCB1 and Neural Guidance.
*   **Policy & Value Heads**: Predicts the probability distribution $\pi(a|s)$ for the next move, and win probability $v \in [0, 1]$ directly from the leaf nodes.
*   **Nash Equilibrium**: Simulates the remaining 10-player draft sequence to find the optimal path against highly specific opposing compositions.

---

## 🚀 Getting Started

### Prerequisites
*   Python 3.10+
*   PyTorch (CUDA highly recommended for MCTS inference speed)
*   A Riot Games Developer API Key (To power the data pipeline)

### Installation

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/cibakhun/LoL-Draft-AI.git
    cd LoL-Draft-AI
    ```

2.  **Environment Setup**
    Create a `.env` file in the root directory and add your Riot Developer credentials:
    ```
    RIOT_API_KEY=RGAPI-your-key-here
    RIOT_REGION=euw1
    ```

3.  **Install Python Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Launch the Core System**
    ```bash
    # Start the local Engine Interface
    python src/interface/titan_app.py
    ```

---

## 📂 Project Architecture

*   `src/engine/`: Core Neural Network & MCTS Logic.
*   `src/data/`: Pipeline scripts interfacing with Riot League-V4 and Match-V5 APIs.
*   `src/tools/`: Scripts for data sanitation, SQLite ingestion, and Tensor compilation.
*   `landing-page/`: Front-end static assets for the DraftDiff application verification.

---

## 🤝 Contributing & Legal

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details context.

*DraftDiff isn’t endorsed by Riot Games and doesn’t reflect the views or opinions of Riot Games or anyone officially involved in producing or managing League of Legends. League of Legends and Riot Games are trademarks or registered trademarks of Riot Games, Inc. League of Legends © Riot Games, Inc.*

---
*Powered by PyTorch, MCTS, and Statistical Rigor.*

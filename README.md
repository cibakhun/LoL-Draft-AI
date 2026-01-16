# VANTAGE: Titan V3.5 Spatial Engine

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)
![PyTorch](https://img.shields.io/badge/PyTorch-2.0+-ee4c2c.svg)
![Architecture](https://img.shields.io/badge/Architecture-Transformer_Small-green)

**VANTAGE** is an advanced Neural-Symbolic drafting engine for *League of Legends*, powered by **TitanNet V3.5**, a custom Transformer architecture designed for multi-agent pick/ban strategy optimization.

Unlike traditional statistical overlays, Vantage uses a "God Schema" architecture—a unified spatial representation of the draft state—combined with **AlphaZero-Lite MCTS** to predict optimal moves, detect draft archetypes, and simulate future game states in real-time.

---

## ⚡ Architecture: The God Schema

The core innovation of Titan V3.5 is the **Spatial Draft Representation**, which factorizes the draft sequence into five causal tensors, allowing the model to understand "Top Lane Blue" vs "Top Lane Red" not just as a Pick Order, but as a topological identity.

### 1. TitanNet (Neural Engine)
*   **Type**: Causal Transformer Encoder (Pre-LN, 6 Layers, 8 Heads, $d_{model}=256$).
*   **Input**: A composite embedding of 5 independent feature spaces:
    *   **$X_{picks}, X_{bans}$**: Champion Identity (Vocab Size 2000).
    *   **$X_{pos}$**: Temporal Index (1-20 sequence position).
    *   **$X_{seat}$**: Spatial Seat ID (1-10, decoupling role from turn order).
    *   **$X_{mast}$**: Player Mastery (Log-normalized skill vector).
    *   **$X_{meta}$**: Global Context (Patch, Side, CS/Min).
*   **Mechanism**: Uses **Dynamic Spatial Masking** to enforce strict temporal causality during training, ensuring the model never "cheats" by seeing future bans/picks while processing the current state.

### 2. Spatial MCTS (Inference Engine)
*   **Algorithm**: Monte Carlo Tree Search with UCB1 and Neural Guidance.
*   **Policy Head**: Predicts the probability distribution $\pi(a|s)$ for the next move.
*   **Value Head**: Predicts win probability $v \in [0, 1]$ from the current leaf node.
*   **Draft Simulation**: Simulates the remaining 10-player draft sequence to find the Nash Equilibrium of the current lobby.

---

## 🚀 Getting Started

### Prerequisites
*   Python 3.10+
*   PyTorch (CUDA recommended for inference speed)
*   Node.js & NPM (for the Overlay)

### Installation

1.  **Clone the Repository**
    ```bash
    git clone https://github.com/cibakhun/LoL-Draft-AI.git
    cd LoL-Draft-AI
    ```

2.  **Install Python Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Launch the Engine & Overlay**
    ```bash
    # Start the Python Backend (Lobby Sensor + Inference)
    python src/interface/titan_app.py
    ```

    *The overlay communicates with the League Client (LCU) automatically.*

---

## 📂 Project Structure

*   `src/engine/`: Core Neural Network & MCTS Logic.
    *   `titan_brain.py`: **TitanNet V3.5** Model Definition (PyTorch).
    *   `mcts.py`: **SpatialMCTS** Implementation.
    *   `train_titan.py`: Training Loop with Causal Masking.
*   `src/interface/`: UI and LCU Integration.
    *   `titan_app.py`: Main Application Entry Point (PyQt/Overlay).
    *   `lcu_connector.py`: WebSocket bridge to the League Client.
*   `overlay/`: Electron/React Frontend (Legacy/Alternative UI).

---

## 🤝 Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

*Powered by PyTorch & Spatial Intelligence.*

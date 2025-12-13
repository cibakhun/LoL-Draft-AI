# VANTAGE
> **VANTAGE: An advanced Neural-Symbolic drafting engine for League of Legends, utilizing deep entity embeddings and real-time inference.**

![Build Status](https://img.shields.io/badge/build-passing-brightgreen) ![Python](https://img.shields.io/badge/python-3.14-blue) ![PyTorch](https://img.shields.io/badge/core-PyTorch_CUDA-orange) ![Status](https://img.shields.io/badge/status-Gold_Standard-gold)

**VANTAGE** is not just a stats overlay. It is a neural-enhanced co-pilot that fuses Deep Learning (`LeagueNet`), Statistical Rigor (Wilson Score), and Real-Time LCU Data to provide tactical dominance in Champion Select.

---

## ⚡ The Architecture ("The Hive Mind")

The system operates on a Hybrid Intelligence architecture designed to handle millions of data points while delivering sub-millisecond inference.

### 1. The Dreamer (LeagueNet)
*   **Tech:** PyTorch Deep Feed-Forward Network.
*   **Logic:** Uses 16-dimensional **Entity Embeddings** to "intuit" champion synergies without explicit rules. It understands that *Yasuo* needs *Knockups* not because we told it, but because it learned from 500,000+ matches.
*   **Performance:** GPU-Accelerated Tensor Batching allows evaluating 165+ draft scenarios instantly.

### 2. The Realist (Statistical Anchor)
*   **Tech:** Weighted Wilson Score Interval.
*   **Logic:** Prevents "Small Sample Size Hallucinations". A champion with 100% winrate in 1 game will correctly rank below a champion with 55% winrate in 10,000 games.

### 3. The Core (Data Engine)
*   **Storage:** SQLite with WAL (Write-Ahead-Logging) for concurrent read/write operations.
*   **Crawler:** Recursive "Snowball" crawler that mines Challenger replays 24/7 to feed the neural network.

---

## 🛠 Tech Stack

*   **Brain:** Python 3.14, PyTorch, Scikit-Learn, NumPy.
*   **Body:** Electron, React, Vite (Glassmorphism UI).
*   **Spine:** Flask (Local API), SQLite (Persistence).
*   **Nerves:** LCU Connector (WebSockets).

## 🚀 Getting Started

### Prerequisites
*   Python 3.14+
*   Node.js & NPM
*   NVIDIA GPU (Recommended for Neural Training)

### Installation
1.  **Clone the Repo** (Private Access Only)
    ```bash
    git clone https://github.com/Start-Vantage/vantage-core.git
    cd vantage-core
    ```

2.  **Ignite the Backend**
    ```bash
    pip install -r requirements.txt
    python src/server.py
    ```

3.  **Launch the UI**
    ```bash
    cd overlay
    npm install
    npm run dev
    ```

## 🔒 Security & Privacy
*   **Zero-Leak Policy:** API Keys and Databases are strictly git-ignored.
*   **Local-First:** All data processing happens on your machine. No external servers required.

---

*Powered by Neural Intelligence.*

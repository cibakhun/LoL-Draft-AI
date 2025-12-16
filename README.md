# VANTAGE v1.2: AI Coaching Evolved
> **VANTAGE: An advanced Neural-Symbolic drafting engine for League of Legends, utilizing deep entity embeddings, timeline analysis, and real-time inference.**

![Build Status](https://img.shields.io/badge/build-passing-brightgreen) ![Python](https://img.shields.io/badge/python-3.14-blue) ![PyTorch](https://img.shields.io/badge/core-PyTorch_CUDA-orange) ![Feature](https://img.shields.io/badge/feature-Timeline_DNA-purple)

**VANTAGE** is not just a stats overlay. It is a neural-enhanced co-pilot that fuses Deep Learning (`LeagueNet`), Match Timelines (`Course Chronos`), and Real-Time LCU Data to provide tactical dominance in Champion Select.

---

## ⚡ The Architecture ("The Hive Mind")

The system operates on a Hybrid Intelligence architecture designed to handle millions of data points while delivering sub-millisecond inference.

### 1. The Dreamer (LeagueNet)
*   **Tech:** PyTorch Deep Feed-Forward Network (82 Dim Inputs).
*   **Logic:** Uses **Entity Embeddings** to "intuit" champion synergies without explicit rules. It understands that *Yasuo* needs *Knockups* not because we told it, but because it learned from 500,000+ matches.

### 2. The Time Lord (Project Chronos)
*   **Tech:** Timeline Engine (`src/engine/timeline.py`).
*   **Logic:** Extracts **Temporal DNA** from every match.
    *   **Tempo Score:** Analyzes Gold@15 to identify early-game stompers.
    *   **Snowball Index:** Calculates probability of victory given a small lead.
    *   **Comeback Factor:** Identifies scaling champions who win from behind.

### 3. The Core (Data Engine)
*   **Storage:** SQLite with WAL (Write-Ahead-Logging) for concurrent read/write operations.
*   **Crawler:** Recursive "Snowball" crawler that mines Challenger replays 24/7 to feed the neural network.

---

## 📂 Project Structure

*   `src/`: Core logic (Brain, Crawler, Server).
*   `tests/`: Comprehensive unit and integration tests.
*   `tools/`: Utility scripts for maintenance and debugging.
*   `overlay/`: Electron/React Frontend.

## 🚀 Getting Started

### Prerequisites
*   Python 3.14+
*   Node.js & NPM
*   NVIDIA GPU (Recommended)

### Installation
1.  **Clone the Repo**
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

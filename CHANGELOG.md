# Changelog

All notable changes to the **VANTAGE** (Titan V3.5) project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **TitanNet V3.5**: Implemented the "God Schema" Transformer architecture with 5-tensor input factorization (Picks, Bans, Position, Seat, Meta).
- **Spatial MCTS**: Added Monte Carlo Tree Search with UCB1 and Neural Guidance (`src/engine/mcts.py`).
- **Dynamic Masking**: Implemented causal masking to strictly enforce temporal dependencies during drafting.
- **Documentation**: Added professional `README.md`, `CONTRIBUTING.md`, and `LICENSE`.
- **Frontend**: integrated `overlay/` directory for the Electron/React UI.
- **Verification**: Added `verify_masking.py` and `verify_refactor.py` to ensure mathematical correctness.

### Changed
- **Architecture**: Migrated from V1.2 "Dreamer/Time Lord" to V3.5 Spatial Engine.
- **Repository**: Restructured for better separation of concerns between `engine` (Neural) and `interface` (LCU).



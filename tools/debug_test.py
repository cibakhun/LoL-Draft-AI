import sys
import os
import traceback
from unittest.mock import MagicMock, patch

# Glue
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src'))) # Wait, src is root? No, . is root.

from src.engine.ensemble_brain import EnsembleBrain
from src.engine.neural_brain import NeuralBrain
from src.engine.persistence import BrainDatabase

def run():
    print("Starting Debug Test...")
    try:
        brain = EnsembleBrain()
        brain.neural = MagicMock()
        brain.neural.train_on_batch.return_value = 0.5
        brain.forest = MagicMock()
        brain.booster = MagicMock()
        
        # Mock DDragon
        ddragon = MagicMock()
        ddragon.champions = {'1': {'key': '1'}, '2': {'key': '2'}}
        
        # Mock DB
        with patch('src.engine.ensemble_brain.BrainDatabase') as MockDB:
            mock_db = MockDB.return_value
            b1 = [{'blue': {'TOP': 1}, 'red': {'TOP': 2}, 'win': 1}]
            mock_db.yield_training_batches.return_value = iter([b1])
            mock_db.get_meta_stats.return_value = {1: {'total_games': 10}}
            
            print("Running brain.train()...")
            brain.train("dummy", ddragon)
            print("Finished brain.train()")
            
    except Exception:
        traceback.print_exc()

if __name__ == "__main__":
    run()

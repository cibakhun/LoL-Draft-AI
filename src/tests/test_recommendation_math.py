
import unittest
from unittest.mock import MagicMock
from src.engine.recommendation import RecommendationEngine

class TestRecommendationMath(unittest.TestCase):
    def test_bayesian_smoothing_and_clamp(self):
        # Setup Mocks
        brain = MagicMock()
        ddragon = MagicMock()
        
        # Mock DDragon Champions
        ddragon.champions = {
            "Swain": {"key": 1, "name": "Swain"},
            "Janna": {"key": 2, "name": "Janna"},
            "Akshan": {"key": 3, "name": "Akshan"}
        }
        
        # Mock Brain Meta Stats
        # Swain: 2 games, 2 wins (100% WR) -> Should be smoothed
        # Janna: 100 games, 52 wins (52% WR) -> Should remain ~52%
        brain.meta_stats = {
            1: {"total_games": 2, "SUPPORT": {"games": 2, "wins": 2}},
            2: {"total_games": 100, "SUPPORT": {"games": 100, "wins": 52}},
            3: {"total_games": 2, "SUPPORT": {"games": 2, "wins": 2}}
        }
        
        # Mock Brain Predict Batch
        # Assume base prediction is 0.55 (55%) for everyone
        brain.predict_batch.return_value = [0.55, 0.55, 0.55]
        
        engine = RecommendationEngine(brain, ddragon)
        
        # Run Recommendation for SUPPORT
        my_team = [10, 11, 12, 13, 0] # 0 is empty support slot
        enemy_team = [20, 21, 22, 23, 24]
        
        recs = engine.recommend(my_team, enemy_team, "SUPPORT", config={'proficiency_bias': 0.5}, top_k=5)
        
        # Analyze Results
        print("\nTest Results:")
        for r in recs:
            cid = r['champion_id']
            prob = r['win_probability']
            name = [n for n, d in ddragon.champions.items() if d['key'] == cid][0]
            print(f"Name: {name}, WinProb: {prob:.4f}")
            
            # Assertions
            if name == "Swain":
                # Old Math: 1.0 WR -> +25% -> 80% total.
                # New Math: (2 + 5) / (2 + 10) = 7/12 = 0.583. Diff = 0.083. Bonus = 0.0415. 
                # Base 0.55 + 0.0415 = 0.5915 (59%)
                # Expected < 0.65
                self.assertLess(prob, 0.65, "Swain probability should be smoothed down significantly.")
                self.assertGreater(prob, 0.55, "Swain should still have a small positive bias.")
                
            if name == "Janna":
                # New Math: (52 + 5) / (100 + 10) = 57/110 = 0.518. Diff = 0.018. Bonus = 0.009.
                # Base 0.55 + 0.009 = 0.559
                self.assertAlmostEqual(prob, 0.559, delta=0.02)
                
        # Test Clamp
        # Force a massive base prediction
        brain.predict_batch.return_value = [0.99, 0.99, 0.99]
        recs_high = engine.recommend(my_team, enemy_team, "SUPPORT", top_k=5)
        for r in recs_high:
             self.assertLessEqual(r['win_probability'], 0.75, "Result should be clamped to 75%")

if __name__ == '__main__':
    unittest.main()

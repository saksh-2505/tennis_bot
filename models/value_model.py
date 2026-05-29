import logging
import xgboost as xgb
import os
import pandas as pd
from tennis_bot.models.elo_tracker import EloTracker
from tennis_bot.models.markov_chain import TennisMarkovChain
from tennis_bot.models.volatility_tracker import VolatilityTracker
from rapidfuzz import process, fuzz


class ValueModel:
    """
    Analyzes odds using a unified ensemble of Fundamental ML, 
    Markov Chains, and Market Volatility tracking.
    Supports Exchange Trading (Back and Lay).
    """

    def __init__(self, db_manager=None):
        self.logger = logging.getLogger("models.ValueModel")
        self.ml_model = None
        self.tracker = EloTracker()
        self.markov = TennisMarkovChain()
        self.db = db_manager
        self.volatility = VolatilityTracker(db_manager) if db_manager else None
        self.load_ml_assets()

    def load_ml_assets(self):
        """Loads the XGBoost model and Elo state."""
        try:
            model_path = os.path.join(os.path.dirname(__file__), "model.xgb")
            if os.path.exists(model_path):
                self.ml_model = xgb.XGBClassifier()
                self.ml_model.load_model(model_path)
                self.logger.info("XGBoost model loaded successfully.")
            else:
                self.logger.warning(f"Model file not found at {model_path}")

            if self.tracker.load_state():
                self.logger.info("Elo tracker state loaded successfully.")
            else:
                self.logger.warning("Elo tracker state file not found.")
        except Exception as e:
            self.logger.error(f"Failed to load ML assets: {e}")

    def predict_win_prob(self, p_a_name, p_b_name, surface="Hard"):
        """
        Predicts win probability for Player A using the ML model.
        """
        if not self.ml_model or not self.tracker.name_to_id:
            return None

        def get_js_id(name):
            if not name: return None
            if name in self.tracker.name_to_id:
                return self.tracker.name_to_id[name]
            match = process.extractOne(
                name, self.tracker.name_to_id.keys(),
                scorer=fuzz.token_sort_ratio
            )
            if match and match[1] >= 90:
                return self.tracker.name_to_id[match[0]]
            return None

        id_a = get_js_id(p_a_name)
        id_b = get_js_id(p_b_name)

        if id_a is None or id_b is None:
            return None

        elo_a = self.tracker.elo_overall[id_a]
        elo_b = self.tracker.elo_overall[id_b]
        surface_elo_a = self.tracker.elo_surface.get(surface, {}).get(id_a, elo_a)
        surface_elo_b = self.tracker.elo_surface.get(surface, {}).get(id_b, elo_b)
        h2h_a = self.tracker.h2h[id_a][id_b]
        h2h_b = self.tracker.h2h[id_b][id_a]

        features = pd.DataFrame([{
            'elo_diff': elo_a - elo_b,
            'surface_elo_diff': surface_elo_a - surface_elo_b,
            'h2h_a': h2h_a,
            'h2h_b': h2h_b
        }])

        prob = self.ml_model.predict_proba(features)[0, 1]
        return prob

    def find_ev(self, true_prob, odds):
        """EV = (True Prob * Odds) - 1"""
        if true_prob <= 0 or odds <= 1.0: return 0.0
        return (true_prob * odds) - 1

    def calculate_kelly(self, prob, odds, fraction=0.25):
        if odds <= 1.0: return 0.0
        b = odds - 1
        q = 1 - prob
        kelly = (prob * b - q) / b
        return max(0, kelly * fraction)

    def analyze_match(self, soft_odds_list, player_a=None, player_b=None, surface="Hard", match_id=None):
        """
        Ensemble analysis supporting BACK and LAY.
        """
        true_h = self.predict_win_prob(player_a, player_b, surface) if player_a and player_b else None
        if true_h is None: return []

        true_a = 1 - true_h
        opportunities = []

        for soft in soft_odds_list:
            # 1. Moneyline BACK Analysis
            ev_h_back = self.find_ev(true_h, soft['home'])
            ev_a_back = self.find_ev(true_a, soft['away'])

            # 2. Volatility
            is_fade = False
            if self.volatility and match_id:
                is_fade = self.volatility.is_sentiment_fade(match_id, soft['bookmaker'], true_h)

            # --- BACK SIGNALS ---
            if ev_h_back > 0.05 or (ev_h_back > 0.02 and is_fade):
                opportunities.append({
                    "selection": "1", "side": "back", "bookmaker": soft['bookmaker'],
                    "ev": ev_h_back, "true_prob": true_h, "odds": soft['home'],
                    "stake": f"{self.calculate_kelly(true_h, soft['home']):.1%}",
                    "method": "Fundamental + Fade" if is_fade else "Fundamental ML"
                })

            if ev_a_back > 0.05:
                opportunities.append({
                    "selection": "2", "side": "back", "bookmaker": soft['bookmaker'],
                    "ev": ev_a_back, "true_prob": true_a, "odds": soft['away'],
                    "stake": f"{self.calculate_kelly(true_a, soft['away']):.1%}",
                    "method": "Fundamental ML"
                })

            # --- LAY SIGNALS (Opponent Undervalued) ---
            # If our model says Player A is 80% (1.25 fair), but market is 1.10 to Lay A.
            # Laying A at 1.10 is equivalent to Backing B at 11.0 (very high value).
            # Rule: If Market Odds < Fair Odds * 0.90 -> LAY (Player is overvalued)
            if soft['home'] < (1/true_h) * 0.85:
                opportunities.append({
                    "selection": "1", "side": "lay", "bookmaker": soft['bookmaker'],
                    "ev": 0.10, "true_prob": true_h, "odds": soft['home'],
                    "stake": "2.0%", "method": "Overvalued (LAY)"
                })

        return opportunities

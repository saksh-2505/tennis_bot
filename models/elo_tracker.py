import pandas as pd
from collections import defaultdict
import logging
import pickle
import os

logger = logging.getLogger("models.elo_tracker")
logging.basicConfig(level=logging.INFO)


class EloTracker:
    """
    Calculates and tracks Elo ratings (Overall and Surface-specific)
    and H2H records.
    """

    def __init__(self, k_factor=32, initial_rating=1500):
        self.k_factor = k_factor
        self.initial_rating = initial_rating

        # Ratings structures
        self.elo_overall = defaultdict(lambda: self.initial_rating)
        # {surface: {player: rating}}
        self.elo_surface = defaultdict(
            lambda: defaultdict(lambda: self.initial_rating)
        )
        # {p1_id: {p2_id: p1_wins}}
        self.h2h = defaultdict(lambda: defaultdict(int))
        self.name_to_id = {}  # {"Standard Name": id}
        # {player_id: [p_serve_values]}
        self.p_serve_history = defaultdict(list)

    def get_avg_p_serve(self, player_id):
        """Returns the average point win probability on serve."""
        history = self.p_serve_history[player_id]
        if not history:
            return 0.65  # Neutral baseline
        return sum(history) / len(history)

    def get_expected_score(self, rating_a, rating_b):
        """Calculates the expected score for Player A."""
        return 1 / (1 + 10 ** ((rating_b - rating_a) / 400))

    def update_ratings(self, winner_id, loser_id, surface=None):
        """Updates overall and surface-specific Elo ratings after a match."""

        # 1. Update Overall Elo
        expected_winner = self.get_expected_score(
            self.elo_overall[winner_id], self.elo_overall[loser_id]
        )

        change = self.k_factor * (1 - expected_winner)
        self.elo_overall[winner_id] += change
        self.elo_overall[loser_id] -= change

        # 2. Update Surface Elo
        if surface and surface in ['Hard', 'Clay', 'Grass']:
            expected_surface_winner = self.get_expected_score(
                self.elo_surface[surface][winner_id],
                self.elo_surface[surface][loser_id]
            )
            surface_change = self.k_factor * (1 - expected_surface_winner)
            self.elo_surface[surface][winner_id] += surface_change
            self.elo_surface[surface][loser_id] -= surface_change

        # 3. Update H2H
        self.h2h[winner_id][loser_id] += 1

        return change

    def process_matches(self, df):
        """
        Iterates through a DataFrame of matches and generates features.
        Returns a DataFrame ready for training.
        """
        features = []

        # Standardize surface names
        df['surface'] = df['surface'].fillna('Unknown')

        logger.info(f"Processing {len(df)} matches...")

        for idx, row in df.iterrows():
            w_id = row['winner_id']
            l_id = row['loser_id']
            w_name = row['winner_name']
            l_name = row['loser_name']
            surface = row['surface']

            # Map names to IDs for later lookup
            self.name_to_id[w_name] = w_id
            self.name_to_id[l_name] = l_id

            # Record current (pre-match) ratings as features
            # We use a neutral perspective (Player A vs Player B)
            # In training, we can randomize which player is A

            p_a_surf_elo = self.elo_overall[w_id]
            if surface != 'Unknown':
                p_a_surf_elo = self.elo_surface[surface][w_id]

            p_b_surf_elo = self.elo_overall[l_id]
            if surface != 'Unknown':
                p_b_surf_elo = self.elo_surface[surface][l_id]

            match_features = {
                'tourney_date': row['tourney_date'],
                'surface': surface,
                'p_a_id': w_id,
                'p_b_id': l_id,
                'p_a_elo': self.elo_overall[w_id],
                'p_b_elo': self.elo_overall[l_id],
                'p_a_surface_elo': p_a_surf_elo,
                'p_b_surface_elo': p_b_surf_elo,
                'h2h_a': self.h2h[w_id][l_id],
                'h2h_b': self.h2h[l_id][w_id],
                'label': 1  # Player A (winner) won
            }
            features.append(match_features)

            # Update ratings for next matches
            self.update_ratings(w_id, l_id, surface)

            # --- Update Service Statistics ---
            # Jeff Sackmann columns: w_svpt, w_1stIn, w_1stWon, w_2ndWon
            # (winner's serve points won) / (winner's total serve points)
            if 'w_svpt' in row and row['w_svpt'] > 0:
                try:
                    w_p_serve = (row['w_1stWon'] + row['w_2ndWon']) / row['w_svpt']
                    self.p_serve_history[w_id].append(w_p_serve)
                except: pass
            
            if 'l_svpt' in row and row['l_svpt'] > 0:
                try:
                    l_p_serve = (row['l_1stWon'] + row['l_2ndWon']) / row['l_svpt']
                    self.p_serve_history[l_id].append(l_p_serve)
                except: pass

        return pd.DataFrame(features)

    def save_state(self, filepath=None):
        if filepath is None:
            filepath = os.path.join(os.path.dirname(__file__), "elo_state.pkl")

        state = {
            'elo_overall': dict(self.elo_overall),
            'elo_surface': {k: dict(v) for k, v in self.elo_surface.items()},
            'h2h': {k: dict(v) for k, v in self.h2h.items()},
            'name_to_id': self.name_to_id,
            'p_serve_history': dict(self.p_serve_history)
        }
        with open(filepath, 'wb') as f:
            pickle.dump(state, f)
        logger.info(f"Elo state saved to {filepath}")

    def load_state(self, filepath=None):
        if filepath is None:
            filepath = os.path.join(os.path.dirname(__file__), "elo_state.pkl")

        if os.path.exists(filepath):
            with open(filepath, 'rb') as f:
                state = pickle.load(f)

            self.elo_overall.update(state['elo_overall'])
            for surface, ratings in state['elo_surface'].items():
                self.elo_surface[surface].update(ratings)
            for p1, opponents in state['h2h'].items():
                self.h2h[p1].update(opponents)
            if 'name_to_id' in state:
                self.name_to_id.update(state['name_to_id'])
            if 'p_serve_history' in state:
                for k, v in state['p_serve_history'].items():
                    self.p_serve_history[k].extend(v)
            logger.info(f"Elo state loaded from {filepath}")
            return True
        return False


if __name__ == "__main__":
    from tennis_bot.models.data_loader import TennisDataLoader
    loader = TennisDataLoader()
    df = loader.load_data(2022, 2023)
    tracker = EloTracker()
    feat_df = tracker.process_matches(df)
    print(feat_df.tail())
    tracker.save_state()

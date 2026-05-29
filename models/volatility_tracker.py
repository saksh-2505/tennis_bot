import logging

class VolatilityTracker:
    """
    Tracks line movements and market volatility for Mean Reversion signals.
    """

    def __init__(self, db_manager):
        self.db = db_manager
        self.logger = logging.getLogger("models.VolatilityTracker")

    def get_line_movement(self, match_id, bookmaker):
        """
        Calculates the movement from Opening Line to Current Line.
        Returns % change in implied probability.
        """
        conn = self.db.get_connection()
        try:
            # 1. Get Opening Line (First entry for this match/bookmaker)
            query_opening = """
                SELECT home_odds, away_odds, timestamp
                FROM odds_history
                WHERE match_id = ? AND bookmaker = ?
                ORDER BY timestamp ASC
                LIMIT 1
            """
            cursor = conn.execute(query_opening, (match_id, bookmaker))
            opening = cursor.fetchone()

            # 2. Get Current Line (Latest entry)
            query_current = """
                SELECT home_odds, away_odds, timestamp
                FROM odds_history
                WHERE match_id = ? AND bookmaker = ?
                ORDER BY timestamp DESC
                LIMIT 1
            """
            cursor = conn.execute(query_current, (match_id, bookmaker))
            current = cursor.fetchone()

            if not opening or not current:
                return None

            # 3. Calculate % change in Implied Probability for Home
            opening_implied = 1 / opening['home_odds']
            current_implied = 1 / current['home_odds']
            
            movement = current_implied - opening_implied
            
            return {
                'opening': dict(opening),
                'current': dict(current),
                'movement_abs': movement,
                'is_overreaction': abs(movement) > 0.05 # 5% shift threshold
            }
        except Exception as e:
            self.logger.error(f"Error tracking volatility: {e}")
            return None
        finally:
            conn.close()

    def is_sentiment_fade(self, match_id, bookmaker, our_true_prob):
        """
        Checks if the market is moving AWAY from our true probability.
        This identifies a Mean Reversion opportunity (fading the public).
        """
        data = self.get_line_movement(match_id, bookmaker)
        if not data:
            return False
            
        movement = data['movement_abs']
        
        # If our true prob says Player A is undervalued, 
        # but the market moved to make Player A even CHEAPER (implied prob decreased),
        # this is a sentiment fade opportunity.
        
        # simplified: if market moves >5% against our model's direction
        if our_true_prob > (1 / data['opening']['home_odds']):
            # We think Home is a value.
            if movement < -0.03: # Market moved even lower on Home
                return True
                
        return False

import sqlite3
import os
import logging


import sqlite3
import os
import logging
from contextlib import contextmanager

class DatabaseManager:
    """
    Manages database connections and operations for the Tennis Bot.
    Defaulting to SQLite for this environment.
    """

    def __init__(self, db_path="tennis_bot.db"):
        self.db_path = db_path
        self.logger = logging.getLogger("database.manager")
        self.init_db()

    @contextmanager
    def connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            self.logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()

    def get_connection(self):
        """Legacy support for direct connection access."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        """Initializes the database with the schema."""
        schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        if not os.path.exists(schema_path):
            self.logger.error(f"Schema file not found at {schema_path}")
            return

        with open(schema_path, "r") as f:
            schema_sql = f.read()

        # SQLite specific tweaks
        schema_sql = schema_sql.replace("SERIAL PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
        schema_sql = schema_sql.replace("TIMESTAMP DEFAULT CURRENT_TIMESTAMP", "DATETIME DEFAULT CURRENT_TIMESTAMP")

        with self.connection() as conn:
            conn.executescript(schema_sql)
            self.logger.info("Database initialized successfully.")

    def insert_match(self, match_data):
        """Inserts a new match or ignores if it already exists."""
        query = """
            INSERT OR IGNORE INTO matches (
                player_a, player_b, start_time, tournament,
                tournament_surface
            )
            VALUES (?, ?, ?, ?, ?)
        """
        try:
            with self.connection() as conn:
                conn.execute(query, (
                    match_data['player_a'], match_data['player_b'],
                    match_data['start_time'], match_data.get('tournament'),
                    match_data.get('surface')
                ))
            return True
        except Exception:
            return False

    def insert_odds(self, odds_data):
        """Inserts a new odds record."""
        try:
            with self.connection() as conn:
                # First find match_id
                cursor = conn.execute("""
                    SELECT id FROM matches
                    WHERE player_a = ? AND player_b = ? AND start_time = ?
                """, (
                    odds_data['player_a'], odds_data['player_b'],
                    odds_data['start_time']
                ))
                row = cursor.fetchone()
                if not row:
                    self.logger.warning(f"Match not found for odds: {odds_data['player_a']} vs {odds_data['player_b']}")
                    return False

                match_id = row['id']
                conn.execute("""
                    INSERT INTO odds_history (
                        match_id, bookmaker, market, home_odds, away_odds
                    )
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    match_id, odds_data['bookmaker'], odds_data['market'],
                    odds_data['home_odds'], odds_data['away_odds']
                ))
            return True
        except Exception:
            return False

    def get_upcoming_matches(self):
        """Returns a list of upcoming matches."""
        with self.connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM matches WHERE match_status = 'upcoming' "
                "ORDER BY start_time ASC"
            )
            return [dict(row) for row in cursor.fetchall()]

    def insert_placed_bet(self, match_id, bookmaker, selection, odds, stake, ev=None, bet_type='simulated', side='back', trade_group_id=None):
        """Records a back or lay bet in the database."""
        query = """
            INSERT INTO placed_bets (
                match_id, trade_group_id, bookmaker, selection, 
                bet_side, amount_wagered, odds_taken, expected_value, 
                bet_type
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        try:
            with self.connection() as conn:
                conn.execute(query, (
                    match_id, trade_group_id, bookmaker, selection, 
                    side, stake, odds, ev, bet_type
                ))
            return True
        except Exception:
            return False

    def get_active_trades(self, match_id):
        """Returns all pending bets for a match to calculate net exposure."""
        with self.connection() as conn:
            query = "SELECT * FROM placed_bets WHERE match_id = ? AND status = 'pending'"
            cursor = conn.execute(query, (match_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_simulator_stats(self):
        """Calculates total PnL and ROI for simulated bets."""
        with self.connection() as conn:
            query = """
                SELECT 
                    COUNT(*) as total_bets,
                    SUM(amount_wagered) as total_wagered,
                    SUM(pnl) as total_pnl,
                    AVG(expected_value) as avg_ev
                FROM placed_bets
                WHERE bet_type = 'simulated' AND status != 'pending'
            """
            cursor = conn.execute(query)
            return dict(cursor.fetchone())


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    db = DatabaseManager()
    db.insert_match({
        'player_a': 'Novak Djokovic',
        'player_b': 'Rafael Nadal',
        'start_time': '2026-05-01 14:00:00',
        'tournament': 'French Open',
        'surface': 'Clay'
    })
    matches = db.get_upcoming_matches()
    print(f"Upcoming Matches: {matches}")

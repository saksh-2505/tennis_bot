from rapidfuzz import process, fuzz
import logging
import sqlite3
import json


class NormalizationEngine:
    """
    Standardizes player names and tournament names using fuzzy matching.
    Supports persistent storage in SQLite.
    """

    def __init__(self, db_path="tennis_bot.db", threshold=85):
        self.db_path = db_path
        self.threshold = threshold
        self.logger = logging.getLogger("core.normalization")
        self.master_players = {}  # {id: "Standard Name"}
        self.name_to_id = {}     # {"alias": id}
        self.load_from_db()

    def load_from_db(self):
        """
        Loads player data from the database into memory.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT id, standard_name, aliases FROM players"
            )
            rows = cursor.fetchall()

            self.master_players = {}
            self.name_to_id = {}

            for row in rows:
                pid = row['id']
                std_name = row['standard_name']
                self.master_players[pid] = std_name
                self.name_to_id[std_name] = pid

                if row['aliases']:
                    try:
                        aliases = json.loads(row['aliases'])
                        for alias in aliases:
                            self.name_to_id[alias] = pid
                    except Exception:
                        # Fallback for comma-separated if not JSON
                        for alias in row['aliases'].split(","):
                            self.name_to_id[alias.strip()] = pid

            conn.close()
            self.logger.info(
                f"Loaded {len(self.master_players)} players from database."
            )
        except Exception as e:
            self.logger.error(f"Failed to load players from DB: {e}")

    def normalize_player(self, name, auto_add=True):
        """
        Maps a player alias to a standard master name.
        If auto_add is True, new players are added to the database.
        """
        if not name:
            return None

        name = name.strip()

        # 1. Exact match check (including aliases)
        if name in self.name_to_id:
            return self.master_players[self.name_to_id[name]]

        # 2. Fuzzy match against all known names/aliases
        if self.name_to_id:
            # Using token_sort_ratio is better for names like "N. Djokovic"
            # vs "Djokovic N."
            match = process.extractOne(
                name, self.name_to_id.keys(), scorer=fuzz.token_sort_ratio
            )
            if match and match[1] >= self.threshold:
                matched_name = match[0]
                player_id = self.name_to_id[matched_name]
                self.logger.info(
                    f"Fuzzy matched '{name}' to "
                    f"'{self.master_players[player_id]}' (score: {match[1]})"
                )
                return self.master_players[player_id]

        # 3. If no match, add to DB as a new player if auto_add is True
        if auto_add:
            return self._add_new_player(name)

        self.logger.warning(f"No match found for player: {name}.")
        return name

    def _add_new_player(self, name):
        """Adds a new player to the database and refreshes memory."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute(
                "INSERT INTO players (standard_name, aliases) VALUES (?, ?)",
                (name, json.dumps([name]))
            )
            player_id = cursor.lastrowid
            conn.commit()
            conn.close()

            # Update memory
            self.master_players[player_id] = name
            self.name_to_id[name] = player_id
            self.logger.info(f"Added new player to database: {name}")
            return name
        except Exception as e:
            self.logger.error(f"Failed to add new player {name}: {e}")
            return name


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Basic test
    engine = NormalizationEngine()
    print(f"Match: {engine.normalize_player('Novak Djokovic')}")

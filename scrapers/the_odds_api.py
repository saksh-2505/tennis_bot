from tennis_bot.scrapers.base_scraper import BaseScraper
import requests
import logging
import os


class TheOddsApiScraper(BaseScraper):
    """
    Scraper for The Odds API (Professional Data Provider).
    Requires an API Key. Provides access to Pinnacle, Betfair, etc.
    """

    BASE_URL = "https://api.the-odds-api.com/v4/sports/tennis_atp/odds/"

    def __init__(self, api_key=None, proxy_url=None):
        super().__init__("TheOddsApi", proxy_url=proxy_url)
        self.api_key = api_key or os.environ.get("THE_ODDS_API_KEY")
        self.logger = logging.getLogger("scraper.TheOddsApi")

    def get_matches(self):
        """
        Fetches upcoming matches and odds from the API.
        """
        if not self.api_key:
            self.logger.error("API Key missing for The Odds API.")
            return []

        params = {
            "apiKey": self.api_key,
            "regions": "us,eu",
            "markets": "h2h",
            "oddsFormat": "decimal"
        }

        try:
            self.logger.info("Fetching odds from The Odds API...")
            response = requests.get(self.BASE_URL, params=params, timeout=10)

            if response.status_code != 200:
                self.logger.error(
                    f"API Error: {response.status_code} - {response.text}"
                )
                return []

            data = response.json()
            matches = []

            for item in data:
                # Map to project schema
                match = {
                    "player_a": item["home_team"],
                    "player_b": item["away_team"],
                    "start_time": item["commence_time"],
                    "tournament": item["sport_title"],
                    "external_id": item["id"],
                    "bookmaker_odds": []
                }

                # Extract odds from different bookmakers
                for bookie in item.get("bookmakers", []):
                    market = next(
                        (m for m in bookie.get("markets", []) if m["key"] == "h2h"),
                        None
                    )
                    if market:
                        home_odd = next(
                            (o["price"] for o in market["outcomes"]
                             if o["name"] == item["home_team"]), 0
                        )
                        away_odd = next(
                            (o["price"] for o in market["outcomes"]
                             if o["name"] == item["away_team"]), 0
                        )

                        match["bookmaker_odds"].append({
                            "bookmaker": bookie["key"],
                            "home_odds": home_odd,
                            "away_odds": away_odd
                        })

                # Also provide a 'default' odds for the discovery job
                if match["bookmaker_odds"]:
                    match["home_odds"] = match["bookmaker_odds"][0]["home_odds"]
                    match["away_odds"] = match["bookmaker_odds"][0]["away_odds"]

                matches.append(match)

            self.logger.info(
                f"Successfully fetched {len(matches)} matches from The Odds API."
            )
            return matches

        except Exception as e:
            self.logger.error(f"The Odds API failed: {e}")
            return []

    def get_odds(self, external_id):
        # API fetches everything in get_matches
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Using a fake key for demo
    scraper = TheOddsApiScraper(api_key="DEMO")
    matches = scraper.get_matches()

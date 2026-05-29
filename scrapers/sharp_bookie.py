from tennis_bot.scrapers.base_scraper import BaseScraper
from tennis_bot.scrapers.flashscore_scraper import FlashscoreScraper
from tennis_bot.scrapers.pinnacle_scraper import PinnacleScraper
from tennis_bot.scrapers.betfair_scraper import BetfairScraper
import logging


class SharpBookieScraper(BaseScraper):
    """
    Factory/Aggregator for Sharp Bookmakers.
    Attempts to get the best baseline prices from Pinnacle, Betfair,
    and Flashscore.
    """

    def __init__(self, proxy_url=None):
        super().__init__("SharpBookie", proxy_url=proxy_url)
        self.logger = logging.getLogger("scraper.SharpBookie")
        self.scrapers = [
            FlashscoreScraper(proxy_url=proxy_url),
            PinnacleScraper(proxy_url=proxy_url),
            BetfairScraper(proxy_url=proxy_url)
        ]

    def get_matches(self):
        """
        Tries all sharp scrapers and merges results.
        Flashscore is used as the primary source due to its reliability.
        """
        all_matches = []
        for scraper in self.scrapers:
            try:
                self.logger.info(
                    f"Trying sharp scraper: {scraper.bookmaker_name}..."
                )
                matches = scraper.get_matches()
                if matches:
                    self.logger.info(
                        f"Success! {scraper.bookmaker_name} returned "
                        f"{len(matches)} matches."
                    )
                    all_matches.extend(matches)
                else:
                    self.logger.warning(
                        f"{scraper.bookmaker_name} returned no matches."
                    )
            except Exception as e:
                self.logger.error(
                    f"Scraper {scraper.bookmaker_name} failed: {e}"
                )

        # In a real app, we'd de-duplicate and merge matches here
        return all_matches

    def get_odds(self, match_id):
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    scraper = SharpBookieScraper()
    matches = scraper.get_matches()
    print(f"\nTotal Sharp Matches Found: {len(matches)}")

from tennis_bot.scrapers.base_scraper import BaseScraper
import asyncio
from playwright.async_api import async_playwright
import logging
import datetime
import nest_asyncio
import re

nest_asyncio.apply()


class ReddyBookScraper(BaseScraper):
    """
    Scraper for ReddyBook (Diamond Exchange Platform) using Playwright.
    Updated for April 2026 UI structure.
    """

    BASE_URL = "https://reddybook.green"

    def __init__(self, proxy_url=None):
        super().__init__("ReddyBook", proxy_url=proxy_url)
        self.logger = logging.getLogger("scraper.ReddyBook")

    async def _get_matches_async(self):
        async with async_playwright() as p:
            self.logger.info("Launching browser...")
            browser = await p.chromium.launch(headless=True)
            u_agent = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent=u_agent
            )
            page = await context.new_page()

            # Navigate directly to Tennis section
            tennis_url = f"{self.BASE_URL}/sports/2"
            self.logger.info(f"Navigating to {tennis_url}...")

            try:
                await page.goto(tennis_url, wait_until="networkidle", timeout=60000)

                # Wait for match rows
                await page.wait_for_selector('.bet-table-row', timeout=20000)

                matches = []
                rows = await page.query_selector_all('.bet-table-row')
                self.logger.info(f"Found {len(rows)} potential match rows.")

                for row in rows:
                    try:
                        # Extract Match Name
                        name_elem = await row.query_selector('.team-name')
                        if not name_elem:
                            continue

                        match_text = await name_elem.inner_text()
                        match_text = match_text.strip()

                        # Handle different formats: "A v B" or "A vs. B"
                        if " v " in match_text.lower():
                            player_a, player_b = re.split(
                                r' [vV] ', match_text, 1
                            )
                        elif " vs. " in match_text.lower():
                            player_a, player_b = re.split(
                                r' [vV][sS]\. ', match_text, 1
                            )
                        else:
                            continue

                        # Extract Odds
                        odds_containers = await row.query_selector_all(
                            '.h-backLay'
                        )

                        home_odds = 0.0
                        away_odds = 0.0

                        if len(odds_containers) >= 2:
                            # Selection 1 (Home)
                            h_selector = '.back .bet-button-price'
                            h_back = await odds_containers[0].query_selector(
                                h_selector
                            )
                            if h_back:
                                h_text = await h_back.inner_text()
                                # Clean up text
                                h_val = h_text.split()[0]
                                try:
                                    home_odds = float(h_val)
                                except Exception:
                                    pass

                            # Selection 2 (Away)
                            a_selector = '.back .bet-button-price'
                            a_back = await odds_containers[-1].query_selector(
                                a_selector
                            )
                            if a_back:
                                a_text = await a_back.inner_text()
                                a_val = a_text.split()[0]
                                try:
                                    away_odds = float(a_val)
                                except Exception:
                                    pass

                        if home_odds > 1.0 or away_odds > 1.0:
                            now_str = datetime.datetime.now().strftime(
                                "%Y-%m-%d %H:%M:%S"
                            )
                            matches.append({
                                "player_a": player_a.strip(),
                                "player_b": player_b.strip(),
                                "start_time": now_str,
                                "tournament": "ReddyBook Tennis",
                                "home_odds": home_odds,
                                "away_odds": away_odds,
                                "bookmaker": self.bookmaker_name,
                                "external_id": f"reddy_{match_text}"
                                    .replace(" ", "_").lower()
                            })
                    except Exception as e:
                        self.logger.debug(f"Error parsing row: {e}")

                await browser.close()
                return matches

            except Exception as e:
                self.logger.error(f"ReddyBook scraping failed: {e}")
                await browser.close()
                return []

    def get_matches(self):
        try:
            return asyncio.run(self._get_matches_async())
        except Exception as e:
            self.logger.error(f"Scraper failed: {e}")
            return []

    def get_odds(self, match_id):
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    scraper = ReddyBookScraper()
    matches = scraper.get_matches()
    print(f"\nTotal Matches Found: {len(matches)}")
    for m in matches[:10]:
        print(
            f"{m['player_a']} vs {m['player_b']} | "
            f"Odds: {m['home_odds']} - {m['away_odds']}"
        )

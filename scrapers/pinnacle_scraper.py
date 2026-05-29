from tennis_bot.scrapers.base_scraper import BaseScraper
import asyncio
from playwright.async_api import async_playwright
import logging
import datetime
import nest_asyncio

nest_asyncio.apply()


class PinnacleScraper(BaseScraper):
    """
    Scraper for Pinnacle to get sharp odds using Playwright.
    Pinnacle is considered a 'Sharp' bookmaker.
    """

    BASE_URL = "https://www.pinnacle.com/en/tennis/matchups/"

    def __init__(self, proxy_url=None):
        super().__init__("Pinnacle", proxy_url=proxy_url)
        self.logger = logging.getLogger("scraper.Pinnacle")

    async def _get_matches_async(self):
        async with async_playwright() as p:
            self.logger.info("Launching browser...")
            browser = await p.chromium.launch(headless=True)
            user_agent = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent=user_agent,
                ignore_https_errors=True
            )
            page = await context.new_page()

            self.logger.info(f"Navigating to {self.BASE_URL}...")
            try:
                # Pinnacle can be slow or have anti-bot
                response = await page.goto(
                    self.BASE_URL, wait_until="networkidle", timeout=60000
                )
                self.logger.info(
                    f"Page loaded with status: "
                    f"{response.status if response else 'N/A'}"
                )

                # Check for common bot detection patterns in title
                title = await page.title()
                self.logger.info(f"Page title: {title}")

                if "Access Denied" in title or "Cloudflare" in title:
                    self.logger.error("Blocked by bot detection.")
                    await page.screenshot(path="pinnacle_blocked.png")
                    await browser.close()
                    return []

                # Wait for any button which usually represents odds
                try:
                    await page.wait_for_selector(
                        'button[class*="style_button__"]', timeout=15000
                    )
                except Exception:
                    self.logger.warning(
                        "Timed out waiting for odds buttons. Taking screenshot."
                    )
                    await page.screenshot(path="pinnacle_failed.png")

                matches = []
                # Find all match rows - trying more generic approach
                # Rows often have a specific structure or common class prefix
                rows = await page.query_selector_all(
                    'div[class*="style_row__"], div[class*="style_matchupMetadata"]'
                )

                self.logger.info(f"Found {len(rows)} potential match rows.")

                for row in rows:
                    try:
                        # Extract Player Names
                        name_elems = await row.query_selector_all(
                            'span[class*="style_participantName__"]'
                        )
                        if len(name_elems) < 2:
                            continue

                        player_a = await name_elems[0].inner_text()
                        player_b = await name_elems[1].inner_text()

                        # Extract Odds (Moneyline)
                        # Usually the first two buttons with numbers
                        odds_buttons = await row.query_selector_all(
                            'button[class*="style_button__"]'
                        )

                        home_odds = 0.0
                        away_odds = 0.0

                        found_odds = []
                        for btn in odds_buttons:
                            text = await btn.inner_text()
                            if text and any(char.isdigit() for char in text):
                                try:
                                    found_odds.append(float(text.strip()))
                                except Exception:
                                    pass

                        if len(found_odds) >= 2:
                            home_odds = found_odds[0]
                            away_odds = found_odds[1]

                        # Pinnacle list doesn't always show full date/time clearly
                        now_str = datetime.datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        )
                        matches.append({
                            "player_a": player_a.strip(),
                            "player_b": player_b.strip(),
                            "start_time": now_str,
                            "tournament": "Pinnacle Tennis",
                            "home_odds": home_odds,
                            "away_odds": away_odds,
                            "bookmaker": self.bookmaker_name,
                            "external_id": f"pinnacle_{player_a}_{player_b}"
                                .replace(" ", "_").lower(),
                            "scraped_at": datetime.datetime.now().isoformat()
                        })
                    except Exception as e:
                        self.logger.debug(f"Error parsing Pinnacle row: {e}")

                await browser.close()
                self.logger.info(
                    f"Successfully scraped {len(matches)} matches from Pinnacle."
                )
                return matches

            except Exception as e:
                self.logger.error(f"Pinnacle navigation failed: {e}")
                await browser.close()
                return []

    def get_matches(self):
        """Synchronous wrapper for async scraper."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                return asyncio.run_coroutine_threadsafe(
                    self._get_matches_async(), loop
                ).result()
            else:
                return asyncio.run(self._get_matches_async())
        except Exception as e:
            self.logger.error(f"Scraper failed: {e}")
            return []

    def get_odds(self, match_id):
        """In this implementation, odds are fetched during get_matches."""
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    scraper = PinnacleScraper()
    matches = scraper.get_matches()
    print(f"\nTotal Matches Found: {len(matches)}")
    for m in matches[:5]:
        print(
            f"{m['player_a']} vs {m['player_b']} | "
            f"Odds: {m['home_odds']} - {m['away_odds']}"
        )

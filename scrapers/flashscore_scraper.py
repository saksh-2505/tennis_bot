from tennis_bot.scrapers.base_scraper import BaseScraper
import asyncio
from playwright.async_api import async_playwright
import logging
import datetime
import nest_asyncio

nest_asyncio.apply()


class FlashscoreScraper(BaseScraper):
    """
    Scraper for Flashscore to get matches and sharp odds using Playwright.
    """

    BASE_URL = "https://www.flashscore.com/tennis/"

    def __init__(self, proxy_url=None):
        super().__init__("Flashscore", proxy_url=proxy_url)
        self.logger = logging.getLogger("scraper.Flashscore")

    async def _get_matches_async(self):
        async with async_playwright() as p:
            self.logger.info("Launching browser...")
            browser = await p.chromium.launch(headless=True)
            user_agent = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
            context = await browser.new_context(user_agent=user_agent)
            page = await context.new_page()

            self.logger.info(f"Navigating to {self.BASE_URL}...")
            await page.goto(self.BASE_URL, wait_until="networkidle")

            # Close cookie consent
            try:
                await page.click("#onetrust-accept-btn-handler", timeout=3000)
                self.logger.info("Accepted cookies.")
            except Exception:
                pass

            # Click ODDS tab to show odds in the list
            try:
                self.logger.info("Clicking ODDS filter...")
                odds_tab = await page.query_selector('[data-analytics-alias="odds"]')
                if odds_tab:
                    await odds_tab.click()
                    await page.wait_for_timeout(3000)
                    self.logger.info("ODDS filter active.")
                else:
                    self.logger.warning("ODDS tab not found.")
            except Exception as e:
                self.logger.error(f"Failed to click ODDS tab: {e}")

            # Wait for matches to load
            try:
                await page.wait_for_selector(".event__match", timeout=10000)
            except Exception:
                self.logger.error("Timed out waiting for .event__match")
                await browser.close()
                return []

            matches = []
            elements = await page.query_selector_all(".headerLeague, .event__match")
            current_tournament = "Unknown Tournament"

            for element in elements:
                try:
                    class_name = await element.get_attribute("class")

                    if "headerLeague" in class_name:
                        title_elem = await element.query_selector(
                            ".headerLeague__title-text"
                        )
                        cat_elem = await element.query_selector(
                            ".headerLeague__category-text"
                        )
                        title = await title_elem.inner_text() if title_elem else ""
                        category = await cat_elem.inner_text() if cat_elem else ""
                        current_tournament = f"{category}: {title}".strip(": ")
                        continue

                    if "event__match" in class_name:
                        home_p = await element.query_selector(
                            ".event__participant--home"
                        )
                        away_p = await element.query_selector(
                            ".event__participant--away"
                        )

                        if not home_p or not away_p:
                            continue

                        home_name = await home_p.inner_text()
                        away_name = await away_p.inner_text()

                        time_elem = await element.query_selector(".event__time")
                        start_time = await time_elem.inner_text() if time_elem else ""

                        h_odds_elem = await element.query_selector(
                            ".event__odd--odd1 span"
                        )
                        a_odds_elem = await element.query_selector(
                            ".event__odd--odd2 span"
                        )

                        home_odds = 0.0
                        away_odds = 0.0

                        if h_odds_elem:
                            try:
                                home_odds = float(await h_odds_elem.inner_text())
                            except Exception:
                                pass

                        if a_odds_elem:
                            try:
                                away_odds = float(await a_odds_elem.inner_text())
                            except Exception:
                                pass

                        matches.append({
                            "player_a": home_name.strip(),
                            "player_b": away_name.strip(),
                            "start_time": start_time.strip(),
                            "tournament": current_tournament,
                            "home_odds": home_odds,
                            "away_odds": away_odds,
                            "external_id": await element.get_attribute("id"),
                            "scraped_at": datetime.datetime.now().isoformat()
                        })
                except Exception as e:
                    self.logger.debug(f"Error parsing element: {e}")

            await browser.close()
            self.logger.info(
                f"Successfully scraped {len(matches)} matches from Flashscore."
            )
            return matches

    def get_matches(self):
        """Synchronous wrapper for async scraper with retries."""
        @self.retry_on_failure(max_retries=3, delay=5)
        def _execute():
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
                raise

        return _execute()

    def get_odds(self, match_id):
        """
        In this implementation, odds are fetched during get_matches.
        We can return a cached value or implement detail page scraping here if needed.
        """
        # For now, we'll assume the orchestrator uses the odds returned by get_matches
        return None


if __name__ == "__main__":
    scraper = FlashscoreScraper()
    matches = scraper.get_matches()
    matches_with_odds = [m for m in matches if m['home_odds'] > 0]
    print(f"\nTotal Matches Found: {len(matches)}")
    print(f"Matches with Odds: {len(matches_with_odds)}")

    print("\nSample Matches with Odds:")
    for m in matches_with_odds[:10]:
        print(
            f"[{m['start_time']}] {m['tournament']} | "
            f"{m['player_a']} vs {m['player_b']} | "
            f"Odds: {m['home_odds']} - {m['away_odds']}"
        )

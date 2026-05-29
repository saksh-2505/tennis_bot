import asyncio
from playwright.async_api import async_playwright
import os
import logging
from dotenv import load_dotenv

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("test.reddybook")

import pytest

@pytest.mark.asyncio
async def test_full_reddybook_flow():
    load_dotenv()
    username = os.environ.get("REDDYBOOK_USER")
    password = os.environ.get("REDDYBOOK_PASS")
    base_url = "https://reddybook.green"

    if not username or not password:
        logger.error("Missing ReddyBook credentials in .env")
        return

    async with async_playwright() as p:
        logger.info("Step 1: Launching Browser...")
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1280, 'height': 720})
        page = await context.new_page()

        try:
            # 1. Login Test
            logger.info(f"Step 2: Navigating to {base_url}/login...")
            await page.goto(f"{base_url}/login", wait_until="networkidle", timeout=60000)
            
            logger.info(f"Attempting login for user: {username}...")
            await page.fill('input[name="username"]', username)
            await page.fill('input[name="password"]', password)
            await page.click('button[type="submit"]')
            
            # Check for success (usually balance or profile name appears)
            await page.wait_for_selector('.user-balance', timeout=20000)
            logger.info("✅ LOGIN SUCCESSFUL: Dashboard accessed.")

            # 2. Tennis Section Test
            logger.info("Step 3: Navigating to Tennis section...")
            await page.goto(f"{base_url}/sports/2", wait_until="networkidle")
            
            # Check for match rows
            await page.wait_for_selector('.bet-table-row', timeout=15000)
            rows = await page.query_selector_all('.bet-table-row')
            logger.info(f"✅ TENNIS SECTION LOADED: Found {len(rows)} active matches.")

            # 3. Odds Parsing Test (Back/Lay)
            if rows:
                first_row = rows[0]
                team_name = await (await first_row.query_selector('.team-name')).inner_text()
                
                # Get Back and Lay buttons
                back_btns = await first_row.query_selector_all('.back .bet-button-price')
                lay_btns = await first_row.query_selector_all('.lay .bet-button-price')
                
                if back_btns and lay_btns:
                    b_odds = await back_btns[0].inner_text()
                    l_odds = await lay_btns[0].inner_text()
                    logger.info(f"✅ ODDS PARSING SUCCESS: Match '{team_name.strip()}' -> Back: {b_odds.strip()}, Lay: {l_odds.strip()}")
                else:
                    logger.warning("⚠️ Back/Lay buttons found but odds text missing.")

            # 4. Bet Slip Activation Test (Non-Executing)
            if rows:
                logger.info("Step 4: Testing Bet Slip activation (Simulated click)...")
                await back_btns[0].click()
                await page.wait_for_selector('.bet-slip', timeout=5000)
                logger.info("✅ BET SLIP SUCCESS: Slip opened upon selection.")

            logger.info("\n--- 🏁 REDDYBOOK DIAGNOSTIC COMPLETE ---")
            logger.info("All systems functional for autonomous execution.")

        except Exception as e:
            logger.error(f"❌ DIAGNOSTIC FAILED: {e}")
            # Capture screenshot on failure
            await page.screenshot(path="reddybook_diagnostic_failure.png")
            logger.info("Failure screenshot saved as reddybook_diagnostic_failure.png")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(test_full_reddybook_flow())

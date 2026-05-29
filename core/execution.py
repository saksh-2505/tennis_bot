import logging
import asyncio
from playwright.async_api import async_playwright
import os
import os.path
import datetime

logger = logging.getLogger("core.execution")

class ExecutionEngine:
    """
    Highly resilient execution engine for ReddyBook.
    Handles dynamic popups, intercepting modals, and provides visual proof.
    """

    def __init__(self):
        self.username = os.environ.get("REDDYBOOK_USER")
        self.password = os.environ.get("REDDYBOOK_PASS")
        self.base_url = "https://reddybook.green"
        self.enabled = bool(self.username and self.password)

    async def _handle_popups(self, page):
        """Identifies and closes known blocking modals/popups."""
        try:
            # 1. Force Change Password or Security Popups
            # We look for close buttons or 'Cancel' on common modals
            close_selectors = [
                '.modal-header .close', 
                'button:has-text("Close")', 
                '.force-change-password-popup .close',
                '.announcement-popup .btn-close'
            ]
            for selector in close_selectors:
                btn = await page.query_selector(selector)
                if btn and await btn.is_visible():
                    logger.info(f"🛡️ Closing popup: {selector}")
                    await btn.click()
                    await page.wait_for_timeout(1000)
        except Exception:
            pass

    async def login_and_prepare_async(self, match_name, selection, odds, stake, confirm=False):
        """
        Navigates to match and prepares bet slip. 
        If confirm=False, it takes a screenshot of the filled slip as proof.
        """
        async with async_playwright() as p:
            logger.info("🚀 Launching Resilient Browser (Headless=True)...")
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={'width': 1280, 'height': 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            )
            page = await context.new_page()

            try:
                # 1. Resilient Login
                logger.info(f"Navigating to {self.base_url}...")
                await page.goto(self.base_url, wait_until="networkidle", timeout=60000)
                
                # Check if already logged in (look for balance)
                if not await page.query_selector('.user-balance'):
                    logger.info("Attempting Login...")
                    # Try to trigger login modal
                    login_btn = await page.query_selector('text=Login')
                    if login_btn: await login_btn.click()
                    
                    # Resilience: Use multiple selector attempts for inputs
                    user_input = await page.wait_for_selector('input[placeholder*="Username"], input[type="text"]', timeout=10000)
                    pass_input = await page.query_selector('input[placeholder*="Password"], input[type="password"]')
                    
                    await user_input.fill(self.username)
                    await pass_input.fill(self.password)
                    
                    submit_btn = await page.query_selector('button:has-text("Login"), .btn-login, input[type="submit"]')
                    await submit_btn.click()
                    
                    # Wait for balance to confirm login
                    await page.wait_for_selector('.user-balance', timeout=20000)
                    logger.info("✅ Login Successful.")

                await self._handle_popups(page)

                # 2. Navigate to Tennis
                logger.info("Navigating to Tennis section...")
                await page.goto(f"{self.base_url}/sports/2", wait_until="networkidle")
                await page.wait_for_selector('.bet-table-row', timeout=15000)

                # 3. Find Match
                logger.info(f"Searching for match: {match_name}")
                match_row = await page.get_by_text(match_name, exact=False).first
                if not match_row:
                    logger.error(f"❌ Match not found: {match_name}")
                    await page.screenshot(path="logs/match_not_found.png")
                    return False
                
                await match_row.click()
                await page.wait_for_selector('.bet-slip, .bet-table-row', timeout=10000)

                # 4. Interact with Bet Slip
                logger.info(f"Opening Bet Slip for selection {selection}...")
                # Selection 1 is usually the first Back button, 2 is the second
                back_btns = await page.query_selector_all('.back')
                idx = 0 if selection == '1' else 1
                if len(back_btns) > idx:
                    await back_btns[idx].click()
                else:
                    logger.error("❌ Back buttons not found.")
                    return False

                # 5. Fill Stake
                stake_input = await page.wait_for_selector('.bet-input, input[name="stake"]', timeout=5000)
                await stake_input.fill(str(stake))
                logger.info(f"✅ Bet slip prepared with stake: {stake}")

                # 6. Visual Proof / Confirmation
                if not confirm:
                    proof_path = f"logs/proof_{datetime.datetime.now().strftime('%H%M%S')}.png"
                    await page.screenshot(path=proof_path, full_page=False)
                    logger.info(f"📸 GHOST EXECUTION PROOF SAVED: {proof_path}")
                    return True
                else:
                    # REAL EXECUTION
                    confirm_btn = await page.query_selector('.btn-place-bet, button:has-text("Place Bet")')
                    await confirm_btn.click()
                    await page.wait_for_selector('.bet-success-msg', timeout=10000)
                    logger.info("💰 REAL BET PLACED SUCCESSFULLY.")
                    return True

            except Exception as e:
                logger.error(f"❌ Execution Failure: {e}")
                await page.screenshot(path="logs/execution_error.png")
                return False
            finally:
                await browser.close()

    def execute_with_proof(self, match_name, selection, odds, stake):
        """Runs the loop in simulation mode but on the actual UI for visual verification."""
        try:
            return asyncio.run(self.login_and_prepare_async(match_name, selection, odds, stake, confirm=False))
        except Exception as e:
            logger.error(f"Async Wrapper Error: {e}")
            return False

if __name__ == "__main__":
    # Test execution
    logging.basicConfig(level=logging.INFO)
    engine = ExecutionEngine()
    # engine.place_bet("Novak Djokovic v Carlos Alcaraz", "1", 1.85, 100)

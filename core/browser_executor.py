import asyncio
import os
import logging
from browser_use import Agent
from langchain_openai import ChatOpenAI
from tennis_bot.core.execution import ExecutionEngine

logger = logging.getLogger("core.browser_executor")

class BrowserExecutionEngine(ExecutionEngine):
    """
    Advanced Execution Engine using browser-use (LLM Agent) for maximum reliability.
    Ideal for navigating complex, changing UIs like ReddyBook.
    """

    def __init__(self):
        super().__init__()
        # Ensure OPENAI_API_KEY is set in environment for this to work
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.warning("⚠️ OPENAI_API_KEY not found. BrowserExecutionEngine will fail.")
        
        self.llm = ChatOpenAI(model="gpt-4o")

    async def place_autonomous_bet_async(self, match_name, selection, odds, stake, confirm=False):
        """
        Uses an LLM agent to handle the entire betting flow:
        Login -> Navigation -> Finding Match -> Verifying Odds -> Placing Bet.
        """
        if not self.enabled:
            logger.error("Execution disabled (missing credentials).")
            return False

        mode_str = "PLACE a real bet" if confirm else "PREPARE a bet slip (simulated)"
        
        task = (
            f"Go to {self.base_url}. "
            f"Login using username '{self.username}' and password '{self.password}'. "
            f"Handle any security or announcement popups if they appear. "
            f"Navigate to the Tennis section. "
            f"Find the match '{match_name}'. "
            f"If the match is found, click it to open the market. "
            f"Find the 'Match Winner' market. "
            f"Look for selection '{selection}' (1 for first player, 2 for second). "
            f"Verify the 'Back' odds are close to {odds}. "
            f"Click the 'Back' button for that selection to open the bet slip. "
            f"Enter the stake '{stake}' into the amount input. "
        )

        if confirm:
            task += "Click the 'Place Bet' or 'Confirm' button to finish."
        else:
            task += "Take a screenshot of the filled bet slip and stop."

        logger.info(f"🤖 Starting Agentic Betting Flow: {match_name} ({selection}) @ {odds}")
        
        try:
            agent = Agent(
                task=task,
                llm=self.llm,
            )
            result = await agent.run()
            
            # browser-use returns a result object. We can check if it succeeded.
            # Usually, if it finishes without error and the last step was successful.
            logger.info(f"✅ Agent Task Completed: {result}")
            return True
        except Exception as e:
            logger.error(f"❌ Agentic Betting Failed: {e}")
            return False

    def place_bet(self, match_name, selection, odds, stake, confirm=False):
        """Synchronous wrapper for orchestrator."""
        try:
            return asyncio.run(self.place_autonomous_bet_async(match_name, selection, odds, stake, confirm))
        except Exception as e:
            logger.error(f"BrowserExecutor Wrapper Error: {e}")
            return False

if __name__ == "__main__":
    # Example usage
    # engine = BrowserExecutionEngine()
    # engine.place_bet("Novak Djokovic v Carlos Alcaraz", "1", 1.85, 100, confirm=False)
    pass

from abc import ABC, abstractmethod
from tennis_bot.core.session_manager import SessionManager
import logging


class BaseScraper(ABC):
    """
    Abstract base class for all bookmaker scrapers.
    """

    def __init__(self, bookmaker_name, proxy_url=None):
        self.bookmaker_name = bookmaker_name
        self.session_manager = SessionManager(proxy_url=proxy_url)
        self.logger = logging.getLogger(f"scraper.{bookmaker_name}")
        self.session = self.session_manager.get_session()

    def random_sleep(self, min_sec=2, max_sec=5):
        """Adds random delay to mimic human behavior."""
        import time
        import random
        sleep_time = random.uniform(min_sec, max_sec)
        self.logger.debug(f"Sleeping for {sleep_time:.2f}s")
        time.sleep(sleep_time)

    async def async_random_sleep(self, min_sec=2, max_sec=5):
        """Async version of random_sleep."""
        import asyncio
        import random
        sleep_time = random.uniform(min_sec, max_sec)
        await asyncio.sleep(sleep_time)

    def retry_on_failure(self, max_retries=3, delay=5):
        """Decorator for retrying fragile scraping methods."""
        def decorator(func):
            import functools
            import asyncio
            if asyncio.iscoroutinefunction(func):
                @functools.wraps(func)
                async def wrapper(*args, **kwargs):
                    for i in range(max_retries):
                        try:
                            return await func(*args, **kwargs)
                        except Exception as e:
                            self.logger.warning(f"Attempt {i+1} failed for {func.__name__}: {e}")
                            if i < max_retries - 1:
                                await asyncio.sleep(delay * (i + 1))
                            else:
                                raise
                return wrapper
            else:
                @functools.wraps(func)
                def wrapper(*args, **kwargs):
                    for i in range(max_retries):
                        try:
                            return func(*args, **kwargs)
                        except Exception as e:
                            self.logger.warning(f"Attempt {i+1} failed for {func.__name__}: {e}")
                            if i < max_retries - 1:
                                import time
                                time.sleep(delay * (i + 1))
                            else:
                                raise
                return wrapper
        return decorator

    @abstractmethod
    def get_matches(self):
        """
        Fetches upcoming matches from the bookmaker.
        Should return a list of match dictionaries.
        """
        pass

    @abstractmethod
    def get_odds(self, match_id):
        """
        Fetches current odds for a specific match.
        Should return a dictionary of odds.
        """
        pass

    def refresh_session(self):
        """
        Rotates the session to maintain stealth.
        """
        self.session = self.session_manager.get_session()
        self.logger.info("Session refreshed/rotated.")

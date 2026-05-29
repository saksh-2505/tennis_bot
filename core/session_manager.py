import random
from curl_cffi import requests


class SessionManager:
    """
    Manages HTTP sessions with rotated User-Agents and JA3 fingerprints.
    """

    USER_AGENTS = [
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        ),
        (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
        ),
        (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/119.0.0.0 Safari/537.36"
        ),
        (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) "
            "Gecko/20100101 Firefox/119.0"
        ),
    ]

    IMPERSONATE_BROWERS = ["chrome110", "chrome116", "chrome119", "safari15_5"]

    def __init__(self, proxy_url=None):
        self.proxy_url = proxy_url

    def get_session(self):
        """
        Creates and returns a curl_cffi session with a random
        browser impersonation.
        """
        impersonate = random.choice(self.IMPERSONATE_BROWERS)
        user_agent = random.choice(self.USER_AGENTS)

        session = requests.Session(impersonate=impersonate)
        session.headers.update({
            "User-Agent": user_agent,
            "Accept-Language": "en-US,en;q=0.9",
        })

        if self.proxy_url:
            session.proxies = {
                "http": self.proxy_url,
                "https": self.proxy_url
            }

        return session


if __name__ == "__main__":
    # Quick test
    manager = SessionManager()
    session = manager.get_session()
    resp = session.get("https://httpbin.org/headers")
    print(resp.json())

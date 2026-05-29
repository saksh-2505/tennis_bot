import logging
import requests
import os

logger = logging.getLogger("core.alerts")


class TelegramAlerter:
    """
    Sends betting alerts to a Telegram chat.
    """

    def __init__(self, token=None, chat_id=None):
        self.token = token or os.environ.get("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID")
        self.enabled = bool(self.token and self.chat_id)

        if not self.enabled:
            logger.warning(
                "Telegram alerts disabled: TELEGRAM_BOT_TOKEN or "
                "TELEGRAM_CHAT_ID missing."
            )

    def send_alert(
        self, match_name, bookmaker, selection, odds, ev, method, true_prob, stake="N/A"
    ):
        """Sends a formatted message to Telegram."""
        if not self.enabled:
            return False

        emoji = "🔥" if ev > 0.05 else "✅"
        message = (
            f"{emoji} **Value Opportunity Found** {emoji}\n\n"
            f"🎾 **Match:** {match_name}\n"
            f"🏛 **Bookmaker:** {bookmaker}\n"
            f"🎯 **Selection:** {selection}\n"
            f"💰 **Odds:** {odds}\n"
            f"📊 **Recommended Stake:** {stake}\n"
            f"📈 **Expected Value:** {ev:.2%}\n"
            f"🧠 **Method:** {method}\n"
            f"📊 **True Win Prob:** {true_prob:.2%}\n"
        )

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }

        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            logger.info(f"Telegram alert sent for {match_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")
            return False


if __name__ == "__main__":
    # Test alert
    alerter = TelegramAlerter(token="DUMMY", chat_id="DUMMY")
    alerter.send_alert(
        "Nadal vs Alcaraz", "Bet365", "Selection 1", 2.10, 0.07, "ML", 0.51
    )

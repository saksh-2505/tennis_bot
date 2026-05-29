import sys
from tennis_bot.core.orchestrator import Orchestrator


# Add project root to sys.path
PROJECT_ROOT = "/home/matrix/Desktop/brain"
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)


def sync_now():
    print("🚀 Starting One-Time Data Sync...")
    orch = Orchestrator()

    print("📡 Discovering matches and odds...")
    orch.discovery_job()

    print("📊 Updating live odds...")
    orch.odds_update_job()

    print("🧠 Running value detection...")
    orch.value_detection_job()

    print("✅ Sync Complete!")


if __name__ == "__main__":
    sync_now()


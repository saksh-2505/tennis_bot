import os
import logging
import sys
import time
from datetime import datetime
from tennis_bot.core.orchestrator import Orchestrator

# Force LIVE mode
os.environ["SIMULATION_MODE"] = "False"

# Configure logging to be more verbose for live tracking
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/live_betting.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("live_runner")

def main():
    print("🚀 STARTING TENNIS BOT IN LIVE AUTONOMOUS MODE")
    print("⚠️ WARNING: Real money will be used for betting if credentials are correct.")
    
    try:
        orchestrator = Orchestrator()
        
        # Live Performance Tweaks
        orchestrator.bet_threshold = 0.05 # 5% EV for live entries
        orchestrator.max_bets_per_match = 3
        
        # Custom scheduler for maximum responsiveness
        orchestrator.scheduler.remove_all_jobs()
        
        # 1. High frequency monitoring for value
        orchestrator.scheduler.add_job(orchestrator.live_monitoring_job, 'interval', minutes=2, id='live_monitor')
        
        # 2. Match discovery
        orchestrator.scheduler.add_job(orchestrator.discovery_job, 'interval', hours=1, id='discovery')
        
        # 3. Result resolution
        orchestrator.scheduler.add_job(orchestrator.resolver.resolve_pending_bets, 'interval', minutes=30, id='resolution')
        
        # 4. Daily maintenance
        orchestrator.scheduler.add_job(orchestrator.maintenance_job, 'cron', hour=4, id='maintenance')

        # Record start in session log
        with open("logs/session-log.md", "a") as f:
            f.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}: Live Autonomous Betting Started.\n")

        orchestrator.start()
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"BOT CRASHED: {e}")
        # Capture trace for debugging
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)

if __name__ == "__main__":
    main()

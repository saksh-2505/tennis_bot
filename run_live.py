import os
import logging
from tennis_bot.core.orchestrator import Orchestrator

# Force LIVE mode
os.environ["SIMULATION_MODE"] = "False"

# Configure logging to be more verbose for live tracking
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("logs/live_betting.log"),
        logging.StreamHandler()
    ]
)

if __name__ == "__main__":
    print("🚀 STARTING TENNIS BOT IN LIVE AUTONOMOUS MODE")
    print("⚠️ WARNING: Real money will be used for betting if credentials are correct.")
    
    orchestrator = Orchestrator()
    
    # Increase frequency for "continuous" feel
    # We can override the scheduler jobs here or just modify the class defaults
    orchestrator.bet_threshold = 0.05 # Slightly lower threshold for live opportunities
    
    # Re-schedule live monitoring to every 1 minute
    orchestrator.scheduler.remove_all_jobs()
    orchestrator.scheduler.add_job(orchestrator.live_monitoring_job, 'interval', minutes=1)
    orchestrator.scheduler.add_job(orchestrator.discovery_job, 'interval', hours=1)
    orchestrator.scheduler.add_job(orchestrator.resolver.resolve_pending_bets, 'interval', minutes=30)
    
    orchestrator.start()

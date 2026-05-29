from apscheduler.schedulers.blocking import BlockingScheduler
from tennis_bot.database.db_manager import DatabaseManager
from tennis_bot.scrapers.reddybook import ReddyBookScraper
from tennis_bot.scrapers.the_odds_api import TheOddsApiScraper
from tennis_bot.scrapers.flashscore_scraper import FlashscoreScraper
from tennis_bot.models.value_model import ValueModel
from tennis_bot.core.normalization import NormalizationEngine
from tennis_bot.core.alerts import TelegramAlerter
from tennis_bot.core.execution import ExecutionEngine
from tennis_bot.core.simulator import BettingSimulator
from tennis_bot.core.resolver import ResultResolver
from tennis_bot.models.data_loader import TennisDataLoader
import logging
import datetime
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("core.orchestrator")


from tennis_bot.core.browser_executor import BrowserExecutionEngine
import time

class Orchestrator:
    """
    Orchestrates automated daily scraping jobs and data processing.
    Now enhanced for continuous live monitoring and autonomous betting.
    """

    def __init__(self):
        self.db = DatabaseManager()
        self.normalization = NormalizationEngine()
        self.value_model = ValueModel(db_manager=self.db)
        self.alerter = TelegramAlerter()
        
        # Use Smart Browser Execution for reliability
        self.execution = BrowserExecutionEngine()
        
        self.simulator = BettingSimulator(db_manager=self.db, initial_balance=10000.0)
        self.resolver = ResultResolver(db_manager=self.db)
        self.scheduler = BlockingScheduler()
        self.loader = TennisDataLoader()
        
        self.bet_threshold = 0.07 # 7% EV required for autonomous bet
        self.max_bets_per_match = 3 # Allow scaling into a position
        self.is_simulation = os.environ.get("SIMULATION_MODE", "True").lower() == "true"

        # Initialize scrapers
        self.scrapers = [
            FlashscoreScraper(),
            ReddyBookScraper()
        ]

    def live_monitoring_job(self):
        """
        Continuously polls for live odds on matches we've identified as potentially valuable.
        """
        logger.info("📡 Starting Continuous Live Monitoring Loop...")
        upcoming = self.db.get_upcoming_matches()
        
        # We only monitor matches starting soon (e.g., next 2 hours) or already started
        now = datetime.datetime.now()
        to_monitor = []
        for match in upcoming:
            start = datetime.datetime.strptime(match['start_time'], "%Y-%m-%d %H:%M:%S")
            if (start - now).total_seconds() < 7200: # 2 hours
                to_monitor.append(match)

        for match in to_monitor:
            logger.info(f"🔍 Monitoring: {match['player_a']} vs {match['player_b']}")
            
            # Use ReddyBookScraper to get FRESH live odds
            rb_scraper = next((s for s in self.scrapers if isinstance(s, ReddyBookScraper)), None)
            if rb_scraper:
                live_odds = asyncio.run(rb_scraper.get_live_odds_async(match['player_a'], match['player_b']))
                if live_odds and live_odds['home'] > 1.0:
                    # Insert fresh odds into DB
                    self.db.insert_odds({
                        'player_a': match['player_a'],
                        'player_b': match['player_b'],
                        'start_time': match['start_time'],
                        'bookmaker': 'ReddyBook',
                        'market': '1x2',
                        'home_odds': live_odds['home'],
                        'away_odds': live_odds['away']
                    })
                    
                    # Immediate Value Detection
                    self.process_value_for_match(match, [{
                        'bookmaker': 'ReddyBook',
                        'home': live_odds['home'],
                        'away': live_odds['away']
                    }])

    def process_value_for_match(self, match, odds_list):
        """Analyze a specific match and execute bets if value is found."""
        opps = self.value_model.analyze_match(
            odds_list,
            player_a=match['player_a'],
            player_b=match['player_b'],
            surface=match.get('tournament_surface', 'Hard'),
            match_id=match['id']
        )
        
        for opp in opps:
            if opp['ev'] >= self.bet_threshold:
                # Check how many bets we've already placed on this match/selection
                active_bets = self.db.get_active_trades(match['id'])
                matching_bets = [b for b in active_bets if b['selection'] == opp['selection']]
                
                if len(matching_bets) >= self.max_bets_per_match:
                    logger.info(f"⏸️ Max bets reached for {match['player_a']} selection {opp['selection']}. Skipping.")
                    continue

                logger.info(f"🔥 VALUE DETECTED: {opp['ev']:.2%} EV on {match['player_a']} vs {match['player_b']}")
                
                # 1. Alert
                self.alerter.send_alert(
                    match_name=f"{match['player_a']} vs {match['player_b']}",
                    bookmaker=opp['bookmaker'],
                    selection=opp['selection'],
                    odds=opp['odds'],
                    ev=opp['ev'],
                    method="Live Continuous Monitor",
                    true_prob=opp['true_prob'],
                    stake=opp.get('stake', '100')
                )

                # 2. Execute
                if self.is_simulation:
                    self.simulator.record_simulated_bet(
                        match_id=match['id'],
                        match_name=f"{match['player_a']} vs {match['player_b']}",
                        bookmaker=opp['bookmaker'],
                        selection=opp['selection'],
                        side='back',
                        odds=opp['odds'],
                        ev=opp['ev'],
                        stake_pct='100'
                    )
                else:
                    # REAL AUTONOMOUS BETTING
                    logger.info("💰 PLACING REAL AUTONOMOUS BET...")
                    success = self.execution.place_bet(
                        match_name=f"{match['player_a']} v {match['player_b']}",
                        selection=opp['selection'],
                        odds=opp['odds'],
                        stake=100, # Base stake
                        confirm=True
                    )
                    if success:
                        self.db.insert_placed_bet(
                            match_id=match['id'],
                            bookmaker=opp['bookmaker'],
                            selection=opp['selection'],
                            odds=opp['odds'],
                            stake=100,
                            ev=opp['ev'],
                            bet_type='real'
                        )

    def value_detection_job(self):
        """
        Original batch job, now delegates to process_value_for_match.
        """
        logger.info("Starting Batch Value Detection Job...")
        upcoming_matches = self.db.get_upcoming_matches()

        for match in upcoming_matches:
            conn = self.db.get_connection()
            query = "SELECT bookmaker, home_odds, away_odds FROM odds_history WHERE match_id = ? AND timestamp > datetime('now', '-24 hours')"
            cursor = conn.execute(query, (match['id'],))
            all_odds = cursor.fetchall()
            conn.close()

            if all_odds:
                odds_list = [{'bookmaker': s['bookmaker'], 'home': s['home_odds'], 'away': s['away_odds']} for s in all_odds]
                self.process_value_for_match(match, odds_list)

    def start(self):
        """Starts the scheduler for daily/batch execution and live monitoring."""
        # Initial run
        self.discovery_job()
        self.value_detection_job()

        # Continuous Monitoring: Every 5 minutes for upcoming matches
        self.scheduler.add_job(self.live_monitoring_job, 'interval', minutes=5)
        
        # Discovery: Every 2 hours
        self.scheduler.add_job(self.discovery_job, 'interval', hours=2)
        
        # Maintenance and Reports
        self.scheduler.add_job(self.resolver.resolve_pending_bets, 'interval', hours=1)
        self.scheduler.add_job(self.report_job, 'cron', hour=23)
        self.scheduler.add_job(self.maintenance_job, 'interval', days=1)

        mode = "SIMULATION" if self.is_simulation else "LIVE"
        logger.info(f"Orchestrator started in {mode} Mode. Live loop active every 5m.")
        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            pass


if __name__ == "__main__":
    orchestrator = Orchestrator()
    orchestrator.start()

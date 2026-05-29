from apscheduler.schedulers.blocking import BlockingScheduler
from tennis_bot.database.db_manager import DatabaseManager
from tennis_bot.scrapers.reddybook import ReddyBookScraper
from tennis_bot.scrapers.pinnacle_scraper import PinnacleScraper
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
            ReddyBookScraper(),
            PinnacleScraper()
        ]

    def live_monitoring_job(self):
        """
        Continuously polls for live odds on matches starting soon.
        """
        logger.info("📡 Starting Continuous Live Monitoring Loop...")
        try:
            upcoming = self.db.get_upcoming_matches()
            now = datetime.datetime.now()
            
            # Monitor matches starting in the next 3 hours or already live
            to_monitor = [
                m for m in upcoming 
                if (datetime.datetime.strptime(m['start_time'], "%Y-%m-%d %H:%M:%S") - now).total_seconds() < 10800
            ]

            if not to_monitor:
                logger.info("No active or upcoming matches to monitor right now.")
                return

            # Get fresh data from ALL scrapers to have a complete market picture
            for scraper in self.scrapers:
                try:
                    logger.info(f"Polling {scraper.bookmaker_name} for fresh live odds...")
                    matches = scraper.get_matches()
                    for m in matches:
                        # Normalize and Update DB
                        m['player_a'] = self.normalization.normalize_player(m['player_a'])
                        m['player_b'] = self.normalization.normalize_player(m['player_b'])
                        
                        self.db.insert_match(m)
                        if m.get('home_odds') and m.get('away_odds'):
                            self.db.insert_odds({
                                'player_a': m['player_a'],
                                'player_b': m['player_b'],
                                'start_time': m['start_time'],
                                'bookmaker': scraper.bookmaker_name,
                                'market': '1x2',
                                'home_odds': m['home_odds'],
                                'away_odds': m['away_odds']
                            })
                except Exception as e:
                    logger.error(f"Live poll failed for {scraper.bookmaker_name}: {e}")

            # Re-check value for monitored matches
            for match in to_monitor:
                self.value_detection_job_for_single_match(match)

        except Exception as e:
            logger.error(f"Critical error in live monitoring loop: {e}")

    def value_detection_job_for_single_match(self, match):
        """Analyze a specific match with the latest data from all bookmakers."""
        conn = self.db.get_connection()
        # Get latest odds from all sources for this match in last hour
        query = """
            SELECT bookmaker, home_odds, away_odds 
            FROM odds_history 
            WHERE match_id = ? 
            AND timestamp > datetime('now', '-1 hour')
        """
        cursor = conn.execute(query, (match['id'],))
        all_odds = cursor.fetchall()
        conn.close()

        if all_odds:
            odds_list = [{'bookmaker': s['bookmaker'], 'home': s['home_odds'], 'away': s['away_odds']} for s in all_odds]
            self.process_value_for_match(match, odds_list)

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
        
        # Notify Telegram of restart
        self.alerter.send_status(
            f"Orchestrator initialized in **{mode}** mode.\n"
            f"Threshold: {self.bet_threshold:.1%}\n"
            f"Scrapers Active: {', '.join([s.bookmaker_name for s in self.scrapers])}",
            title="🚀 **Tennis Bot Started**"
        )
        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            pass


if __name__ == "__main__":
    orchestrator = Orchestrator()
    orchestrator.start()

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


class Orchestrator:
    """
    Orchestrates automated daily scraping jobs and data processing.
    """

    def __init__(self):
        self.db = DatabaseManager()
        self.normalization = NormalizationEngine()
        self.value_model = ValueModel(db_manager=self.db)
        self.alerter = TelegramAlerter()
        self.execution = ExecutionEngine()
        self.simulator = BettingSimulator(db_manager=self.db, initial_balance=10000.0)
        self.resolver = ResultResolver(db_manager=self.db)
        self.scheduler = BlockingScheduler()
        self.loader = TennisDataLoader()
        
        self.bet_threshold = 0.07 # 7% EV required for autonomous bet
        self.is_simulation = os.environ.get("SIMULATION_MODE", "True").lower() == "true"

        # Initialize scrapers
        self.scrapers = [
            FlashscoreScraper(),
            ReddyBookScraper()
        ]

        # Optional professional API
        if os.environ.get("THE_ODDS_API_KEY"):
            self.scrapers.append(TheOddsApiScraper())

    def discovery_job(self):
        """
        Discovers upcoming matches and populates the database.
        """
        logger.info("Starting Discovery Job...")
        for scraper in self.scrapers:
            try:
                matches = scraper.get_matches()
                for match in matches:
                    # Normalize player names
                    match['player_a'] = self.normalization.normalize_player(
                        match['player_a']
                    )
                    match['player_b'] = self.normalization.normalize_player(
                        match['player_b']
                    )

                    # Insert match metadata
                    self.db.insert_match(match)

                    # Insert odds if provided
                    if match.get('home_odds') and match.get('away_odds'):
                        self.db.insert_odds({
                            'player_a': match['player_a'],
                            'player_b': match['player_b'],
                            'start_time': match['start_time'],
                            'bookmaker': scraper.bookmaker_name,
                            'market': '1x2',
                            'home_odds': match['home_odds'],
                            'away_odds': match['away_odds']
                        })
            except Exception as e:
                logger.error(f"Discovery failed for {scraper.bookmaker_name}: {e}")
        logger.info("Discovery Job completed.")

    def maintenance_job(self):
        """
        Updates historical data and Elo ratings to keep the ML model fresh.
        """
        logger.info("Starting Maintenance Job (Updating Elo State)...")
        # Download latest matches for current year
        current_year = datetime.datetime.now().year
        df = self.loader.load_data(current_year, current_year)

        if not df.empty:
            # Process matches to update ratings
            self.value_model.tracker.process_matches(df)
            self.value_model.tracker.save_state()
            logger.info("Elo state updated with latest results.")
        else:
            logger.warning("No new match data found for maintenance.")

    def value_detection_job(self):
        """
        Uses predictive models to find EV+ opportunities against market odds.
        """
        logger.info("Starting Value Detection Job...")
        upcoming_matches = self.db.get_upcoming_matches()

        for match in upcoming_matches:
            # 1. Get latest odds for this match from DB
            conn = self.db.get_connection()
            query = """
                SELECT bookmaker, home_odds, away_odds
                FROM odds_history
                WHERE match_id = ?
                AND timestamp > datetime('now', '-24 hours')
            """
            cursor = conn.execute(query, (match['id'],))
            all_odds = cursor.fetchall()
            conn.close()

            if not all_odds:
                continue

            # 2. Extract soft odds for analysis
            soft_data_list = [
                {
                    'bookmaker': s['bookmaker'],
                    'home': s['home_odds'],
                    'away': s['away_odds']
                } for s in all_odds
            ]

            # 3. Analyze using predictive ML model
            opps = self.value_model.analyze_match(
                soft_data_list,
                player_a=match['player_a'],
                player_b=match['player_b'],
                surface=match.get('tournament_surface', 'Hard'),
                match_id=match['id']
            )
            for opp in opps:
                logger.info(
                    f"🔥 VALUE FOUND: {match['player_a']} vs "
                    f"{match['player_b']} | {opp['bookmaker']} | "
                    f"{opp['side'].upper()} | EV: {opp['ev']:.2%}"
                )

                # 1. Trigger Telegram Alert
                self.alerter.send_alert(
                    match_name=f"{match['player_a']} vs {match['player_b']}",
                    bookmaker=opp['bookmaker'],
                    selection=opp['selection'],
                    odds=opp['odds'],
                    ev=opp['ev'],
                    method=opp['method'],
                    true_prob=opp['true_prob'],
                    stake=opp.get('stake', 'N/A')
                )

                # 2. Autonomous Action (Real or Simulated)
                if self.is_simulation:
                    # SIMULATION MODE: Use the exchange simulator to record trades
                    self.simulator.record_simulated_bet(
                        match_id=match['id'],
                        match_name=f"{match['player_a']} vs {match['player_b']}",
                        bookmaker=opp['bookmaker'],
                        selection=opp['selection'],
                        side=opp.get('side', 'back'),
                        odds=opp['odds'],
                        ev=opp['ev'],
                        stake_pct=opp.get('stake', '2.0%')
                    )
                else:
                    # LIVE MODE: Automated Execution with Back/Lay
                    if opp['bookmaker'] == 'ReddyBook' and opp['ev'] >= self.bet_threshold:
                        # Execution engine would need to be updated for 'side' (Back/Lay)
                        # Currently placing fixed units for demo
                        base_stake = 100 
                        logger.info(f"🤖 AUTONOMOUS EXECUTION: Placing {base_stake} units on {match['player_a']} ({opp['side'].upper()})")
                        
                        # success = self.execution.place_bet(...)
                        # if success: self.db.insert_placed_bet(...)
                        pass
        logger.info("Value Detection Job completed.")

    def report_job(self):
        """Generates and sends a performance report."""
        if self.is_simulation:
            report = self.simulator.generate_report()
            logger.info(report)
            # Send to Telegram
            self.alerter.send_alert(
                match_name="📊 DAILY SIMULATION REPORT",
                bookmaker="Simulator",
                selection="N/A",
                odds=0.0,
                ev=0.0,
                method="Performance Analysis",
                true_prob=0.0,
                stake=f"Balance: ${self.simulator.get_current_balance():.2f}"
            )

    def start(self):
        """Starts the scheduler for daily/batch execution."""
        # Initial run
        self.discovery_job()
        self.value_detection_job()
        self.resolver.resolve_pending_bets()

        # Schedule jobs for daily/batch frequency
        # Discovery and Analysis every 6 hours (4 times a day)
        self.scheduler.add_job(self.discovery_job, 'interval', hours=6)
        self.scheduler.add_job(self.value_detection_job, 'interval', hours=6)
        
        # Resolve pending bets every 12 hours
        self.scheduler.add_job(self.resolver.resolve_pending_bets, 'interval', hours=12)
        
        # Daily report at 11 PM
        self.scheduler.add_job(self.report_job, 'cron', hour=23)
        
        # Maintenance once a day
        self.scheduler.add_job(self.maintenance_job, 'interval', days=1)

        mode = "SIMULATION" if self.is_simulation else "LIVE"
        logger.info(f"Orchestrator started in {mode} Mode. Press Ctrl+C to exit.")
        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            pass


if __name__ == "__main__":
    orchestrator = Orchestrator()
    orchestrator.start()

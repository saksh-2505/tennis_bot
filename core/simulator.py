import logging
import os
import uuid

class BettingSimulator:
    """
    Advanced Exchange Simulator supporting Back, Lay, and Profit Locking.
    Initial Balance: $10,000
    Commission: 2% on net market profit.
    """

    def __init__(self, db_manager, initial_balance=10000.0, commission=0.02):
        self.db = db_manager
        self.logger = logging.getLogger("core.simulator")
        self.initial_balance = initial_balance
        self.commission = commission
        
    def get_current_balance(self):
        stats = self.db.get_simulator_stats()
        total_pnl = stats.get('total_pnl') or 0.0
        return self.initial_balance + total_pnl

    def get_net_exposure(self, match_id):
        """Calculates the PnL for both outcomes based on active bets."""
        trades = self.db.get_active_trades(match_id)
        # Outcome 1: Player A Wins, Outcome 2: Player B Wins
        pnl_a = 0.0
        pnl_b = 0.0

        for t in trades:
            odds = float(t['odds_taken'])
            stake = float(t['amount_wagered'])
            selection = t['selection']
            side = t['bet_side']

            if side == 'back':
                if selection == '1': # Back A
                    pnl_a += stake * (odds - 1)
                    pnl_b -= stake
                else: # Back B
                    pnl_a -= stake
                    pnl_b += stake * (odds - 1)
            else: # lay
                if selection == '1': # Lay A
                    pnl_a -= stake * (odds - 1)
                    pnl_b += stake
                else: # Lay B
                    pnl_a += stake
                    pnl_b -= stake * (odds - 1)

        return pnl_a, pnl_b

    def record_simulated_bet(self, match_id, match_name, bookmaker, selection, odds, side, ev, stake_pct):
        """Records an exchange trade."""
        current_balance = self.get_current_balance()
        
        # Kelly Stake calculation
        try:
            pct = float(stake_pct.strip('%')) / 100
        except:
            pct = 0.02
            
        amount_wagered = round(current_balance * pct, 2)
        
        # Check if we can "Green Up" (Hedge)
        # Logic: If we already have a Back on A, and now we want to Lay A at lower odds.
        pnl_a, pnl_b = self.get_net_exposure(match_id)
        
        # Simple auto-hedge: if pnl_a > 0 and pnl_b < 0, and current odds allow a green book
        # (This would be implemented in the Orchestrator's trade manager)

        success = self.db.insert_placed_bet(
            match_id=match_id,
            bookmaker=bookmaker,
            selection=selection,
            side=side,
            odds=odds,
            stake=amount_wagered,
            ev=ev,
            bet_type='simulated',
            trade_group_id=str(uuid.uuid4())[:8]
        )

        if success:
            self.logger.info(
                f"📊 EXCHANGE {'BACK' if side=='back' else 'LAY'} RECORDED: {match_name} | "
                f"Odds: {odds} | Stake: ${amount_wagered} | EV: {ev:.2%}"
            )
            return True
        return False

    def generate_report(self):
        stats = self.db.get_simulator_stats()
        total_pnl = stats.get('total_pnl') or 0.0
        total_wagered = stats.get('total_wagered') or 0.0
        roi = (total_pnl / total_wagered * 100) if total_wagered > 0 else 0.0
        
        return (
            f"\n--- 📈 Exchange Simulator Report ---\n"
            f"  Balance: ${self.initial_balance + total_pnl:,.2f}\n"
            f"  Net PnL: ${total_pnl:,.2f} | ROI: {roi:.2f}%\n"
            f"  Total Trades: {stats.get('total_bets')}\n"
            f"------------------------------------\n"
        )

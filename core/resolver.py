import logging
from tennis_bot.scrapers.flashscore_scraper import FlashscoreScraper

class ResultResolver:
    """
    Resolves Exchange trades based on match outcomes.
    Calculates net PnL per market and applies exchange commission.
    """

    def __init__(self, db_manager, commission=0.02):
        self.db = db_manager
        self.logger = logging.getLogger("core.resolver")
        self.scraper = FlashscoreScraper()
        self.commission = commission

    def resolve_pending_bets(self):
        self.logger.info("Starting Exchange Resolution Job...")
        
        conn = self.db.get_connection()
        try:
            # 1. Get matches with pending bets
            query = """
                SELECT DISTINCT m.id, m.player_a, m.player_b, m.start_time
                FROM matches m
                JOIN placed_bets b ON m.id = b.match_id
                WHERE b.status = 'pending'
            """
            cursor = conn.execute(query)
            pending_matches = [dict(row) for row in cursor.fetchall()]
            
            if not pending_matches:
                return

            # 2. Fetch results
            all_matches = self.scraper.get_matches()
            
            for pm in pending_matches:
                # Find result
                # (In real implementation, we'd use external_id or fuzzy match)
                res = next((m for m in all_matches if m['player_a'] == pm['player_a']), None)
                
                # Assume Flashscore returns 'winner' attribute (1 or 2)
                # For this simulator, we'll assume matches finished if found in results
                if res and res.get('match_status') == 'finished':
                    winner = res.get('winner')
                    if winner:
                        self.resolve_match_market(pm['id'], winner)
                        
        except Exception as e:
            self.logger.error(f"Resolution Error: {e}")
        finally:
            conn.close()

    def resolve_match_market(self, match_id, winner_selection):
        """Calculates net market PnL, applies commission, and updates DB."""
        conn = self.db.get_connection()
        try:
            # 1. Get all bets for this match
            cursor = conn.execute("SELECT * FROM placed_bets WHERE match_id = ? AND status = 'pending'", (match_id,))
            bets = [dict(row) for row in cursor.fetchall()]
            
            net_pnl = 0.0
            
            # 2. Calculate PnL for each bet
            for b in bets:
                odds = float(b['odds_taken'])
                stake = float(b['amount_wagered'])
                selection = b['selection']
                side = b['bet_side']

                # PnL if this bet's predicted outcome happens
                if side == 'back':
                    if selection == str(winner_selection):
                        pnl = stake * (odds - 1)
                    else:
                        pnl = -stake
                else: # lay
                    if selection == str(winner_selection):
                        pnl = -stake * (odds - 1)
                    else:
                        pnl = stake

                net_pnl += pnl

            # 3. Apply Commission on net win
            commission_paid = 0.0
            if net_pnl > 0:
                commission_paid = net_pnl * self.commission
                net_pnl -= commission_paid

            # 4. Update bets
            # Simplified: Assign net PnL to the first bet for accounting, 0 to others
            # Or mark all as resolved.
            for i, b in enumerate(bets):
                status = 'resolved'
                # Account for net pnl in the first record
                pnl_to_record = net_pnl if i == 0 else 0.0
                comm_to_record = commission_paid if i == 0 else 0.0
                
                conn.execute("""
                    UPDATE placed_bets 
                    SET status = ?, pnl = ?, commission_paid = ?
                    WHERE id = ?
                """, (status, pnl_to_record, comm_to_record, b['id']))
            
            conn.execute("UPDATE matches SET match_status = 'finished' WHERE id = ?", (match_id,))
            conn.commit()
            self.logger.info(f"✅ MARKET RESOLVED: Match {match_id} | Net PnL: ${net_pnl:.2f} | Comm: ${commission_paid:.2f}")

        except Exception as e:
            self.logger.error(f"Market Resolution Error: {e}")
        finally:
            conn.close()

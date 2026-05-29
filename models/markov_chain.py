import math

class TennisMarkovChain:
    """
    Point-by-point Markov Chain model for predicting tennis match outcomes
    and derivative markets (Game/Set totals).
    """

    def __init__(self):
        pass

    def prob_game(self, p_serve):
        """
        Calculates the probability of winning a game given prob of winning a point on serve.
        Formula derived from Markov state transitions.
        """
        p = p_serve
        q = 1 - p
        # Prob of reaching deuce
        p_deuce = 20 * (p**3) * (q**3)
        # Prob of winning from deuce
        p_win_deuce = (p**2) / (1 - 2 * p * q)
        
        # Prob of winning before deuce (40-0, 40-15, 40-30)
        p_win_before_deuce = p**4 + 4*(p**4)*q + 10*(p**4)*(q**2)
        
        return p_win_before_deuce + p_deuce * p_win_deuce

    def prob_set(self, p_a_serve, p_b_serve):
        """
        Calculates probability of Player A winning a set.
        Simplification: Assumes constant p_serve and p_return.
        """
        # Prob of A winning a game on serve
        p_a_hold = self.prob_game(p_a_serve)
        # Prob of B winning a game on serve
        p_b_hold = self.prob_game(p_b_serve)
        # Prob of A breaking B
        p_a_break = 1 - p_b_hold
        
        # This is a complex transition matrix. 
        # For this implementation, we use a calibrated approximation 
        # of the 6-game set transition.
        # True probability of winning a set given game win probs p_h and p_b
        # can be modeled as a binomial distribution of holds/breaks.
        
        # Simplified: Average game win probability for A
        p_a_game = (p_a_hold + p_a_break) / 2
        
        # Binary expansion for a 6-game set (ignoring tiebreaks for now)
        # P(Set) = sum of binomials for 6-0, 6-1, 6-2, 6-3, 6-4, 7-5, 7-6
        # Using a common statistical proxy:
        if p_a_game == 0.5: return 0.5
        z = (p_a_game - 0.5) / math.sqrt(p_a_game * (1 - p_a_game) / 10)
        return 0.5 * (1 + math.erf(z / math.sqrt(2)))

    def project_totals(self, p_a_serve, p_b_serve, best_of=3):
        """
        Projects the total number of games in a match.
        """
        p_set_a = self.prob_set(p_a_serve, p_b_serve)
        
        if best_of == 3:
            # Prob of 2 sets: p^2 + (1-p)^2
            p_2_sets = p_set_a**2 + (1 - p_set_a)**2
            p_3_sets = 1 - p_2_sets
            avg_games_per_set = 9.8 # Average based on ATP data
            return (2 * p_2_sets + 3 * p_3_sets) * avg_games_per_set
        else:
            # Best of 5 (Grand Slams)
            # p^3 + 3p^3(1-p) + 6p^3(1-p)^2 ...
            p_3_sets = p_set_a**3 + (1 - p_set_a)**3
            p_4_sets = 3 * p_set_a**3 * (1 - p_set_a) + 3 * (1 - p_set_a)**3 * p_set_a
            p_5_sets = 1 - p_3_sets - p_4_sets
            avg_games_per_set = 10.1
            return (3 * p_3_sets + 4 * p_4_sets + 5 * p_5_sets) * avg_games_per_set

if __name__ == "__main__":
    model = TennisMarkovChain()
    # Djokovic (80% hold) vs Nadal (75% hold)
    p_a_serve = 0.70 # Point win prob on serve
    p_b_serve = 0.65 
    
    p_game_a = model.prob_game(p_a_serve)
    p_set_a = model.prob_set(p_a_serve, p_b_serve)
    total_games = model.project_totals(p_a_serve, p_b_serve)
    
    print(f"Prob Game A Hold: {p_game_a:.2%}")
    print(f"Prob Set A: {p_set_a:.2%}")
    print(f"Projected Total Games: {total_games:.1f}")

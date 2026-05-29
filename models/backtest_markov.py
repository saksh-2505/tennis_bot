import pandas as pd
import numpy as np
import os
import sys
from collections import defaultdict
from tennis_bot.models.markov_chain import TennisMarkovChain

# Add project root to sys.path
sys.path.append(os.getcwd())

def run_backtest(year=2023):
    print(f"📊 Starting Markov Chain Backtest for {year} ATP Season...")
    
    filepath = f"tennis_bot/models/raw_data/atp_{year}.csv"
    if not os.path.exists(filepath):
        print(f"❌ Data file not found: {filepath}")
        return

    df = pd.read_csv(filepath)
    # Ensure date sorting
    df['tourney_date'] = pd.to_datetime(df['tourney_date'], format='%Y%m%d')
    df = df.sort_values('tourney_date')
    
    # Filter for matches with serve stats
    df = df.dropna(subset=['w_svpt', 'w_1stWon', 'w_2ndWon', 'l_svpt', 'l_1stWon', 'l_2ndWon'])
    
    # Track rolling service stats
    player_serve_points = defaultdict(int)
    player_serve_won = defaultdict(int)
    
    results = []
    markov = TennisMarkovChain()
    
    # Split: first 30% for warmup, next 70% for testing
    split_idx = int(len(df) * 0.3)
    warmup_df = df.iloc[:split_idx]
    test_df = df.iloc[split_idx:]
    
    print(f"🔥 Warming up on {len(warmup_df)} matches...")
    for _, row in warmup_df.iterrows():
        w_id, l_id = row['winner_id'], row['loser_id']
        player_serve_points[w_id] += row['w_svpt']
        player_serve_won[w_id] += (row['w_1stWon'] + row['w_2ndWon'])
        player_serve_points[l_id] += row['l_svpt']
        player_serve_won[l_id] += (row['l_1stWon'] + row['l_2ndWon'])

    print(f"🧪 Testing on {len(test_df)} matches...")
    for _, row in test_df.iterrows():
        w_id, l_id = row['winner_id'], row['loser_id']
        
        # Get current avg p_serve
        p_w_serve = player_serve_won[w_id] / player_serve_points[w_id] if player_serve_points[w_id] > 0 else 0.65
        p_l_serve = player_serve_won[l_id] / player_serve_points[l_id] if player_serve_points[l_id] > 0 else 0.65
        
        # Predict Total Games
        # Determine best_of
        best_of = row['best_of']
        pred_games = markov.project_totals(p_w_serve, p_l_serve, best_of=best_of)
        
        # Actual games
        # We need to parse score (e.g. 6-4 6-2)
        # This is complex, we'll use a simplified total from svpt if available or parse score
        actual_games = 0
        try:
            score = str(row['score'])
            parts = score.split()
            for part in parts:
                if '-' in part and '[' not in part:
                    games = part.split('-')
                    actual_games += int(games[0].strip('()')) + int(games[1].strip('()'))
        except:
            continue
            
        if actual_games > 0:
            results.append({
                'predicted': pred_games,
                'actual': actual_games,
                'error': pred_games - actual_games
            })
            
        # Update stats for next iteration
        player_serve_points[w_id] += row['w_svpt']
        player_serve_won[w_id] += (row['w_1stWon'] + row['w_2ndWon'])
        player_serve_points[l_id] += row['l_svpt']
        player_serve_won[l_id] += (row['l_1stWon'] + row['l_2ndWon'])

    # Analysis
    res_df = pd.DataFrame(results)
    mae = res_df['error'].abs().mean()
    bias = res_df['error'].mean()
    
    print("\n✅ Backtest Results:")
    print(f"  Matches Tested: {len(res_df)}")
    print(f"  Mean Absolute Error (MAE): {mae:.2f} games")
    print(f"  Model Bias: {bias:.2f} games (Positive means over-predicting)")
    print(f"  Correlation: {res_df['predicted'].corr(res_df['actual']):.2f}")

if __name__ == "__main__":
    run_backtest(2023)

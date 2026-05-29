-- Tennis Bot Database Schema (PostgreSQL/SQLite compatible)

-- 1. Matches Table: Stores the upcoming events
CREATE TABLE IF NOT EXISTS matches (
    id SERIAL PRIMARY KEY,
    player_a VARCHAR(255) NOT NULL,
    player_b VARCHAR(255) NOT NULL,
    start_time TIMESTAMP NOT NULL,
    tournament VARCHAR(255),
    tournament_surface VARCHAR(50),
    match_status VARCHAR(50) DEFAULT 'upcoming', -- upcoming, live, finished, cancelled
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(player_a, player_b, start_time)
);

-- 2. Odds History Table: Stores all scraped odds for time-series analysis
CREATE TABLE IF NOT EXISTS odds_history (
    id SERIAL PRIMARY KEY,
    match_id INTEGER REFERENCES matches(id),
    bookmaker VARCHAR(100) NOT NULL,
    market VARCHAR(50) NOT NULL, -- e.g., '1x2', 'handicap'
    home_odds DECIMAL(10, 3) NOT NULL,
    away_odds DECIMAL(10, 3) NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Placed Bets Table: Tracks both simulated and real bets
CREATE TABLE IF NOT EXISTS placed_bets (
    id SERIAL PRIMARY KEY,
    match_id INTEGER REFERENCES matches(id),
    trade_group_id VARCHAR(100), -- To group multiple bets on same match
    bookmaker VARCHAR(100) NOT NULL,
    selection VARCHAR(10) NOT NULL, -- '1' for Home, '2' for Away
    bet_side VARCHAR(10) DEFAULT 'back', -- 'back' or 'lay'
    amount_wagered DECIMAL(15, 2) NOT NULL,
    odds_taken DECIMAL(10, 3) NOT NULL,
    expected_value DECIMAL(5, 2), -- EV%
    bet_type VARCHAR(50) DEFAULT 'simulated', -- simulated, real
    status VARCHAR(50) DEFAULT 'pending', -- pending, won, lost, void
    pnl DECIMAL(15, 2),
    commission_paid DECIMAL(15, 2) DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. Master Players Table: For normalization
CREATE TABLE IF NOT EXISTS players (
    id SERIAL PRIMARY KEY,
    standard_name VARCHAR(255) NOT NULL UNIQUE,
    aliases TEXT, -- JSON or comma-separated list
    atp_rank INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indices for performance
CREATE INDEX IF NOT EXISTS idx_odds_history_match_id ON odds_history(match_id);
CREATE INDEX IF NOT EXISTS idx_odds_history_timestamp ON odds_history(timestamp);
CREATE INDEX IF NOT EXISTS idx_matches_start_time ON matches(start_time);

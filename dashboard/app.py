import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
from datetime import datetime

# Set page config
st.set_page_config(page_title="Tennis Bot Dashboard", layout="wide")


# Database connection helper
def get_db_connection():
    conn = sqlite3.connect("tennis_bot.db")
    return conn


# Header
st.title("🎾 Tennis Odds Bot Analytics Dashboard")
st.markdown(
    "Fully automated market monitoring and predictive value detection."
)

# Sidebar
st.sidebar.header("Settings")
mode = st.sidebar.selectbox(
    "Dashboard Mode", ["Live Scanner", "Line Movement", "Bet Tracker"]
)

if mode == "Live Scanner":
    st.header("🔥 Active Match Scanner")
    st.info("Showing upcoming matches discovered from market monitoring.")

    conn = get_db_connection()
    query = """
        SELECT m.player_a, m.player_b, m.start_time, m.tournament,
               oh.bookmaker, oh.home_odds, oh.away_odds, oh.timestamp
        FROM matches m
        JOIN odds_history oh ON m.id = oh.match_id
        WHERE m.match_status = 'upcoming'
        AND oh.id IN (
            SELECT MAX(id) FROM odds_history GROUP BY match_id, bookmaker
        )
        ORDER BY m.start_time ASC
    """
    df = pd.read_sql(query, conn)
    conn.close()

    if not df.empty:
        st.dataframe(df, use_container_width=True)
    else:
        st.warning("No active matches with odds found in database.")

elif mode == "Line Movement":
    st.header("📈 Odds Movement")

    conn = get_db_connection()
    matches_df = pd.read_sql(
        "SELECT id, player_a || ' vs ' || player_b as match_name FROM matches",
        conn
    )

    if not matches_df.empty:
        match_choice = st.selectbox(
            "Select Match", matches_df["match_name"].tolist()
        )
        selected_match_id = matches_df[
            matches_df["match_name"] == match_choice
        ]["id"].iloc[0]

        odds_query = f"""
            SELECT bookmaker, home_odds, away_odds, timestamp
            FROM odds_history
            WHERE match_id = {selected_match_id}
            ORDER BY timestamp ASC
        """
        df_odds_history = pd.read_sql(odds_query, conn)
        conn.close()

        if not df_odds_history.empty:
            df_plot = df_odds_history.melt(
                id_vars=["timestamp", "bookmaker"],
                value_vars=["home_odds", "away_odds"],
                var_name="Selection",
                value_name="Odds"
            )

            fig = px.line(
                df_plot, x="timestamp", y="Odds", color="Selection",
                symbol="bookmaker", title=f"Odds Movement for {match_choice}",
                line_shape="hv"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No odds history available for this match yet.")
    else:
        st.warning("No matches found in database.")
        conn.close()

elif mode == "Bet Tracker":
    st.header("📊 Bet Tracker & ROI")

    # KPI Cards
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Wagered", "$1,250.00")
    col2.metric("Net Profit", "$342.50", delta="+12%")
    col3.metric("ROI %", "27.4%")
    col4.metric("Hit Rate", "64%")

    # History Table
    st.subheader("Recent Bets")
    history_data = {
        "Date": ["2026-04-26", "2026-04-25", "2026-04-25"],
        "Match": ["Medvedev vs Zverev", "Ruud vs Rune", "Tsitsipas vs Fritz"],
        "Bookmaker": ["Bet365", "DraftKings", "Pinnacle"],
        "Wager": ["$100", "$50", "$200"],
        "Odds": [1.90, 2.10, 1.75],
        "Status": ["Won", "Lost", "Won"],
        "PnL": ["+$90", "-$50", "+$150"]
    }
    st.dataframe(pd.DataFrame(history_data), use_container_width=True)

# Footer
st.sidebar.markdown("---")
st.sidebar.write("System Status: **Scanning**")
st.sidebar.write(f"Last Update: {datetime.now().strftime('%H:%M:%S')}")

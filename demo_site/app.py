from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import sqlite3
from tennis_bot.models.value_model import ValueModel
from tennis_bot.database.db_manager import DatabaseManager
import os

app = FastAPI()
templates = Jinja2Templates(
    directory=os.path.join(os.path.dirname(__file__), "templates")
)
db_manager = DatabaseManager()
value_model = ValueModel()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    conn = sqlite3.connect("tennis_bot.db")
    conn.row_factory = sqlite3.Row

    # Get matches with latest odds
    query = """
        SELECT m.id, m.player_a, m.player_b, m.tournament, m.start_time,
               oh.bookmaker, oh.home_odds, oh.away_odds
        FROM matches m
        JOIN odds_history oh ON m.id = oh.match_id
        WHERE m.match_status = 'upcoming'
        AND oh.id IN (
            SELECT MAX(id) FROM odds_history GROUP BY match_id, bookmaker
        )
        ORDER BY m.start_time ASC
        LIMIT 20
    """
    matches_raw = conn.execute(query).fetchall()

    matches = []
    for row in matches_raw:
        match = dict(row)
        # Get AI Prediction
        prob = value_model.predict_win_prob(
            match['player_a'], match['player_b']
        )
        if prob:
            match['ai_prob_a'] = prob
            match['ai_prob_b'] = 1 - prob
            match['ai_odds_a'] = round(1/prob, 2)
            match['ai_odds_b'] = round(1/(1-prob), 2)

            # Highlight value
            match['value_a'] = match['home_odds'] > match['ai_odds_a']
            match['value_b'] = match['away_odds'] > match['ai_odds_b']
        else:
            match['ai_prob_a'] = None

        matches.append(match)

    conn.close()
    return templates.TemplateResponse(
        "index.html", {"request": request, "matches": matches}
    )


@app.post("/place_bet")
async def place_bet(
    match_id: int = Form(...),
    selection: str = Form(...),
    odds: float = Form(...),
    amount: float = Form(...),
):
    conn = sqlite3.connect("tennis_bot.db")
    query = """
        INSERT INTO placed_bets (
            match_id, bookmaker, amount_wagered, odds_taken, bet_type, status
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """
    conn.execute(
        query,
        (match_id, "DemoSite", amount, odds, "simulated", "pending")
    )
    conn.commit()
    conn.close()
    return {
        "status": "success",
        "message": f"Bet placed on selection {selection} at {odds}"
    }


@app.get("/history", response_class=HTMLResponse)
async def history(request: Request):
    conn = sqlite3.connect("tennis_bot.db")
    conn.row_factory = sqlite3.Row
    bets = conn.execute("""
        SELECT pb.*, m.player_a, m.player_b
        FROM placed_bets pb
        JOIN matches m ON pb.match_id = m.id
        ORDER BY pb.created_at DESC
    """).fetchall()
    conn.close()
    return templates.TemplateResponse(
        "history.html", {"request": request, "bets": bets}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

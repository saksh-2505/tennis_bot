# 🎾 Fully Automated Tennis Odds Bot

A professional-grade, end-to-end system for tennis market monitoring, predictive win probability modeling, and automated value detection.

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Start the Automated Extraction Engine (Orchestrator)
The orchestrator handles match discovery and periodic odds updates.
```bash
python -m tennis_bot.core.orchestrator
```

### 3. Launch the Analytics Dashboard
Open the interactive dashboard to view active value opportunities and line movement graphs.
```bash
streamlit run tennis_bot/dashboard/app.py
```

## 🏗 Project Structure

- `tennis_bot/core/`: The central nervous system (Orchestration, Session Management, Normalization).
- `tennis_bot/scrapers/`: Individual bookmaker scraper implementations (API & UI).
- `tennis_bot/database/`: Database schema and connection manager.
- `tennis_bot/dashboard/`: Streamlit web application.
- `tennis_bot/models/`: (Placeholder) Predictive win probability ML models.

## 🧠 Features

- **Stealth Pipeline:** Rotated JA3 fingerprints and User-Agents via `curl_cffi`.
- **Direct API Scraping:** High-performance data extraction bypassing HTML parsing.
- **Fuzzy Normalization:** Standardizes player names across different bookmakers.
- **Value Detection:** Identifies "Steam" movements and compares them against predictive models.
- **Interactive Graphs:** Visualize odds movement over time to spot market laggards.

## 🛠 Tech Stack

- **Backend:** Python 3.11, APScheduler, curl_cffi.
- **Data:** pandas, RapidFuzz, SQLite (PostgreSQL compatible).
- **Frontend:** Streamlit, Plotly, Chart.js.

---
*Developed for Saksham Rai's Second Brain.*

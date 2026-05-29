import pandas as pd
import xgboost as xgb
from sklearn.model_selection import train_test_split
from sklearn.metrics import log_loss, brier_score_loss
import logging
import os
from tennis_bot.models.data_loader import TennisDataLoader
from tennis_bot.models.elo_tracker import EloTracker


logger = logging.getLogger("models.train_model")
logging.basicConfig(level=logging.INFO)


def train_pipeline(start_year=2015, train_from_year=2018):
    """
    Full pipeline: Load data -> Elo Features -> Train XGBoost.
    """
    # 1. Load Data
    loader = TennisDataLoader()
    df = loader.load_data(start_year, 2024)

    if df.empty:
        logger.error("No data loaded. Training aborted.")
        return

    # 2. Generate Elo Features
    tracker = EloTracker()
    feat_df = tracker.process_matches(df)

    # 3. Data Augmentation (Swap Player A/B to balance labels)
    # Since labels are currently all 1 (Player A is winner), we need to swap 50%
    logger.info("Augmenting data (swapping A/B for balance)...")

    # Split into 50% to swap
    mask = feat_df.index % 2 == 0
    df_to_swap = feat_df[mask].copy()

    # Swap columns
    df_to_swap['p_a_id'], df_to_swap['p_b_id'] = (
        feat_df.loc[mask, 'p_b_id'], feat_df.loc[mask, 'p_a_id']
    )
    df_to_swap['p_a_elo'], df_to_swap['p_b_elo'] = (
        feat_df.loc[mask, 'p_b_elo'], feat_df.loc[mask, 'p_a_elo']
    )
    df_to_swap['p_a_surface_elo'], df_to_swap['p_b_surface_elo'] = (
        feat_df.loc[mask, 'p_b_surface_elo'], feat_df.loc[mask, 'p_a_surface_elo']
    )
    df_to_swap['h2h_a'], df_to_swap['h2h_b'] = (
        feat_df.loc[mask, 'h2h_b'], feat_df.loc[mask, 'h2h_a']
    )
    df_to_swap['label'] = 0  # Player A (now loser) lost

    feat_df.loc[mask] = df_to_swap

    # 4. Filter for training (Burn-in period for Elo)
    feat_df['year'] = pd.to_datetime(feat_df['tourney_date']).dt.year
    train_df = feat_df[feat_df['year'] >= train_from_year]

    # 5. Prepare features
    # Calculate Elo differences as high-signal features
    train_df['elo_diff'] = train_df['p_a_elo'] - train_df['p_b_elo']
    train_df['surface_elo_diff'] = (
        train_df['p_a_surface_elo'] - train_df['p_b_surface_elo']
    )

    features = ['elo_diff', 'surface_elo_diff', 'h2h_a', 'h2h_b']
    X = train_df[features]
    y = train_df['label']

    # 6. Train/Test Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # 7. Train XGBoost
    logger.info("Training XGBoost model...")
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=3,
        learning_rate=0.1,
        objective='binary:logistic',
        random_state=42
    )
    model.fit(X_train, y_train)

    # 8. Evaluation
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    loss = log_loss(y_test, y_pred_proba)
    brier = brier_score_loss(y_test, y_pred_proba)

    logger.info("Evaluation Results:")
    logger.info(f"Log Loss: {loss:.4f}")
    logger.info(f"Brier Score: {brier:.4f}")

    # 9. Save Model and Final Elo State
    model_path = os.path.join(os.path.dirname(__file__), "model.xgb")
    model.save_model(model_path)
    tracker.save_state()

    logger.info(f"Model saved to {model_path}")
    return model


if __name__ == "__main__":
    train_pipeline()

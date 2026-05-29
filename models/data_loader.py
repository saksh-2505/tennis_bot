import pandas as pd
import requests
import os
import logging
import time
from datetime import datetime

logger = logging.getLogger("models.data_loader")
logging.basicConfig(level=logging.INFO)


class TennisDataLoader:
    """
    Handles downloading and loading historical tennis match data
    from JeffSackmann GitHub.
    """

    BASE_URLS = {
        "atp": (
            "https://raw.githubusercontent.com/JeffSackmann/"
            "tennis_atp/master/atp_matches_{year}.csv"
        ),
        "wta": (
            "https://raw.githubusercontent.com/JeffSackmann/"
            "tennis_wta/master/wta_matches_{year}.csv"
        )
    }

    DATA_DIR = os.path.join(os.path.dirname(__file__), "raw_data")

    def __init__(self):
        if not os.path.exists(self.DATA_DIR):
            os.makedirs(self.DATA_DIR)

    def download_year(self, year, circuit="atp"):
        """Downloads a specific year of match data."""
        url = self.BASE_URLS[circuit].format(year=year)
        filename = f"{circuit}_{year}.csv"
        filepath = os.path.join(self.DATA_DIR, filename)

        # Skip if updated in last 24 hours
        if os.path.exists(filepath):
            mtime = os.path.getmtime(filepath)
            if (time.time() - mtime) < 86400:
                logger.info(f"Skipping {circuit} {year} - recently updated.")
                return True

        logger.info(f"Downloading {circuit} data for {year}...")
        try:
            response = requests.get(url)
            response.raise_for_status()
            with open(filepath, "wb") as f:
                f.write(response.content)
            logger.info(f"Saved to {filepath}")
            return True
        except Exception as e:
            logger.error(f"Failed to download {url}: {e}")
            return False

    def download_range(
        self, start_year, end_year=None, circuits=["atp", "wta"]
    ):
        """Downloads data for a range of years."""
        if end_year is None:
            end_year = datetime.now().year

        for circuit in circuits:
            for year in range(start_year, end_year + 1):
                self.download_year(year, circuit)

    def load_data(self, start_year, end_year=None, circuits=["atp", "wta"]):
        """Loads and concatenates data into a single DataFrame."""
        if end_year is None:
            end_year = datetime.now().year

        dfs = []
        for circuit in circuits:
            for year in range(start_year, end_year + 1):
                filename = f"{circuit}_{year}.csv"
                filepath = os.path.join(self.DATA_DIR, filename)

                if not os.path.exists(filepath):
                    self.download_year(year, circuit)

                if os.path.exists(filepath):
                    df = pd.read_csv(filepath)
                    # Add circuit column to distinguish
                    df['circuit'] = circuit
                    dfs.append(df)

        if not dfs:
            return pd.DataFrame()

        combined_df = pd.concat(dfs, ignore_index=True)
        # Convert tourney_date to datetime
        combined_df['tourney_date'] = pd.to_datetime(
            combined_df['tourney_date'], format='%Y%m%d', errors='coerce'
        )
        combined_df = combined_df.sort_values(by=['tourney_date', 'match_num'])

        logger.info(
            f"Loaded {len(combined_df)} matches from "
            f"{start_year} to {end_year}"
        )
        return combined_df


if __name__ == "__main__":
    loader = TennisDataLoader()
    # Test with a single year
    df = loader.load_data(2023, 2024)
    print(df.head())
    print(df.columns)

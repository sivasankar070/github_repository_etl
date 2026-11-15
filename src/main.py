
import logging
from pathlib import Path
import pandas as pd
import argparse

from .extract import extract_repositories
from .transform import transform_data
from .load import (
    get_connection,
    load_repositories,
    load_repository_topics,
)


# Project paths
BASE_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = BASE_DIR / "logs"
LOG_FILE = LOG_DIR / "etl.log"

LOG_DIR.mkdir(parents=True, exist_ok=True)

# Configure logging once for the entire ETL pipeline
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
    ],
)

logger = logging.getLogger(__name__)

def parse_args():
    parser = argparse.ArgumentParser(
        description="GitHub repository ETL pipeline"
    )

    parser.add_argument(
        "--account-type",
        choices=["users", "orgs"],
        default=None,
        help="GitHub account type: users or orgs"
    )

    parser.add_argument(
        "--owner",
        default=None,
        help="GitHub organization name"
    )

    return parser.parse_args()


def main(owner, account_type):
    conn = None

    logger.info("ETL pipeline started")

    try:
        # 1. Extract
        raw_data = extract_repositories(owner, account_type)

        logger.info(
            "Extraction stage completed | repositories=%s | account_type=%s",
            len(raw_data),
            account_type
        )

        # 2. Convert extracted records into a DataFrame
        raw_df = pd.DataFrame(raw_data)

        # 3. Transform
        repositories_df, repository_topics_df = transform_data(raw_df)

        logger.info(
            "Transformation stage completed | repositories=%s | "
            "topic_relationships=%s",
            len(repositories_df),
            len(repository_topics_df),
        )

        # 4. Connect to PostgreSQL
        conn = get_connection()

        # 5. Load both tables within the same transaction
        load_repositories(conn, repositories_df)

        load_repository_topics(
            conn,
            repository_topics_df,
            repositories_df["id"],
        )

        # 6. Commit only after both loading stages succeed
        conn.commit()

        logger.info("ETL pipeline completed successfully")

    except Exception:
        logger.error(
            "ETL pipeline failed; attempting transaction rollback"
        )

        if conn is not None:
            try:
                conn.rollback()
                logger.info("Database transaction rolled back")
            except Exception:
                logger.exception("Database rollback failed")

        # Propagate the failure so the process exits unsuccessfully
        raise

    finally:
        if conn is not None:
            try:
                conn.close()
                logger.info("Database connection closed")
            except Exception:
                logger.exception("Failed to close database connection")


if __name__ == "__main__":
    args = parse_args()

    account_type = args.account_type

    owner = args.owner

    if account_type is None:
        account_type = input(
            "Enter GitHub account type (users/orgs) [users]: "
        ).strip().lower()

        if not account_type:
            account_type = "user"

    if owner is None:
        owner = input(
            "Enter GitHub organization or user name [openai]: "
        ).strip().lower()

        if not owner:
            owner = "openai"

    main(owner, account_type)

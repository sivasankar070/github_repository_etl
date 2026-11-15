
import json
import logging
import re

from datetime import timedelta
from pathlib import Path

import pandas as pd
import pendulum

from airflow.sdk import dag, task, Param, get_current_context

from src.extract import extract_repositories
from src.transform import transform_data
from src.load import (
    get_connection,
    load_repositories,
    load_repository_topics,
)


logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]

RUNS_DIR = (
    PROJECT_ROOT
    / "include"
    / "github_etl"
    / "runs"
)


@dag(
    dag_id="github_repository_etl",
    description="Extract GitHub repositories and load them into PostgreSQL",
    start_date=pendulum.datetime(2025, 1, 1, tz="UTC"),
    schedule=None,
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "data_engineering",
        "retries": 2,
        "retry_delay": timedelta(minutes=1),
    },
    params={
        "owner": Param(
            "sivasankar070",
            type="string",
            minLength=1,
            title="GitHub username or organization",
        ),
        "account_type": Param(
            "users",
            type="string",
            enum=["users", "orgs"],
            title="GitHub account type",
        ),
    },
    tags=["github", "etl", "postgresql"],
)
def github_repository_etl():

    # TASK 1: EXTRACT
    @task(task_id="extract")
    def extract_task() -> str:

        context = get_current_context()

        owner = context["params"]["owner"].strip()
        account_type = context["params"]["account_type"]

        # Create a unique directory for each DAG run
        run_id = context["run_id"]

        safe_run_id = re.sub(
            r"[^A-Za-z0-9_.-]+",
            "_",
            run_id,
        )

        run_dir = RUNS_DIR / safe_run_id
        raw_file = run_dir / "repositories.json"

        logger.info(
            "Starting extraction | owner=%s | account_type=%s",
            owner,
            account_type,
        )

        repositories = extract_repositories(
            owner,
            account_type,
            output_file=raw_file,
        )

        logger.info(
            "Extraction completed | repositories=%s",
            len(repositories),
        )

        return str(raw_file)

    # TASK 2: TRANSFORM
    @task(task_id="transform")
    def transform_task(raw_file_path: str) -> dict:

        raw_file = Path(raw_file_path)

        logger.info(
            "Starting transformation | input=%s",
            raw_file,
        )

        with raw_file.open("r", encoding="utf-8") as file:
            raw_data = json.load(file)

        raw_df = pd.DataFrame(raw_data)

        repositories_df, repository_topics_df = transform_data(
            raw_df
        )

        processed_dir = raw_file.parent / "processed"
        processed_dir.mkdir(parents=True, exist_ok=True)

        repositories_file = processed_dir / "repositories.csv"
        topics_file = processed_dir / "repository_topics.csv"

        repositories_df.to_csv(
            repositories_file,
            index=False,
        )

        repository_topics_df.to_csv(
            topics_file,
            index=False,
        )

        logger.info(
            "Transformation completed | repositories=%s | topics=%s",
            len(repositories_df),
            len(repository_topics_df),
        )

        # Return file paths, not entire DataFrames
        return {
            "repositories_file": str(repositories_file),
            "topics_file": str(topics_file),
        }

    # TASK 3: LOAD
    @task(task_id="load")
    def load_task(processed_files: dict) -> None:

        logger.info("Starting PostgreSQL loading")

        repositories_df = pd.read_csv(
            processed_files["repositories_file"]
        )

        repository_topics_df = pd.read_csv(
            processed_files["topics_file"]
        )

        # Restore timezone-aware timestamp columns
        for column in [
            "created_at",
            "updated_at",
            "pushed_at",
        ]:
            repositories_df[column] = pd.to_datetime(
                repositories_df[column],
                utc=True,
            )

        # Restore repository IDs if topic records exist
        if not repository_topics_df.empty:
            repository_topics_df["repository_id"] = (
                pd.to_numeric(
                    repository_topics_df["repository_id"],
                    errors="raise",
                ).astype("int64")
            )

        conn = None

        try:
            # Connect to PostgreSQL running on Windows
            conn = get_connection(
                host_override="host.docker.internal"
            )

            load_repositories(
                conn,
                repositories_df,
            )

            load_repository_topics(
                conn,
                repository_topics_df,
                repositories_df["id"],
            )

            conn.commit()

            logger.info(
                "PostgreSQL loading completed successfully"
            )

        except Exception:
            if conn is not None:
                try:
                    conn.rollback()
                    logger.info("Database transaction rolled back")
                except Exception:
                    logger.exception("Database rollback failed")

            raise

        finally:
            if conn is not None:
                conn.close()
                logger.info("Database connection closed")

    # DEFINE TASK DEPENDENCIES
    raw_file_path = extract_task()

    processed_files = transform_task(raw_file_path)

    load_task(processed_files)


github_repository_etl()

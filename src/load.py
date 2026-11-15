
from dotenv import load_dotenv
from pathlib import Path
import os
import logging
import pandas as pd
import psycopg


BASE_DIR = Path(__file__).resolve().parent.parent

logger = logging.getLogger(__name__)

load_dotenv(BASE_DIR / ".env")


def get_connection(host_override=None):
    stage = "validating database configuration"

    try:
        db_host = host_override or os.getenv("DB_HOST")
        db_name = os.getenv("DB_NAME")
        db_user = os.getenv("DB_USER")
        db_password = os.getenv("DB_PASSWORD")
        db_port = os.getenv("DB_PORT")

        required_vars = {
            "DB_HOST": db_host,
            "DB_NAME": db_name,
            "DB_USER": db_user,
            "DB_PASSWORD": db_password,
            "DB_PORT": db_port,
        }

        missing_vars = [
            name
            for name, value in required_vars.items()
            if not value
        ]

        if missing_vars:
            raise ValueError(
                "Missing database environment variables: "
                + ", ".join(missing_vars)
            )

        db_port = int(db_port)

        stage = "connecting to PostgreSQL"

        conn = psycopg.connect(
            host=db_host,
            dbname=db_name,
            user=db_user,
            password=db_password,
            port=db_port,
        )

        logger.info(
            "Database connection established | "
            "host=%s | dbname=%s | user=%s | port=%s",
            db_host,
            db_name,
            db_user,
            db_port,
        )

        return conn

    except Exception:
        logger.exception(
            "Database connection failed | stage=%s",
            stage,
        )
        raise


def load_repositories(conn, repositories_df):
    stage = "validating repository data"

    repository_columns = [
        "id",
        "name",
        "full_name",
        "description",
        "html_url",
        "private",
        "fork",
        "created_at",
        "updated_at",
        "pushed_at",
        "size",
        "stargazers_count",
        "forks_count",
        "open_issues_count",
        "language",
        "visibility",
        "archived",
        "disabled",
        "default_branch",
    ]

    try:
        logger.info(
            "Repository loading started | input_rows=%s",
            len(repositories_df),
        )

        missing_columns = [
            column
            for column in repository_columns
            if column not in repositories_df.columns
        ]

        if missing_columns:
            raise ValueError(
                f"Missing repository columns: {missing_columns}"
            )

        # Match the SQL insert column order and convert pandas
        # missing values such as NaT/NaN to Python None.
        stage = "preparing repository records"

        db_df = repositories_df[repository_columns].astype(object)
        db_df = db_df.where(pd.notna(db_df), None)

        stage = "executing repository upserts"

        insert_query = """
            INSERT INTO github.repositories (
                id,
                name,
                full_name,
                description,
                html_url,
                private,
                fork,
                created_at,
                updated_at,
                pushed_at,
                size,
                stargazers_count,
                forks_count,
                open_issues_count,
                language,
                visibility,
                archived,
                disabled,
                default_branch
            )
            VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s
            )
            ON CONFLICT (id)
            DO UPDATE SET
                name = EXCLUDED.name,
                full_name = EXCLUDED.full_name,
                description = EXCLUDED.description,
                html_url = EXCLUDED.html_url,
                private = EXCLUDED.private,
                fork = EXCLUDED.fork,
                created_at = EXCLUDED.created_at,
                updated_at = EXCLUDED.updated_at,
                pushed_at = EXCLUDED.pushed_at,
                size = EXCLUDED.size,
                stargazers_count = EXCLUDED.stargazers_count,
                forks_count = EXCLUDED.forks_count,
                open_issues_count = EXCLUDED.open_issues_count,
                language = EXCLUDED.language,
                visibility = EXCLUDED.visibility,
                archived = EXCLUDED.archived,
                disabled = EXCLUDED.disabled,
                default_branch = EXCLUDED.default_branch;
        """

        with conn.cursor() as cur:
            for row in db_df.itertuples(index=False, name=None):
                cur.execute(insert_query, row)

        logger.info(
            "Repository upserts executed successfully | processed_rows=%s",
            len(db_df),
        )

    except Exception:
        logger.exception(
            "Repository loading failed | stage=%s",
            stage,
        )
        raise


def load_repository_topics(
    conn,
    repository_topics_df,
    repository_ids,
):
    stage = "validating repository topics"

    try:
        logger.info(
            "Repository topic loading started | "
            "input_relationships=%s",
            len(repository_topics_df),
        )

        topic_columns = ["repository_id", "topic"]

        missing_columns = [
            column
            for column in topic_columns
            if column not in repository_topics_df.columns
        ]

        if missing_columns:
            raise ValueError(
                f"Missing repository topic columns: {missing_columns}"
            )

        repository_ids = [int(repository_id) for repository_id in repository_ids]

        # Delete existing topic relationships for the repositories
        # being refreshed. This also clears topics for repositories
        # whose current topic list is empty.
        stage = "deleting existing topic relationships"

        delete_query = """
            DELETE FROM github.repository_topics
            WHERE repository_id = %s;
        """

        deleted_rows = 0

        with conn.cursor() as cur:
            for repository_id in repository_ids:
                cur.execute(delete_query, (repository_id,))
                deleted_rows += cur.rowcount

        logger.info(
            "Existing topic relationships deleted | "
            "repositories_checked=%s | deleted_rows=%s",
            len(repository_ids),
            deleted_rows,
        )

        # Insert the current topic relationships
        stage = "inserting topic relationships"

        insert_query = """
            INSERT INTO github.repository_topics (
                repository_id,
                topic
            )
            VALUES (%s, %s)
            ON CONFLICT (repository_id, topic)
            DO NOTHING;
        """

        topics_df = repository_topics_df[topic_columns]

        with conn.cursor() as cur:
            for row in topics_df.itertuples(index=False, name=None):
                cur.execute(insert_query, row)

        logger.info(
            "Repository topic loading completed | "
            "processed_relationships=%s",
            len(topics_df),
        )

    except Exception:
        logger.exception(
            "Repository topic loading failed | stage=%s",
            stage,
        )
        raise

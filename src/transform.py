
import logging
import pandas as pd


logger = logging.getLogger(__name__)


REPOSITORY_COLUMNS = [
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
    "topics",
    "visibility",
    "archived",
    "disabled",
    "default_branch",
]


def transform_data(repositories_df: pd.DataFrame):
    stage = "validating input"

    try:
        input_rows = len(repositories_df)

        logger.info(
            "Transformation started | input_rows=%s",
            input_rows
        )

        if repositories_df.empty:
            logger.warning(
                "Input DataFrame contains no repositories"
            )

        # 1. Validate required columns
        stage = "validating required columns"

        missing_columns = [
            column
            for column in REPOSITORY_COLUMNS
            if column not in repositories_df.columns
        ]

        if missing_columns:
            raise ValueError(
                f"Missing required columns: {missing_columns}"
            )

        repositories_df = repositories_df[
            REPOSITORY_COLUMNS
        ].copy()

        logger.info(
            "Required columns validated | column_count=%s",
            len(REPOSITORY_COLUMNS)
        )

        # 2. Handle missing text values
        stage = "handling missing text values"

        missing_descriptions = (
            repositories_df["description"].isna().sum()
        )
        missing_languages = (
            repositories_df["language"].isna().sum()
        )

        repositories_df["description"] = (
            repositories_df["description"].fillna("No description")
        )
        repositories_df["language"] = (
            repositories_df["language"].fillna("Unknown")
        )

        if repositories_df["description"].isna().any():
            raise ValueError(
                "Null values remain in description"
            )

        if repositories_df["language"].isna().any():
            raise ValueError(
                "Null values remain in language"
            )

        logger.info(
            "Missing text values handled | "
            "descriptions_filled=%s | languages_filled=%s",
            missing_descriptions,
            missing_languages
        )

        # 3. Convert timestamps to UTC
        stage = "converting timestamps"

        timestamp_columns = [
            "created_at",
            "updated_at",
            "pushed_at"
        ]

        try:
            for column in timestamp_columns:
                repositories_df[column] = pd.to_datetime(
                    repositories_df[column],
                    utc=True
                )
        except (ValueError, TypeError) as e:
            raise ValueError(
                "Invalid value found while processing timestamps"
            ) from e

        # created_at and updated_at are required.
        # pushed_at is allowed to be null.
        required_timestamp_columns = [
            "created_at",
            "updated_at"
        ]

        if repositories_df[
            required_timestamp_columns
        ].isna().any().any():
            raise ValueError(
                "Missing created_at or updated_at timestamp"
            )

        invalid_updated_at = (
            repositories_df["created_at"]
            > repositories_df["updated_at"]
        )

        if invalid_updated_at.any():
            raise ValueError(
                "created_at is later than updated_at"
            )

        logger.info(
            "Timestamp validation completed | "
            "columns_processed=%s",
            len(timestamp_columns)
        )

        # 4. Validate repository IDs and numeric measures
        stage = "validating numeric columns"

        integer_columns = [
            "id",
            "size",
            "stargazers_count",
            "forks_count",
            "open_issues_count",
        ]

        for column in integer_columns:
            try:
                values = pd.to_numeric(
                    repositories_df[column],
                    errors="raise"
                )
            except (ValueError, TypeError) as e:
                raise ValueError(
                    f"Invalid numeric values in column '{column}'"
                ) from e

            if values.isna().any():
                raise ValueError(
                    f"Missing values found in column '{column}'"
                )

            if (values % 1 != 0).any():
                raise ValueError(
                    f"Non-integer values found in column '{column}'"
                )

            if (values < 0).any():
                raise ValueError(
                    f"Negative values found in column '{column}'"
                )

            repositories_df[column] = values.astype("int64")

        if (repositories_df["id"] == 0).any():
            raise ValueError(
                "Repository IDs must not be zero"
            )

        if repositories_df["id"].duplicated().any():
            raise ValueError(
                "Duplicate repository IDs found"
            )

        logger.info(
            "Numeric validation completed | "
            "columns_validated=%s",
            len(integer_columns)
        )

        # 5. Validate topic data
        stage = "validating topics"

        if not repositories_df["topics"].map(
            lambda value: isinstance(value, list)
        ).all():
            raise ValueError(
                "Non-list value found in topics column"
            )

        if not repositories_df["topics"].map(
            lambda topics: all(
                isinstance(topic, str) and topic.strip()
                for topic in topics
            )
        ).all():
            raise ValueError(
                "Invalid or empty topic value found"
            )

        logger.info(
            "Topic validation completed | repositories=%s",
            len(repositories_df)
        )

        # 6. Create repository-topic relationships
        stage = "creating repository-topic relationships"

        repository_topics_df = (
            repositories_df[["id", "topics"]]
            .rename(
                columns={
                    "id": "repository_id",
                    "topics": "topic"
                }
            )
            .explode("topic")
            .dropna(subset=["topic"])
            .reset_index(drop=True)
        )

        if repository_topics_df[
            ["repository_id", "topic"]
        ].duplicated().any():
            raise ValueError(
                "Duplicate repository-topic relationships found"
            )

        missing_repository_ids = repository_topics_df.loc[
            ~repository_topics_df["repository_id"].isin(
                repositories_df["id"]
            ),
            "repository_id"
        ].unique()

        if len(missing_repository_ids) > 0:
            raise ValueError(
                "Topic records reference unknown repository IDs: "
                f"{missing_repository_ids.tolist()}"
            )

        logger.info(
            "Repository-topic relationships created | "
            "topic_relationships=%s",
            len(repository_topics_df)
        )

        # 7. Remove topics from the repository table
        stage = "finalizing transformed data"

        repositories_df = repositories_df.drop(
            columns=["topics"]
        )

        logger.info(
            "Transformation completed successfully | "
            "repositories=%s | topic_relationships=%s",
            len(repositories_df),
            len(repository_topics_df)
        )

        return repositories_df, repository_topics_df

    except Exception:
        logger.exception(
            "Transformation failed | stage=%s",
            stage
        )
        raise

import pandas as pd
import pytest

from src.transform import transform_data

test_df = pd.DataFrame(
    {
        "id": [12345],
        "name": ["etl-demo"],
        "full_name": ["sivasankar070/etl-demo"],
        "description": ["A sample ETL project"],
        "html_url": ["https://github.com/example/etl-demo"],
        "private": [False],
        "fork": [False],
        "created_at": ["2025-01-01T10:00:00Z"],
        "updated_at": ["2025-02-01T10:00:00Z"],
        "pushed_at": ["2025-02-01T10:00:00Z"],
        "size": [100],
        "stargazers_count": [10],
        "forks_count": [2],
        "open_issues_count": [1],
        "language": ["Python"],
        "topics": [["python", "etl"]],
        "visibility": ["public"],
        "archived": [False],
        "disabled": [False],
        "default_branch": ["main"]
    }
)

def test_transform_data_valid_input():
    transformed_repos_df, transformed_topics_df = transform_data(test_df)

    # Check the repository DataFrame
    assert transformed_repos_df.shape == (1, 19)
    assert transformed_repos_df.iloc[0]["id"] == 12345
    assert "topics" not in transformed_repos_df.columns

    # Check the repository topics DataFrame
    assert transformed_topics_df.shape == (2, 2)
    assert set(transformed_topics_df["topic"]) == {"python", "etl"}
    assert set(transformed_topics_df["repository_id"]) == {12345}

    # Check timestamp conversion
    assert pd.api.types.is_datetime64_any_dtype(
        transformed_repos_df["created_at"]
    )
    assert str(transformed_repos_df["created_at"].dt.tz) == "UTC"

def test_transform_data_missing_columns():
    df = test_df.copy()
    df = df.drop(columns=["description"])

    with pytest.raises(
        ValueError,
        match=r"Missing required columns: \['description'\]"
    ):
        transform_data(df)

def test_transform_data_handles_missing_text():
    df = test_df.copy()

    df.loc[0, "description"] = None
    df.loc[0, "language"] = None

    transformed_repos_df, transformed_topics_df = transform_data(df)

    assert transformed_repos_df.loc[0, "description"] == "No description"
    assert transformed_repos_df.loc[0, "language"] == "Unknown"

    assert transformed_repos_df["description"].notna().all()
    assert transformed_repos_df["language"].notna().all()

def test_transform_data_duplicate_ids():
    df = pd.concat(
        [test_df, test_df.copy()],
        ignore_index=True
    )

    with pytest.raises(
        ValueError,
        match="Duplicate repository IDs found"
    ):
        transform_data(df)

def test_transform_data_invalid_timestamp():
    df = test_df.copy()
    df.loc[0, "created_at"] = "not-a-valid-timestamp"

    with pytest.raises(
        ValueError,
        match="Invalid value found while processing timestamps"
    ):
        transform_data(df)

def test_transform_data_missing_timestamps():
    df = test_df.copy()
    df.loc[0, "created_at"] = None

    with pytest.raises(
        ValueError,
        match="Missing created_at or updated_at timestamp"
    ):
        transform_data(df)

def test_transform_data_updated_at_earlier_than_created_at():
    df = test_df.copy()
    df.loc[0, "updated_at"] = "2024-12-31T10:00:00Z"

    with pytest.raises(
        ValueError,
        match="created_at is later than updated_at"
    ):
        transform_data(df)

def test_transform_data_invalid_numeric():
    df = test_df.copy()
    df["id"] = ["not-a-number"]

    with pytest.raises(
        ValueError,
        match="Invalid numeric values in column 'id'"
    ):
        transform_data(df)

def test_transform_data_missing_numeric():
    df = test_df.copy()
    df.loc[0, "id"] = None

    with pytest.raises(
        ValueError,
        match="Missing values found in column 'id'"
    ):
        transform_data(df)

def test_transform_data_non_integer_numeric():
    df = test_df.copy()
    df["id"] = [1.11]

    with pytest.raises(
        ValueError,
        match="Non-integer values found in column 'id'"
    ):
        transform_data(df)

def test_transform_data_negative_numeric():
    df = test_df.copy()
    df.loc[0, "id"] = -1

    with pytest.raises(
        ValueError,
        match="Negative values found in column 'id'"
    ):
        transform_data(df)

def test_transform_data_if_id_is_zero():
    df = test_df.copy()
    df.loc[0, "id"] = 0

    with pytest.raises(
        ValueError,
        match="Repository IDs must not be zero"
    ):
        transform_data(df)

def test_transform_data_non_list_topics():
    df = test_df.copy()
    df.loc[0, "topics"] = "not-a-list"

    with pytest.raises(
        ValueError,
        match="Non-list value found in topics column"
    ):
        transform_data(df)

def test_transform_data_missing_topics():
    df = test_df.copy()
    df.at[0, "topics"] = [None, "etl"]

    with pytest.raises(
        ValueError,
        match="Invalid or empty topic value found"
    ):
        transform_data(df)

def test_transform_data_empty_topic_string():
    df = test_df.copy()
    df.at[0, "topics"] = [""]

    with pytest.raises(
        ValueError,
        match="Invalid or empty topic value found"
    ):
        transform_data(df)

def test_transform_data_duplicate_repository_topic_relationships():
    df = test_df.copy()
    df.at[0, "topics"] = ["python", "etl", "python"]

    with pytest.raises(
        ValueError,
        match="Duplicate repository-topic relationships found"
    ):
        transform_data(df)

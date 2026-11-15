
import pandas as pd
from unittest.mock import MagicMock

from src.load import load_repositories
from src.load import load_repository_topics


def test_load_repositories_executes_upsert():
    # 1. Create a sample transformed repository
    repositories_df = pd.DataFrame({
        "id": [12345],
        "name": ["etl-demo"],
        "full_name": ["sivasankar070/etl-demo"],
        "description": ["A sample ETL project"],
        "html_url": ["https://github.com/example/etl-demo"],
        "private": [False],
        "fork": [False],
        "created_at": [pd.Timestamp("2025-01-01T10:00:00Z")],
        "updated_at": [pd.Timestamp("2025-02-01T10:00:00Z")],
        "pushed_at": [pd.Timestamp("2025-02-01T10:00:00Z")],
        "size": [100],
        "stargazers_count": [10],
        "forks_count": [2],
        "open_issues_count": [1],
        "language": ["Python"],
        "visibility": ["public"],
        "archived": [False],
        "disabled": [False],
        "default_branch": ["main"],
    })

    # 2. Create a fake database connection
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value

    # 3. Run the loader
    load_repositories(conn, repositories_df)

    # 4. Verify that one SQL statement was executed
    cursor.execute.assert_called_once()

    query, parameters = cursor.execute.call_args.args

    # 5. Verify the SQL uses the expected table and upsert
    assert "INSERT INTO github.repositories" in query
    assert "ON CONFLICT (id)" in query
    assert "DO UPDATE SET" in query

    # 6. Verify the repository ID was passed to PostgreSQL
    assert parameters[0] == 12345

    # The loader must not commit the transaction itself
    conn.commit.assert_not_called()

def test_load_repository_topics_refreshes_data():
    # Two repositories: one has topics; the other has none.
    repository_ids = [12345, 67890]

    repository_topics_df = pd.DataFrame({
        "repository_id": [12345, 12345],
        "topic": ["python", "etl"],
    })

    # Create a mock database connection and cursor.
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value

    # Simulate one deleted row for each DELETE statement.
    cursor.rowcount = 1

    # Execute the loader.
    load_repository_topics(
        conn,
        repository_topics_df,
        repository_ids,
    )

    calls = cursor.execute.call_args_list

    # Expect two DELETE statements and two INSERT statements.
    assert len(calls) == 4

    # Verify deletion happens for both repository IDs,
    # including repository 67890, which has no current topics.
    assert "DELETE FROM github.repository_topics" in calls[0].args[0]
    assert calls[0].args[1] == (12345,)

    assert "DELETE FROM github.repository_topics" in calls[1].args[0]
    assert calls[1].args[1] == (67890,)

    # Verify the current topic relationships are inserted.
    assert "INSERT INTO github.repository_topics" in calls[2].args[0]
    assert calls[2].args[1] == (12345, "python")

    assert "INSERT INTO github.repository_topics" in calls[3].args[0]
    assert calls[3].args[1] == (12345, "etl")

    # Transaction control belongs to main.py.
    conn.commit.assert_not_called()

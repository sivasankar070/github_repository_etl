import pandas as pd
import pytest
from unittest.mock import Mock

import src.main as main_module


def test_main_rolls_back_when_topic_loading_fails(monkeypatch):
    # Arrange: prepare fake ETL results and a fake connection
    conn = Mock()

    repositories_df = pd.DataFrame({
        "id": [12345],
    })

    repository_topics_df = pd.DataFrame({
        "repository_id": [12345],
        "topic": ["python"],
    })

    # Replace extraction and transformation with controlled results
    monkeypatch.setattr(
        main_module,
        "extract_repositories",
        Mock(return_value=[{"id": 12345}]),
    )

    monkeypatch.setattr(
        main_module,
        "transform_data",
        Mock(return_value=(repositories_df, repository_topics_df)),
    )

    monkeypatch.setattr(
        main_module,
        "get_connection",
        Mock(return_value=conn),
    )

    # Repository loading succeeds, but topic loading fails
    monkeypatch.setattr(
        main_module,
        "load_repositories",
        Mock(),
    )

    monkeypatch.setattr(
        main_module,
        "load_repository_topics",
        Mock(side_effect=RuntimeError("Simulated topic loading failure")),
    )

    # Act and assert: the original error must propagate
    with pytest.raises(
        RuntimeError,
        match="Simulated topic loading failure",
    ):
        main_module.main("test-owner", "users")

    # Assert transaction and connection behavior
    conn.commit.assert_not_called()
    conn.rollback.assert_called_once()
    conn.close.assert_called_once()


def test_main_commits_when_pipeline_succeeds(monkeypatch):
    # Arrange: create sample data and a mock connection
    conn = Mock()

    repositories_df = pd.DataFrame({
        "id": [12345],
    })

    repository_topics_df = pd.DataFrame({
        "repository_id": [12345],
        "topic": ["python"],
    })

    # Simulate successful extraction
    monkeypatch.setattr(
        main_module,
        "extract_repositories",
        Mock(return_value=[{"id": 12345}]),
    )

    # Simulate successful transformation
    monkeypatch.setattr(
        main_module,
        "transform_data",
        Mock(return_value=(repositories_df, repository_topics_df)),
    )

    # Return the mock database connection
    monkeypatch.setattr(
        main_module,
        "get_connection",
        Mock(return_value=conn),
    )

    # Simulate successful loading of both tables
    monkeypatch.setattr(
        main_module,
        "load_repositories",
        Mock(),
    )

    monkeypatch.setattr(
        main_module,
        "load_repository_topics",
        Mock(),
    )

    # Act: execute the pipeline
    main_module.main("test-owner", "user")

    # Assert: verify transaction and cleanup
    conn.commit.assert_called_once()
    conn.rollback.assert_not_called()
    conn.close.assert_called_once()

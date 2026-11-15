
import json
from unittest.mock import Mock
import pytest

from src import extract as extract_module


def make_response(data, status_code=200):
    """Create a simulated HTTP response."""
    response = Mock()
    response.status_code = status_code
    response.json.return_value = data
    response.raise_for_status.return_value = None
    return response


def test_extract_repositories_success(monkeypatch, tmp_path):
    # 1. Simulate the GitHub token
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    # 2. Use a temporary output file for this test
    output_file = tmp_path / "repositories.json"
    monkeypatch.setattr(extract_module, "RAW_FILE", output_file)

    # 3. Simulate the API data
    api_data = [
        {
            "id": 101,
            "name": "test-repo",
            "full_name": "sivasankar070/test-repo",
        }
    ]

    # First response contains a repository.
    # Second response is empty, ending pagination.
    mock_get = Mock(
        side_effect=[
            make_response(api_data),
            make_response([]),
        ]
    )

    # 4. Replace the real HTTP request with our mock
    monkeypatch.setattr(
        extract_module.requests,
        "get",
        mock_get
    )

    # 5. Execute the extraction function
    result = extract_module.extract_repositories(
        "sivasankar070",
        "users"
    )

    # 6. Verify the results
    assert result == api_data
    assert output_file.exists()

    saved_data = json.loads(
        output_file.read_text(encoding="utf-8")
    )
    assert saved_data == api_data

    # Verify pagination made two requests
    assert mock_get.call_count == 2

    # Verify the correct endpoint and authentication header
    first_call = mock_get.call_args_list[0]
    assert "/users/sivasankar070/repos" in first_call.args[0]
    assert (
        first_call.kwargs["headers"]["Authorization"]
        == "Bearer test-token"
    )


def test_extract_repositories_http_error(monkeypatch, caplog):
    # 1. Provide a test token
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")

    # 2. Create a simulated HTTP 404 response
    error_response = make_response([], status_code=404)

    error_response.raise_for_status.side_effect = (
        extract_module.requests.exceptions.HTTPError(
            "404 Client Error"
        )
    )

    # 3. Replace the real API request with our simulated response
    mock_get = Mock(return_value=error_response)

    monkeypatch.setattr(
        extract_module.requests,
        "get",
        mock_get
    )

    # 4. Verify that the extraction function raises the error
    with pytest.raises(
        extract_module.requests.exceptions.HTTPError,
        match="404 Client Error"
    ):
        extract_module.extract_repositories(
            "invalid-owner",
            "users"
        )

    # 5. Verify that the failure was logged
    assert "Extraction failed" in caplog.text
    assert "status=404" in caplog.text

    # Only one request should be made before the failure
    assert mock_get.call_count == 1

def test_extract_repositories_missing_token(monkeypatch, caplog):
    # 1. Remove the token for this test
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    # 2. Mock the API request so no real request can happen
    mock_get = Mock()

    monkeypatch.setattr(
        extract_module.requests,
        "get",
        mock_get
    )

    # 3. Verify that extraction raises an error
    with pytest.raises(
        ValueError,
        match="GitHub token not found"
    ):
        extract_module.extract_repositories(
            "sivasankar070",
            "users"
        )

    # 4. Verify that the error was logged
    assert "Extraction failed" in caplog.text

    # 5. Verify that no API request was made
    mock_get.assert_not_called()
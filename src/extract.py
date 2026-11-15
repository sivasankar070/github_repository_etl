
from dotenv import load_dotenv
from pathlib import Path
import os
import requests
import logging
import json

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_FILE = BASE_DIR / "data" / "raw" / "repositories.json"

logger = logging.getLogger(__name__)

load_dotenv(BASE_DIR / ".env")


def extract_repositories(owner, account_type="user"):
    logger.info(
        "Extraction started | owner=%s | account_type=%s",
        owner,
        account_type
    )

    stage = "validating configuration"
    page = None
    url = None
    status = None

    try:
        # 1. Validate GitHub token
        github_token = os.getenv("GITHUB_TOKEN")

        if not github_token:
            raise ValueError("GitHub token not found in environment")

        # 2. Prepare output directory
        stage = "preparing output directory"
        RAW_FILE.parent.mkdir(parents=True, exist_ok=True)

        repos = []
        page = 1

        headers = {
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json"
        }

        # 3. Fetch all repository pages
        while True:
            stage = "requesting GitHub API"

            url = (
                f"https://api.github.com/{account_type}/{owner}/repos"
                f"?per_page=100&page={page}"
            )

            response = requests.get(
                url,
                headers=headers,
                timeout=10
            )

            status = response.status_code
            response.raise_for_status()

            # 4. Validate API response
            stage = "validating API response"
            data = response.json()

            if not isinstance(data, list):
                raise ValueError(
                    f"Unexpected API response on page {page}: "
                    "expected a list of repositories"
                )

            if not data:
                logger.info(
                    "No more repositories returned | page=%s",
                    page
                )
                break

            repos.extend(data)

            logger.info(
                "Fetched page %s | repositories_fetched=%s | "
                "total_repositories=%s",
                page,
                len(data),
                len(repos)
            )

            page += 1

        # 5. Save raw API response
        stage = "writing raw JSON"
        with RAW_FILE.open("w", encoding="utf-8") as file:
            json.dump(
                repos,
                file,
                indent=4,
                ensure_ascii=False
            )

        logger.info(
            "Extraction completed | owner=%s | total_repositories=%s "
            "| output=%s",
            owner,
            len(repos),
            RAW_FILE
        )

        return repos

    except Exception:
        logger.exception(
            "Extraction failed | owner=%s | stage=%s | page=%s "
            "| status=%s | url=%s",
            owner,
            stage,
            page if page is not None else "N/A",
            status if status is not None else "N/A",
            url if url is not None else "N/A"
        )
        raise

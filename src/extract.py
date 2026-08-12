from dotenv import load_dotenv
from pathlib import Path
import os
import requests
import logging
import json

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

logger = logging.getLogger(__name__)

load_dotenv()

github_token = os.getenv("GITHUB_TOKEN")

if not github_token:
    raise ValueError("Github token not found")

logger.info("Starting extraction")


def extract_repositories(owner):
    repos = []
    page = 1

    while True:
        url = f"https://api.github.com/orgs/{owner}/repos?per_page=100&page={page}"

        headers = {
            "Authorization": f"Bearer {github_token}",
            "Accept": "application/vnd.github+json"
        }

        response = None

        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()

        except requests.exceptions.RequestException as e:
            status = response.status_code if response is not None else "N/A"

            logger.error(
                "request failed | page=%s | status=%s | url=%s | error=%s",
                page,
                status,
                url,
                e
            )
            raise

        if not data:
            break
        repos.extend(data)

        logger.info("Fetched page %s with %s repositories", page, len(data))

        page += 1
    return repos

data = extract_repositories('openai')

with open(Path.cwd() / "data/raw/repositories.json","w", encoding="utf-8") as f:
    json.dump(data, f, indent = 4)

logger.info("Extraction completed")
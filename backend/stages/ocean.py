import time

import requests

from config import OCEAN_API_KEY
from utils.logger import logger

_ENDPOINT = "https://api.ocean.io/v2/search/companies"
_MAX_RESULTS = 50
_PAGE_SIZE = 25


def find_lookalike_companies(seed_domain: str) -> list[str]:
    """Return up to 50 lookalike company domains for the given seed domain."""
    headers = {
        "x-api-token": OCEAN_API_KEY,
        "Content-Type": "application/json",
    }

    seen: set[str] = set()
    search_after: list | None = None
    first_page = True

    while len(seen) < _MAX_RESULTS:
        payload: dict = {
            "companiesFilters": {
                "lookalikeDomains": [seed_domain],
            },
            "size": min(_PAGE_SIZE, _MAX_RESULTS - len(seen)),
            "fields": ["domain"],
        }
        if search_after is not None:
            payload["searchAfter"] = search_after

        if not first_page:
            time.sleep(1)
        first_page = False

        response = requests.post(_ENDPOINT, json=payload, headers=headers, timeout=30)

        if not response.ok:
            raise Exception(
                f"Ocean.io API error {response.status_code}: {response.text}"
            )

        data: dict = response.json()
        companies: list[dict] = data.get("companies", [])

        for company in companies:
            domain: str | None = company.get("domain")
            if domain:
                seen.add(domain)

        search_after = data.get("searchAfter")
        if not search_after or not companies:
            break

    result = list(seen)[:_MAX_RESULTS]

    if not result:
        raise Exception(
            f"Ocean.io returned 0 lookalike companies for '{seed_domain}'"
        )

    logger.info("Ocean: found %d lookalike domains for %s", len(result), seed_domain)
    return result

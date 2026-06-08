import requests

from config import APOLLO_API_KEY
from utils.logger import logger

_ENDPOINT = "https://api.apollo.io/v1/people/search"

# Apollo accepts a list of titles and does partial matching
_SENIORITY_TITLES = [
    "CEO", "CTO", "CMO", "CFO", "COO",
    "VP", "Vice President",
    "Director",
    "Head",
    "Founder", "Co-Founder",
    "President",
]


def find_decision_makers(domains: list[str]) -> list[dict]:
    """Find C-suite / VP-level decision makers at the given domains via Apollo people search."""
    headers = {
        "x-api-key": APOLLO_API_KEY,
        "Content-Type": "application/json",
    }

    resp = requests.post(
        _ENDPOINT,
        json={
            "organization_domains": domains,
            "person_titles": _SENIORITY_TITLES,
            "page": 1,
            "per_page": 10,
        },
        headers=headers,
        timeout=30,
    )

    if not resp.ok:
        raise Exception(
            f"Apollo people search error {resp.status_code}: {resp.text}"
        )

    people: list[dict] = resp.json().get("people", [])

    seen_linkedin: set[str] = set()
    results: list[dict] = []

    for person in people:
        linkedin_url: str = person.get("linkedin_url") or ""
        if not linkedin_url or linkedin_url in seen_linkedin:
            continue
        seen_linkedin.add(linkedin_url)

        domain: str = (person.get("organization") or {}).get("primary_domain") or ""

        results.append({
            "name":         person.get("name") or "",
            "title":        person.get("title") or "",
            "domain":       domain,
            "linkedin_url": linkedin_url,
        })

    logger.info(
        "Apollo people: found %d decision makers across %d domains",
        len(results), len(domains),
    )
    return results

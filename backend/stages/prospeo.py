import requests

from utils.rate_limiter import rate_limit, retry
from config import PROSPEO_API_KEY
from utils.logger import logger

_ENDPOINT = "https://api.prospeo.io/domain-search"
_RATE_DELAY = 1.5

_SENIORITY_KEYWORDS = (
    "ceo", "cto", "cmo", "cfo", "coo",
    "vp", "vice president",
    "director",
    "head of",
    "founder", "co-founder",
    "president",
)


def _is_decision_maker(title: str) -> bool:
    t = title.lower()
    return any(kw in t for kw in _SENIORITY_KEYWORDS)


@retry(max_attempts=3, delay=2, backoff=2)
def _fetch_people(domain: str, headers: dict) -> list[dict]:
    """Call Prospeo domain-search and return the raw people list. Raises on any error."""
    response = requests.post(
        _ENDPOINT,
        json={"company": domain, "limit": 10},
        headers=headers,
        timeout=30,
    )
    if not response.ok:
        raise Exception(f"HTTP {response.status_code}: {response.text}")
    data: dict = response.json()
    if data.get("error"):
        raise Exception(f"API error: {data.get('message', 'unknown')}")
    return data.get("people", [])


def find_decision_makers(domains: list[str]) -> list[dict]:
    """Return C-suite / VP-level decision makers found across the given domains."""
    headers = {
        "X-KEY": PROSPEO_API_KEY,
        "Content-Type": "application/json",
    }

    seen_linkedin: set[str] = set()
    results: list[dict] = []
    total = len(domains)

    for i, domain in enumerate(domains, start=1):
        logger.info("Prospeo: processing domain %d of %d: %s", i, total, domain)

        try:
            people = _fetch_people(domain, headers)
        except Exception as exc:
            logger.error("Prospeo: failed for %s — %s", domain, exc)
            if i < total:
                rate_limit(_RATE_DELAY)
            continue

        for person in people:
            title: str = person.get("current_job_title") or ""
            if not _is_decision_maker(title):
                continue

            linkedin_url: str = person.get("linkedin_url") or ""
            if not linkedin_url:
                continue

            if linkedin_url in seen_linkedin:
                continue
            seen_linkedin.add(linkedin_url)

            results.append({
                "name": person.get("full_name") or "",
                "title": title,
                "domain": domain,
                "linkedin_url": linkedin_url,
            })

        if i < total:
            rate_limit(_RATE_DELAY)

    logger.info(
        "Prospeo: found %d decision makers across %d domains",
        len(results), total,
    )
    return results

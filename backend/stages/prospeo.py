import requests

from config import SNOV_CLIENT_ID, SNOV_CLIENT_SECRET
from utils.rate_limiter import rate_limit
from utils.logger import logger

_TOKEN_URL   = "https://api.snov.io/v1/oauth/access_token"
_SEARCH_URL  = "https://api.snov.io/v2/domain-emails-with-info"
_RATE_DELAY  = 1.0
_MAX_DOMAINS = 5

# Snov.io seniority values that qualify as decision makers
_SENIORITY_LEVELS = {"c_suite", "vp", "director"}

_SENIORITY_KEYWORDS = (
    "ceo", "cto", "cmo", "cfo", "coo",
    "vp", "vice president",
    "director",
    "head of",
    "founder", "co-founder",
    "president",
)


def _get_token() -> str:
    resp = requests.post(
        _TOKEN_URL,
        json={
            "grant_type":    "client_credentials",
            "client_id":     SNOV_CLIENT_ID,
            "client_secret": SNOV_CLIENT_SECRET,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _is_decision_maker(title: str, seniority: str) -> bool:
    if seniority.lower() in _SENIORITY_LEVELS:
        return True
    t = title.lower()
    return any(kw in t for kw in _SENIORITY_KEYWORDS)


def find_decision_makers(domains: list[str]) -> list[dict]:
    """Find decision makers at the given domains via Snov.io domain search.
    Returns people dicts that already include email — Eazyreach will pass them through."""
    token = _get_token()

    domains = domains[:_MAX_DOMAINS]
    seen_emails: set[str] = set()
    results: list[dict] = []
    total = len(domains)

    for i, domain in enumerate(domains, start=1):
        logger.info("Snov.io: processing domain %d of %d: %s", i, total, domain)

        try:
            resp = requests.post(
                _SEARCH_URL,
                data={
                    "access_token": token,
                    "domain":       domain,
                    "type":         "personal",
                    "limit":        5,
                },
                timeout=30,
            )

            if not resp.ok:
                logger.error("Snov: failed for %s — HTTP %s: %s", domain, resp.status_code, resp.text)
                if i < total:
                    rate_limit(_RATE_DELAY)
                continue

            emails: list[dict] = resp.json().get("emails", [])

            for person in emails:
                title:    str = person.get("position")  or ""
                seniority:str = person.get("seniority") or ""
                email:    str = person.get("email")     or ""

                if not email:
                    continue
                if not _is_decision_maker(title, seniority):
                    continue
                if email in seen_emails:
                    continue
                seen_emails.add(email)

                first = person.get("firstName") or ""
                last  = person.get("lastName")  or ""
                name  = f"{first} {last}".strip()

                results.append({
                    "name":         name,
                    "title":        title,
                    "domain":       domain,
                    "email":        email,
                    "linkedin_url": person.get("linkedIn") or "",
                })

        except Exception as exc:
            logger.error("Snov: failed for %s — %s", domain, exc)

        if i < total:
            rate_limit(_RATE_DELAY)

    logger.info("Snov.io: found %d decision makers across %d domains", len(results), total)
    return results

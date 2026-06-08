import time

import requests

from config import APOLLO_API_KEY
from utils.logger import logger

_ENRICH_URL = "https://api.apollo.io/v1/organizations/enrich"
_SEARCH_URL = "https://api.apollo.io/v1/mixed_companies/search"
_PER_PAGE   = 25
_MAX_PAGES  = 2   # 50 results max — keeps free-tier credit usage low


def find_lookalike_companies(seed_domain: str) -> list[str]:
    headers = {
        "x-api-key": APOLLO_API_KEY,
        "Content-Type": "application/json",
    }

    # ── Step 1: Enrich seed domain to get industry tag ────────────────────
    industry_tag_id: str | None = None
    try:
        resp = requests.post(
            _ENRICH_URL,
            json={"domain": seed_domain},
            headers=headers,
            timeout=30,
        )
        if resp.ok:
            org = resp.json().get("organization") or {}
            industry_tag_id = org.get("industry_tag_id") or None
            logger.info(
                "Apollo enrich: domain=%s industry_tag_id=%s",
                seed_domain, industry_tag_id,
            )
        else:
            logger.warning(
                "Apollo enrich failed (%s) — falling back to keyword search",
                resp.status_code,
            )
    except Exception as exc:
        logger.warning("Apollo enrich error — falling back to keyword search: %s", exc)

    time.sleep(1.5)

    # ── Step 2: Search for similar companies (2 pages max = 50 results) ───
    seen: set[str] = set()

    for page in range(1, _MAX_PAGES + 1):
        payload: dict = {
            "organization_num_employees_ranges": ["1,500"],
            "page": page,
            "per_page": _PER_PAGE,
        }

        if industry_tag_id:
            payload["organization_industry_tag_ids"] = [industry_tag_id]
        else:
            # fallback: derive keyword from seed domain (e.g. "stripe" from "stripe.com")
            keyword = seed_domain.split(".")[0]
            payload["q_organization_keyword_tags"] = [keyword]

        resp = requests.post(
            _SEARCH_URL,
            json=payload,
            headers=headers,
            timeout=30,
        )

        if not resp.ok:
            raise Exception(
                f"Apollo search error {resp.status_code}: {resp.text}"
            )

        organizations: list[dict] = resp.json().get("organizations", [])

        for org in organizations:
            domain: str | None = org.get("primary_domain") or None
            if domain and domain != seed_domain:
                seen.add(domain)

        # stop early if Apollo returned a partial page (no more results)
        if len(organizations) < _PER_PAGE:
            break

        if page < _MAX_PAGES:
            time.sleep(1.5)

    result = list(seen)

    if not result:
        raise Exception(
            f"Apollo: no lookalike companies found for {seed_domain}"
        )

    logger.info("Apollo.io: found %d lookalike companies for %s", len(result), seed_domain)
    return result

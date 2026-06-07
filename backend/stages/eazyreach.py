import requests

from utils.rate_limiter import rate_limit, retry
from config import EAZYREACH_API_KEY
from utils.logger import logger

# Verify this endpoint and response field names against your Eazyreach account.
_ENDPOINT = "https://api.eazyreach.app/v1/email-finder"
_RATE_DELAY = 2.0
_MIN_CONFIDENCE = 80


class _CreditsExhausted(Exception):
    """Raised on HTTP 402 so the caller can stop the pipeline immediately."""


@retry(max_attempts=3, delay=2, backoff=2)
def _request(linkedin_url: str, headers: dict) -> requests.Response:
    """Raw HTTP POST. Only raises on network-level failures (timeout, DNS, etc.).
    Returns the Response object for any HTTP status, so @retry never sees 402.
    """
    return requests.post(
        _ENDPOINT,
        json={"linkedin_url": linkedin_url},
        headers=headers,
        timeout=30,
    )


def _post(linkedin_url: str, headers: dict) -> dict:
    """Call _request(), then check status codes. Credits exhaustion propagates immediately."""
    response = _request(linkedin_url, headers)

    if response.status_code == 402:
        raise _CreditsExhausted(response.text)

    if not response.ok:
        raise Exception(f"HTTP {response.status_code}: {response.text}")

    return response.json()


def _safe_confidence(value) -> int:
    try:
        return int(value or 0)
    except (ValueError, TypeError):
        return 0


def resolve_emails(people: list[dict]) -> list[dict]:
    """Resolve each person's linkedin_url to a verified work email via Eazyreach."""
    headers = {
        "X-API-KEY": EAZYREACH_API_KEY,
        "Content-Type": "application/json",
    }

    results: list[dict] = []
    total = len(people)

    for i, person in enumerate(people, start=1):
        linkedin_url: str = person.get("linkedin_url", "")
        name: str = person.get("name", "unknown")

        data: dict | None = None
        try:
            data = _post(linkedin_url, headers)
        except _CreditsExhausted as exc:
            raise Exception(
                f"EazyReach credits exhausted — stopping pipeline: {exc}"
            ) from exc
        except Exception as exc:
            logger.error("EazyReach: skipping %s — %s", name, exc)

        if data is None:
            if i < total:
                rate_limit(_RATE_DELAY)
            continue

        # Some APIs signal credits exhaustion via 200 + error body
        error_msg: str = str(data.get("error") or "").lower()
        if "credit" in error_msg and ("exhaust" in error_msg or "out" in error_msg):
            raise Exception(
                f"EazyReach credits exhausted: {data.get('message', error_msg)}"
            )

        email: str = data.get("email") or ""
        verified: bool = bool(data.get("verified", False))
        confidence: int = _safe_confidence(data.get("confidence"))

        if email and verified and confidence >= _MIN_CONFIDENCE:
            logger.info("EazyReach: Resolved: %s -> %s", name, email)
            results.append({**person, "email": email})
        else:
            logger.info("EazyReach: Skipped: %s (no email found)", name)

        if i < total:
            rate_limit(_RATE_DELAY)

    logger.info(
        "EazyReach: resolved %d of %d people to verified emails",
        len(results), total,
    )
    return results

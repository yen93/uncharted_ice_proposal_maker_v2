"""Best-guess client logo URL, with no network call of our own. Copied from
../uncharted_ice_proposal_maker/src/logo_service.py.

Builds a Google favicon URL from the highest-priority guessed domain and returns
it unvalidated. That URL is only ever fetched by Slides' replaceImage, server-side
on Google's infrastructure — never by this process — so it works regardless of
this process's network access. It is a GUESS, not a confirmed match: callers must
surface it for human review. (Clearbit's logo API was discontinued in 2026-08.)
"""

import re

_SUFFIXES = re.compile(
    r"\b(pty|ltd|limited|llc|inc|incorporated|corp|corporation|company|co|group)\b",
    re.IGNORECASE,
)
_NON_ALNUM = re.compile(r"[^a-z0-9]+")

CANDIDATE_TLDS = [".com.au", ".com", ".co"]


def _guess_domains(client_org: str) -> list[str]:
    name = _SUFFIXES.sub("", client_org.lower())
    slug = _NON_ALNUM.sub("", name)
    if not slug:
        return []
    return [f"{slug}{tld}" for tld in CANDIDATE_TLDS]


def find_logo_url(client_org: str, client_domain: str = "") -> dict:
    """Returns {logo_url, domain}. Prefers an explicit `client_domain` (e.g. one
    the transcription guessed) over a name-derived guess. Returns
    {logo_url: None, domain: None} if there's nothing to guess from. Never raises.
    The URL is an unverified guess — flag it for human review."""
    domain = (client_domain or "").strip().lower()
    if not domain:
        domains = _guess_domains(client_org)
        if not domains:
            return {"logo_url": None, "domain": None}
        domain = domains[0]
    # normalise a pasted URL down to a bare domain
    domain = re.sub(r"^https?://", "", domain).split("/")[0]
    return {
        "logo_url": f"https://www.google.com/s2/favicons?domain={domain}&sz=256",
        "domain": domain,
    }

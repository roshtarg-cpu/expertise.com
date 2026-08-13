"""
Parser for Expertise.com — Next.js App Router site.

The site uses RSC (React Server Components) streaming via self.__next_f.push([1, "..."]).
There is no __NEXT_DATA__ JSON blob. Professional listings live in a "providers" array
embedded within the RSC payload string. HTML <article> tags carry data-position,
data-featured, and an id slug for each provider card.

Confirmed from live inspection of:
  https://www.expertise.com/legal/personal-injury-lawyers/texas/dallas
"""

from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Optional

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Debug helper — run this first to confirm data structure
# ---------------------------------------------------------------------------

def debug_structure(html: str, url: str) -> None:
    """Print the real data structure from the RSC payload for a given page."""
    print(f"\n{'='*60}")
    print(f"DEBUG: Inspecting {url}")
    print(f"{'='*60}")

    rsc = _combine_rsc_payloads(html)
    print(f"Combined RSC payload length: {len(rsc)} chars")

    # Check for __NEXT_DATA__ (legacy Next.js pages pages)
    if '__NEXT_DATA__' in html:
        print("Found __NEXT_DATA__ (legacy Next.js page)")
    else:
        print("No __NEXT_DATA__ - uses Next.js App Router RSC streaming (expected)")

    # Confirm providers array
    providers_idx = rsc.find('"providers":[')
    if providers_idx != -1:
        print(f"\n[OK] Found 'providers' array at RSC offset {providers_idx}")
        # Show first provider fields
        provider_start = rsc.find('{"__typename":"Provider"', providers_idx)
        if provider_start != -1:
            sample = rsc[provider_start:provider_start + 400]
            print(f"\nFirst provider sample:\n{sample}\n...")
    else:
        print("\n[FAIL] 'providers' array NOT found — site may have changed structure")

    # Article count from HTML
    soup = BeautifulSoup(html, "lxml")
    articles = soup.find_all("article", attrs={"data-providerid": True})
    print(f"\n[OK] Found {len(articles)} <article> provider cards in HTML")
    if articles:
        a = articles[0]
        print(f"  First article: id='{a.get('id')}' data-providerid='{a.get('data-providerid')}'"
              f" data-position='{a.get('data-position')}' data-featured='{a.get('data-featured')}'")

    # Vertical/category data
    verticals = _extract_verticals_from_rsc(rsc)
    print(f"\n[OK] Found {len(verticals)} verticals/categories on this page")
    if verticals:
        print(f"  Sample vertical: {verticals[0]}")

    print(f"\n{'='*60}\n")


# ---------------------------------------------------------------------------
# RSC payload extraction
# ---------------------------------------------------------------------------

def _combine_rsc_payloads(html: str) -> str:
    """Concatenate all self.__next_f.push([1, "..."]) string payloads."""
    payloads = re.findall(r'self\.__next_f\.push\(\[1,(.*?)\]\)', html, re.DOTALL)
    combined = ""
    for raw in payloads:
        try:
            decoded = json.loads(raw)
            if isinstance(decoded, str):
                combined += decoded
        except (json.JSONDecodeError, ValueError):
            pass
    return combined


def _extract_json_array(text: str, key: str) -> Optional[str]:
    """
    Extract a JSON array value by key from an RSC payload string.
    Uses bracket counting to find the matching close bracket.
    """
    pattern = f'"{key}":'
    idx = text.find(pattern)
    if idx == -1:
        return None

    start = idx + len(pattern)
    while start < len(text) and text[start] in " \t\n\r":
        start += 1

    if start >= len(text) or text[start] != "[":
        return None

    depth = 0
    pos = start
    in_string = False
    escape_next = False

    while pos < len(text):
        c = text[pos]
        if escape_next:
            escape_next = False
        elif c == "\\" and in_string:
            escape_next = True
        elif c == '"' and not in_string:
            in_string = True
        elif c == '"' and in_string:
            in_string = False
        elif not in_string:
            if c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    return text[start : pos + 1]
        pos += 1

    return None


# ---------------------------------------------------------------------------
# City and state discovery
# ---------------------------------------------------------------------------

def extract_city_links(html: str, state: str) -> list[str]:
    """
    Extract city slugs from a state page (e.g. /texas).
    Returns slugs like ['dallas', 'houston', 'austin', ...].
    """
    pattern = rf'href="/{re.escape(state)}/([a-z][a-z0-9-]+)"'
    slugs = re.findall(pattern, html)
    # Deduplicate while preserving order
    seen: set[str] = set()
    result = []
    for s in slugs:
        if s not in seen:
            seen.add(s)
            result.append(s)
    return result


def _extract_verticals_from_rsc(rsc: str) -> list[dict]:
    """
    Extract verticals (service categories) from an RSC payload.
    Returns list of dicts with keys: name, slug, cSlug.
    Confirmed field names from live site: name, slug, cSlug.
    """
    matches = re.findall(
        r'\{"name":"([^"]+)","slug":"([^"]+)","cSlug":"([^"]+)"[^}]*\}',
        rsc,
    )
    seen: set[tuple] = set()
    result = []
    for name, slug, cslug in matches:
        key = (slug, cslug)
        if key not in seen:
            seen.add(key)
            result.append({"name": name, "slug": slug, "cSlug": cslug})
    return result


def extract_city_verticals(html: str) -> list[dict]:
    """
    Extract all service category verticals from a city page.
    Returns list of dicts with: name, slug, cSlug.
    """
    rsc = _combine_rsc_payloads(html)
    return _extract_verticals_from_rsc(rsc)


def find_cslug_for_category(html: str, category_slug: str) -> Optional[str]:
    """
    Given a city page HTML and a category slug, return its cSlug (category group).
    E.g. 'personal-injury-lawyers' → 'legal', 'roofing' → 'home-improvement'.
    """
    verticals = extract_city_verticals(html)
    for v in verticals:
        if v["slug"] == category_slug:
            return v["cSlug"]
    return None


# ---------------------------------------------------------------------------
# Provider extraction from listing page
# ---------------------------------------------------------------------------

def _parse_html_articles(html: str, listing_url: str) -> dict[str, dict]:
    """
    Parse <article data-providerid="..."> tags for position, featured, and slug.
    Returns dict keyed by provider id (str).
    """
    soup = BeautifulSoup(html, "lxml")
    articles = soup.find_all("article", attrs={"data-providerid": True})
    result: dict[str, dict] = {}
    for art in articles:
        pid = art.get("data-providerid", "")
        position_raw = art.get("data-position")
        slug = art.get("id", "")
        featured_raw = art.get("data-featured", "false")
        result[pid] = {
            "ranking": int(position_raw) if position_raw and position_raw.isdigit() else None,
            "isFeatured": featured_raw.lower() == "true",
            "articleSlug": slug,
            "profileUrl": f"{listing_url}#{slug}" if slug else listing_url,
        }
    return result


def _format_phone(raw: Optional[str]) -> Optional[str]:
    """Normalize phone to US format e.g. '4693012400' → '(469) 301-2400'."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) == 10:
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
    return raw  # return as-is if not standard


def _extract_score(score_obj: Optional[dict]) -> Optional[float]:
    """Extract averageScore from a ProviderScore object."""
    if not score_obj or not isinstance(score_obj, dict):
        return None
    val = score_obj.get("averageScore")
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def _extract_ratings(ratings_obj: Optional[dict]) -> tuple[Optional[float], Optional[int]]:
    """Return (average_rating, total_reviews) from a ProviderRatings object."""
    if not ratings_obj or not isinstance(ratings_obj, dict):
        return None, None
    avg_raw = ratings_obj.get("averageScore")
    total = ratings_obj.get("totalReviews")
    try:
        avg = float(avg_raw) if avg_raw is not None else None
    except (TypeError, ValueError):
        avg = None
    try:
        count = int(total) if total is not None else None
    except (TypeError, ValueError):
        count = None
    return avg, count


def _extract_tags(tags_list: Optional[list]) -> Optional[list[str]]:
    """Extract specialty/service tag names from ProviderTags array."""
    if not tags_list:
        return None
    names = []
    for item in tags_list:
        if isinstance(item, dict):
            tag = item.get("tag", {})
            if isinstance(tag, dict) and tag.get("name"):
                names.append(tag["name"])
    return names or None


def _extract_member_info(members: Optional[list]) -> Optional[str]:
    """Extract primary contact name from members array."""
    if not members:
        return None
    for m in members:
        if isinstance(m, dict) and m.get("contactName"):
            return m["contactName"]
    return None


def _build_provider_record(
    provider: dict,
    html_meta: dict,
    listing_url: str,
    category_slug: str,
    city_slug: str,
    state_slug: str,
) -> dict:
    """
    Combine RSC provider dict + HTML article metadata into a final output record.
    Only uses REAL field names confirmed from live site inspection.
    """
    phone_raw = provider.get("phone") or (
        (provider.get("cta_setting") or {}).get("call_us_number")
    )

    rating, review_count = _extract_ratings(provider.get("ratings"))
    expertise_score = _extract_score(provider.get("score"))

    website = provider.get("businessWebsite") or (
        (provider.get("cta_setting") or {}).get("landing_page")
    )

    address_parts = [
        p for p in [
            provider.get("businessAddress"),
            provider.get("city"),
            provider.get("state"),
            provider.get("zipCode"),
        ] if p
    ]
    address = ", ".join(address_parts) if address_parts else None

    return {
        "businessName": provider.get("businessName"),
        "profileUrl": html_meta.get("profileUrl", listing_url),
        "ranking": html_meta.get("ranking"),
        "isFeatured": html_meta.get("isFeatured", False),
        "category": category_slug,
        "city": provider.get("city") or city_slug,
        "state": provider.get("state") or state_slug.upper(),
        "address": address,
        "phone": _format_phone(phone_raw),
        "website": website if not provider.get("hideWebsite") else None,
        "rating": rating,
        "reviewCount": review_count,
        "expertiseScore": expertise_score,
        "description": provider.get("snippet") or None,
        "services": _extract_tags(provider.get("tags")),
        "licenseNumber": provider.get("licenseNumber") or None,
        "licenseStatus": provider.get("licenseStatus") or None,
        "isVerified": bool(provider.get("boosted")),
        "primaryContact": _extract_member_info(provider.get("members")),
        "providerId": provider.get("id"),
        "scrapedAt": datetime.now(timezone.utc).isoformat(),
    }


def parse_listing_page(
    html: str,
    listing_url: str,
    category_slug: str,
    city_slug: str,
    state_slug: str,
) -> list[dict]:
    """
    Parse a category+city listing page and return a list of provider records.

    Steps:
    1. Combine RSC payloads from self.__next_f.push([1, ...])
    2. Extract the 'providers' JSON array (real field name confirmed from live site)
    3. Parse HTML <article> tags for position, featured, and slug
    4. Merge both sources into output records
    """
    rsc = _combine_rsc_payloads(html)

    # Extract providers JSON array from RSC payload
    providers_json_str = _extract_json_array(rsc, "providers")
    if not providers_json_str:
        logger.warning("No 'providers' array found in RSC payload for %s", listing_url)
        return []

    try:
        providers_list: list[dict] = json.loads(providers_json_str)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse providers JSON for %s: %s", listing_url, exc)
        return []

    # Parse HTML articles for position/slug metadata
    html_meta_by_id = _parse_html_articles(html, listing_url)

    records = []
    for provider in providers_list:
        if not isinstance(provider, dict):
            continue
        pid = str(provider.get("id", ""))
        html_meta = html_meta_by_id.get(pid, {})
        record = _build_provider_record(
            provider, html_meta, listing_url, category_slug, city_slug, state_slug
        )
        if record.get("businessName"):
            records.append(record)

    # Sort by ranking (data-position from HTML); unranked providers go last
    records.sort(key=lambda r: r.get("ranking") or 9999)

    logger.info("Extracted %d providers from %s", len(records), listing_url)
    return records

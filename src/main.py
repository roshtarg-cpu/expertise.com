"""
Expertise.com Professional Directory Scraper
Apify Actor — Python / httpx / BeautifulSoup

URL patterns confirmed from live site inspection (2026-08):
  State page:     https://www.expertise.com/{state}
  City page:      https://www.expertise.com/{state}/{city}
  Category page:  https://www.expertise.com/{cSlug}/{category}/{state}/{city}

Data lives in Next.js RSC streaming payloads (self.__next_f.push),
NOT in __NEXT_DATA__ (the site uses the App Router, not Pages Router).
"""

from __future__ import annotations

import logging
from typing import Optional

from apify import Actor

from .parser import (
    debug_structure,
    extract_city_links,
    extract_city_verticals,
    find_cslug_for_category,
    parse_listing_page,
)
from .utils import BASE_URL, build_client, fetch_page

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Discovery helpers
# ---------------------------------------------------------------------------

async def get_state_cities(client, state: str) -> list[str]:
    """Return all city slugs for a state by scraping the state index page."""
    url = f"{BASE_URL}/{state}"
    html = await fetch_page(client, url)
    if not html:
        logger.error("Could not fetch state page: %s", url)
        return []
    cities = extract_city_links(html, state)
    logger.info("Found %d cities for state '%s'", len(cities), state)
    return cities


async def get_city_verticals(client, state: str, city: str) -> list[dict]:
    """Return all verticals (categories) available in a city."""
    url = f"{BASE_URL}/{state}/{city}"
    html = await fetch_page(client, url)
    if not html:
        logger.error("Could not fetch city page: %s", url)
        return []
    verticals = extract_city_verticals(html)
    logger.info("Found %d verticals for %s, %s", len(verticals), city, state)
    return verticals


async def resolve_cslug(
    client,
    state: str,
    city: str,
    category: str,
) -> Optional[str]:
    """
    Find the category group slug (cSlug) for a given category slug.
    Requires a city page to look up the mapping.
    e.g. 'personal-injury-lawyers' → 'legal', 'roofing' → 'home-improvement'
    """
    url = f"{BASE_URL}/{state}/{city}"
    html = await fetch_page(client, url)
    if not html:
        return None
    cslug = find_cslug_for_category(html, category)
    if not cslug:
        logger.warning(
            "Category '%s' not found in verticals for %s, %s", category, city, state
        )
    return cslug


# ---------------------------------------------------------------------------
# Core scraping function
# ---------------------------------------------------------------------------

async def scrape_category(
    client,
    cslug: str,
    category: str,
    state: str,
    city: str,
    results_so_far: int,
    max_results: int,
    run_debug: bool = False,
) -> list[dict]:
    """Scrape one category+city listing page and return provider records."""
    url = f"{BASE_URL}/{cslug}/{category}/{state}/{city}"
    html = await fetch_page(client, url)
    if not html:
        return []

    if run_debug:
        debug_structure(html, url)

    providers = parse_listing_page(html, url, category, city, state)

    # Trim to stay within max_results
    remaining = max_results - results_so_far
    if len(providers) > remaining:
        providers = providers[:remaining]

    return providers


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    async with Actor:
        actor_input = await Actor.get_input() or {}

        state: str = actor_input.get("state", "texas").strip().lower()
        city: str = actor_input.get("city", "").strip().lower()
        category: str = actor_input.get("category", "").strip().lower()
        max_results: int = int(actor_input.get("maxResults", 100))
        proxy_config = actor_input.get("proxyConfiguration")

        Actor.log.info(
            "Starting scrape — state=%s city=%s category=%s maxResults=%d",
            state, city or "(all)", category or "(all)", max_results,
        )

        # Build proxy URL if configured
        proxy_url: Optional[str] = None
        if proxy_config and isinstance(proxy_config, dict):
            proxy_url = proxy_config.get("proxyUrls", [None])[0]

        results_count = 0
        debug_done = False

        async with build_client(proxy_url) as client:

            # ------------------------------------------------------------------
            # CASE 1: state + city + category  →  single listing page
            # ------------------------------------------------------------------
            if state and city and category:
                cslug = await resolve_cslug(client, state, city, category)
                if not cslug:
                    Actor.log.error(
                        "Cannot find category group for '%s' in %s, %s. "
                        "Check that the category slug is correct.",
                        category, city, state,
                    )
                    return

                providers = await scrape_category(
                    client, cslug, category, state, city,
                    results_count, max_results, run_debug=True,
                )
                results_count += len(providers)
                if providers:
                    await Actor.push_data(providers)
                    Actor.log.info("Pushed %d records (total: %d)", len(providers), results_count)

            # ------------------------------------------------------------------
            # CASE 2: state + city  →  all categories for that city
            # ------------------------------------------------------------------
            elif state and city:
                verticals = await get_city_verticals(client, state, city)
                if not verticals:
                    Actor.log.error("No categories found for %s, %s", city, state)
                    return

                for v in verticals:
                    if results_count >= max_results:
                        break
                    cslug = v["cSlug"]
                    cat_slug = v["slug"]

                    providers = await scrape_category(
                        client, cslug, cat_slug, state, city,
                        results_count, max_results, run_debug=not debug_done,
                    )
                    debug_done = True

                    if providers:
                        results_count += len(providers)
                        await Actor.push_data(providers)
                        if results_count % 10 == 0 or results_count >= max_results:
                            Actor.log.info(
                                "Progress: %d/%d records scraped", results_count, max_results
                            )

            # ------------------------------------------------------------------
            # CASE 3: state + category (no city)  →  all cities for given category
            # ------------------------------------------------------------------
            elif state and category:
                cities = await get_state_cities(client, state)
                if not cities:
                    Actor.log.error("No cities found for state '%s'", state)
                    return

                # Resolve cSlug from the first city that has this vertical
                cslug: Optional[str] = None
                for first_city in cities[:5]:
                    cslug = await resolve_cslug(client, state, first_city, category)
                    if cslug:
                        break

                if not cslug:
                    Actor.log.error(
                        "Category '%s' not found in any of the first cities of %s", category, state
                    )
                    return

                for city_slug in cities:
                    if results_count >= max_results:
                        break
                    providers = await scrape_category(
                        client, cslug, category, state, city_slug,
                        results_count, max_results, run_debug=not debug_done,
                    )
                    debug_done = True

                    if providers:
                        results_count += len(providers)
                        await Actor.push_data(providers)
                        if results_count % 10 == 0 or results_count >= max_results:
                            Actor.log.info(
                                "Progress: %d/%d records scraped", results_count, max_results
                            )

            # ------------------------------------------------------------------
            # CASE 4: state only  →  all cities × all categories
            # ------------------------------------------------------------------
            else:
                cities = await get_state_cities(client, state)
                if not cities:
                    Actor.log.error("No cities found for state '%s'", state)
                    return

                for city_slug in cities:
                    if results_count >= max_results:
                        break

                    verticals = await get_city_verticals(client, state, city_slug)

                    for v in verticals:
                        if results_count >= max_results:
                            break
                        cslug = v["cSlug"]
                        cat_slug = v["slug"]

                        providers = await scrape_category(
                            client, cslug, cat_slug, state, city_slug,
                            results_count, max_results, run_debug=not debug_done,
                        )
                        debug_done = True

                        if providers:
                            results_count += len(providers)
                            await Actor.push_data(providers)
                            if results_count % 10 == 0 or results_count >= max_results:
                                Actor.log.info(
                                    "Progress: %d/%d records scraped",
                                    results_count, max_results,
                                )

        Actor.log.info("Scrape complete. Total records: %d", results_count)

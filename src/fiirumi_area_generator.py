"""Automatic generation of Fiirumi election areas."""

import logging
from datetime import datetime
from typing import Any, Dict, Optional, cast

import requests

from .config import BASE_URL, API_KEY, API_USERNAME, set_generated_vaalilakana_post_url

logger = logging.getLogger("vaalilakanabot")


def get_discourse_headers(
    content_type: Optional[str] = "application/json",
) -> Dict[str, str]:
    """Get headers for Discourse API requests.

    Args:
        content_type: Value for the Content-Type header, or None to omit it
                      (e.g. when posting form data so requests sets the boundary automatically).
    """
    headers: Dict[str, str] = {
        "Api-Key": API_KEY,
        "Api-Username": API_USERNAME,
    }
    if content_type is not None:
        headers["Content-Type"] = content_type
    return headers


def create_category(
    name: str,
    color: str = "0088CC",
    text_color: str = "FFFFFF",
    parent_category_id: Optional[int] = None,
    slug: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Create a new Discourse category.

    Args:
        name: Display name of the category
        color: Hex color code (without #)
        text_color: Text color hex code (without #)
        parent_category_id: ID of parent category if this is a subcategory
        slug: URL slug (auto-generated if not provided)

    Returns:
        Category data dict with 'id' field if successful, None otherwise
    """
    url = f"{BASE_URL}/categories.json"

    payload: Dict[str, Any] = {
        "name": name,
        "color": color,
        "text_color": text_color,
    }

    if slug:
        payload["slug"] = slug

    if parent_category_id is not None:
        payload["parent_category_id"] = parent_category_id

    try:
        response = requests.post(
            url,
            headers=get_discourse_headers(),
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()
        category = result.get("category")
        if category is not None:
            logger.info("Created category '%s' with ID %s", name, category.get("id"))
        return cast(Optional[Dict[str, Any]], result.get("category"))
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 422:
            # Category already exists; return a stub so callers treat this as success
            logger.info("Category '%s' already exists (422)", name)
            return {"name": name, "slug": slug or name}
        logger.error("Failed to create category '%s': %s", name, e)
        return None
    except Exception as e:
        logger.error("Error creating category '%s': %s", name, e)
        return None


def find_category_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    """Find a category by its slug.

    Args:
        slug: Category slug to search for

    Returns:
        Category data dict if found, None otherwise
    """
    url = f"{BASE_URL}/c/{slug}/show.json"

    try:
        response = requests.get(
            url,
            headers=get_discourse_headers(),
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()
        return cast(Optional[Dict[str, Any]], result.get("category"))
    except Exception as e:
        logger.debug("Category with slug '%s' not found: %s", slug, e)
        return None


def _first_post_url_from_topic_data(t_data: Dict[str, Any]) -> Optional[str]:
    """Extract the first post URL from a topic JSON response."""
    post_stream = t_data.get("post_stream", {}) or {}
    posts = post_stream.get("posts", [])
    if posts:
        post_id = posts[0].get("id")
        if post_id is not None:
            return f"{BASE_URL}/posts/{post_id}.json"
    return None


def _topic_id_to_post_url(topic_id: int) -> Optional[str]:
    """Fetch a topic by ID and return its first post URL."""
    try:
        tr = requests.get(
            f"{BASE_URL}/t/{topic_id}.json",
            headers=get_discourse_headers(),
            timeout=30,
        )
        tr.raise_for_status()
        url = _first_post_url_from_topic_data(tr.json())
        if url:
            logger.info("Found election sheet topic (id=%d): %s", topic_id, url)
        return url
    except Exception as e:
        logger.warning("Failed to fetch topic id=%d: %s", topic_id, e)
        return None


def _find_by_category_list(title: str, parent_slug: str) -> Optional[str]:
    """Scan the parent category's topic list for a topic with the given title."""
    if not parent_slug:
        return None
    list_url = f"{BASE_URL}/c/{parent_slug}/l/latest.json"
    logger.info("Scanning category topic list: %s", list_url)
    try:
        r = requests.get(list_url, headers=get_discourse_headers(), timeout=30)
        r.raise_for_status()
        topics = r.json().get("topic_list", {}).get("topics", [])
        logger.info(
            "Category '%s' has %d topic(s): %s",
            parent_slug,
            len(topics),
            [t.get("title") for t in topics],
        )
        for topic in topics:
            if topic.get("title") == title:
                topic_id = topic.get("id")
                if topic_id:
                    return _topic_id_to_post_url(int(topic_id))
    except Exception as e:
        logger.warning("Category list scan failed for '%s': %s", parent_slug, e)
    return None


def _find_election_sheet_post_url(year: int, parent_slug: str) -> Optional[str]:
    """Find the election sheet topic for the given year via the parent category topic list."""
    return _find_by_category_list(f"Vaalilakana {year}", parent_slug)


def _create_election_sheet_topic(
    year: int, category_id: int, parent_slug: str = ""
) -> Optional[str]:
    """Create the election sheet topic in the given category; return its first post URL.

    If the topic already exists (422), falls back to searching for it.
    """
    url = f"{BASE_URL}/posts.json"
    title = f"Vaalilakana {year}"
    # Initial body: the sheet heading satisfies Discourse's minimum-body quality check
    # and also acts as the preamble delimiter for the sheet updater.
    raw = (
        f"Tämä postaus sisältää automaattisesti päivitetyn vaalilakanan. "
        f"This post contains the automatically updated election sheet.\n\n"
        f"# VAALILAKANA {year} / ELECTION SHEET {year}\n\n"
    )
    # Discourse often expects form data for POST /posts.json (some instances reject JSON);
    # omit Content-Type so requests sets the correct multipart boundary automatically.
    payload: Dict[str, Any] = {
        "title": title,
        "raw": raw,
        "category": category_id,
    }
    try:
        response = requests.post(
            url,
            headers=get_discourse_headers(content_type=None),
            data=payload,
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()
        post_id = result.get("id")
        if post_id is not None:
            logger.info(
                "Created election sheet topic '%s' with post id %s", title, post_id
            )
            return f"{BASE_URL}/posts/{post_id}.json"
        return None
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 422:
            body = e.response.text[:500]
            logger.info(
                "Election sheet topic '%s' already exists (422); body: %s", title, body
            )
            return _find_election_sheet_post_url(year, parent_slug)
        logger.error(
            "Failed to create election sheet topic: %s — %s", e, e.response.text[:500]
        )
        return None
    except Exception as e:
        logger.error("Error creating election sheet topic: %s", e)
        return None


def generate_election_areas(year: int) -> bool:
    """Generate Discourse categories for election year.

    Creates:
    - Parent category: vaalipeli-{year} (election sheet topic posted here)
    - Subcategory: esittelyt (introductions)
    - Subcategory: kysymykset (questions)

    Args:
        year: Election year

    Returns:
        True if all categories created/exist, False otherwise
    """
    logger.info("Generating election areas for year %d", year)

    # Define category structure
    parent_slug = f"vaalipeli-{year}"
    parent_name = f"Vaalipeli {year}"

    # Check if parent category exists
    parent_category = find_category_by_slug(parent_slug)

    if not parent_category:
        # Create parent category
        parent_category = create_category(
            name=parent_name,
            slug=parent_slug,
            color="ED207B",  # Pink/magenta color for elections
            text_color="FFFFFF",
        )

        if not parent_category:
            logger.error("Failed to create parent category for year %d", year)
            return False
    else:
        logger.info("Parent category '%s' already exists", parent_slug)

    parent_id: int = int(parent_category["id"])

    # Create subcategories
    subcategories = [
        {
            "name": "Esittelyt",
            "slug": "esittelyt",
            "color": "0088CC",  # Blue
        },
        {
            "name": "Kysymykset",
            "slug": "kysymykset",
            "color": "F7941D",  # Orange
        },
    ]

    all_success = True

    for subcat in subcategories:
        full_slug = f"{parent_slug}/{subcat['slug']}"
        # Try slug-based lookup first, then numeric-parent-ID-based lookup as fallback
        # (some Discourse instances don't support /c/{parent_slug}/{child_slug}/show.json)
        existing = find_category_by_slug(full_slug) or find_category_by_slug(
            f"{parent_id}/{subcat['slug']}"
        )

        if not existing:
            result = create_category(
                name=subcat["name"],
                slug=subcat["slug"],
                color=subcat["color"],
                text_color="FFFFFF",
                parent_category_id=parent_id,
            )
            if not result:
                logger.error("Failed to create subcategory '%s'", subcat["name"])
                all_success = False
        else:
            logger.info(
                "Subcategory '%s' already exists (id=%s)", full_slug, existing.get("id")
            )

    # Log area URLs regardless of subcategory success
    logger.info("Election area URLs:")
    logger.info("  Main: %s/c/%s", BASE_URL, parent_slug)
    logger.info("  Introductions: %s/c/%s/esittelyt", BASE_URL, parent_slug)
    logger.info("  Questions: %s/c/%s/kysymykset", BASE_URL, parent_slug)

    if all_success:
        logger.info("Successfully generated all election areas for year %d", year)

    # Find or create the election sheet topic in the parent category
    post_url = _find_election_sheet_post_url(year, parent_slug)
    if not post_url:
        post_url = _create_election_sheet_topic(year, parent_id, parent_slug)
    if post_url:
        set_generated_vaalilakana_post_url(post_url)
        logger.info("Election sheet post URL: %s", post_url)
    else:
        logger.warning(
            "Could not create or find election sheet topic for year %d; "
            "set VAALILAKANA_POST_URL in bot.env to update the sheet on Discourse",
            year,
        )

    return all_success


def should_generate_areas(election_year: Optional[int]) -> bool:
    """Check if election areas should be generated based on current year.

    Args:
        election_year: Target election year from config, or None

    Returns:
        True if areas should be generated, False otherwise
    """
    if election_year is None:
        logger.debug("ELECTION_YEAR not set, skipping area generation")
        return False

    current_year = datetime.now().year

    if current_year == election_year:
        logger.debug("Current year matches election year, should generate areas")
        return True
    logger.debug(
        "Current year %d does not match election year %d, skipping",
        current_year,
        election_year,
    )
    return False

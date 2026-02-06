"""Automatic generation of Fiirumi election areas."""

import logging
from datetime import datetime
from typing import Optional, Dict, Any
import requests

from .config import BASE_URL, API_KEY, API_USERNAME

logger = logging.getLogger("vaalilakanabot")


def get_discourse_headers() -> Dict[str, str]:
    """Get headers for Discourse API requests."""
    return {
        "Api-Key": API_KEY,
        "Api-Username": API_USERNAME,
        "Content-Type": "application/json",
    }


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

    payload = {
        "name": name,
        "color": color,
        "text_color": text_color,
    }

    if slug:
        payload["slug"] = slug

    if parent_category_id:
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
        logger.info("Created category '%s' with ID %s", name, result["category"]["id"])
        return result["category"]
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 422:
            # Category might already exist
            logger.warning("Category '%s' might already exist: %s", name, e)
        else:
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
        return result["category"]
    except Exception as e:
        logger.debug("Category with slug '%s' not found: %s", slug, e)
        return None


def generate_election_areas(year: int) -> bool:
    """Generate Discourse categories for election year.

    Creates:
    - Parent category: vaalipeli-{year}
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

    parent_id = parent_category["id"]

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
        # Check if subcategory exists
        full_slug = f"{parent_slug}/{subcat['slug']}"
        existing = find_category_by_slug(full_slug)

        if not existing:
            # Create subcategory
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
            logger.info("Subcategory '%s' already exists", full_slug)

    if all_success:
        logger.info("Successfully generated all election areas for year %d", year)

        # Log the URLs for convenience
        logger.info("Election area URLs:")
        logger.info("  Main: %s/c/%s", BASE_URL, parent_slug)
        logger.info("  Introductions: %s/c/%s/esittelyt", BASE_URL, parent_slug)
        logger.info("  Questions: %s/c/%s/kysymykset", BASE_URL, parent_slug)

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
    else:
        logger.debug(
            "Current year %d does not match election year %d, skipping",
            current_year,
            election_year
        )
        return False

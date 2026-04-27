#!/usr/bin/env python3
"""Scrape City of Orlando volunteer opportunities for Mission Reboot ingestion."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

SOURCE_URL = "https://volunteer.orlando.gov/custom/501/opp_search"
OUTPUT_FILE = "orlando_cares_opportunities.json"
SOURCE_NAME = "City of Orlando Volunteer Portal"
BAD_TITLES = {"more details", "opportunity details", "view details", "details"}
DETAIL_ID_RE = re.compile(r"opp_details/([^/?#]+)")


def render_page(url: str) -> BeautifulSoup | None:
    """Render JavaScript-driven volunteer pages and return parsed HTML."""
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="networkidle", timeout=60_000)
            html = page.content()
            browser.close()
            return BeautifulSoup(html, "html.parser")
    except PlaywrightTimeoutError:
        print(f"Timed out rendering {url}", file=sys.stderr)
    except Exception as exc:
        print(f"Error rendering {url}: {exc}", file=sys.stderr)
    return None


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def opportunity_id_from_url(url: str) -> str | None:
    match = DETAIL_ID_RE.search(url)
    return match.group(1) if match else None


def is_valid_title(title: str) -> bool:
    normalized = title.strip().lower()
    return bool(normalized) and normalized not in BAD_TITLES and len(normalized) > 3


def extract_labeled_value(soup: BeautifulSoup, labels: tuple[str, ...]) -> str:
    """Best-effort extraction for common label/value detail page layouts."""
    label_pattern = re.compile("|".join(re.escape(label) for label in labels), re.I)

    for text_node in soup.find_all(string=label_pattern):
        parent = text_node.parent
        if not parent:
            continue

        candidates = [
            parent.find_next_sibling(),
            parent.parent.find_next_sibling() if parent.parent else None,
        ]
        for candidate in candidates:
            if candidate:
                value = clean_text(candidate.get_text(" ", strip=True))
                if value and not label_pattern.fullmatch(value):
                    return value

        parent_text = clean_text(parent.get_text(" ", strip=True))
        for label in labels:
            if parent_text.lower().startswith(label.lower()):
                value = clean_text(parent_text[len(label) :].strip(" :-"))
                if value:
                    return value

    return ""


def extract_description(soup: BeautifulSoup) -> str:
    selectors = [
        ".opp-description",
        ".opportunity-description",
        "[class*=description]",
        "[class*=Description]",
        "main",
    ]
    for selector in selectors:
        element = soup.select_one(selector)
        if element:
            text = clean_text(element.get_text(" ", strip=True))
            if len(text) > 80:
                return text[:1500]
    body_text = clean_text(soup.get_text(" ", strip=True))
    return body_text[:1500]


def classify_opportunity(title: str, description: str) -> list[str]:
    text = f"{title} {description}".lower()
    tags: list[str] = []
    keyword_tags = {
        "youth": ("youth", "coach", "basketball", "baseball", "softball", "lacrosse", "book buddy"),
        "parks": ("garden", "wetland", "cleanup", "leu gardens", "greenwood cemetery"),
        "education": ("book", "tutor", "mentor", "school"),
        "community": ("volunteer", "open house", "neighborhood"),
        "veteran_adjacent": ("wreaths across america", "cemetery", "veteran"),
    }
    for tag, keywords in keyword_tags.items():
        if any(keyword in text for keyword in keywords):
            tags.append(tag)
    return tags or ["community"]


def extract_search_results(soup: BeautifulSoup) -> list[dict[str, str]]:
    """Extract canonical opportunity links from the search results page."""
    results: dict[str, dict[str, str]] = {}

    for link in soup.find_all("a", href=lambda href: href and "opp_details" in href):
        title = clean_text(link.get_text(" ", strip=True))
        href = link.get("href")
        if not href or not is_valid_title(title):
            continue

        full_url = urljoin(SOURCE_URL, href)
        opp_id = opportunity_id_from_url(full_url)
        if not opp_id or opp_id.startswith(":"):
            continue

        results[opp_id] = {
            "id": f"orlando-cares-{opp_id}",
            "source_id": opp_id,
            "title": title,
            "link": full_url,
        }

    return list(results.values())


def enrich_opportunity(base: dict[str, str]) -> dict[str, Any]:
    detail_soup = render_page(base["link"])
    description = ""
    date = ""
    location = ""

    if detail_soup:
        description = extract_description(detail_soup)
        date = extract_labeled_value(detail_soup, ("Date", "When", "Schedule", "Time"))
        location = extract_labeled_value(detail_soup, ("Location", "Where", "Address"))

    return {
        **base,
        "description": description,
        "date": date,
        "location": location,
        "source": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "status": "available",
        "tags": classify_opportunity(base["title"], description),
        "last_seen_at": datetime.now(timezone.utc).isoformat(),
    }


def scrape_opportunities(enrich: bool = True) -> list[dict[str, Any]]:
    soup = render_page(SOURCE_URL)
    if not soup:
        return []

    opportunities = extract_search_results(soup)
    if not enrich:
        return [
            {
                **opp,
                "description": "",
                "date": "",
                "location": "",
                "source": SOURCE_NAME,
                "source_url": SOURCE_URL,
                "status": "available",
                "tags": classify_opportunity(opp["title"], ""),
                "last_seen_at": datetime.now(timezone.utc).isoformat(),
            }
            for opp in opportunities
        ]

    return [enrich_opportunity(opp) for opp in opportunities]


def save_to_json(opportunities: list[dict[str, Any]], filename: str = OUTPUT_FILE) -> None:
    output = {
        "schema_version": 1,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "source": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "total_opportunities": len(opportunities),
        "opportunities": opportunities,
    }

    with open(filename, "w", encoding="utf-8") as file:
        json.dump(output, file, ensure_ascii=False, indent=2)
        file.write("\n")


def main() -> int:
    print(f"Scraping {SOURCE_NAME}: {SOURCE_URL}")
    opportunities = scrape_opportunities(enrich=True)

    if not opportunities:
        print("No valid opportunities found; refusing to publish empty feed.", file=sys.stderr)
        return 1

    save_to_json(opportunities)
    print(f"Saved {len(opportunities)} opportunities to {OUTPUT_FILE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

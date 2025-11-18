#!/usr/bin/env python3
"""
Scraper for City of Orlando volunteer opportunities.
Scrapes data from https://volunteer.orlando.gov/custom/501/opp_search
and saves to orlando_cares_opportunities.json
"""

import requests
from bs4 import BeautifulSoup
import json
import sys
from datetime import datetime
from urllib.parse import urljoin, urlparse

URL = 'https://volunteer.orlando.gov/custom/501/opp_search'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

from playwright.sync_api import sync_playwright

def fetch_page(url):
    """Fetch and render a page with Playwright."""
    html_content = ""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=60000)
            page.wait_for_timeout(5000)  # wait for JS to load
            html_content = page.content()
            browser.close()
        return BeautifulSoup(html_content, 'html.parser')
    except Exception as e:
        print(f"Error rendering {url}: {e}", file=sys.stderr)
        return None


def extract_opportunity_data(opportunity_element):
    """
    Extract data from an opportunity HTML element.
    This function should be adjusted based on the actual HTML structure.
    """
    opportunity = {}
    
    # Try to find title/link
    title_elem = opportunity_element.find(['a', 'h1', 'h2', 'h3', 'h4'], class_=lambda x: x and ('title' in x.lower() or 'name' in x.lower()))
    if not title_elem:
        title_elem = opportunity_element.find(['a', 'h1', 'h2', 'h3', 'h4'])
    
    if title_elem:
        opportunity['title'] = title_elem.get_text(strip=True)
        if title_elem.name == 'a' and title_elem.get('href'):
            href = title_elem.get('href')
            opportunity['link'] = urljoin(URL, href) if not href.startswith('http') else href
    else:
        opportunity['title'] = opportunity_element.get_text(strip=True)[:100]
    
    # Try to find description
    desc_elem = opportunity_element.find(['p', 'div'], class_=lambda x: x and ('desc' in x.lower() or 'summary' in x.lower() or 'detail' in x.lower()))
    if desc_elem:
        opportunity['description'] = desc_elem.get_text(strip=True)
    
    # Try to find date/time information
    date_elem = opportunity_element.find(['span', 'div', 'p'], class_=lambda x: x and ('date' in x.lower() or 'time' in x.lower()))
    if date_elem:
        opportunity['date'] = date_elem.get_text(strip=True)
    
    # Try to find location
    location_elem = opportunity_element.find(['span', 'div', 'p'], class_=lambda x: x and ('location' in x.lower() or 'address' in x.lower() or 'place' in x.lower()))
    if location_elem:
        opportunity['location'] = location_elem.get_text(strip=True)
    
    # Extract all text as fallback
    if 'description' not in opportunity:
        text_parts = [p.get_text(strip=True) for p in opportunity_element.find_all(['p', 'div', 'span'])]
        full_text = ' '.join(text_parts)
        if len(full_text) > len(opportunity.get('title', '')):
            opportunity['description'] = full_text[:500]
    
    return opportunity

def find_opportunities(soup):
    """
    Find all opportunity elements on the City of Orlando volunteer portal.
    Each opportunity link uses href='opp_details/...'
    """
    opportunities = []

    # Find all <a> tags linking to opportunity details
    links = soup.find_all('a', href=lambda h: h and 'opp_details' in h)

    for link in links:
        title = link.get_text(strip=True)
        href = link.get('href')

        if title and href:
            full_url = urljoin(URL, href)
            opportunities.append({
                'title': title,
                'link': full_url
            })

    return opportunities


def find_next_page(soup):
    """Find the URL for the next page if pagination exists."""
    next_link = soup.find('a', class_=lambda x: x and 'next' in x.lower())
    if not next_link:
        next_link = soup.find('a', string=lambda x: x and 'next' in x.lower() if x else False)
    if next_link and next_link.get('href'):
        return urljoin(URL, next_link.get('href'))
    return None

def scrape_all_opportunities():
    """Scrape all opportunities, handling pagination if present."""
    all_opportunities = []
    current_url = URL
    visited_urls = set()
    max_pages = 100  # Safety limit
    
    page_count = 0
    
    while current_url and page_count < max_pages:
        if current_url in visited_urls:
            break
        visited_urls.add(current_url)
        
        print(f"Fetching page {page_count + 1}: {current_url}")
        soup = fetch_page(current_url)
        
        if not soup:
            break
        
        opportunities = find_opportunities(soup)
        all_opportunities.extend(opportunities)
        print(f"Found {len(opportunities)} opportunities on this page")
        
        # Check for next page
        next_url = find_next_page(soup)
        if next_url and next_url not in visited_urls:
            current_url = next_url
        else:
            break
        
        page_count += 1
    
    # Remove duplicates based on title
    seen_titles = set()
    unique_opportunities = []
    for opp in all_opportunities:
        title = opp.get('title', '').lower().strip()
        if title and title not in seen_titles:
            seen_titles.add(title)
            unique_opportunities.append(opp)
    
    return unique_opportunities

def save_to_json(data, filename='orlando_cares_opportunities.json'):
    """Save opportunities to JSON file."""
    output = {
        'scraped_at': datetime.now().isoformat(),
        'source_url': URL,
        'total_opportunities': len(data),
        'opportunities': data
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    return len(data)

def main():
    """Main execution function."""
    print("Starting scraper...")
    print(f"Target URL: {URL}")
    
    opportunities = scrape_all_opportunities()
    
    if not opportunities:
        print("Warning: No opportunities found. The HTML structure may have changed.", file=sys.stderr)
        print("Please inspect the website and update the selectors in scraper.py", file=sys.stderr)
        # Still create an empty file
        save_to_json([])
        sys.exit(1)
    
    count = save_to_json(opportunities)
    print(f"\nSuccessfully scraped {count} opportunities")
    print(f"Data saved to orlando_cares_opportunities.json")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())


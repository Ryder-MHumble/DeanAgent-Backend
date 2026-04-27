#!/usr/bin/env python3
"""
CTFtime Crawler - Scrape CTF team rankings and competition data

This script fetches data from CTFtime API:
- Global team rankings
- Team details (country, rating)
- Competition results

Output: JSON format with team rankings and competition data
"""

import json
import time
import requests
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

# API Configuration
BASE_URL = "https://ctftime.org/api/v1"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; CTFtimeCrawler/1.0; +https://github.com/openclaw)"
}
REQUEST_DELAY = 0.5  # seconds between requests to be polite


def make_request(endpoint: str, params: Optional[Dict] = None) -> Optional[Any]:
    """Make a request to CTFtime API with error handling"""
    url = f"{BASE_URL}/{endpoint}"
    
    try:
        response = requests.get(url, headers=HEADERS, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {endpoint}: {e}")
        return None


def get_top_teams(limit: int = 100) -> List[Dict]:
    """Get top teams from current year's leaderboard"""
    print(f"Fetching top {limit} teams...")
    data = make_request("top/", params={"limit": limit})
    
    if not data:
        return []
    
    # Data is organized by year: {"2026": [...], "2025": [...]}
    current_year = str(datetime.now().year)
    teams_data = data.get(current_year, [])
    
    # If current year not available, try previous year
    if not teams_data:
        prev_year = str(datetime.now().year - 1)
        teams_data = data.get(prev_year, [])
    
    return teams_data


def get_team_details(team_id: int) -> Optional[Dict]:
    """Get detailed information about a specific team"""
    print(f"  Fetching details for team {team_id}...")
    data = make_request(f"teams/{team_id}/")
    
    if not data:
        return None
    
    # Extract relevant information
    return {
        "id": data.get("id"),
        "name": data.get("name"),
        "country": data.get("country"),
        "academic": data.get("academic", False),
        "primary_alias": data.get("primary_alias"),
        "aliases": data.get("aliases", []),
        "rating": extract_current_rating(data.get("rating", {})),
        "logo": data.get("logo")
    }


def extract_current_rating(rating_data: Dict) -> Optional[Dict]:
    """Extract the current year's rating from rating history"""
    current_year = str(datetime.now().year)
    
    if current_year in rating_data:
        return rating_data[current_year]
    
    # Fall back to most recent year with data
    years = sorted([y for y in rating_data.keys() if y.isdigit()], reverse=True)
    if years:
        return rating_data[years[0]]
    
    return None


def get_events(limit: int = 50) -> List[Dict]:
    """Get recent/upcoming CTF events"""
    print(f"Fetching {limit} events...")
    
    # Get events from recent time period
    now = int(time.time())
    start = now - (30 * 24 * 60 * 60)  # 30 days ago
    finish = now + (60 * 24 * 60 * 60)  # 60 days from now
    
    data = make_request("events/", params={
        "limit": limit,
        "start": start,
        "finish": finish
    })
    
    return data if data else []


def get_results(year: Optional[int] = None) -> Dict:
    """Get competition results for a specific year"""
    year = year or datetime.now().year
    print(f"Fetching results for {year}...")
    
    data = make_request(f"results/{year}/")
    return data if data else {}


def crawl_ctftime(teams_limit: int = 100, events_limit: int = 50) -> Dict:
    """
    Main crawling function
    
    Args:
        teams_limit: Maximum number of teams to fetch
        events_limit: Maximum number of events to fetch
    
    Returns:
        Dict containing crawled data
    """
    result = {
        "source": "ctftime",
        "crawl_time": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "crawl_config": {
            "teams_limit": teams_limit,
            "events_limit": events_limit
        },
        "teams": [],
        "events": [],
        "results": {}
    }
    
    # 1. Get top teams with basic info
    top_teams = get_top_teams(limit=teams_limit)
    
    # 2. Get detailed info for each team
    for team in top_teams:
        team_id = team.get("team_id")
        if team_id:
            details = get_team_details(team_id)
            if details:
                # Merge basic info with details
                details["points"] = team.get("points")
                details["rank"] = len(result["teams"]) + 1
                result["teams"].append(details)
            
            # Be polite to the API
            time.sleep(REQUEST_DELAY)
    
    # 3. Get events
    events = get_events(limit=events_limit)
    if events:
        for event in events:
            result["events"].append({
                "id": event.get("id"),
                "title": event.get("title"),
                "format": event.get("format"),
                "start": event.get("start"),
                "finish": event.get("finish"),
                "url": event.get("url"),
                "participants": event.get("participants"),
                "weight": event.get("weight"),
                "onsite": event.get("onsite"),
                "location": event.get("location")
            })
    
    # 4. Get current year results (summary of competition outcomes)
    results_data = get_results()
    if results_data:
        result["results"] = {
            "events_count": len(results_data),
            "events": list(results_data.keys())[:20]  # Just store event IDs
        }
    
    return result


def main():
    """Main entry point"""
    import argparse
    import os
    
    parser = argparse.ArgumentParser(description="CTFtime Crawler")
    parser.add_argument("--teams", type=int, default=100, help="Number of teams to fetch")
    parser.add_argument("--events", type=int, default=50, help="Number of events to fetch")
    parser.add_argument("--output", "-o", type=str, default="results.json", help="Output file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("CTFtime Crawler")
    print("=" * 60)
    print(f"Fetching top {args.teams} teams and {args.events} events")
    print()
    
    # Run crawler
    data = crawl_ctftime(teams_limit=args.teams, events_limit=args.events)
    
    # Add summary
    data["summary"] = {
        "total_teams": len(data["teams"]),
        "total_events": len(data["events"]),
        "countries_represented": len(set(t["country"] for t in data["teams"] if t.get("country")))
    }
    
    # Save results
    output_path = args.output
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print()
    print("=" * 60)
    print("Crawl Complete!")
    print("=" * 60)
    print(f"Teams: {data['summary']['total_teams']}")
    print(f"Events: {data['summary']['total_events']}")
    print(f"Countries: {data['summary']['countries_represented']}")
    print(f"Output: {output_path}")
    
    if args.verbose:
        print()
        print("Top 5 Teams:")
        for team in data["teams"][:5]:
            rating_info = team.get("rating", {})
            rating_place = rating_info.get("rating_place", "N/A") if rating_info else "N/A"
            print(f"  {team['rank']}. {team['name']} ({team.get('country', 'N/A')}) - Rating place: {rating_place}")
    
    return data


if __name__ == "__main__":
    main()

import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
import json
import os
from datetime import datetime, timedelta
import time

def get_website_html(url):
    """Fetch HTML content from a given URL"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def scrape_economy_news():
    """Scrape economy news links from multiple Turkish news websites and return only unique links with full URLs"""
    # Set to keep track of all unique links
    all_unique_links = set()
    
    # Define base URLs for each website
    base_urls = {
        "haberturk": "https://www.haberturk.com",
        "trthaber": "",  # TRT Haber links are already complete
        "cnnhaber": "https://www.cnnturk.com",
        "bloomberght": "https://www.bloomberght.com",
        "bigpara": "https://bigpara.hurriyet.com.tr"
    }
    
    # Haberturk
    haberturk_url = "https://www.haberturk.com/ekonomi/"
    haberturk = get_website_html(haberturk_url)
    if haberturk:
        soup = BeautifulSoup(haberturk, 'html.parser')
        haberturk_links = soup.find_all('a', {'data-newscategory': 'Ekonomi'}, class_="block gtm-tracker", href=True)
        for link in haberturk_links:
            full_url = urljoin(base_urls["haberturk"], link['href'])
            all_unique_links.add(full_url)
    
    # TRT Haber
    trthaber_url = "https://www.trthaber.com/haber/ekonomi/"
    trthaber = get_website_html(trthaber_url)
    if trthaber:
        soup = BeautifulSoup(trthaber, 'html.parser')
        all_trt_links = soup.find_all('a', class_="site-url", href=True)
        for link in all_trt_links:
            if link['href'].startswith("https://www.trthaber.com/haber/ekonomi/") and link['href'].endswith(".html"):
                # TRT Haber links are already complete
                all_unique_links.add(link['href'])
    
    # CNN Türk
    cnnhaber_url = "https://www.cnnturk.com/ekonomi-haberleri/"
    cnnhaber = get_website_html(cnnhaber_url)
    if cnnhaber:
        soup = BeautifulSoup(cnnhaber, 'html.parser')
        all_cnn_links = soup.find_all('a', class_="navigate", href=True)
        for link in all_cnn_links:
            if link['href'].startswith("/ekonomi/"):
                full_url = urljoin(base_urls["cnnhaber"], link['href'])
                all_unique_links.add(full_url)
    
    # Bloomberg HT
    bloomberght_url = "https://www.bloomberght.com/haberler/turkiye-ekonomisi/"
    bloomberght = get_website_html(bloomberght_url)
    if bloomberght:
        soup = BeautifulSoup(bloomberght, 'html.parser')
        all_bloomberg_links = soup.find_all('a', href=True)
        for link in all_bloomberg_links:
            if re.search(r'\d$', link['href']):
                full_url = urljoin(base_urls["bloomberght"], link['href'])
                all_unique_links.add(full_url)
    
    # Big Para
    bigpara_url = "https://bigpara.hurriyet.com.tr/haberler/ekonomi-haberleri/"
    bigpara = get_website_html(bigpara_url)
    if bigpara:
        soup = BeautifulSoup(bigpara, 'html.parser')
        all_bigpara_links = soup.find_all('a', {'data-query-param': "bpc", 'href': True})
        for link in all_bigpara_links:
            if link['href'].startswith("/haberler/ekonomi-haberleri/"):
                full_url = urljoin(base_urls["bigpara"], link['href'])
                all_unique_links.add(full_url)
    
    # Return just the list of all unique links with full URLs
    return list(all_unique_links)

def load_historical_data():
    """Load historical news data from JSON file"""
    if os.path.exists("news_archive.json"):
        try:
            with open("news_archive.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {"entries": []}
    return {"entries": []}

def save_historical_data(data):
    """Save historical news data to JSON file"""
    with open("news_archive.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def clean_old_entries(data, hours=24):
    """Remove entries older than specified hours"""
    now = datetime.utcnow()
    retention_limit = now - timedelta(hours=hours)
    
    # Convert retention_limit to ISO format string for comparison
    retention_limit_iso = retention_limit.isoformat()
    
    # Filter out entries older than retention_limit
    data["entries"] = [entry for entry in data["entries"] if entry["timestamp"] > retention_limit_iso]
    return data

def identify_new_articles(current_links, historical_data):
    """Identify articles that are new in this run"""
    # Get all historical links
    historical_links = set()
    for entry in historical_data["entries"]:
        historical_links.update(entry["news_links"])
    
    # Find links that are in current_links but not in historical_links
    new_articles = [link for link in current_links if link not in historical_links]
    return new_articles

def main():
    """Main function to run the news scraper."""
    current_time = datetime.utcnow()
    current_time_iso = current_time.isoformat()
    
    # Scrape current news
    news_links = scrape_economy_news()
    print(f"Scraped {len(news_links)} news links at {current_time_iso}")
    
    # Load historical data
    historical_data = load_historical_data()
    
    # Identify new articles
    new_articles = identify_new_articles(news_links, historical_data)
    
    # Add current batch to historical data
    historical_data["entries"].append({
        "timestamp": current_time_iso,
        "news_links": news_links
    })
    
    # Clean old entries (older than 24 hours)
    historical_data = clean_old_entries(historical_data)
    
    # Save updated historical data
    save_historical_data(historical_data)
    
    # Output new articles
    if new_articles:
        print(f"\n{len(new_articles)} NEW ARTICLES FOUND IN THIS RUN:")
        for article in new_articles:
            print(article)
        
        # Save new articles to a separate file
        new_articles_data = {
            "timestamp": current_time_iso,
            "new_articles": new_articles
        }
        with open("new_articles.json", "w", encoding="utf-8") as f:
            json.dump(new_articles_data, f, indent=2)
        print("New articles saved to new_articles.json")
    else:
        print("\nNo new articles found in this run.")

if __name__ == "__main__":
    main()

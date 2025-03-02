import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin
import json
import os
from datetime import datetime, timedelta
import time
import pandas as pd
from openai import OpenAI

# Initialize OpenAI client
client = OpenAI()

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
        json.dump(data, f, indent=2, ensure_ascii=False)

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

def load_bist100_stocks():
    """Load BIST 100 stocks from CSV with both names and codes"""
    csv_path = "bist_100_hisseleri.csv"
    
    if not os.path.exists(csv_path):
        print("Downloading BIST 100 stocks data...")
        url = "https://raw.githubusercontent.com/burakemretetik/news_signal/master/bist_100_hisseleri.csv"
        response = requests.get(url)
        with open(csv_path, "wb") as f:
            f.write(response.content)
    
    bist_100 = pd.read_csv(csv_path)
    
    # Return a list of dictionaries with both code and name
    stocks_with_codes = []
    for _, row in bist_100.iterrows():
        stocks_with_codes.append({
            "kod": row["Hisse Kodu"],
            "adi": row["Hisse Adı"]
        })
    
    return stocks_with_codes

def create_stock_name_code_mapping(stocks_list):
    """Creates a mapping between stock names and codes"""
    name_to_code = {}
    for stock in stocks_list:
        name_to_code[stock["adi"]] = stock["kod"]
    return name_to_code

def create_stock_batches(stock_list, n=10):
    """Creates batches of stock information from a list."""
    stock_batches = []
    for i in range(0, len(stock_list), n):
        stock_batches.append(stock_list[i : i + n])  # Slices list into batches of size n
    return stock_batches

def get_llm_response(stock_batch, recent_news):
    """Sends a prompt with stock batch and news to the LLM and gets a response."""
    # Create a stock list with both names and codes for the prompt
    stock_info_list = []
    for stock in stock_batch:
        stock_info_list.append(f'{stock["kod"]} - {stock["adi"]}')
    
    # Join the stock info into a single string for the prompt
    stocks_text = ", ".join(stock_info_list)
    
    prompt = f"""Analyze the news URLs below and identify **ONLY** URLs that **explicitly** mention one of my listed stocks.
    ----------
    **Rules**:
    1. **Direct Mention Required**: Include ONLY if the URL directly mentions the company (e.g., "COMPANY_NAME announces record profits").
    2. **Exclude**:
      - Sector-wide trends.
      - Government policies.
      - Indirect references.
    3. **No interpretations/speculations**: If unsure, omit.
    ----------
    **Output Format**:
    {{
      "direct_news": [
        {{"hisse_kodu": "STOCK_CODE", "sirket_adi": "COMPANY_NAME", "haber_url": "NEWS_URL"}}
      ],
      "no_direct_news_found": true/false
    }}
    My Stocks: {stocks_text}

    News URL: {recent_news}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Using gpt-4o-mini as specified
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Respond with plain JSON only, no markdown formatting."},
                {"role": "user", "content": prompt}
            ]
        )
        content = response.choices[0].message.content
        
        # Remove markdown code block formatting if present
        if content.startswith("```json") and content.endswith("```"):
            content = content.strip("```json").strip("```").strip()
        elif content.startswith("```") and content.endswith("```"):
            content = content.strip("```").strip()
            
        return content
    except Exception as e:
        print(f"Error getting LLM response: {e}")
        return json.dumps({"direct_news": [], "no_direct_news_found": True, "error": str(e)})

def analyze_news_for_stocks(new_articles):
    """Analyze new articles for relevance to BIST 100 stocks"""
    # Load BIST 100 stocks with codes
    stocks_with_codes = load_bist100_stocks()
    
    # Create a mapping from company name to stock code for later use
    name_to_code_map = create_stock_name_code_mapping(stocks_with_codes)
    
    # Create batches of 10 stocks
    stock_batches = create_stock_batches(stocks_with_codes, n=10)
    
    # Initialize results
    all_results = []
    
    # Process each batch
    for batch_idx, stock_batch in enumerate(stock_batches):
        print(f"Processing batch {batch_idx+1}/{len(stock_batches)}")
        response = get_llm_response(stock_batch, new_articles)
        
        try:
            # Try to parse the response as JSON
            result = json.loads(response)
            all_results.append({
                "batch": batch_idx + 1,
                "stocks": stock_batch,
                "result": result
            })
        except json.JSONDecodeError:
            print(f"Error parsing JSON response for batch {batch_idx+1}")
            all_results.append({
                "batch": batch_idx + 1,
                "stocks": stock_batch,
                "result": {"error": "Failed to parse response", "raw_response": response}
            })
    
    # Aggregate all direct news
    direct_news = []
    for result in all_results:
        if "result" in result and "direct_news" in result["result"]:
            direct_news.extend(result["result"]["direct_news"])
    
    # Save results
    current_time = datetime.utcnow().isoformat()
    analysis_results = {
        "timestamp": current_time,
        "total_batches": len(stock_batches),
        "total_direct_news": len(direct_news),
        "direct_news": direct_news,
        "batch_results": all_results
    }
    
    with open("stock_news_analysis.json", "w", encoding="utf-8") as f:
        json.dump(analysis_results, f, indent=2, ensure_ascii=False)
    
    print(f"Stock news analysis completed. Found {len(direct_news)} relevant news articles.")
    return analysis_results

def create_stock_news_mapping(direct_news):
    """Create a mapping of stocks to their related news articles"""
    stock_news_mapping = {}
    
    for news_item in direct_news:
        stock_code = news_item['hisse_kodu']
        news_url = news_item['haber_url']
        
        if stock_code not in stock_news_mapping:
            stock_news_mapping[stock_code] = {
                "hisse_kodu": stock_code,  # Added this line to include the stock code in each entry
                "sirket_adi": news_item['sirket_adi'],
                "haberler": []
            }
        
        stock_news_mapping[stock_code]["haberler"].append(news_url)
    
    return stock_news_mapping

def save_stock_news_mapping(stock_news_mapping, timestamp):
    """Save the stock-to-news mapping to a JSON file"""
    mapping_data = {
        "timestamp": timestamp,
        "updated": len(stock_news_mapping) > 0,
        "stock_news": stock_news_mapping
    }
    
    with open("stock_news_mapping.json", "w", encoding="utf-8") as f:
        json.dump(mapping_data, f, indent=2, ensure_ascii=False)
    
    return mapping_data

def ensure_mapping_file_exists():
    """Ensure stock_news_mapping.json file exists"""
    if not os.path.exists("stock_news_mapping.json"):
        # Create an empty mapping file
        mapping_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "updated": False,
            "stock_news": {}
        }
        with open("stock_news_mapping.json", "w", encoding="utf-8") as f:
            json.dump(mapping_data, f, indent=2, ensure_ascii=False)
        print("Created initial stock_news_mapping.json file")

def main():
    """Main function to run the news scraper and analyzer."""
    # Ensure mapping file exists
    ensure_mapping_file_exists()
    
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
    
    # Always create/update the new_articles.json file with timestamp even if empty
    new_articles_data = {
        "timestamp": current_time_iso,
        "new_articles": new_articles if new_articles else []
    }
    with open("new_articles.json", "w", encoding="utf-8") as f:
        json.dump(new_articles_data, f, indent=2, ensure_ascii=False)
    print(f"New articles file updated at {current_time_iso}")
    
    # Initialize analysis_results with current timestamp
    analysis_results = {
        "timestamp": current_time_iso,
        "total_batches": 0,
        "total_direct_news": 0,
        "direct_news": [],
        "batch_results": []
    }
    
    # Output new articles
    if new_articles:
        print(f"\n{len(new_articles)} NEW ARTICLES FOUND IN THIS RUN:")
        for article in new_articles:
            print(article)
        
        # Analyze new articles for BIST 100 stock relevance
        print("\nAnalyzing new articles for BIST 100 stock relevance...")
        analysis_results = analyze_news_for_stocks(new_articles)
        
        # Print summary of analysis
        if analysis_results["total_direct_news"] > 0:
            print("\nRELEVANT NEWS FOUND:")
            for news in analysis_results["direct_news"]:
                print(f"Stock: {news['hisse_kodu']} - {news['sirket_adi']} - URL: {news['haber_url']}")
        else:
            print("\nNo relevant news found for BIST 100 stocks.")
    else:
        print("\nNo new articles found in this run.")
    
    # Always save analysis results with updated timestamp, even if empty
    analysis_results["timestamp"] = current_time_iso  # Ensure timestamp is always current
    with open("stock_news_analysis.json", "w", encoding="utf-8") as f:
        json.dump(analysis_results, f, indent=2, ensure_ascii=False)
    
    # Load existing stock news mapping if it exists
    existing_mapping = {}
    if os.path.exists("stock_news_mapping.json"):
        try:
            with open("stock_news_mapping.json", "r", encoding="utf-8") as f:
                mapping_data = json.load(f)
                existing_mapping = mapping_data.get("stock_news", {})
        except:
            print("Error loading existing stock news mapping, creating new one")
    
    # Create new mapping from direct news
    if analysis_results["total_direct_news"] > 0:
        new_mapping = create_stock_news_mapping(analysis_results["direct_news"])
        
        # Merge with existing mapping
        new_mapping_items = False
        for stock_code, stock_data in new_mapping.items():
            if stock_code not in existing_mapping:
                # Add new stock entry with hisse_kodu
                existing_mapping[stock_code] = {
                    "hisse_kodu": stock_code,  # Added this line to include the stock code in each entry
                    "sirket_adi": stock_data["sirket_adi"],
                    "haberler": []
                }
            elif "hisse_kodu" not in existing_mapping[stock_code]:
                # Add hisse_kodu to existing entries that might not have it
                existing_mapping[stock_code]["hisse_kodu"] = stock_code
            
            # Add any new news URLs
            for news_url in stock_data["haberler"]:
                if news_url not in existing_mapping[stock_code]["haberler"]:
                    existing_mapping[stock_code]["haberler"].append(news_url)
                    new_mapping_items = True
    else:
        new_mapping_items = False
    
    # Always save the mapping file with current timestamp in every run
    mapping_data = {
        "timestamp": current_time_iso,  # Always update timestamp
        "updated": new_mapping_items,
        "stock_news": existing_mapping
    }
    
    with open("stock_news_mapping.json", "w", encoding="utf-8") as f:
        json.dump(mapping_data, f, indent=2, ensure_ascii=False)
    
    print(f"\nStock news mapping updated at {current_time_iso}")
    if new_mapping_items:
        print(f"Added new news for stocks")
    else:
        print("No new stock-specific news added in this run")

if __name__ == "__main__":
    main()

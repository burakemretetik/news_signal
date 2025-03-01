import os
from datetime import datetime, timedelta
import time
import pandas as pd
from openai import OpenAI

# Initialize OpenAI client
client = OpenAI()

def get_website_html(url):
    """Fetch HTML content from a given URL"""
@@ -129,8 +134,121 @@ def identify_new_articles(current_links, historical_data):
    new_articles = [link for link in current_links if link not in historical_links]
    return new_articles

def load_bist100_stocks():
    """Load BIST 100 stocks from CSV or download if not available"""
    csv_path = "bist_100_hisseleri.csv"
    
    if not os.path.exists(csv_path):
        print("Downloading BIST 100 stocks data...")
        url = "https://raw.githubusercontent.com/burakemretetik/news_signal/master/bist_100_hisseleri.csv"
        response = requests.get(url)
        with open(csv_path, "wb") as f:
            f.write(response.content)
    
    bist_100 = pd.read_csv(csv_path)
    return bist_100["Hisse Adı"].tolist()

def create_stock_batches(stock_list, n=10):
    """Creates batches of stock names from a list."""
    stock_batches = []
    for i in range(0, len(stock_list), n):
        stock_batches.append(stock_list[i : i + n])  # Slices list into batches of size n
    return stock_batches

def get_llm_response(stock_batch, recent_news):
    """Sends a prompt with stock batch and news to the LLM and gets a response."""
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
    ```json
    {{
      "direct_news": [
        {{"sirket_adi": "COMPANY_NAME", "haber_url": "NEWS_URL"}}
      ],
      "no_direct_news_found": true/false
    }}
    ```
    My Stocks: {stock_batch}

    News URL: {recent_news}"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",  # Using gpt-4o-mini as specified
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error getting LLM response: {e}")
        return json.dumps({"direct_news": [], "no_direct_news_found": True, "error": str(e)})

def analyze_news_for_stocks(new_articles):
    """Analyze new articles for relevance to BIST 100 stocks"""
    # Load BIST 100 stocks
    stock_list = load_bist100_stocks()
    
    # Create batches of 10 stocks
    stock_batches = create_stock_batches(stock_list, n=10)
    
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
        json.dump(analysis_results, f, indent=2)
    
    print(f"Stock news analysis completed. Found {len(direct_news)} relevant news articles.")
    return analysis_results

def main():
    """Main function to run the news scraper."""
    """Main function to run the news scraper and analyzer."""
    current_time = datetime.utcnow()
    current_time_iso = current_time.isoformat()

@@ -170,6 +288,18 @@ def main():
        with open("new_articles.json", "w", encoding="utf-8") as f:
            json.dump(new_articles_data, f, indent=2)
        print("New articles saved to new_articles.json")
        
        # Analyze new articles for stock relevance
        print("\nAnalyzing new articles for BIST 100 stock relevance...")
        analysis_results = analyze_news_for_stocks(new_articles)
        
        # Print summary of analysis
        if analysis_results["total_direct_news"] > 0:
            print("\nRELEVANT NEWS FOUND:")
            for news in analysis_results["direct_news"]:
                print(f"Stock: {news['sirket_adi']} - URL: {news['haber_url']}")
        else:
            print("\nNo relevant news found for BIST 100 stocks.")
    else:
        print("\nNo new articles found in this run.")

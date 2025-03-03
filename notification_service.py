import json
import os
import requests
from datetime import datetime, timedelta
import time
from supabase import create_client

# Initialize Supabase client
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# WhatsApp Business API credentials
WHATSAPP_API_URL = os.environ.get("WHATSAPP_API_URL")
WHATSAPP_API_TOKEN = os.environ.get("WHATSAPP_API_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_TEMPLATE_NAME = os.environ.get("WHATSAPP_TEMPLATE_NAME", "stock_news_alert")

def load_stock_news_mapping():
    """Load the stock news mapping from the JSON file"""
    try:
        with open("stock_news_mapping.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading stock news mapping: {e}")
        return {"timestamp": "", "updated": False, "stock_news": {}}

def get_users_for_stock(stock_kod):
    """Get all users subscribed to a specific stock"""
    try:
        response = supabase.table("user_stock_subscriptions")\
            .select("users(id, phone_number)")\
            .eq("stock_kod", stock_kod)\
            .execute()
        
        users = []
        for item in response.data:
            if item.get("users"):
                users.append({
                    "id": item["users"]["id"],
                    "phone_number": item["users"]["phone_number"]
                })
        return users
    except Exception as e:
        print(f"Error getting users for stock {stock_kod}: {e}")
        return []

def is_news_already_sent(user_id, stock_kod, news_url):
    """Check if this news has already been sent to this user"""
    try:
        response = supabase.table("sent_notifications")\
            .select("id")\
            .eq("user_id", user_id)\
            .eq("stock_kod", stock_kod)\
            .eq("news_url", news_url)\
            .execute()
        
        return len(response.data) > 0
    except Exception as e:
        print(f"Error checking if news was already sent: {e}")
        return True  # Assume already sent to prevent duplicate notifications

def send_whatsapp_message(to_phone, stock_kod, stock_name, news_url):
    """Send a WhatsApp message using the WhatsApp Business API"""
    headers = {
        "Authorization": f"Bearer {WHATSAPP_API_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # Format the message using a template
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone,
        "type": "template",
        "template": {
            "name": WHATSAPP_TEMPLATE_NAME,
            "language": {
                "code": "tr"  # Turkish language code (change as needed)
            },
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {
                            "type": "text",
                            "text": stock_kod
                        },
                        {
                            "type": "text",
                            "text": stock_name
                        },
                        {
                            "type": "text",
                            "text": news_url
                        }
                    ]
                }
            ]
        }
    }
    
    try:
        response = requests.post(
            f"{WHATSAPP_API_URL}/{WHATSAPP_PHONE_NUMBER_ID}/messages",
            headers=headers,
            json=payload
        )
        response.raise_for_status()
        result = response.json()
        return {
            "success": True,
            "message_id": result.get("messages", [{}])[0].get("id", "unknown"),
            "error": None
        }
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "message_id": None,
            "error": str(e)
        }

def record_sent_notification(user_id, stock_kod, news_url, status, message_id=None):
    """Record the sent notification in the database"""
    try:
        data = {
            "user_id": user_id,
            "stock_kod": stock_kod,
            "news_url": news_url,
            "status": status,
            "whatsapp_message_id": message_id
        }
        
        response = supabase.table("sent_notifications").insert(data).execute()
        return True
    except Exception as e:
        print(f"Error recording sent notification: {e}")
        return False

def process_notifications():
    """Process stock news and send notifications to subscribed users"""
    # Load stock news mapping
    mapping_data = load_stock_news_mapping()
    
    # Check if there are any updates
    if not mapping_data["updated"]:
        print("No updates in stock news mapping, skipping notification processing")
        return
    
    # Process each stock with news
    for stock_kod, stock_data in mapping_data["stock_news"].items():
        # Skip if no news
        if not stock_data.get("haberler"):
            continue
            
        # Get all users subscribed to this stock
        users = get_users_for_stock(stock_kod)
        if not users:
            print(f"No users subscribed to {stock_kod}, skipping")
            continue
            
        stock_name = stock_data.get("sirket_adi", stock_kod)
        
        # Process each news article for this stock
        for news_url in stock_data["haberler"]:
            # Send notification to each subscribed user
            for user in users:
                # Skip if already sent to this user
                if is_news_already_sent(user["id"], stock_kod, news_url):
                    continue
                    
                # Send WhatsApp message
                result = send_whatsapp_message(
                    user["phone_number"], 
                    stock_kod, 
                    stock_name, 
                    news_url
                )
                
                # Record the notification
                record_sent_notification(
                    user["id"],
                    stock_kod,
                    news_url,
                    "sent" if result["success"] else "failed",
                    result.get("message_id")
                )
                
                if result["success"]:
                    print(f"Notification sent to {user['phone_number']} for {stock_kod}")
                else:
                    print(f"Failed to send notification to {user['phone_number']} for {stock_kod}: {result['error']}")
                
                # Rate limiting to avoid API limits
                time.sleep(1)

def main():
    """Main function to run the notification service"""
    print(f"Starting notification service at {datetime.utcnow().isoformat()}")
    process_notifications()
    print(f"Notification processing completed at {datetime.utcnow().isoformat()}")

if __name__ == "__main__":
    main()

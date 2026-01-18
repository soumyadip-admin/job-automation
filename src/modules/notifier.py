"""
Telegram Notifier - Sends alerts and updates
"""
import os
import requests
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class Notifier:
    """Handles Telegram notifications."""
    
    def __init__(self):
        self.bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
        self.chat_id = os.getenv('TELEGRAM_CHAT_ID')
        self.enabled = bool(self.bot_token and self.chat_id)
        
        if not self.enabled:
            print("⚠️ Telegram not configured. Notifications disabled.")
    
    def send(self, message):
        """Send a Telegram message."""
        if not self.enabled:
            print(f"📢 [LOCAL] {message[:100]}...")
            return False
        
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True
            }
            response = requests.post(url, json=payload, timeout=10)
            return response.ok
        except Exception as e:
            print(f"❌ Telegram error: {e}")
            return False
    
    def notify_startup(self):
        """Notify that automation started."""
        msg = f"🚀 <b>Job Automation Started</b>\n\n🕐 {datetime.now().strftime('%d %b %Y, %I:%M %p')}"
        self.send(msg)
    
    def notify_application(self, job_data):
        """Notify about successful application."""
        msg = f"""✅ <b>Application Submitted!</b>

📋 <b>Job:</b> {job_data.get('title', 'N/A')}
🏢 <b>Company:</b> {job_data.get('company', 'N/A')}
📍 <b>Location:</b> {job_data.get('location', 'N/A')}
📊 <b>Match:</b> {job_data.get('match_score', 0)}%
🔗 <b>Platform:</b> {job_data.get('platform', 'N/A')}

🕐 {datetime.now().strftime('%d %b %Y, %I:%M %p')}"""
        self.send(msg)
    
    def notify_high_match(self, job_data):
        """Notify about high-matching job found."""
        msg = f"""🎯 <b>HIGH MATCH FOUND!</b>

📋 <b>Job:</b> {job_data.get('title', 'N/A')}
🏢 <b>Company:</b> {job_data.get('company', 'N/A')}
📊 <b>Match:</b> {job_data.get('match_score', 0)}%
💰 <b>Salary:</b> {job_data.get('salary', 'Not disclosed')}

🔗 {job_data.get('url', '')}"""
        self.send(msg)
    
    def notify_error(self, error_message):
        """Notify about an error."""
        msg = f"""❌ <b>Error Occurred</b>

{error_message[:200]}

🕐 {datetime.now().strftime('%d %b %Y, %I:%M %p')}"""
        self.send(msg)
    
    def notify_summary(self, stats):
        """Send daily summary."""
        msg = f"""📊 <b>Run Summary</b>

🔍 Jobs Scanned: {stats.get('scanned', 0)}
✅ Applied: {stats.get('applied', 0)}
⏭️ Skipped: {stats.get('skipped', 0)}
❌ Errors: {stats.get('errors', 0)}

🕐 {datetime.now().strftime('%d %b %Y, %I:%M %p')}"""
        self.send(msg)


# Test if run directly
if __name__ == "__main__":
    notifier = Notifier()
    notifier.send("🧪 Test message from Job Automation Bot!")
    print("Test complete!")
"""
Google Sheets Manager - Handles all spreadsheet operations
"""
import os
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class SheetsManager:
    """Manages Google Sheets operations for job tracking."""
    
    def __init__(self):
        self.spreadsheet_id = os.getenv('GOOGLE_SHEETS_SPREADSHEET_ID')
        self.credentials_path = os.getenv('GOOGLE_SHEETS_CREDENTIALS_PATH', 'config/credentials.json')
        self.client = None
        self.spreadsheet = None
        self._connected = False
    
    def connect(self):
        """Connect to Google Sheets."""
        try:
            import gspread
            from google.oauth2.service_account import Credentials
            
            SCOPES = [
                'https://www.googleapis.com/auth/spreadsheets',
                'https://www.googleapis.com/auth/drive'
            ]
            
            # STEP 1: Try JSON Secret (GitHub Actions - Priority 1)
            creds_json = os.getenv('GOOGLE_SHEETS_CREDENTIALS_JSON')
            
            if creds_json:
                try:
                    creds_dict = json.loads(creds_json)
                    credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
                    self.client = gspread.authorize(credentials)
                    self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
                    self._connected = True
                    print("✅ Connected to Google Sheets (via JSON Secret)")
                    return True
                except Exception as e:
                    print(f"⚠️ JSON secret failed, trying file path: {e}")
            
            # STEP 2: Try File Path (Local Development - Priority 2)
            creds_path = os.getenv('GOOGLE_SHEETS_CREDENTIALS_PATH', 'config/credentials.json')
            if os.path.exists(creds_path):
                credentials = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
                self.client = gspread.authorize(credentials)
                self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
                self._connected = True
                print("✅ Connected to Google Sheets (via File)")
                return True
            
            # STEP 3: No credentials found
            print("⚠️ No Google credentials found. Sheets logging disabled.")
            return False
            
        except Exception as e:
            print(f"❌ Google Sheets connection failed: {e}")
            self._connected = False
            return False
    
    def get_sheet(self, sheet_name):
        """Get or create a sheet by name."""
        if not self._connected:
            return None
        try:
            return self.spreadsheet.worksheet(sheet_name)
        except:
            return self.spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=20)
    
    def log_application(self, job_data):
        """Log a job application to the sheet."""
        if not self._connected:
            print(f"📝 [LOCAL LOG] Applied to: {job_data.get('company', 'Unknown')}")
            return
        
        try:
            sheet = self.get_sheet('Job_Applications')
            row = [
                f"APP_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                job_data.get('platform', ''),
                job_data.get('title', ''),
                job_data.get('company', ''),
                job_data.get('url', ''),
                job_data.get('location', ''),
                job_data.get('salary', ''),
                job_data.get('match_score', 0),
                'Applied',
                ', '.join(job_data.get('matched_skills', []))
            ]
            sheet.append_row(row)
            print(f"📝 Logged: {job_data.get('title')} at {job_data.get('company')}")
        except Exception as e:
            print(f"❌ Failed to log application: {e}")
    
    def check_already_applied(self, job_url):
        """Check if already applied to this job."""
        if not self._connected:
            return False
        try:
            sheet = self.get_sheet('Job_Applications')
            cell = sheet.find(job_url)
            return cell is not None
        except:
            return False
    
    def log_error(self, error_type, error_message, platform=''):
        """Log an error."""
        if not self._connected:
            print(f"❌ [ERROR] {error_type}: {error_message}")
            return
        try:
            sheet = self.get_sheet('Error_Log')
            row = [
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                error_type,
                error_message[:500],
                platform
            ]
            sheet.append_row(row)
        except Exception as e:
            print(f"Failed to log error: {e}")


# Test if run directly
if __name__ == "__main__":
    manager = SheetsManager()
    if manager.connect():
        print(f"Connected to: {manager.spreadsheet.title}")
    else:
        print("Running in offline mode")
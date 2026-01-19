"""
Google Sheets Manager - Handles all spreadsheet operations
"""
import os
import json
import base64
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class SheetsManager:
    """Manages Google Sheets operations for job tracking."""
    
    def __init__(self):
        self.spreadsheet_id = os.getenv('GOOGLE_SHEETS_SPREADSHEET_ID')
        self.client = None
        self.spreadsheet = None
        self._connected = False
        
        # Debug print
        print(f"[DEBUG] Spreadsheet ID: {self.spreadsheet_id}")
    
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
                print("[DEBUG] Found GOOGLE_SHEETS_CREDENTIALS_JSON")
                try:
                    # Handle Base64 decoding
                    if not creds_json.strip().startswith('{'):
                        decoded_bytes = base64.b64decode(creds_json)
                        decoded_str = decoded_bytes.decode('utf-8')
                        creds_dict = json.loads(decoded_str)
                        print("✅ Decoded Base64 credentials successfully")
                    else:
                        creds_dict = json.loads(creds_json)
                        print("✅ Parsed Raw JSON credentials")
                        
                    credentials = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
                    self.client = gspread.authorize(credentials)
                    
                    # Verify connection by opening sheet
                    self.spreadsheet = self.client.open_by_key(self.spreadsheet_id)
                    self._connected = True
                    print(f"✅ Connected to Google Sheet: {self.spreadsheet.title}")
                    return True
                except Exception as e:
                    print(f"❌ JSON Secret Error: {e}")
                    # Don't return False yet, try file fallback
            
            # STEP 2: Try File Path (Local Development - Priority 2)
            creds_path = os.getenv('GOOGLE_SHEETS_CREDENTIALS_PATH', 'config/credentials.json')
            if os.path.exists(creds_path):
                print(f"[DEBUG] Found credentials file at: {creds_path}")
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
            print(f"❌ Google Sheets Connection CRITICAL FAILURE: {e}")
            import traceback
            traceback.print_exc()
            self._connected = False
            return False
    
    def get_sheet(self, sheet_name):
        """Get or create a sheet by name."""
        if not self._connected:
            print("[ERROR] Cannot get sheet - not connected")
            return None
        try:
            return self.spreadsheet.worksheet(sheet_name)
        except:
            print(f"[INFO] Sheet '{sheet_name}' not found, creating it...")
            return self.spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=20)
    
    def log_application(self, job_data):
        """Log a job application to the sheet."""
        if not self._connected:
            print(f"📝 [LOCAL LOG ONLY] Applied to: {job_data.get('company', 'Unknown')}")
            return
        
        try:
            sheet = self.get_sheet('Job_Applications')
            if not sheet:
                print("❌ Failed to get 'Job_Applications' sheet")
                return

            row = [
                f"APP_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                str(job_data.get('platform', '')),
                str(job_data.get('title', '')),
                str(job_data.get('company', '')),
                str(job_data.get('url', '')),
                str(job_data.get('location', '')),
                str(job_data.get('salary', '')),
                str(job_data.get('match_score', 0)),
                'Applied',
                str(', '.join(job_data.get('matched_skills', [])))
            ]
            
            # Append row
            sheet.append_row(row)
            print(f"✅ [SHEET UPDATED] Logged: {job_data.get('title')} at {job_data.get('company')}")
            
        except Exception as e:
            print(f"❌ FAILED TO LOG APPLICATION: {e}")
            import traceback
            traceback.print_exc()
    
    def check_already_applied(self, job_url):
        """Check if already applied to this job."""
        if not self._connected:
            return False
        try:
            sheet = self.get_sheet('Job_Applications')
            if not sheet: return False
            
            # Search for URL in column F (index 6) or whole sheet
            cell = sheet.find(job_url)
            return cell is not None
        except:
            return False
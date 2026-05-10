"""
Ame Email & Calendar Agent (Google Integration)
Uses Google's InstalledAppFlow for a seamless one-click browser login.
"""

import os
import base64
import mimetypes
import shutil
import tempfile
import io
from email.message import EmailMessage
from datetime import datetime, timedelta

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# Scopes allow AME to read/send emails and view the calendar
SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/calendar.readonly'
]

def _get_credentials():
    """Handles the seamless Google login flow."""
    creds = None
    # Use hidden user directory for secure credential storage
    ame_dir = os.path.join(os.path.expanduser("~"), ".ame")
    os.makedirs(ame_dir, exist_ok=True)
    token_path = os.path.join(ame_dir, 'token.json')
    
    # Look for credentials.json in the backend folder first (developer drops it there),
    # but save the token securely in ~/.ame
    creds_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'credentials.json')

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(creds_path):
                raise FileNotFoundError("Google credentials.json not found! You must download your Desktop OAuth client from Google Cloud Console and place it in the backend folder.")
            # This spins up a local server and opens the user's browser to log in
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, 'w') as token:
            token.write(creds.to_json())
    
    return creds

def read_recent_emails(limit: int = 5, unread_only: bool = False) -> dict:
    """Read recent emails from the user's Gmail inbox."""
    try:
        creds = _get_credentials()
        service = build('gmail', 'v1', credentials=creds)
        
        query = "is:unread" if unread_only else ""
        results = service.users().messages().list(userId='me', labelIds=['INBOX'], q=query, maxResults=limit).execute()
        messages = results.get('messages', [])
        
        emails = []
        for msg in messages:
            # Fetch basic headers (Subject/From) and snippet to save tokens
            msg_data = service.users().messages().get(userId='me', id=msg['id'], format='metadata', metadataHeaders=['Subject', 'From']).execute()
            headers = msg_data.get('payload', {}).get('headers', [])
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
            
            emails.append({
                "id": msg['id'],
                "sender": sender,
                "subject": subject,
                "body": msg_data.get('snippet', '') + "..."
            })
            
        return {"success": True, "emails": emails, "message": f"Found {len(emails)} emails."}
    except Exception as e:
        return {"success": False, "message": f"Gmail error: {str(e)}"}

def send_email(to: str, subject: str, body: str = "", attachment_path: str = None) -> dict:
    """Draft and send a Gmail message, optionally with an attachment."""
    try:
        creds = _get_credentials()
        service = build('gmail', 'v1', credentials=creds)
        
        if to and to.lower() in ("me", "myself", "my email"):
            profile = service.users().getProfile(userId='me').execute()
            to = profile.get('emailAddress', to)
            
        message = EmailMessage()
        message.set_content(body or "")
        message['To'] = to or ""
        message['Subject'] = subject or ""
        
        if attachment_path:
            expanded_path = os.path.expanduser(attachment_path)
            if os.path.exists(expanded_path):
                attachment_path = expanded_path
            if not os.path.exists(attachment_path):
                return {"success": False, "message": f"Attachment failed: '{attachment_path}' does not exist. Did you use the exact absolute path from search_files?"}
            if os.path.isdir(attachment_path):
                # Automatically zip the folder into a temporary directory
                base_name = os.path.basename(attachment_path.rstrip("\\/"))
                zip_target = os.path.join(tempfile.gettempdir(), base_name)
                attachment_path = shutil.make_archive(zip_target, 'zip', attachment_path)
                
            ctype, encoding = mimetypes.guess_type(attachment_path)
            if ctype is None or encoding is not None:
                ctype = 'application/octet-stream'
            maintype, subtype = ctype.split('/', 1)
            with open(attachment_path, 'rb') as fp:
                message.add_attachment(fp.read(), maintype=maintype, subtype=subtype, filename=os.path.basename(attachment_path))
            
        message_bytes = message.as_bytes()
        media = MediaIoBaseUpload(io.BytesIO(message_bytes), mimetype='message/rfc822')
        service.users().messages().send(userId="me", body={}, media_body=media).execute()
        
        return {"success": True, "message": f"Email sent.", "ame_should_say": "Done, I sent it off!"}
    except Exception as e:
        return {"success": False, "message": f"Failed to send email: {str(e)}"}

def get_upcoming_meetings(days: int = 1) -> dict:
    """Read upcoming events from Google Calendar."""
    try:
        creds = _get_credentials()
        service = build('calendar', 'v3', credentials=creds)
        
        now = datetime.utcnow().isoformat() + 'Z'
        end = (datetime.utcnow() + timedelta(days=days)).isoformat() + 'Z'
        
        events_result = service.events().list(calendarId='primary', timeMin=now, timeMax=end, maxResults=10, singleEvents=True, orderBy='startTime').execute()
        events = events_result.get('items', [])
        
        parsed_events = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            parsed_events.append({
                "subject": event.get('summary', 'No Title'),
                "start": start,
            })
        return {"success": True, "events": parsed_events, "message": f"Found {len(parsed_events)} upcoming events."}
    except Exception as e:
        return {"success": False, "message": f"Calendar error: {str(e)}"}

def track_orders(days: int = 14) -> dict:
    """Find recent online orders, shipping confirmations, and deliveries from Gmail."""
    try:
        creds = _get_credentials()
        service = build('gmail', 'v1', credentials=creds)
        
        # Gmail search query for common order/shipping keywords
        query = f'(subject:"order" OR subject:"shipped" OR subject:"delivery" OR subject:"receipt" OR subject:"tracking") newer_than:{days}d'
        results = service.users().messages().list(userId='me', q=query, maxResults=15).execute()
        messages = results.get('messages', [])
        
        if not messages:
            return {"success": True, "orders": [], "message": f"No recent orders or shipping emails found in the last {days} days."}
            
        orders = []
        for msg in messages:
            msg_data = service.users().messages().get(userId='me', id=msg['id'], format='metadata', metadataHeaders=['Subject', 'From', 'Date']).execute()
            headers = msg_data.get('payload', {}).get('headers', [])
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
            date = next((h['value'] for h in headers if h['name'] == 'Date'), '')
            
            orders.append({
                "store": sender.split('<')[0].strip(' "'),
                "subject": subject,
                "date": date,
                "details": msg_data.get('snippet', '') + "..."
            })
            
        return {"success": True, "orders": orders, "message": f"Found {len(orders)} order-related emails."}
    except Exception as e:
        return {"success": False, "message": f"Failed to track orders: {str(e)}"}
import os
import base64
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.send'
]

CREDENTIALS_FILE = 'credentials.json'
TOKEN_FILE = 'token.json'

def get_credentials():
    creds = None
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception:
            # Token file is corrupted or invalid — delete and force re-auth
            os.remove(TOKEN_FILE)
            return None

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            with open(TOKEN_FILE, 'w') as f:
                f.write(creds.to_json())
        except Exception:
            # Refresh failed — token is dead, delete it
            os.remove(TOKEN_FILE)
            return None

    return creds

def is_authenticated():
    creds = get_credentials()
    return creds is not None and creds.valid and not creds.expired

def do_auth():
    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    creds = flow.run_local_server(port=8080, prompt='consent')
    with open(TOKEN_FILE, 'w') as f:
        f.write(creds.to_json())

def get_gmail_service():
    creds = get_credentials()
    return build('gmail', 'v1', credentials=creds)

def get_emails(max_results=10):
    service = get_gmail_service()
    results = service.users().threads().list(
        userId='me',
        labelIds=['INBOX'],
        maxResults=max_results
    ).execute()

    threads = results.get('threads', [])
    emails = []

    for thread in threads:
        thread_data = service.users().threads().get(
            userId='me',
            id=thread['id'],
            format='full'
        ).execute()

        messages = thread_data.get('messages', [])
        if not messages:
            continue

        latest = messages[-1]
        headers = latest['payload']['headers']
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
        date = next((h['value'] for h in headers if h['name'] == 'Date'), '')
        message_id = next((h['value'] for h in headers if h['name'].lower() == 'message-id'), None)
        snippet = thread_data.get('snippet', '')
        labels = latest.get('labelIds', [])

        thread_messages = []
        for msg in messages:
            msg_headers = msg['payload']['headers']
            msg_sender = next((h['value'] for h in msg_headers if h['name'] == 'From'), 'Unknown')
            msg_date = next((h['value'] for h in msg_headers if h['name'] == 'Date'), '')
            msg_body = extract_body(msg['payload'])
            thread_messages.append({
                'sender': msg_sender,
                'date': msg_date,
                'body': msg_body
            })

        emails.append({
            'id': thread['id'],
            'subject': subject,
            'sender': sender,
            'date': date,
            'snippet': snippet,
            'body': extract_body(latest['payload']),
            'unread': 'UNREAD' in labels,
            'thread_messages': thread_messages,
            'message_count': len(messages),
            'message_id': message_id,
            'latest_message_id': latest.get('id')
        })

    return emails

def extract_body(payload):
    body = ''
    if 'parts' in payload:
        for part in payload['parts']:
            if part['mimeType'] == 'text/plain':
                data = part['body'].get('data', '')
                if data:
                    body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
                    break
            elif 'parts' in part:
                body = extract_body(part)
                if body:
                    break
    else:
        data = payload['body'].get('data', '')
        if data:
            body = base64.urlsafe_b64decode(data).decode('utf-8', errors='ignore')
    return body[:3000]

def send_email(to, subject, body, thread_id=None, message_id=None):
    service = get_gmail_service()
    import email.mime.text
    import email.mime.multipart

    message = email.mime.multipart.MIMEMultipart()
    message['to'] = to
    message['subject'] = subject if subject.lower().startswith('re:') else f'Re: {subject}'
    if message_id:
        message['In-Reply-To'] = message_id
        message['References'] = message_id
    msg = email.mime.text.MIMEText(body)
    message.attach(msg)

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    send_body = {'raw': raw}
    if thread_id:
        send_body['threadId'] = thread_id
    service.users().messages().send(
        userId='me',
        body=send_body
    ).execute()

def get_new_emails(since_id=None, max_results=5):
    service = get_gmail_service()
    results = service.users().threads().list(
        userId='me',
        labelIds=['INBOX', 'UNREAD'],
        maxResults=max_results
    ).execute()

    threads = results.get('threads', [])
    emails = []

    for thread in threads:
        if since_id and thread['id'] == since_id:
            break

        thread_data = service.users().threads().get(
            userId='me',
            id=thread['id'],
            format='full'
        ).execute()

        messages = thread_data.get('messages', [])
        if not messages:
            continue

        latest = messages[-1]
        headers = latest['payload']['headers']
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
        sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown')
        date = next((h['value'] for h in headers if h['name'] == 'Date'), '')
        snippet = thread_data.get('snippet', '')
        labels = latest.get('labelIds', [])

        thread_messages = []
        for msg in messages:
            msg_headers = msg['payload']['headers']
            msg_sender = next((h['value'] for h in msg_headers if h['name'] == 'From'), 'Unknown')
            msg_date = next((h['value'] for h in msg_headers if h['name'] == 'Date'), '')
            msg_body = extract_body(msg['payload'])
            thread_messages.append({
                'sender': msg_sender,
                'date': msg_date,
                'body': msg_body
            })

        emails.append({
            'id': thread['id'],
            'subject': subject,
            'sender': sender,
            'date': date,
            'snippet': snippet,
            'body': extract_body(latest['payload']),
            'unread': 'UNREAD' in labels,
            'thread_messages': thread_messages,
            'message_count': len(messages),
            'latest_message_id': latest.get('id')
        })

    return emails

def mark_as_read(thread_id):
    service = get_gmail_service()
    # Get all message IDs in the thread
    thread = service.users().threads().get(
        userId='me',
        id=thread_id,
        format='minimal'
    ).execute()
    
    messages = thread.get('messages', [])
    for msg in messages:
        labels = msg.get('labelIds', [])
        if 'UNREAD' in labels:
            service.users().messages().modify(
                userId='me',
                id=msg['id'],
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
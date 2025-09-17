import json
import arxiv

import re
import os
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient
import gspread
from oauth2client.service_account import ServiceAccountCredentials

from datetime import datetime
from pathlib import Path
from rich.pretty import pprint

# ARXIV_REGEX = re.compile(r"https?://arxiv\.org/(abs|pdf)/[\w\.]+(?:\.pdf)?", re.IGNORECASE)
ARXIV_REGEX = re.compile(r"https?://arxiv\.org/(abs|pdf|html)/([\w\.]+)(?:\.pdf)?", re.IGNORECASE)

creds_path = Path('credentials.json')
creds      = json.loads(creds_path.read_text())

pprint(creds)
pprint(creds['google'])

GOOGLE_SCOPE  = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
GOOGLE_CREDS  = ServiceAccountCredentials.from_json_keyfile_dict(creds['google'], GOOGLE_SCOPE)
GOOGLE_CLIENT = gspread.authorize(GOOGLE_CREDS)
GOOGLE_SHEET_NAME = "Yochan Lab Reading Group Fight Club"  
GOOGLE_SHEET = GOOGLE_CLIENT.open(GOOGLE_SHEET_NAME).sheet1 # Suggested Papers, first worksheet

# spreadsheets = GOOGLE_CLIENT.openall()
# if not spreadsheets:
#     print("No spreadsheets found. Check sharing and credentials.")
# else:
#     print("Available spreadsheets:")
#     for sheet in spreadsheets:
#         print(f"- {sheet.title} (ID: {sheet.id})")
# 
# exit()

app = App(token=creds['socket_token'])

def extract_arxiv_id(match):
    """Extract the arXiv ID from the match."""
    section, paper_id = match.groups()
    return paper_id

def get_paper_title(paper_id):
    """Fetch title from arXiv API."""
    try:
        client = arxiv.Client()
        search = arxiv.Search(id_list=[paper_id])
        results = list(client.results(search))
        if results:
            return results[0].title
    except Exception as e:
        print(f"Error fetching title for {paper_id}: {e}")
    return "Unknown Title"

slack_bot_client = WebClient(token=creds['oauth'])

@app.event("message")
def handle_message_events(event, say, client):
    # Ignore bot messages or non-message subtypes
    if "subtype" in event or "bot_id" in event:
        return

    text    = event.get("text", "")
    user_id = event.get("user")

    print('Received message:')
    print(text)
    print(user_id)

    # # Find all arXiv links in the message
    matches = ARXIV_REGEX.finditer(text)
    links = [m.group(0) for m in matches]
    if not links:
        print('Message contained no arxiv links!')
        return
    print('Message contained ArXiv links')

    # # Get user's display name
    user_info = slack_bot_client.users_info(user=user_id)
    user_name = user_info["user"]["profile"]["real_name"]
    print('User name:', user_name)
    print('User info:', user_info)

    timestamp = datetime.now().strftime("%m/%d/%Y %H:%M:%S")

    matches = ARXIV_REGEX.finditer(text)
    for match in matches:
        paper_id = extract_arxiv_id(match)
        title    = get_paper_title(paper_id)
        row      = [timestamp, user_name, title, match.group(0), "1", ""]  # Topic blank
        GOOGLE_SHEET.append_row(row)  

    acknowledge_message = f'Added the follow arXiv links from {user_name} to the suggestions spreadsheet: ' + '\n'.join(links)
    slack_bot_client.chat_postMessage(channel=event["channel"], 
                                      text=acknowledge_message)

# Run the app
if __name__ == "__main__":
    handler = SocketModeHandler(app, creds['socket_token'])
    handler.start()

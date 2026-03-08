import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timezone
from notion_client import Client
from shared.config import NOTION_TOKEN, DATABASE_ID


def register_print_job(file_name: str, drive_path: str, copies: int,
                        duplex: str, color: str, paper_size: str = "A4") -> str:
    notion = Client(auth=NOTION_TOKEN)

    response = notion.pages.create(
        parent={"database_id": DATABASE_ID},
        properties={
            "file_name": {
                "title": [{"text": {"content": file_name}}]
            },
            "drive_path": {
                "rich_text": [{"text": {"content": drive_path}}]
            },
            "copies": {
                "number": copies
            },
            "duplex": {
                "select": {"name": duplex}
            },
            "color": {
                "select": {"name": color}
            },
            "paper_size": {
                "select": {"name": paper_size}
            },
            "status": {
                "select": {"name": "Pending"}
            },
            "created_at": {
                "date": {"start": datetime.now(timezone.utc).isoformat()}
            },
        },
    )

    return response["url"]

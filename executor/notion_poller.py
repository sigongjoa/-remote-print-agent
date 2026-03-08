import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timezone
from notion_client import Client
from shared.config import NOTION_TOKEN, DATABASE_ID


def _client() -> Client:
    return Client(auth=NOTION_TOKEN)


def get_pending_jobs() -> list[dict]:
    notion = _client()
    response = notion.databases.query(
        database_id=DATABASE_ID,
        filter={"property": "status", "select": {"equals": "Pending"}},
        sorts=[{"property": "created_at", "direction": "ascending"}],
    )
    jobs = []
    for page in response.get("results", []):
        props = page["properties"]

        def text(key):
            items = props.get(key, {}).get("rich_text", [])
            return items[0]["plain_text"] if items else ""

        def title(key):
            items = props.get(key, {}).get("title", [])
            return items[0]["plain_text"] if items else ""

        def select(key):
            s = props.get(key, {}).get("select")
            return s["name"] if s else ""

        def number(key):
            return props.get(key, {}).get("number") or 1

        jobs.append({
            "page_id": page["id"],
            "notion_url": page["url"],
            "file_name": title("file_name"),
            "drive_path": text("drive_path"),
            "copies": int(number("copies")),
            "duplex": select("duplex"),
            "color": select("color"),
            "paper_size": select("paper_size"),
        })
    return jobs


def set_status(page_id: str, status: str, error_msg: str = "") -> None:
    notion = _client()
    props = {
        "status": {"select": {"name": status}},
    }
    if status == "Done":
        props["printed_at"] = {
            "date": {"start": datetime.now(timezone.utc).isoformat()}
        }
    if error_msg:
        props["error_msg"] = {
            "rich_text": [{"text": {"content": error_msg[:2000]}}]
        }
    notion.pages.update(page_id=page_id, properties=props)

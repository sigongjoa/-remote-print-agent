import os
from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
DATABASE_ID = os.getenv("DATABASE_ID", "")
DRIVE_FOLDER = os.getenv("DRIVE_FOLDER", "remote-print-agent")
DRIVE_SYNC_PATH = os.getenv("DRIVE_SYNC_PATH", "")
PRINTER_NAME = os.getenv("PRINTER_NAME", "")
KAKAO_TOKEN = os.getenv("KAKAO_TOKEN", "")
SUMATRA_PATH = os.getenv("SUMATRA_PATH", "SumatraPDF.exe")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "60"))

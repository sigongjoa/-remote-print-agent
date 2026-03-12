#!/usr/bin/env python3
"""
Academy Executor - Notion DB를 폴링하여 Pending 출력 작업을 자동으로 처리한다.
Windows 시작 프로그램에 등록해 PC 부팅 시 자동 실행.

사용법:
    python executor.py
    python executor.py --once   # 한 번만 실행 (테스트용)
"""
import argparse
import logging
import os
import sys
import time
from pathlib import Path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from notion_poller import get_pending_jobs, set_status
from print_handler import send_to_printer
from spooler_check import wait_for_spooler
from notifier import send_failure_alert
from shared.config import DRIVE_SYNC_PATH, POLL_INTERVAL

# Google Drive API 연동
try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    HAS_GDRIVE = True
except ImportError:
    HAS_GDRIVE = False

GDRIVE_TOKEN_PATH = Path.home() / '.config/gws/drive_token.json'
GDRIVE_SCOPES = ['https://www.googleapis.com/auth/drive']

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("executor.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


def get_gdrive_service():
    """Google Drive API 서비스 객체 반환"""
    if not HAS_GDRIVE:
        return None
    if not GDRIVE_TOKEN_PATH.exists():
        log.warning("Google Drive 토큰 없음 - gdrive_tool.py로 먼저 인증 필요")
        return None
    creds = Credentials.from_authorized_user_file(str(GDRIVE_TOKEN_PATH), GDRIVE_SCOPES)
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        GDRIVE_TOKEN_PATH.write_text(creds.to_json())
    return build('drive', 'v3', credentials=creds)


def resolve_folder_id(svc, folder_path: str, parent_id: str = 'root') -> str:
    """폴더 경로를 Drive 폴더 ID로 변환 (예: '학생 교제/서재용/범주론')"""
    parts = [p.strip() for p in folder_path.replace('\\', '/').split('/') if p.strip()]
    current_id = parent_id
    for part in parts:
        q = f"'{current_id}' in parents and name='{part}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        res = svc.files().list(q=q, fields='files(id,name)').execute()
        files = res.get('files', [])
        if not files:
            return None
        current_id = files[0]['id']
    return current_id


def download_from_gdrive(drive_path: str, local_path: str) -> bool:
    """Google Drive에서 파일 다운로드"""
    svc = get_gdrive_service()
    if not svc:
        return False

    # 경로 정규화: 슬래시로 통일
    drive_path = drive_path.replace('\\', '/')
    parts = [p for p in drive_path.split('/') if p]
    if len(parts) < 1:
        return False

    file_name = parts[-1]
    folder_path = '/'.join(parts[:-1]) if len(parts) > 1 else ''

    try:
        # 폴더 ID 찾기
        if folder_path:
            folder_id = resolve_folder_id(svc, folder_path)
            if not folder_id:
                log.error(f"  Drive 폴더를 찾을 수 없음: {folder_path}")
                return False
        else:
            folder_id = 'root'

        # 파일 찾기
        q = f"'{folder_id}' in parents and name='{file_name}' and trashed=false"
        res = svc.files().list(q=q, fields='files(id,name)').execute()
        files = res.get('files', [])
        if not files:
            log.error(f"  Drive에서 파일을 찾을 수 없음: {file_name}")
            return False

        file_id = files[0]['id']

        # 로컬 폴더 생성
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)

        # 다운로드
        request = svc.files().get_media(fileId=file_id)
        with open(local_path, 'wb') as fh:
            downloader = MediaIoBaseDownload(fh, request)
            done = False
            while not done:
                _, done = downloader.next_chunk()

        log.info(f"  Drive에서 다운로드 완료: {file_name}")
        return True
    except Exception as e:
        log.error(f"  Drive 다운로드 실패: {e}")
        return False


def resolve_local_path(drive_path: str) -> str:
    """drive_path를 로컬 경로로 변환 (경로 구분자 통일)"""
    rel = drive_path.replace('/', os.sep).replace('\\', os.sep).lstrip(os.sep)
    return os.path.join(DRIVE_SYNC_PATH, rel)


def process_job(job: dict) -> None:
    page_id = job["page_id"]
    file_name = job["file_name"]
    log.info(f"처리 시작: {file_name}")

    set_status(page_id, "Printing")

    local_path = resolve_local_path(job["drive_path"])

    # 파일이 로컬에 없으면 Google Drive에서 다운로드
    if not os.path.isfile(local_path):
        log.info(f"  로컬에 파일 없음, Drive에서 다운로드 시도...")
        if not download_from_gdrive(job["drive_path"], local_path):
            err = f"파일을 찾을 수 없음: {local_path}"
            log.error(err)
            set_status(page_id, "Failed", err)
            send_failure_alert(file_name, err, job["notion_url"])
            return

    # 파일 존재 확인
    if not os.path.isfile(local_path):
        err = f"파일을 찾을 수 없음: {local_path}"
        log.error(err)
        set_status(page_id, "Failed", err)
        send_failure_alert(file_name, err, job["notion_url"])
        return

    try:
        send_to_printer(
            file_path=local_path,
            copies=job["copies"],
            duplex=job["duplex"],
            color=job["color"],
            paper_size=job["paper_size"],
        )
    except Exception as e:
        err = str(e)
        log.error(f"  출력 실패: {err}")
        set_status(page_id, "Failed", err)
        send_failure_alert(file_name, err, job["notion_url"])
        return

    received = wait_for_spooler(file_name, timeout=30)
    if not received:
        err = "스풀러 수신 확인 실패 (30초 타임아웃)"
        log.warning(f"  {err}")
        set_status(page_id, "Failed", err)
        send_failure_alert(file_name, err, job["notion_url"])
        return

    set_status(page_id, "Done")
    log.info(f"  완료: {file_name} ({job['copies']}부 / {job['duplex']} / {job['color']})")


def run_once() -> None:
    jobs = get_pending_jobs()
    if not jobs:
        log.info("대기 중인 출력 작업 없음")
        return
    log.info(f"Pending 작업 {len(jobs)}개 발견")
    for job in jobs:
        process_job(job)


def main():
    parser = argparse.ArgumentParser(description="Remote Print Agent - Academy Executor")
    parser.add_argument("--once", action="store_true", help="한 번만 실행 후 종료")
    args = parser.parse_args()

    if args.once:
        run_once()
        return

    log.info(f"Executor 시작 (폴링 간격: {POLL_INTERVAL}초)")
    while True:
        try:
            run_once()
        except Exception as e:
            log.error(f"폴링 오류: {e}")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()

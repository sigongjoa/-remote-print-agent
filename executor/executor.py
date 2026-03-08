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
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from notion_poller import get_pending_jobs, set_status
from print_handler import send_to_printer
from spooler_check import wait_for_spooler
from notifier import send_failure_alert
from shared.config import DRIVE_SYNC_PATH, POLL_INTERVAL

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("executor.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)


def resolve_local_path(drive_path: str) -> str:
    """drive_path를 로컬 Google Drive 동기화 경로로 변환한다."""
    rel = drive_path.lstrip("/")
    return os.path.join(DRIVE_SYNC_PATH, rel)


def process_job(job: dict) -> None:
    page_id = job["page_id"]
    file_name = job["file_name"]
    log.info(f"처리 시작: {file_name}")

    set_status(page_id, "Printing")

    local_path = resolve_local_path(job["drive_path"])

    # 파일이 동기화될 때까지 최대 5분 대기
    for attempt in range(10):
        if os.path.isfile(local_path):
            break
        log.info(f"  파일 대기 중... ({attempt + 1}/10): {local_path}")
        time.sleep(30)
    else:
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

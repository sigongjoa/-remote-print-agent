#!/usr/bin/env python3
"""
Remote Print Agent - System Tray Application
Notion DB를 폴링하여 자동으로 출력 작업을 처리하는 시스템 트레이 앱
"""
import os
import sys
import threading
import time
import logging
from datetime import datetime
from pathlib import Path

# 경로 설정
if getattr(sys, 'frozen', False):
    BASE_DIR = Path(sys.executable).parent
else:
    BASE_DIR = Path(__file__).parent

sys.path.insert(0, str(BASE_DIR))

from PIL import Image, ImageDraw
import pystray
from pystray import MenuItem as item

# 로깅 설정
log_path = BASE_DIR / "executor.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_path, encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# Windows 알림 (winotify 사용 - pystray와 호환)
try:
    from winotify import Notification, audio
    HAS_TOAST = True
except:
    HAS_TOAST = False


class PrintAgentTray:
    def __init__(self):
        self.running = False
        self.polling = False
        self.last_poll = None
        self.today_count = 0
        self.poll_interval = 60
        self.thread = None
        self.icon = None

        # 설정 로드
        self._load_config()

    def _load_config(self):
        """환경 변수 로드"""
        from dotenv import load_dotenv
        env_path = BASE_DIR / ".env"
        if env_path.exists():
            load_dotenv(env_path)

        self.poll_interval = int(os.getenv("POLL_INTERVAL", "60"))

    def _create_icon_image(self, color="green"):
        """트레이 아이콘 이미지 생성"""
        size = 64
        image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(image)

        # 프린터 모양 그리기
        colors = {
            "green": (34, 197, 94),
            "yellow": (234, 179, 8),
            "red": (239, 68, 68),
            "gray": (156, 163, 175)
        }
        c = colors.get(color, colors["gray"])

        # 프린터 본체
        draw.rectangle([8, 20, 56, 44], fill=c)
        # 용지 입력
        draw.rectangle([16, 8, 48, 24], fill=(255, 255, 255))
        # 용지 출력
        draw.rectangle([16, 40, 48, 56], fill=(255, 255, 255))
        # 상태 표시등
        draw.ellipse([44, 26, 52, 34], fill=(255, 255, 255))

        return image

    def _get_status_text(self):
        """현재 상태 텍스트"""
        if self.polling:
            return "폴링 중..."
        elif self.running:
            return "실행 중"
        else:
            return "중지됨"

    def _get_last_poll_text(self):
        """마지막 폴링 시간"""
        if self.last_poll:
            return f"마지막 폴링: {self.last_poll.strftime('%H:%M:%S')}"
        return "마지막 폴링: -"

    def _get_today_count_text(self):
        """오늘 출력 건수"""
        return f"오늘 출력: {self.today_count}건"

    def _create_menu(self):
        """트레이 메뉴 생성"""
        return pystray.Menu(
            item(lambda text: f"상태: {self._get_status_text()}", None, enabled=False),
            item(lambda text: self._get_last_poll_text(), None, enabled=False),
            item(lambda text: self._get_today_count_text(), None, enabled=False),
            pystray.Menu.SEPARATOR,
            item("지금 폴링", self._on_poll_now),
            item("로그 열기", self._on_open_log),
            pystray.Menu.SEPARATOR,
            item("일시정지" if self.running else "시작", self._on_toggle),
            item("종료", self._on_quit),
        )

    def _on_poll_now(self, icon, item):
        """수동 폴링"""
        if not self.polling:
            threading.Thread(target=self._run_once, daemon=True).start()

    def _on_open_log(self, icon, item):
        """로그 파일 열기"""
        os.startfile(str(log_path))

    def _on_toggle(self, icon, item):
        """시작/일시정지 토글"""
        if self.running:
            self.running = False
            self._update_icon("gray")
            self._notify("Remote Print Agent", "일시정지됨")
        else:
            self.running = True
            self._update_icon("green")
            self._notify("Remote Print Agent", "실행 시작")

    def _on_quit(self, icon, item):
        """종료"""
        self.running = False
        icon.stop()

    def _update_icon(self, color):
        """아이콘 색상 업데이트"""
        if self.icon:
            self.icon.icon = self._create_icon_image(color)

    def _notify(self, title, message):
        """Windows 알림"""
        if HAS_TOAST:
            try:
                toast = Notification(
                    app_id="Remote Print Agent",
                    title=title,
                    msg=message,
                    duration="short"
                )
                toast.show()
            except:
                pass
        log.info(f"[알림] {title}: {message}")

    def _run_once(self):
        """한 번 폴링 실행"""
        if self.polling:
            return

        self.polling = True
        self._update_icon("yellow")

        try:
            from executor.notion_poller import get_pending_jobs, set_status
            from executor.print_handler import send_to_printer
            from executor.spooler_check import wait_for_spooler
            from shared.config import DRIVE_SYNC_PATH

            jobs = get_pending_jobs()
            self.last_poll = datetime.now()

            if not jobs:
                log.info("대기 중인 출력 작업 없음")
                self._update_icon("green" if self.running else "gray")
                self.polling = False
                return

            log.info(f"Pending 작업 {len(jobs)}개 발견")

            for job in jobs:
                page_id = job["page_id"]
                file_name = job["file_name"]
                log.info(f"처리 시작: {file_name}")

                set_status(page_id, "Printing")

                # 파일 경로 확인
                drive_path = job["drive_path"].lstrip("/")
                local_path = os.path.join(DRIVE_SYNC_PATH, drive_path)

                # 파일 대기 (최대 5분)
                file_found = False
                for attempt in range(10):
                    if os.path.isfile(local_path):
                        file_found = True
                        break
                    log.info(f"  파일 대기 중... ({attempt + 1}/10): {local_path}")
                    time.sleep(30)

                if not file_found:
                    err = f"파일을 찾을 수 없음: {local_path}"
                    log.error(err)
                    set_status(page_id, "Failed", err)
                    self._notify("출력 실패", f"{file_name}: 파일 없음")
                    continue

                # 출력 실행
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
                    self._notify("출력 실패", f"{file_name}: {err[:50]}")
                    continue

                # 스풀러 확인
                received = wait_for_spooler(file_name, timeout=30)
                if not received:
                    err = "스풀러 수신 확인 실패"
                    log.warning(f"  {err}")
                    set_status(page_id, "Failed", err)
                    self._notify("출력 실패", f"{file_name}: 스풀러 오류")
                    continue

                # 완료
                set_status(page_id, "Done")
                self.today_count += 1
                log.info(f"  완료: {file_name}")
                self._notify("출력 완료", f"{file_name} ({job['copies']}부)")

        except Exception as e:
            log.error(f"폴링 오류: {e}")
            self._update_icon("red")
            time.sleep(5)
        finally:
            self.polling = False
            self._update_icon("green" if self.running else "gray")

    def _polling_loop(self):
        """백그라운드 폴링 루프"""
        while True:
            if self.running and not self.polling:
                self._run_once()
            time.sleep(self.poll_interval)

    def run(self):
        """앱 실행"""
        log.info("Remote Print Agent 시작")
        self._notify("Remote Print Agent", "시작됨")

        # 폴링 스레드 시작
        self.running = True
        self.thread = threading.Thread(target=self._polling_loop, daemon=True)
        self.thread.start()

        # 트레이 아이콘 생성
        self.icon = pystray.Icon(
            "RemotePrintAgent",
            self._create_icon_image("green"),
            "Remote Print Agent",
            menu=self._create_menu()
        )

        # 트레이 실행 (블로킹)
        self.icon.run()

        log.info("Remote Print Agent 종료")


def main():
    app = PrintAgentTray()
    app.run()


if __name__ == "__main__":
    main()

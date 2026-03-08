import subprocess
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.config import SUMATRA_PATH, PRINTER_NAME

DUPLEX_MAP = {
    "단면":        "simplex",
    "양면":        "duplexlong",
    "양면(짧은쪽)": "duplexshort",
}

COLOR_MAP = {
    "흑백": "monochrome",
    "컬러": "color",
}


def build_print_settings(copies: int, duplex: str, color: str, paper_size: str) -> str:
    parts = [
        DUPLEX_MAP.get(duplex, "simplex"),
        COLOR_MAP.get(color, "monochrome"),
        f"paper={paper_size}",
        f"copies={copies}",
    ]
    return ",".join(parts)


def send_to_printer(file_path: str, copies: int, duplex: str,
                    color: str, paper_size: str) -> None:
    """
    SumatraPDF CLI를 통해 파일을 프린터로 전송한다.
    Windows에서 실행하는 것을 전제로 한다.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"파일 없음: {file_path}")

    settings = build_print_settings(copies, duplex, color, paper_size)

    cmd = [
        SUMATRA_PATH,
        "-print-to", PRINTER_NAME,
        "-print-settings", settings,
        "-silent",
        file_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        raise RuntimeError(
            f"SumatraPDF 오류 (returncode={result.returncode}):\n"
            f"{result.stderr or result.stdout}"
        )

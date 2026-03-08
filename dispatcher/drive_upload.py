import subprocess
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.config import DRIVE_FOLDER


def upload(local_path: str, remote_subfolder: str = "") -> str:
    """
    rclone을 이용해 Google Drive에 파일을 업로드한다.
    반환값: Google Drive 상의 상대 경로 (drive_path)
    """
    file_name = os.path.basename(local_path)
    remote_dir = f"gdrive:{DRIVE_FOLDER}"
    if remote_subfolder:
        remote_dir = f"{remote_dir}/{remote_subfolder}"

    result = subprocess.run(
        ["rclone", "copy", local_path, remote_dir, "--progress"],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(f"rclone 업로드 실패:\n{result.stderr}")

    drive_path = f"{DRIVE_FOLDER}/{remote_subfolder}/{file_name}".strip("/")
    return drive_path

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from shared.config import DRIVE_FOLDER

SCOPES      = ['https://www.googleapis.com/auth/drive']
SECRET_PATH = Path.home() / '.config/gws/client_secret.json'
TOKEN_PATH  = Path.home() / '.config/gws/drive_token.json'


def _get_service():
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            TOKEN_PATH.write_text(creds.to_json())
        else:
            raise RuntimeError(
                "Google Drive 인증 필요 — gdrive_tool.py를 WSL 터미널에서 직접 실행해 토큰을 만드세요"
            )
    return build('drive', 'v3', credentials=creds)


def _get_or_create_folder(svc, name: str, parent_id: str = 'root') -> str:
    """폴더가 없으면 생성하고 ID 반환"""
    q = f"'{parent_id}' in parents and name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    res = svc.files().list(q=q, fields='files(id)').execute()
    files = res.get('files', [])
    if files:
        return files[0]['id']
    folder = svc.files().create(
        body={'name': name, 'parents': [parent_id], 'mimeType': 'application/vnd.google-apps.folder'},
        fields='id'
    ).execute()
    return folder['id']


def upload(local_path: str, remote_subfolder: str = "") -> str:
    """
    Google Drive API로 파일을 업로드한다.
    반환값: Google Drive 상의 상대 경로 (drive_path)
    """
    svc = _get_service()
    file_name = os.path.basename(local_path)

    # DRIVE_FOLDER 폴더 확보 (없으면 생성)
    folder_id = _get_or_create_folder(svc, DRIVE_FOLDER)

    # 하위 폴더가 지정된 경우
    if remote_subfolder:
        for part in remote_subfolder.strip('/').split('/'):
            folder_id = _get_or_create_folder(svc, part, folder_id)

    # 기존 파일 있으면 업데이트, 없으면 신규 생성
    q = f"'{folder_id}' in parents and name='{file_name}' and trashed=false"
    res = svc.files().list(q=q, fields='files(id)').execute()
    existing = res.get('files', [])

    mime = 'application/pdf' if local_path.endswith('.pdf') else 'application/octet-stream'
    media = MediaFileUpload(local_path, mimetype=mime, resumable=True)

    if existing:
        svc.files().update(fileId=existing[0]['id'], media_body=media).execute()
    else:
        svc.files().create(
            body={'name': file_name, 'parents': [folder_id]},
            media_body=media,
            fields='id'
        ).execute()

    drive_path = f"{DRIVE_FOLDER}/{remote_subfolder}/{file_name}".strip('/').replace('//', '/')
    return drive_path

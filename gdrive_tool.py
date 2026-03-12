#!/usr/bin/env python3
"""
Google Drive 업로드/다운로드/목록 툴

사용법:
  python3 gdrive_tool.py upload <파일> [파일...] --folder-name "이루다/증명"
  python3 gdrive_tool.py upload --all-pdf --folder-name "김시우/증명"
  python3 gdrive_tool.py upload /임의/경로/파일.pdf --folder-name "이루다/증명"
  python3 gdrive_tool.py list --folder-name "이루다"
  python3 gdrive_tool.py list --folder <FOLDER_ID>
  python3 gdrive_tool.py download 파일명.pdf --folder-name "이루다/증명" --dest ~/Downloads
  python3 gdrive_tool.py folders          # Drive 최상위 폴더 목록
"""
import os, sys, argparse
from pathlib import Path
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

SCOPES      = ['https://www.googleapis.com/auth/drive']
SECRET_PATH = Path.home() / '.config/gws/client_secret.json'
TOKEN_PATH  = Path.home() / '.config/gws/drive_token.json'
WORKDIR     = Path('/mnt/g/mathesis/proof_workbook')

# ── 인증 ────────────────────────────────────────────────────
def get_service():
    creds = None
    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
            TOKEN_PATH.write_text(creds.to_json())
        else:
            print("⚠️  인증 필요 — WSL 터미널에서 직접 실행하세요")
            flow = InstalledAppFlow.from_client_secrets_file(str(SECRET_PATH), SCOPES)
            creds = flow.run_local_server(port=8080, open_browser=False)
            TOKEN_PATH.write_text(creds.to_json())
            print(f"✅ 토큰 저장: {TOKEN_PATH}")
    return build('drive', 'v3', credentials=creds)

# ── 폴더 경로 → ID 변환 ("이루다/증명" → folder_id) ─────────
def resolve_folder(svc, folder_path: str, parent_id: str = 'root') -> str:
    """
    슬래시로 구분된 폴더 경로를 Drive 폴더 ID로 변환.
    예: "학생 교제/이루다/증명" → "1qzJkJk6..."
    """
    parts = [p.strip() for p in folder_path.split('/') if p.strip()]
    current_id = parent_id
    for part in parts:
        q = f"'{current_id}' in parents and name='{part}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        res = svc.files().list(q=q, fields='files(id,name)').execute()
        files = res.get('files', [])
        if not files:
            print(f"[ERROR] 폴더를 찾을 수 없음: '{part}' (경로: {folder_path})")
            print("  /drive-sync folders 로 폴더 목록을 확인하세요")
            sys.exit(1)
        current_id = files[0]['id']
    return current_id

def get_folder_id(svc, args) -> str:
    """--folder-name 또는 --folder(ID) 로 폴더 ID 반환"""
    if hasattr(args, 'folder_name') and args.folder_name:
        return resolve_folder(svc, args.folder_name)
    if hasattr(args, 'folder') and args.folder:
        return args.folder
    # 기본값: 이루다/증명
    return resolve_folder(svc, '학생 교제/이루다/증명')

# ── 전체 폴더 목록 ────────────────────────────────────────────
def list_folders(svc):
    res = svc.files().list(
        q="mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields='files(id,name,parents)',
        orderBy='name',
        pageSize=100
    ).execute()
    files = res.get('files', [])
    # id → name 맵
    id_to_name = {f['id']: f['name'] for f in files}

    def get_path(f):
        parents = f.get('parents', [])
        if not parents or parents[0] not in id_to_name:
            return f['name']
        return get_path({'id': parents[0], 'name': id_to_name[parents[0]],
                         'parents': next((x.get('parents',[]) for x in files if x['id']==parents[0]), [])}) + '/' + f['name']

    print(f'{"폴더 경로":<50} {"ID"}')
    print('-' * 80)
    for f in sorted(files, key=lambda x: x['name']):
        parents = f.get('parents', [])
        parent_name = id_to_name.get(parents[0], 'root') if parents else 'root'
        print(f'{parent_name + "/" + f["name"]:<50} {f["id"]}')

# ── 파일 목록 ────────────────────────────────────────────────
def list_files(svc, folder_id: str):
    res = svc.files().list(
        q=f"'{folder_id}' in parents and trashed=false",
        fields='files(id,name,mimeType,modifiedTime,size)',
        orderBy='name'
    ).execute()
    files = res.get('files', [])
    if not files:
        print('(폴더가 비어 있습니다)')
        return
    print(f'{"이름":<45} {"크기":>8}  {"수정일"}')
    print('-' * 70)
    for f in files:
        size = f.get('size', '-')
        size = f'{int(size)//1024}KB' if size != '-' else '-'
        print(f'{f["name"]:<45} {size:>8}  {f["modifiedTime"][:10]}')

# ── 업로드 ───────────────────────────────────────────────────
def upload_files(svc, files: list, folder_id: str, overwrite: bool = True):
    existing = {}
    if overwrite:
        res = svc.files().list(
            q=f"'{folder_id}' in parents and trashed=false",
            fields='files(id,name)'
        ).execute()
        existing = {f['name']: f['id'] for f in res.get('files', [])}

    for filepath in files:
        path = Path(filepath)
        if not path.exists():
            # WORKDIR 기준으로 재시도
            alt = WORKDIR / path.name
            if alt.exists():
                path = alt
            else:
                print(f'[SKIP] 파일 없음: {filepath}')
                continue

        mime = 'application/pdf' if path.suffix == '.pdf' else 'application/octet-stream'
        media = MediaFileUpload(str(path), mimetype=mime, resumable=True)

        if overwrite and path.name in existing:
            f = svc.files().update(
                fileId=existing[path.name],
                media_body=media,
                fields='id,name'
            ).execute()
            print(f'[UPDATE] {f["name"]}')
        else:
            f = svc.files().create(
                body={'name': path.name, 'parents': [folder_id]},
                media_body=media,
                fields='id,name'
            ).execute()
            print(f'[UPLOAD] {f["name"]}')

# ── 다운로드 ─────────────────────────────────────────────────
def download_file(svc, name_or_id: str, folder_id: str, dest_dir: str):
    dest = Path(dest_dir).expanduser()
    dest.mkdir(parents=True, exist_ok=True)

    if len(name_or_id) > 30 and '.' not in name_or_id:
        # Drive ID로 처리
        file_id = name_or_id
        meta = svc.files().get(fileId=file_id, fields='name').execute()
        file_name = meta['name']
    else:
        res = svc.files().list(
            q=f"'{folder_id}' in parents and name='{name_or_id}' and trashed=false",
            fields='files(id,name)'
        ).execute()
        files = res.get('files', [])
        if not files:
            print(f'[ERROR] 파일을 찾을 수 없음: {name_or_id}')
            sys.exit(1)
        file_id, file_name = files[0]['id'], files[0]['name']

    request = svc.files().get_media(fileId=file_id)
    out_path = dest / file_name
    with open(out_path, 'wb') as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
    print(f'[DOWNLOAD] {file_name} → {out_path}')

# ── CLI ─────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='Google Drive 툴')
    sub = parser.add_subparsers(dest='cmd')

    # 공통 폴더 옵션
    def add_folder_args(p):
        g = p.add_mutually_exclusive_group()
        g.add_argument('--folder-name', metavar='경로',
                       help='폴더 이름 경로 (예: "이루다/증명")')
        g.add_argument('--folder', metavar='ID',
                       help='Drive 폴더 ID')

    # upload
    up = sub.add_parser('upload', help='파일 업로드')
    up.add_argument('files', nargs='*', help='업로드할 파일 경로')
    up.add_argument('--all-pdf', action='store_true', help='workdir의 모든 PDF')
    up.add_argument('--no-overwrite', action='store_true')
    add_folder_args(up)

    # list
    ls = sub.add_parser('list', help='폴더 내 파일 목록')
    add_folder_args(ls)

    # download
    dl = sub.add_parser('download', help='파일 다운로드')
    dl.add_argument('target', help='파일 이름 또는 Drive ID')
    dl.add_argument('--dest', default=str(WORKDIR), help='저장 경로 (기본: workdir)')
    add_folder_args(dl)

    # folders
    sub.add_parser('folders', help='Drive 전체 폴더 목록')

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return

    svc = get_service()

    if args.cmd == 'folders':
        list_folders(svc)

    elif args.cmd == 'list':
        folder_id = get_folder_id(svc, args)
        list_files(svc, folder_id)

    elif args.cmd == 'upload':
        files = list(args.files) or []
        if args.all_pdf:
            files = [str(p) for p in WORKDIR.glob('*.pdf')]
        if not files:
            print('[ERROR] 파일을 지정하거나 --all-pdf를 사용하세요')
            sys.exit(1)
        folder_id = get_folder_id(svc, args)
        upload_files(svc, files, folder_id, overwrite=not args.no_overwrite)

    elif args.cmd == 'download':
        folder_id = get_folder_id(svc, args)
        download_file(svc, args.target, folder_id, args.dest)

if __name__ == '__main__':
    main()

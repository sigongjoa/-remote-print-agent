# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for Remote Print Agent
"""

import os
import sys

block_cipher = None

# 기본 경로
BASE_PATH = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    ['tray_executor.py'],
    pathex=[BASE_PATH],
    binaries=[],
    datas=[
        ('executor', 'executor'),
        ('shared', 'shared'),
        ('.env', '.'),
    ],
    hiddenimports=[
        'pystray._win32',
        'PIL._tkinter_finder',
        'win32api',
        'win32con',
        'win32gui',
        'winotify',
        'notion_client',
        'httpx',
        'dotenv',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='RemotePrintAgent',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # 콘솔 창 숨김
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # 아이콘 파일이 있으면 여기에 지정
)

# Remote Print Agent

학원 PC에 파일을 원격으로 전송하여 자동 출력하는 시스템.

```
로컬 PC → Google Drive → Notion DB → 학원 PC → 프린터
```

## 구조

| 컴포넌트 | 위치 | 역할 |
|----------|------|------|
| **Dispatcher** | 로컬 PC | PDF 업로드 + Notion 큐 등록 |
| **Executor** | 학원 PC (Windows) | Notion 폴링 + 자동 출력 |

---

## 설치

### 공통

```bash
pip install -r requirements.txt
cp .env.example .env
# .env 파일 편집
```

---

### 로컬 PC (Dispatcher)

1. [rclone](https://rclone.org/) 설치 후 Google Drive 연동

```bash
rclone config
# remote 이름을 "gdrive"로 설정
```

2. `.env` 설정

```env
NOTION_TOKEN=secret_xxx
DATABASE_ID=xxx
DRIVE_FOLDER=remote-print-agent
```

---

### 학원 PC (Executor, Windows)

1. [SumatraPDF](https://www.sumatrapdfreader.org/) 설치
2. Google Drive for Desktop 설치 및 로그인 (자동 동기화)
3. `.env` 설정

```env
NOTION_TOKEN=secret_xxx
DATABASE_ID=xxx
DRIVE_SYNC_PATH=G:\내 드라이브
PRINTER_NAME=프린터 이름
SUMATRA_PATH=C:\Program Files\SumatraPDF\SumatraPDF.exe
POLL_INTERVAL=60
```

4. 시작 프로그램 등록 (관리자 권한으로 실행)

```bat
setup_windows_startup.bat
```

---

## 사용법

```bash
python dispatcher/dispatcher.py \
  --file "수학_3단원.pdf" \
  --copies 30 \
  --duplex 양면 \
  --color 흑백 \
  --paper A4
```

### 옵션

| 옵션 | 기본값 | 선택지 |
|------|--------|--------|
| `--copies` | 1 | 숫자 |
| `--duplex` | 단면 | 단면 / 양면 / 양면(짧은쪽) |
| `--color` | 흑백 | 흑백 / 컬러 |
| `--paper` | A4 | A4 / B5 / A3 |
| `--subfolder` | (없음) | Drive 하위 폴더 |

---

## Notion DB 스키마

| 필드 | 타입 | 값 |
|------|------|-----|
| file_name | Title | 파일명 |
| drive_path | Text | Google Drive 상대 경로 |
| copies | Number | 출력 부수 |
| duplex | Select | 단면 / 양면 / 양면(짧은쪽) |
| color | Select | 흑백 / 컬러 |
| paper_size | Select | A4 / B5 / A3 |
| status | Select | Pending → Printing → Done / Failed |
| created_at | Date | 등록 시각 |
| printed_at | Date | 출력 완료 시각 |
| error_msg | Text | 실패 사유 |

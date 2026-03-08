#set document(title: "Remote Print Agent - 구현 보고서", author: "sigongjoa")
#set page(
  paper: "a4",
  margin: (top: 2.5cm, bottom: 2.5cm, left: 2.5cm, right: 2.5cm),
)
#set text(font: "Noto Sans CJK KR", size: 10.5pt, lang: "ko")
#show heading.where(level: 1): it => {
  set text(size: 16pt, weight: "bold")
  block(above: 1.5em, below: 0.8em)[#it]
}
#show heading.where(level: 2): it => {
  set text(size: 13pt, weight: "bold")
  block(above: 1.2em, below: 0.5em)[#it]
}
#show heading.where(level: 3): it => {
  set text(size: 11pt, weight: "bold")
  block(above: 1em, below: 0.4em)[#it]
}

// ── 표지 ───────────────────────────────────────────────────────────────
#align(center)[
  #v(3cm)
  #text(size: 28pt, weight: "bold")[Remote Print Agent]
  #v(0.5cm)
  #text(size: 16pt, fill: gray)[구현 보고서]
  #v(1cm)
  #line(length: 80%, stroke: 0.5pt + gray)
  #v(1cm)
  #grid(
    columns: (auto, auto),
    column-gutter: 2cm,
    row-gutter: 0.5cm,
    align: (right, left),
    [*프로젝트*], [sigongjoa / -remote-print-agent],
    [*작성일*],   [2026-03-08],
    [*목적*],     [학원 자동 출력 시스템 (Producer-Consumer 패턴)],
  )
  #v(3cm)
]

#pagebreak()

// ── 목차 ───────────────────────────────────────────────────────────────
#outline(title: "목차", indent: 1.5em)

#pagebreak()

// ── 1. 프로젝트 개요 ────────────────────────────────────────────────────
= 프로젝트 개요

== 배경 및 문제

로컬 PC에서 PDF 자료를 제작한 후 학원 프린터로 출력하는 기존 프로세스는 다음 6단계를 수동으로 거쳐야 했다.

#block(
  fill: luma(245),
  radius: 4pt,
  inset: 12pt,
)[
  로컬 작업 → CLI 업로드 → Google Drive 동기화 → Notion DB 등록 → 학원 PC 확인 → 수동 출력
]

핵심 제약 조건: 밤에 작업 시 학원 PC가 꺼져 있으므로 *비동기(Asynchronous) 처리*가 필수다.

== 목표

#quote[PDF를 저장만 하면 다음 날 출근 후 프린터 트레이에 이미 출력물이 나와 있는 완전 자동화]

== 전체 아키텍처

#block(
  fill: luma(245),
  radius: 4pt,
  inset: 12pt,
)[
  ```
  [로컬 PC]
    PDF 생성
    → (1) Google Drive 업로드       ← 파일 저장소
    → (2) Notion DB 큐 등록          ← 메타데이터 + 인쇄 설정 + 상태: Pending

  [학원 PC - 비동기, PC 부팅 시 자동 실행]
    → (3) Notion DB 폴링 (60초 간격)
    → (4) Google Drive 동기화 폴더에서 파일 확인
    → (5) SumatraPDF CLI로 지정 설정 출력
    → (6) Windows 스풀러 수신 확인
    → (7) Notion 상태 → Done
    → 실패 시 → 카카오톡 알림 전송
  ```
]

#pagebreak()

// ── 2. GitHub 이슈 #1 ──────────────────────────────────────────────────
= Issue \#1 — 전체 아키텍처 설계

== 구현 내용

Producer-Consumer 패턴을 기반으로 두 개의 독립 에이전트로 시스템을 분리했다.

- *Local Dispatcher* (Producer): 로컬 PC에서 동작, 파일을 클라우드에 던지고 종료
- *Academy Executor* (Consumer): 학원 PC에서 상시 대기, Notion을 폴링하여 작업 처리

이 구조의 핵심 이점은 *Decoupling* — 두 PC가 동시에 켜져 있을 필요가 없다.

== 파일 저장소 결정: Google Drive (Notion 아님)

Notion은 `curl` 한 줄로 PDF 파일 첨부가 불가능하다 (멀티스텝 업로드 API 필요). 따라서:

- *파일 저장소*: Google Drive (rclone으로 업로드)
- *큐 백엔드*: Notion DB (메타데이터만, API 호출 단순)

== 스크린샷

#figure(
  image("screenshots/01_architecture.png", width: 100%),
  caption: [GitHub Issue \#1 — 전체 아키텍처 설계],
)

#pagebreak()

// ── 3. GitHub 이슈 #2 ──────────────────────────────────────────────────
= Issue \#2 — Notion DB 스키마

== 구현 내용

Notion 데이터베이스를 출력 작업 큐로 활용하기 위한 스키마를 설계했다.

#figure(
  table(
    columns: (auto, auto, auto),
    inset: 8pt,
    align: left,
    table.header([*필드명*], [*타입*], [*설명*]),
    [`file_name`],   [Title],  [파일명],
    [`drive_path`],  [Text],   [Google Drive 상대 경로],
    [`copies`],      [Number], [출력 부수],
    [`duplex`],      [Select], [단면 / 양면 / 양면(짧은쪽)],
    [`color`],       [Select], [흑백 / 컬러],
    [`paper_size`],  [Select], [A4 / B5 / A3],
    [`status`],      [Select], [Pending / Printing / Done / Failed],
    [`created_at`],  [Date],   [등록 시각 (UTC)],
    [`printed_at`],  [Date],   [출력 완료 시각],
    [`error_msg`],   [Text],   [실패 사유],
  ),
  caption: [Notion DB 스키마],
)

`notion_poller.py`에서 `get_pending_jobs()`가 이 DB를 쿼리하고, `set_status()`로 상태를 갱신한다.

== 스크린샷

#figure(
  image("screenshots/02_notion_db_schema.png", width: 100%),
  caption: [GitHub Issue \#2 — Notion DB 스키마],
)

#pagebreak()

// ── 4. GitHub 이슈 #3 ──────────────────────────────────────────────────
= Issue \#3 — Local Dispatcher

== 구현 내용

로컬 PC에서 실행하는 CLI 도구다. 단일 명령어로 업로드와 큐 등록을 완료한다.

#block(
  fill: luma(245),
  radius: 4pt,
  inset: 12pt,
)[
  ```bash
  python dispatcher.py \
    --file "수학_3단원.pdf" \
    --copies 30 \
    --duplex 양면 \
    --color 흑백
  ```
]

=== 구성 모듈

- `drive_upload.py` — `rclone copy`로 Google Drive 업로드, 성공 시 `drive_path` 반환
- `notion_queue.py` — Notion API로 새 페이지 생성, 인쇄 설정 + 상태 `Pending` 초기화
- `dispatcher.py` — argparse CLI, 두 모듈을 순서대로 호출

=== 실행 흐름

#block(
  fill: luma(245),
  radius: 4pt,
  inset: 12pt,
)[
  ```
  [1/2] Google Drive 업로드 중... (수학_3단원.pdf)
        완료: remote-print-agent/수학_3단원.pdf
  [2/2] Notion 큐 등록 중...
        완료: https://www.notion.so/xxx

  ✓ 출력 대기열에 등록되었습니다.
    파일: 수학_3단원.pdf
    부수: 30부 / 양면 / 흑백 / A4
  ```
]

== 스크린샷

#figure(
  image("screenshots/03_local_dispatcher.png", width: 100%),
  caption: [GitHub Issue \#3 — Local Dispatcher],
)

#pagebreak()

// ── 5. GitHub 이슈 #4 ──────────────────────────────────────────────────
= Issue \#4 — Academy Executor

== 구현 내용

학원 PC에서 상시 실행되는 폴링 데몬이다. Windows 시작 프로그램에 등록하여 PC 부팅 시 자동 시작.

=== 처리 흐름

+ Notion DB에서 `status == Pending` 항목 조회 (created_at 오름차순)
+ `status → Printing`으로 즉시 업데이트 (중복 처리 방지)
+ Google Drive 동기화 폴더에서 파일 확인 (최대 5분, 30초 간격 재시도)
+ SumatraPDF CLI로 출력 명령 전송
+ Windows 스풀러 수신 확인 (최대 30초)
+ 성공 → `status → Done`, `printed_at` 기록
+ 실패 → `status → Failed`, `error_msg` 기록 + 카카오톡 알림

=== SumatraPDF 설정 변환

#block(
  fill: luma(245),
  radius: 4pt,
  inset: 12pt,
)[
  ```python
  DUPLEX_MAP = {"단면": "simplex", "양면": "duplexlong", ...}
  COLOR_MAP  = {"흑백": "monochrome", "컬러": "color"}

  # → "-print-settings duplexlong,monochrome,paper=A4,copies=30"
  ```
]

== 스크린샷

#figure(
  image("screenshots/04_academy_executor.png", width: 100%),
  caption: [GitHub Issue \#4 — Academy Executor],
)

#pagebreak()

// ── 6. GitHub 이슈 #5 ──────────────────────────────────────────────────
= Issue \#5 — 카카오톡 알림

== 구현 내용

출력 실패 시 카카오톡 *나에게 보내기* REST API로 즉시 알림을 전송한다.

=== 인증 방식

카카오 개발자 콘솔에서 앱 생성 후 `access_token`을 발급받아 `.env`에 저장. 별도 비즈니스 채널 불필요.

=== 알림 예시

#block(
  fill: luma(245),
  radius: 4pt,
  inset: 12pt,
)[
  ```
  [원격 출력 실패 알림]
  파일: 수학_3단원.pdf
  사유: 파일을 찾을 수 없음: G:\내 드라이브\...
  Notion: https://www.notion.so/xxx
  ```
]

`KAKAO_TOKEN`이 미설정된 경우 알림을 스킵하고 콘솔 로그만 출력하여 개발 환경에서 오류 없이 동작한다.

== 스크린샷

#figure(
  image("screenshots/05_kakao_notification.png", width: 100%),
  caption: [GitHub Issue \#5 — 카카오톡 알림],
)

#pagebreak()

// ── 7. GitHub 이슈 #6 ──────────────────────────────────────────────────
= Issue \#6 — 환경 설정

== 구현 내용

=== 프로젝트 디렉토리 구조

#block(
  fill: luma(245),
  radius: 4pt,
  inset: 12pt,
)[
  ```
  remote-print-agent/
  ├── dispatcher/
  │   ├── dispatcher.py       # CLI 진입점
  │   ├── drive_upload.py     # rclone 업로드
  │   └── notion_queue.py     # Notion API 큐 등록
  ├── executor/
  │   ├── executor.py         # 폴링 데몬
  │   ├── notion_poller.py    # Notion 조회/상태 갱신
  │   ├── print_handler.py    # SumatraPDF 출력 제어
  │   ├── spooler_check.py    # Windows 스풀러 확인
  │   └── notifier.py         # 카카오톡 알림
  ├── shared/
  │   └── config.py           # 환경변수 로드
  ├── report/
  │   ├── report.typ          # Typst 보고서 소스
  │   └── screenshots/        # Playwright 스크린샷
  ├── .env.example            # 환경변수 템플릿
  ├── requirements.txt
  └── setup_windows_startup.bat  # 학원 PC 시작 등록
  ```
]

=== 학원 PC Windows 시작 등록

`setup_windows_startup.bat`을 관리자 권한으로 실행하면 `%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup`에 자동 등록된다.

== 스크린샷

#figure(
  image("screenshots/06_setup.png", width: 100%),
  caption: [GitHub Issue \#6 — 환경 설정],
)

#pagebreak()

// ── 8. 요약 ────────────────────────────────────────────────────────────
= 구현 요약

#figure(
  table(
    columns: (auto, auto, auto),
    inset: 8pt,
    align: left,
    table.header([*Issue*], [*제목*], [*상태*]),
    [\#1], [전체 아키텍처 설계],      [완료],
    [\#2], [Notion DB 스키마],        [완료],
    [\#3], [Local Dispatcher],        [완료],
    [\#4], [Academy Executor],        [완료],
    [\#5], [카카오톡 알림],           [완료],
    [\#6], [환경 설정 스크립트],      [완료],
  ),
  caption: [전체 이슈 구현 현황],
)

== 남은 작업 (사용자 직접 수행)

+ `.env` 파일 생성 (`NOTION_TOKEN`, `DATABASE_ID` 등 실제 값 입력)
+ Notion DB 생성 및 스키마 적용
+ `rclone config`로 Google Drive 연결 (로컬 PC)
+ SumatraPDF 설치 및 `PRINTER_NAME` 확인 (학원 PC)
+ 카카오 개발자 앱 생성 및 `KAKAO_TOKEN` 발급
+ `setup_windows_startup.bat` 실행 (학원 PC)

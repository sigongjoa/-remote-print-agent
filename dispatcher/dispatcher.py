#!/usr/bin/env python3
"""
Local Dispatcher - PDF를 Google Drive에 업로드하고 Notion DB에 큐를 등록한다.

사용법:
    python dispatcher.py --file "수학_3단원.pdf" --copies 30 --duplex 양면 --color 흑백
"""
import argparse
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from drive_upload import upload
from notion_queue import register_print_job


def parse_args():
    parser = argparse.ArgumentParser(description="Remote Print Agent - Local Dispatcher")
    parser.add_argument("--file", required=True, help="업로드할 PDF 파일 경로")
    parser.add_argument("--copies", type=int, default=1, help="출력 부수 (기본값: 1)")
    parser.add_argument("--duplex", choices=["단면", "양면", "양면(짧은쪽)"],
                        default="단면", help="단면/양면 선택")
    parser.add_argument("--color", choices=["흑백", "컬러"],
                        default="흑백", help="흑백/컬러 선택")
    parser.add_argument("--paper", choices=["A4", "B5", "A3"],
                        default="A4", help="용지 크기")
    parser.add_argument("--subfolder", default="",
                        help="Google Drive 하위 폴더 (선택)")
    return parser.parse_args()


def main():
    args = parse_args()

    if not os.path.isfile(args.file):
        print(f"[오류] 파일을 찾을 수 없습니다: {args.file}")
        sys.exit(1)

    file_name = os.path.basename(args.file)

    print(f"[1/2] Google Drive 업로드 중... ({file_name})")
    try:
        drive_path = upload(args.file, args.subfolder)
        print(f"      완료: {drive_path}")
    except RuntimeError as e:
        print(f"[오류] {e}")
        sys.exit(1)

    print(f"[2/2] Notion 큐 등록 중...")
    notion_url = register_print_job(
        file_name=file_name,
        drive_path=drive_path,
        copies=args.copies,
        duplex=args.duplex,
        color=args.color,
        paper_size=args.paper,
    )
    print(f"      완료: {notion_url}")
    print()
    print(f"✓ 출력 대기열에 등록되었습니다.")
    print(f"  파일: {file_name}")
    print(f"  부수: {args.copies}부 / {args.duplex} / {args.color} / {args.paper}")
    print(f"  Notion: {notion_url}")


if __name__ == "__main__":
    main()

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import requests
from shared.config import KAKAO_TOKEN

KAKAO_SEND_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"


def send_failure_alert(file_name: str, error_msg: str, notion_url: str) -> None:
    """카카오톡 나에게 보내기로 출력 실패 알림을 전송한다."""
    if not KAKAO_TOKEN:
        print(f"[알림 스킵] KAKAO_TOKEN 미설정 - 실패: {file_name} / {error_msg}")
        return

    text = (
        f"[원격 출력 실패 알림]\n"
        f"파일: {file_name}\n"
        f"사유: {error_msg}\n"
        f"Notion: {notion_url}"
    )

    payload = {
        "template_object": {
            "object_type": "text",
            "text": text,
            "link": {
                "web_url": notion_url,
                "mobile_web_url": notion_url,
            },
        }
    }

    headers = {
        "Authorization": f"Bearer {KAKAO_TOKEN}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    import json
    response = requests.post(
        KAKAO_SEND_URL,
        headers=headers,
        data={"template_object": json.dumps(payload["template_object"])},
    )

    if response.status_code != 200:
        print(f"[알림 오류] 카카오톡 전송 실패: {response.status_code} {response.text}")
    else:
        print(f"[알림] 카카오톡 전송 완료: {file_name}")

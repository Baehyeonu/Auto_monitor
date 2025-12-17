#!/usr/bin/env python3
"""
두 채널의 최근 메시지를 Slack API로 가져와서 구조를 비교하는 스크립트
"""
import os
import sys
import json
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# 프로젝트 루트 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'Back'))

from config import config

def fetch_recent_messages(channel_id: str, limit: int = 3) -> list:
    """채널의 최근 메시지를 가져옴"""
    client = WebClient(token=config.SLACK_BOT_TOKEN)

    try:
        response = client.conversations_history(
            channel=channel_id,
            limit=limit
        )
        return response.get('messages', [])
    except SlackApiError as e:
        print(f"❌ 에러: {e.response['error']}")
        return []

def main():
    print("=" * 80)
    print("📊 Slack 채널 메시지 구조 비교")
    print("=" * 80)

    # 카메라/입장/퇴장 채널
    print("\n🎥 [카메라/입장/퇴장 채널] - Socket Mode 정상 작동")
    print(f"채널 ID: {config.SLACK_CHANNEL_ID}")
    print("-" * 80)

    camera_messages = fetch_recent_messages(config.SLACK_CHANNEL_ID, limit=1)
    if camera_messages:
        print(json.dumps(camera_messages[0], indent=2, ensure_ascii=False))
    else:
        print("❌ 메시지 없음")

    # 상태 채널
    print("\n" + "=" * 80)
    print("\n📋 [OZ헬프센터 상태 채널] - Socket Mode 작동 안 함")
    print(f"채널 ID: {config.SLACK_STATUS_CHANNEL_ID}")
    print("-" * 80)

    status_messages = fetch_recent_messages(config.SLACK_STATUS_CHANNEL_ID, limit=1)
    if status_messages:
        print(json.dumps(status_messages[0], indent=2, ensure_ascii=False))
    else:
        print("❌ 메시지 없음")

    # 핵심 차이점 비교
    if camera_messages and status_messages:
        print("\n" + "=" * 80)
        print("\n🔍 핵심 차이점:")
        print("-" * 80)

        cam_msg = camera_messages[0]
        stat_msg = status_messages[0]

        print(f"카메라 채널 - subtype: {cam_msg.get('subtype', '(없음)')}")
        print(f"상태 채널   - subtype: {stat_msg.get('subtype', '(없음)')}")
        print()
        print(f"카메라 채널 - bot_id: {cam_msg.get('bot_id', '(없음)')}")
        print(f"상태 채널   - bot_id: {stat_msg.get('bot_id', '(없음)')}")
        print()
        print(f"카메라 채널 - user: {cam_msg.get('user', '(없음)')}")
        print(f"상태 채널   - user: {stat_msg.get('user', '(없음)')}")
        print()
        print(f"카메라 채널 - type: {cam_msg.get('type', '(없음)')}")
        print(f"상태 채널   - type: {stat_msg.get('type', '(없음)')}")

if __name__ == "__main__":
    main()

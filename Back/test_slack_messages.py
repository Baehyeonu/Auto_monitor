#!/usr/bin/env python3
"""Slack 메시지 형식 확인 테스트 스크립트"""
import os
import json
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

def main():
    # 환경 변수에서 토큰과 채널 ID 가져오기
    bot_token = os.getenv("SLACK_BOT_TOKEN")
    channel_id = os.getenv("SLACK_STATUS_CHANNEL_ID")

    if not bot_token or not channel_id:
        print("❌ SLACK_BOT_TOKEN 또는 SLACK_STATUS_CHANNEL_ID가 설정되지 않았습니다.")
        print(f"SLACK_BOT_TOKEN: {bool(bot_token)}")
        print(f"SLACK_STATUS_CHANNEL_ID: {channel_id}")
        return

    print(f"✅ 토큰: {bot_token[:10]}...")
    print(f"✅ 채널 ID: {channel_id}")
    print()

    # Slack 클라이언트 생성
    client = WebClient(token=bot_token)

    try:
        # 최근 메시지 10개 가져오기
        result = client.conversations_history(
            channel=channel_id,
            limit=10
        )

        messages = result.get("messages", [])
        print(f"📨 최근 메시지 {len(messages)}개 조회됨\n")
        print("=" * 80)

        for i, msg in enumerate(messages, 1):
            print(f"\n{'='*80}")
            print(f"메시지 #{i}")
            print(f"{'='*80}")

            # 메시지 타입 정보
            print(f"타입: {msg.get('type')}")
            print(f"서브타입: {msg.get('subtype', 'None')}")
            print(f"유저: {msg.get('user', msg.get('bot_id', 'Unknown'))}")
            print(f"타임스탬프: {msg.get('ts')}")

            # text 필드
            text = msg.get("text", "")
            print(f"\n📝 text 필드 (길이: {len(text)}):")
            if text:
                print(text[:200])
            else:
                print("(비어있음)")

            # blocks 필드
            blocks = msg.get("blocks", [])
            print(f"\n📦 blocks 필드 (개수: {len(blocks)}):")
            if blocks:
                # 블록에서 텍스트 추출
                extracted_texts = []
                for block in blocks:
                    if block.get("type") == "rich_text":
                        for element in block.get("elements", []):
                            if element.get("type") == "rich_text_section":
                                for item in element.get("elements", []):
                                    if item.get("type") == "text":
                                        extracted_texts.append(item.get("text", ""))

                if extracted_texts:
                    full_text = "".join(extracted_texts)
                    print(f"추출된 텍스트 (길이: {len(full_text)}):")
                    print(full_text[:300])
                else:
                    print("텍스트 추출 실패")

                # 전체 blocks JSON 출력
                print(f"\n전체 blocks JSON:")
                print(json.dumps(blocks, indent=2, ensure_ascii=False)[:500])
            else:
                print("(비어있음)")

            print(f"\n{'='*80}\n")

    except SlackApiError as e:
        print(f"❌ Slack API 오류: {e.response['error']}")
        print(f"세부 정보: {e.response}")

if __name__ == "__main__":
    main()

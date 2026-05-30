import asyncio
import os

# 테스트용 환경 변수 세팅 
os.environ["TELEGRAM_BOT_TOKEN"] = "8859598706:AAFhUUvltPCKkO-tZ8pj5Gy4QnovTEMxamQ"
os.environ["TELEGRAM_CHAT_ID"] = "8774642535"

from services.alert_service import send_telegram

async def main():
    print("텔레그램 알림 발송 테스트 시작...")
    
    test_message = " [TEST] 공장 모니터링 시스템 텔레그램 연동 성공"
    
    # 함수 실행!
    await send_telegram(test_message)
    
    print("테스트 스크립트 실행 완료!")

if __name__ == "__main__":
    # 비동기 함수 실행
    asyncio.run(main())
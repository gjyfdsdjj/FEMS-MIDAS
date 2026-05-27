# backend/services/alert_service.py
# 알림 생성, 저장, Telegram 발송 로직
#
# - create_alert(factory_id, level, alert_type, message)
#     중복 window 확인 (300초 내 동일 factory_id + type 존재 시 skip)
#     alerts 테이블 INSERT
#     CRITICAL / WARNING 이면 send_telegram 호출
#
# - send_telegram(message)
#     환경변수 TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID 사용
#     httpx.AsyncClient로 발송
#     실패 시 system_events에 에러 기록 (알림 실패가 서비스 중단으로 이어지지 않도록)
#
# - acknowledge_alert(alert_id, acknowledged_by)
#     is_acknowledged=True, acknowledged_at, acknowledged_by 업데이트
#
# - get_alerts(factory_id?, level?, is_acknowledged?, limit, cursor)
#     alerts 커서 페이지네이션
#
# - get_alert_rules()
#     현재 임계값 반환 (temp_deviation_threshold_c / communication_timeout_sec / dedup_window_sec)

import os
import httpx
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from backend.repositories.alert_repository import check_duplicate_alert, insert_alert

logger = logging.getLogger(__name__)

# 텔레그램 봇을 통해 지정된 채팅방으로 메시지를 발송하는 함수
async def send_telegram(message: str):

    # 환경 변수에서 토큰과 챗 ID 가져옴
    BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

    if not BOT_TOKEN or not CHAT_ID:
        logger.warning("텔레그램 환경 변수(TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID)가 설정되지 않았습니다.")
        return
    
    # 텔레그램 API URL 
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": message
    }

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload)
            response.raise_for_status() # 4xx, 5xx 에러 발생 시 예외(Exception)를 유도
            print("텔레그램 알림 발송 성공!")
    
    except Exception as e:
        logger.error(f"텔레그램 발송 실패: {e}")

# 공장 알림을 생성하고 중복 체크 후 발송하는 함수
async def create_alert(db: AsyncSession, factory_id: int, priority: str, alert_type: str, message: str):
    # 300초 전 시간 계산
    time_limit = datetime.now(timezone.utc) - timedelta(seconds=300)
    
    # 300초 내에 동일한 알림이 있는지 확인
    is_dup = await check_duplicate_alert(db, factory_id, alert_type, time_limit)
    
    if is_dup:
        print(f"[{alert_type}] 5분 내 중복 알림이므로 생략합니다. (공장 ID: {factory_id})")
        return None
        
    # 중복이 아니면 DB에 저장 
    # (DDL의 컬럼명이 priority이므로 레포지토리 함수 인자에는 level 값을 priority로 넘겨줌)
    new_alert = await insert_alert(db, factory_id, priority=priority, alert_type=alert_type, message=message)
    
    # 4. CRITICAL / WARNING 이면 send_telegram 호출
    if level.lower() in ["critical", "warning"]:
        telegram_msg = f"⚠️ [{level.upper()}] 공장 {factory_id}번 알림\n타입: {alert_type}\n내용: {message}"
        await send_telegram(telegram_msg)
        
    return new_alert




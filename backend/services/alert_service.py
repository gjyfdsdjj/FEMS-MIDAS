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

from repositories.alert_repository import check_duplicate_alert, insert_alert, update_alert_acknowledge

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
async def create_alert(db: AsyncSession, factory_id: int, priority: str, severity: str, alert_type: str, message: str):
    # 300초 전 시간 계산
    time_limit = datetime.now(timezone.utc) - timedelta(seconds=300)
    
    # 300초 내에 동일한 알림이 있는지 확인
    is_dup = await check_duplicate_alert(db, factory_id, alert_type, time_limit)
    
    if is_dup:
        print(f"[{alert_type}] 5분 내 중복 알림이므로 생략합니다. (공장 ID: {factory_id})")
        return None
        
    # 중복이 아니면 DB에 저장 
    new_alert = await insert_alert(db, factory_id, priority=priority, severity=severity, alert_type=alert_type, message=message)
    
    # 4. CRITICAL / WARNING 이면 send_telegram 호출
    if severity.lower() in ["critical", "warning"]:
        telegram_msg = (
        f"🚨 [FEMS-MIDAS] 냉동공장 이상 감지\n\n"
        f"■ 심각도: ⚠️{severity.upper()}\n"
        f"■ 대상 공장: {factory_id}번 공장\n"
        f"■ 이상 유형: {alert_type}\n"
        f"■ 상세 내용: {message}\n"
        f"※ 관리자 확인이 필요합니다."
    )
        await send_telegram(telegram_msg)
        
    return new_alert

# 관리자가 알림을 확인했을 때 처리 (ack_at 업데이트)
async def acknowledge_alert(db: AsyncSession, alert_id: int):

    updated_alert = await update_alert_acknowledge(db, alert_id)

    if updated_alert is None:
        logger.warning(f"존재하지 않는 알림 ID입니다: {alert_id}")
        return {"success": False, "message": "알림을 찾을 수 없습니다."} 
    
    print(f"[알림 확인 완료] ID: {alert_id} | 완료 시간: {updated_alert.ack_at}")

    return {
        "success": True,
        "message": "알림 확인 처리가 완료되었습니다.",
        "data": updated_alert
    }

# 현재 시스템에 적용된 모니터링 임계값 및 규칙들을 반환
def get_alert_rules():

    return {
        "temp_deviation_threshold_c": 5.0,       # 온도 급변 기준 (5°C)
        "communication_timeout_sec": 180,        # 통신 타임아웃 기준 (3분)
        "dedup_window_sec": 300                  # 중복 알림 방지 윈도우 (5분)
    }




# backend/models/schemas.py
# Pydantic 모델 정의 (요청/응답 스키마)
#
# [Enum / Literal 타입]
# - FactoryStatus      : NORMAL | SAVING | STOPPED | WARNING | EMERGENCY | MANUAL_STOP
# - ControlMode        : AUTO | MANUAL
# - ScheduleMode       : ON | OFF | PRECOOL | COASTING | SOLAR_PRIORITY
# - AlertLevel         : INFO | WARNING | CRITICAL
# - JobStrategy        : COST_MIN | SAFETY_FIRST | BALANCED
# - ManualAction       : START | STOP | RESET | SET_PWM | SET_TARGET_TEMP | SWITCH_AUTO | SWITCH_MANUAL
# - CommunicationStatus: OK | DELAYED | DISCONNECTED
#
# [공통 응답 래퍼]
# - SuccessResponse(data, message)
# - ErrorResponse(code, message, details)
#
# [도메인 스키마]
# - FactorySummary       : 공장 상태 요약 (factory_id ge=1 le=4 제한)
# - CurrentJob           : 현재 활성 작업 정보
# - ScheduleBlock        : 스케줄 블록 단위 (start_at, end_at, mode, target_temp_c 등)
# - AlertItem            : 알림 항목
#
# [요청 스키마]
# - JobCreateRequest      : 작업 등록 (target_units gt=0, deadline_at, strategy 등)
# - JobUpdateRequest      : 작업 수정 (PATCH용, 필드 전부 Optional)
# - ManualControlRequest  : 수동 제어 (factory_id, action, value, reason)
# - ScheduleComputeRequest: 즉시 최적화 계산 실행 요청
# - AlertAckRequest       : 알림 확인 처리
# - ReadonlyTokenRequest  : QR 토큰 발급 요청

# edge/communication/mqtt_client.py
# Edge MQTT 클라이언트 (paho-mqtt)
#
# - EdgeMQTTClient(node_id, factory_ids) 클래스
#     connect()    : 브로커 연결 (MQTT_HOST 환경변수)
#     disconnect() : 연결 종료
#
# - publish_telemetry(factory_id, payload)
#     토픽: factory/{node_id}/{factory_id}/telemetry
#     QoS 1, 오프라인 시 SQLite 로컬 캐시에 저장
#
# - subscribe_command()
#     토픽: factory/{node_id}/+/command
#     수신 시 on_command() 콜백 호출
#
# - on_command(factory_id, payload)
#     action 분기:
#       SET_SCHEDULE    → scheduler에 블록 반영
#       SET_PWM         → pwm_controller.set_duty_cycle()
#       SET_TARGET_TEMP → 목표 온도 로컬 변수 업데이트
#       STOP            → PWM 0% + manual_stop 플래그
#       START           → manual_stop 해제 + 스케줄 재개
#
# - send_ack(factory_id, command_id, status)
#     토픽: factory/{node_id}/{factory_id}/ack
#
# - flush_buffered(factory_id)
#     SQLite 캐시에 쌓인 telemetry를
#     factory/{node_id}/{factory_id}/buffered 토픽으로 일괄 발행

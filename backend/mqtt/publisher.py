# backend/mqtt/publisher.py
# MQTT 명령 발행 (Backend → Edge)
#
# - MQTTPublisher 클래스
#     connect()   : MQTT 브로커 연결 (환경변수: MQTT_HOST, MQTT_PORT)
#     disconnect(): 연결 종료
#
# - publish_command(node_id, factory_id, action, payload)
#     토픽: factory/{node_id}/{factory_id}/command
#     페이로드: command_id(uuid), action, issued_at, payload
#
# - publish_schedule(node_id, factory_id, schedule_blocks)
#     action="SET_SCHEDULE" 으로 publish_command 호출
#
# - publish_all_stop(reason)
#     공장 1~4 전체에 STOP 명령 일괄 발행
#
# - publish_all_start(reason)
#     manual_stop=True 인 공장은 제외하고 START 명령 발행

def convert_status(status):
    if status in ("NORMAL", "SAVING"):
        return "ok"
    if status in ("WARNING", "MANUAL_STOP", "STOPPED"):
        return "warn"
    if status == "EMERGENCY":
        return "err"
    return "ok"


def control_log_text(log):
    action_map = {
        "STOP": "비상 정지",
        "SET_PWM": f"PWM {log.get('value')}% 설정",
        "RECOVER": "정지 복구",
    }

    action = action_map.get(log["action"], log["action"])
    return f"{log['issued_at'][11:16]}  공장 {log['factory_id']} {action}"


def get_factory_alarms(dummy_data, factory_id):
    return [
        {
            "msg": a["message"],
            "time": a["created_at"][11:16],
            "level": a["level"],
            "acknowledged": a["is_acknowledged"],
            "alert_id": a["alert_id"],
        }
        for a in dummy_data.get("alerts", [])
        if a["factory_id"] == factory_id
    ]


def get_all_unacked_alerts(dummy_data):
    return [
        a for a in dummy_data.get("alerts", [])
        if not a["is_acknowledged"]
    ]


def get_maintenance_info(dummy_data, factory_id):
    return next(
        (
            m for m in dummy_data.get("predict_maintenance", [])
            if m["factory_id"] == factory_id
        ),
        None
    )


def get_temp_predictions(dummy_data, factory_id):
    return [
        p for p in dummy_data.get("predict_temperature", [])
        if p["factory_id"] == factory_id
    ]


def get_sensor_logs(dummy_data, factory_id):
    return [
        log for log in dummy_data.get("sensor_logs", [])
        if log["factory_id"] == factory_id
    ]


def get_door_events(dummy_data, factory_id):
    return [
        event for event in dummy_data.get("door_open_events", [])
        if event["factory_id"] == factory_id
    ]


def make_equip(factory):
    return [
        {
            "n": "통신 상태",
            "v": factory["communication_status"],
            "s": "ok" if factory["communication_status"] == "OK" else "warn",
        },
        {
            "n": "제어 모드",
            "v": factory["control_mode"],
            "s": "ok" if factory["control_mode"] == "AUTO" else "warn",
        },
        {
            "n": "스케줄",
            "v": factory["current_schedule_mode"],
            "s": "warn" if factory["current_schedule_mode"] in ("OFF", "COASTING") else "ok",
        },
        {
            "n": "재고",
            "v": f"{factory['current_stock_units']}/{factory['capacity_units']}",
            "s": "ok",
        },
        {
            "n": "노드",
            "v": factory["node_id"],
            "s": "ok",
        },
    ]
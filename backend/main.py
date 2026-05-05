import asyncio
import sys
import os

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from database.connection import engine, create_all_tables
from mqtt.subscriber import MQTTSubscriber
from mqtt.publisher import publisher
from scheduler.jobs import configure_scheduler_jobs
from routers.readonly import router as readonly_router
from routers.control import router as control_router
from routers.weather import router as weather_router
from routers.energy import router as energy_router
from routers.operations import router as operations_router

app = FastAPI()
mqtt_subscriber: MQTTSubscriber = None

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=os.path.join(os.path.dirname(__file__), "static")), name="static")
app.include_router(readonly_router)
app.include_router(control_router)
app.include_router(weather_router)
app.include_router(energy_router)
app.include_router(operations_router)

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "favicon.ico"))

@app.on_event("startup")
async def startup():
    global mqtt_subscriber

    # DB 테이블 생성
    await create_all_tables()

    # DB 연결 확인
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        print("✅ DB 연결 성공")
    except Exception as e:
        print(f"❌ DB 연결 실패: {e}")
        return

    # MQTT publisher 연결
    try:
        publisher.connect()
        print("✅ MQTT publisher 연결 성공")
    except Exception as e:
        print(f"⚠️ MQTT publisher 연결 실패 (브로커 없이 계속): {e}")

    # MQTT 구독 시작
    loop = asyncio.get_event_loop()
    mqtt_subscriber = MQTTSubscriber(loop)
    mqtt_subscriber.start()

    # 스케줄러 시작 (Job A: 30분 주기 최적화, Job C: 1분 주기 이상 감지)
    scheduler = configure_scheduler_jobs()
    scheduler.start()
    print("✅ 스케줄러 시작")

    # 초기 최적화 1회 실행 (별도 스레드에서 실행해야 asyncio.run 충돌 없음)
    import threading
    from scheduler.jobs import run_job_a_optimization

    def _initial_run():
        result = run_job_a_optimization(dry_run=False)
        print(f"[Job A] blocks={len(result.get('schedule_blocks', []))}, db_saved={result.get('db_saved')}, db_error={result.get('db_error')}, skipped={result.get('skipped')}, reason={result.get('reason')}")
        for block in result.get("schedule_blocks", []):
            print(f"  공장 {block['factory_id']} | 권장 온도: {block.get('recommended_temp_c', block.get('target_temp_c'))}°C | 모드: {block.get('mode')}")

    threading.Thread(target=_initial_run, daemon=True).start()


@app.on_event("shutdown")
async def shutdown():
    publisher.disconnect()
    if mqtt_subscriber:
        mqtt_subscriber.stop()
        print("MQTT 연결 종료")
    try:
        from scheduler.jobs import get_scheduler
        get_scheduler().shutdown(wait=False)
        print("스케줄러 종료")
    except Exception:
        pass


@app.get("/health")
async def health():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "db": "connected"}
    except Exception as e:
        return {"status": "error", "db": str(e)}

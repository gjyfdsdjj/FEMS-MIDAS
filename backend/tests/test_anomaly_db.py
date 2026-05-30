import asyncio
import sys
from pprint import pprint

from database.connection import AsyncSessionLocal
from services.anomaly_service import run_anomaly_monitoring


async def main():
    print("====== 🏭 실시간 이상 감지 엔진 가동 ======")
    async with AsyncSessionLocal() as db:
        # 통합 이상 감지 로직 실행
        result = await run_anomaly_monitoring(db)

        print("\n=== DB 기반 이상 감지 결과 ===")
        pprint(result, sort_dicts=False)
        print("\n=========================================")

if __name__ == "__main__":
    # 윈도우 환경에서 실행 시 루프 폐쇄 에러 방지용
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        
    asyncio.run(main())
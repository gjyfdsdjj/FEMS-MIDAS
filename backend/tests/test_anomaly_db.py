import asyncio
from pprint import pprint

from backend.database.connection import AsyncSessionLocal
from backend.services.anomaly_service import run_anomaly_monitoring


async def main():
    async with AsyncSessionLocal() as db:
        result = await run_anomaly_monitoring(db)

        print("\n=== DB 기반 이상 감지 결과 ===")
        pprint(result, sort_dicts=False)

if __name__ == "__main__":
    asyncio.run(main())
import asyncio
from pprint import pprint

from backend.database.connection import AsyncSessionLocal
from backend.services.readonly_service import get_readonly_data


async def main():
    async with AsyncSessionLocal() as db:
       result = await get_readonly_data(db, "rdonly_test_1")

    print(result)


if __name__ == "__main__":
    asyncio.run(main())
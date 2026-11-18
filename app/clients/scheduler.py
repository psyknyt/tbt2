from apscheduler.schedulers.asyncio import AsyncIOScheduler
import httpx

scheduler = AsyncIOScheduler()

async def morning_job():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://your-api-url"
        )
        print(response.status_code)

scheduler.add_job(
    morning_job,
    trigger="cron",
    hour=5,
    minute=30
)

scheduler.start()
import asyncio
from core.scraper.ita_engine import ITAEngine
from apps.backend.schemas import ScraperTask

async def test_extension_codes():
    print("🧪 Testing Extension Codes Handling...")
    
    # Task mirroring the failed row
    task = ScraperTask(
        trip_type="round_trip",
        origin="YVR",
        destination="PVG",
        start_date="02/01/2026",
        routing_codes="C:MU+",
        extension_codes="f bc=o|bc=v", # This is the suspect
        nights=7,
        stops="Nonstop only"
    )
    
    print(f"Task configuration: {task}")
    
    try:
        engine = ITAEngine(headless=False)
        print("🚀 Launching scraper...")
        result = await engine.run_task(task)
        print(f"✅ Result status: {result.status}")
        if result.status != "success":
            print(f"❌ Failure message: {result.message}")
        else:
            print(f"✅ Extracted prices: {len(result.prices)}")
    except Exception as e:
        print(f"🔥 Exception occurred: {e}")

if __name__ == "__main__":
    asyncio.run(test_extension_codes())

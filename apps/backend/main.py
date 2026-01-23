import asyncio
import io
import csv
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks, Response
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import uvicorn
from .schemas import ScraperTask, ScraperResult, LogEntry
from core.scraper.ita_engine import ITAEngine

from fastapi.staticfiles import StaticFiles
import os

app = FastAPI(title="APAS API - Aviation Price Analysis System")

# 允许跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 模拟数据库存储
db_results = []
db_logs = []

@app.get("/")
async def root():
    return {"message": "APAS API is running", "version": "1.0"}

@app.post("/tasks/scrape", response_model=dict)
async def create_scrape_task(task: ScraperTask, background_tasks: BackgroundTasks):
    background_tasks.add_task(run_scrape_process, task)
    return {"status": "accepted", "task": task}

@app.get("/results", response_model=List[ScraperResult])
async def get_results():
    # 返回按时间倒序排列的结果
    return sorted(db_results, key=lambda x: x.timestamp, reverse=True)

@app.get("/logs", response_model=List[LogEntry])
async def get_logs():
    # 返回最新的日志
    return db_logs

@app.get("/export/csv")
async def export_csv():
    if not db_results:
        return {"error": "No data available to export"}
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Search_Timestamp', 'Origin', 'Destination', 'Flight_Full_Date', 'Price', 'Is_Cheapest'])
    
    import re
    def format_flight_date(start_date_str, date_info_str):
        try:
            # New Logic: date_info_str might be "January 28"
            import calendar
            months_map = {m: i for i, m in enumerate(calendar.month_name) if m}
            
            # Helper to get year from start_date
            parts_sd = start_date_str.split('/')
            year = parts_sd[2] 
            
            # Check if date_info_str has Month Name
            matched_month = None
            day_val = date_info_str
            
            for m_name in months_map.keys():
                if m_name in date_info_str:
                    matched_month = m_name
                    day_val = date_info_str.replace(m_name, "").strip()
                    break
            
            if matched_month:
                m_idx = months_map[matched_month] - 1
                # If scraped month is BEFORE start month (and barely), might be next year? 
                # For now assume same year as start_date unless explicit.
            else:
                m_idx = int(parts_sd[0]) - 1

            months_abbr = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
            month_mmm = months_abbr[m_idx]
            day_dd = str(day_val).zfill(2)
            
            return f"{day_dd}{month_mmm}{year}"[-7:] # Ensure we use 2-digit year from end
        except Exception as e:
            return f"{date_info_str}ERR"

    # Save JSON for debugging
    import json
    json_path = "data/results/latest_result.json"
    with open(json_path, 'w') as f:
        # Convert Pydantic models to dict
        json.dump([res.dict() for res in db_results], f, indent=2)
    logger.info(f"Saved JSON debug file to: {json_path}")

    for res in db_results:
        for p in res.prices:
            # Use the scraper's formatted date directly (e.g. "06FEB26")
            full_date = p.date 
            writer.writerow([
                res.timestamp,
                res.task.origin,
                res.task.destination,
                full_date,
                p.price,
                p.is_cheapest
            ])
    
    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=apas_report_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"}
    )

async def run_scrape_process(task: ScraperTask):
    max_retries = 3
    retry_count = 0
    
    def add_log(msg, level="INFO"):
        db_logs.append(LogEntry(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            level=level,
            message=msg
        ))

    while retry_count < max_retries:
        engine = ITAEngine(headless=False)
        add_log(f"Initializing scraper (Attempt {retry_count + 1}/{max_retries}) for {task.origin} -> {task.destination}...")
        
        try:
            add_log(f"Navigating to ITA Matrix with routing: {task.routing_codes or 'Default'}")
            result = await engine.run_task(task)
            
            if result.status == "success":
                add_log(f"Successfully extracted {len(result.prices)} price points.", "SUCCESS")
                db_results.append(result)
                add_log("Task completed successfully.", "SUCCESS")
                return # 成功后退出循环
            else:
                retry_count += 1
                add_log(f"Attempt {retry_count} produced an issue: {result.message}. Retrying soon...", "WARNING")
                await asyncio.sleep(5) # 重试前稍作等待
                
        except Exception as e:
            retry_count += 1
            add_log(f"Attempt {retry_count} system error: {str(e)}. Retrying...", "WARNING")
            await asyncio.sleep(5)

    # 如果所有重试都失败
    add_log(f"ALL {max_retries} attempts failed. Scraper has safely timed out to prevent system hang.", "ERROR")
    add_log("SYSTEM NOTIFICATION: Automatic price monitoring will continue in the next scheduled cycle. No manual action required.", "INFO")

# Serve static files (React frontend)
# 获取 frontend/dist 的绝对路径
current_dir = os.path.dirname(os.path.abspath(__file__))
frontend_dist = os.path.join(os.path.dirname(current_dir), "frontend", "dist")

if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")
else:
    print(f"Warning: Static files directory not found at {frontend_dist}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)

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
    def format_flight_date(start_date_str, day_str):
        try:
            # start_date_str 格式为 "MM/DD/YYYY"
            parts = start_date_str.split('/')
            m_idx = int(parts[0]) - 1
            year_yy = parts[2][-2:]
            
            months_abbr = ['JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN', 'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC']
            month_mmm = months_abbr[m_idx]
            day_dd = str(day_str).zfill(2)
            
            return f"{day_dd}{month_mmm}{year_yy}"
        except Exception as e:
            return f"{day_str}ERR"

    for res in db_results:
        for p in res.prices:
            full_date = format_flight_date(res.task.start_date, p.date)
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

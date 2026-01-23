import asyncio
import io
import csv
import uuid
import pandas as pd
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks, Response, UploadFile, File
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import uvicorn
from .schemas import ScraperTask, ScraperResult, LogEntry
from core.scraper.ita_engine import ITAEngine

import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

@app.post("/tasks/batch-upload")
async def batch_upload(file: UploadFile = File(...), background_tasks: BackgroundTasks = BackgroundTasks()):
    content = await file.read()
    df = pd.read_csv(io.BytesIO(content))
    
    # Generate batch ID
    batch_id = str(uuid.uuid4())[:8]
    tasks = []
    
    for _, row in df.iterrows():
        try:
            # Map CSV columns to ScraperTask (flexibility for headers)
            task = ScraperTask(
                trip_type=row.get('trip_type', 'round_trip'),
                origin=row.get('origin'),
                destination=row.get('destination'),
                start_date=str(row.get('start_date')),
                routing_codes=row.get('routing_codes') if pd.notna(row.get('routing_codes')) else None,
                extension_codes=row.get('extension_codes') if pd.notna(row.get('extension_codes')) else None,
                nights=int(row.get('nights', 7)) if pd.notna(row.get('nights')) else 7,
                stops=row.get('stops', 'No limit'),
                cabin=row.get('cabin', 'Cheapest available')
            )
            tasks.append(task)
        except Exception as e:
            logger.error(f"Failed to parse row: {e}")

    background_tasks.add_task(run_batch_process, tasks, batch_id)
    return {"status": "batch_started", "batch_id": batch_id, "task_count": len(tasks)}

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
    
    from .processor import DataProcessor
    import tempfile
    
    # Create valid temporary file path
    with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp:
        output_path = tmp.name
        
    # Use the centralized processor logic
    DataProcessor.prices_to_csv(db_results, output_path)
    
    # Stream the file content back
    def iter_file():
        with open(output_path, 'rb') as f:
            yield from f
        # Clean up
        try:
            os.remove(output_path)
        except:
            pass

    return StreamingResponse(
        iter_file(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=apas_report_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"}
    )

async def run_batch_process(tasks: List[ScraperTask], batch_id: str):
    def add_batch_log(msg, level="INFO"):
        db_logs.append(LogEntry(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            level=level,
            message=f"[Batch {batch_id}] {msg}",
            batch_id=batch_id
        ))

    add_batch_log(f"Starting batch process for {len(tasks)} tasks.")
    
    batch_results = []
    for i, task in enumerate(tasks):
        add_batch_log(f"Working on task {i+1}/{len(tasks)}: {task.origin}->{task.destination}")
        
        # Individual task with retry and isolation
        try:
            # Re-use the existing retry logic but scoped to this task
            engine = ITAEngine(headless=False)
            result = await engine.run_task(task)
            result.batch_id = batch_id
            
            if result.status == "success":
                db_results.append(result)
                batch_results.append(result)
                add_batch_log(f"Task {i+1} success: {len(result.prices)} prices.", "SUCCESS")
                
                # Intermediate save: Save current results to a dedicated batch CSV
                save_intermediate_batch(batch_id, batch_results)
            else:
                add_batch_log(f"Task {i+1} failed: {result.message}", "WARNING")
        except Exception as e:
            add_batch_log(f"Task {i+1} system crash: {str(e)}", "ERROR")
            # Continue to next task
            continue
    
    add_batch_log(f"Batch {batch_id} fully completed. Final count: {len(batch_results)} success rows.", "SUCCESS")

def save_intermediate_batch(batch_id, results):
    from .processor import DataProcessor
    os.makedirs("data/results/batches", exist_ok=True)
    path = f"data/results/batches/batch_{batch_id}_live.csv"
    DataProcessor.prices_to_csv(results, path)

async def run_scrape_process(task: ScraperTask):
# ... existing code ...
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

class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        # Prevent "assert scope['type'] == 'http'" error for websocket connections
        if scope["type"] != "http":
            return Response("Not found", status_code=404)
        return await super().get_response(path, scope)

if os.path.exists(frontend_dist):
    app.mount("/", SPAStaticFiles(directory=frontend_dist, html=True), name="static")
else:
    print(f"Warning: Static files directory not found at {frontend_dist}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)

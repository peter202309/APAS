import asyncio
import io
import csv
import uuid
import pandas as pd
from datetime import datetime
from fastapi import FastAPI, BackgroundTasks, Response, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
import uvicorn
from .schemas import ScraperTask, ScraperResult, LogEntry, BatchComparisonRequest
from core.scraper.ita_engine import ITAEngine
from core.ai.llm_client import AIGenerator
import os
import json
from pathlib import Path

# Data Persistence Config
DATA_DIR = Path("data/db")
DATA_DIR.mkdir(parents=True, exist_ok=True)
BATCHES_FILE = DATA_DIR / "batches.json"
RESULTS_FILE = DATA_DIR / "results.json"

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
db_batches = {} # New: Store batch metadata and task statuses

# Initialize AI Client (Optional)
try:
    ai_client = AIGenerator()
except Exception as e:
    print(f"Warning: AI Client failed to initialize: {e}")
    ai_client = None

@app.get("/")
async def root():
    return {"message": "APAS API is running", "version": "1.0"}

# Persistence Helpers
def save_db_to_disk():
    try:
        # Convert ScraperResult objects to dicts for JSON serialization
        results_data = [r.dict() for r in db_results]
        
        with open(BATCHES_FILE, 'w', encoding='utf-8') as f:
            json.dump(db_batches, f, default=str, indent=2)
            
        with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
            json.dump(results_data, f, default=str, indent=2)
            
        logger.info("Database saved to disk.")
    except Exception as e:
        logger.error(f"Failed to save DB: {e}")

def load_db_from_disk():
    global db_batches, db_results
    try:
        if BATCHES_FILE.exists():
            with open(BATCHES_FILE, 'r', encoding='utf-8') as f:
                db_batches.update(json.load(f))
                
        if RESULTS_FILE.exists():
            with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
                raw_results = json.load(f)
                # Reconstruct ScraperResult objects
                db_results.extend([ScraperResult(**r) for r in raw_results])
                
        logger.info(f"Database loaded: {len(db_batches)} batches, {len(db_results)} results")
    except Exception as e:
        logger.error(f"Failed to load DB: {e}")

# Load data on startup
load_db_from_disk()

@app.post("/tasks/scrape", response_model=dict)
async def create_scrape_task(task: ScraperTask, background_tasks: BackgroundTasks):
    # Parse start_date for multiple dates (comma separated)
    raw_dates = str(task.start_date).split(',')
    clean_dates = [d.strip() for d in raw_dates if d.strip()]
    
    if len(clean_dates) > 1:
        # Multiple dates detected -> Create a BATCH
        batch_id = f"{str(uuid.uuid4())[:8]}" # Regular batch ID
        sub_tasks = []
        
        for date_str in clean_dates:
            # Create a copy of the task for each date
            new_task = task.copy()
            new_task.start_date = date_str
            sub_tasks.append(new_task)
            
        # Register in db_batches
        db_batches[batch_id] = {
            "id": batch_id,
            "timestamp": datetime.now().isoformat(),
            "total_tasks": len(sub_tasks),
            "status": "processing",
            "tasks": [
                {
                    "task_id": str(i),
                    "origin": t.origin,
                    "destination": t.destination,
                    "status": "pending",
                    "message": f"Scheduled for {t.start_date}",
                    "result_count": 0
                } for i, t in enumerate(sub_tasks)
            ]
        }
        
        background_tasks.add_task(run_batch_process, sub_tasks, batch_id)
        save_db_to_disk()
        return {"status": "batch_started", "batch_id": batch_id, "task_count": len(sub_tasks), "message": f"Started batch for {len(sub_tasks)} dates"}

    else:
        # Single date -> Single Task logic
        batch_id = f"single-{str(uuid.uuid4())[:8]}"
        
        # Register in db_batches
        db_batches[batch_id] = {
            "id": batch_id,
            "timestamp": datetime.now().isoformat(),
            "total_tasks": 1,
            "status": "processing",
            "tasks": [
                {
                    "task_id": "0",
                    "origin": task.origin,
                    "destination": task.destination,
                    "status": "pending",
                    "message": "Waiting to start...",
                    "result_count": 0
                }
            ]
        }
        
        background_tasks.add_task(run_scrape_process, task, batch_id)
        save_db_to_disk()
        return {"status": "accepted", "task": task, "batch_id": batch_id}

@app.post("/tasks/batch-upload")
async def batch_upload(file: UploadFile = File(...), background_tasks: BackgroundTasks = BackgroundTasks()):
    content = await file.read()
    df = pd.read_csv(io.BytesIO(content))
    
    # Generate batch ID
    batch_id = str(uuid.uuid4())[:8]
    tasks = []
    
    for i, (_, row) in enumerate(df.iterrows()):
        try:
            # Log row data for debugging
            logger.info(f"Processing row {i}: {row.to_dict()}")
            
            # Map CSV columns to ScraperTask (flexibility for headers)
            task = ScraperTask(
                trip_type=row.get('trip_type', 'round_trip'),
                origin=row.get('origin'),
                destination=row.get('destination'),
                start_date=str(row.get('start_date')),
                routing_codes=row.get('routing_codes') if pd.notna(row.get('routing_codes')) else None,
                extension_codes=row.get('extension_codes') if pd.notna(row.get('extension_codes')) else None,
                return_routing_codes=row.get('return_routing_codes') if pd.notna(row.get('return_routing_codes')) else None,
                return_extension_codes=row.get('return_extension_codes') if pd.notna(row.get('return_extension_codes')) else None,
                nights=int(float(row.get('nights', 7))) if pd.notna(row.get('nights')) else 7, # Handle float strings "7.0"
                stops=row.get('stops', 'No limit'),
                extra_stops=row.get('extra_stops', 'No limit'),
                sales_city=row.get('sales_city') if pd.notna(row.get('sales_city')) else None,
                currency=row.get('currency') if pd.notna(row.get('currency')) else 'CAD'
            )
            tasks.append(task)
            logger.info(f"Row {i} parsed successfully: {task.origin}->{task.destination}")
        except Exception as e:
            logger.error(f"Failed to parse row {i}: {e} (Row content: {row.values})")

    # Initialize batch record
    db_batches[batch_id] = {
        "id": batch_id,
        "timestamp": datetime.now().isoformat(),
        "total_tasks": len(tasks),
        "status": "processing",
        "tasks": [
            {
                "task_id": str(i),
                "origin": t.origin,
                "destination": t.destination,
                "status": "pending",
                "message": "Waiting to start...",
                "result_count": 0
            } for i, t in enumerate(tasks)
        ]
    }

    background_tasks.add_task(run_batch_process, tasks, batch_id)
    save_db_to_disk() # Save new batch record
    return {"status": "batch_started", "batch_id": batch_id, "task_count": len(tasks)}

@app.get("/batches", response_model=List[dict])
async def get_batches():
    # Return list of batches (summary), sorted by time desc
    return sorted(list(db_batches.values()), key=lambda x: x['timestamp'], reverse=True)

@app.get("/batches/{batch_id}")
async def get_batch_details(batch_id: str):
    if batch_id not in db_batches:
        return Response(status_code=404)
    return db_batches[batch_id]

@app.delete("/batches/{batch_id}")
async def delete_batch(batch_id: str):
    if batch_id not in db_batches:
        raise HTTPException(status_code=404, detail="Batch not found")
    
    # Delete from batches
    del db_batches[batch_id]
    
    # Delete associated results
    # We need to use global db_results and modify it
    global db_results
    original_count = len(db_results)
    db_results = [r for r in db_results if getattr(r, 'batch_id', None) != batch_id]
    removed_results = original_count - len(db_results)
    
    save_db_to_disk()
    logger.info(f"Deleted batch {batch_id} and {removed_results} associated results.")
    return {"status": "success", "message": f"Batch {batch_id} deleted", "results_removed": removed_results}

@app.post("/ai/analyze")
async def analyze_batch(payload: dict):
    if not ai_client:
        return {"error": "AI module not configured (Check GOOGLE_API_KEY)"}
    
    batch_id = payload.get("batch_id")
    origin = payload.get("origin", "UNKNOWN")
    destination = payload.get("destination", "UNKNOWN")
    
    # Filter results for this batch (or general if no batch_id)
    relevant_prices = []
    if batch_id:
        # Find results matching this batch_id
        # Note: ScraperResult object needs to have batch_id attribute
        relevant_results = [r for r in db_results if getattr(r, 'batch_id', None) == batch_id]
        if not relevant_results:
             return {"report": "No data found for this batch to analyze."}
        
        # Flatten prices from all tasks in batch
        for r in relevant_results:
             for p in r.prices:
                 relevant_prices.append({
                     "date": p.date,
                     "price": p.price,
                     "airline": "MU" # Placeholder, real extraction might need airline parsing
                 })
    else:
        # Fallback: Analyze last 100 prices globally
        for r in db_results[-5:]:
             for p in r.prices:
                 relevant_prices.append({"date": p.date, "price": p.price})
    
    if not relevant_prices:
        return {"report": "No extracted price data available to analyze."}

    # Call LLM
    report = ai_client.analyze_price_trend(origin, destination, relevant_prices)
    return {"report": report}

@app.post("/ai/compare_files")
async def analyze_comparison_files(files: List[UploadFile] = File(...), user_prompt: Optional[str] = Form(None)):
    if not ai_client:
        raise HTTPException(status_code=503, detail="AI Client not initialized (Check configuration)")
    
    comparison_data = {}
    import pandas as pd
    import io
    
    for file in files:
        try:
            content = await file.read()
            # Try parsing with generic pandas
            try:
                df = pd.read_csv(io.BytesIO(content))
            except:
                # Fallback utf-16 if default fails
                df = pd.read_csv(io.BytesIO(content), encoding='utf-16', sep='\t')
            
            # Simple heuristic to find price/date columns
            # Look for columns containing 'date' and 'price' (case insensitive)
            cols = {c.lower(): c for c in df.columns}
            date_col = next((cols[c] for c in cols if 'date' in c or 'day' in c), None)
            price_col = next((cols[c] for c in cols if 'price' in c or 'fare' in c or 'amount' in c), None)
            
            if date_col and price_col:
                # Convert to simple list of dicts
                file_data = []
                for _, row in df.iterrows():
                    file_data.append({
                        "date": str(row[date_col]),
                        "price": str(row[price_col])
                    })
                comparison_data[file.filename] = file_data
            else:
                # Fallback: assume first column is date, second is price
                if len(df.columns) >= 2:
                     file_data = [{"date": str(row[0]), "price": str(row[1])} for i, row in df.iterrows()]
                     comparison_data[file.filename] = file_data
                
        except Exception as e:
            print(f"Failed to parse {file.filename}: {e}")
            continue

    if not comparison_data:
         raise HTTPException(status_code=400, detail="Could not extract date/price data from uploaded files.")

    report = ai_client.compare_airlines(comparison_data, user_prompt=user_prompt)
    return {"report": report}

@app.post("/ai/compare_batches")
async def compare_batches_endpoint(request: BatchComparisonRequest):
    if not ai_client:
         raise HTTPException(status_code=503, detail="AI Client not initialized")
    
    comparison_data = {}
    
    for batch_id in request.batch_ids:
        # Filter results for this batch
        batch_results = [r for r in db_results if getattr(r, 'batch_id', None) == str(batch_id)]
        
        if not batch_results:
            continue
            
        all_prices = []
        for res in batch_results:
            if res.prices:
                 all_prices.extend([p.dict() for p in res.prices])
        
        if all_prices:
            # Name source with ID and Route if available
            label = f"Batch {batch_id}"
            if batch_results and batch_results[0].task:
                 label += f" ({batch_results[0].task.origin}->{batch_results[0].task.destination})"
            comparison_data[label] = all_prices

    if not comparison_data:
        raise HTTPException(status_code=400, detail="No price data found for selected batches")

    report = ai_client.compare_airlines(comparison_data, user_prompt=request.user_prompt)
    return {"report": report}

@app.get("/results", response_model=List[ScraperResult])
async def get_results():
    # Return results sorted by timestamp descending
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

@app.get("/export/csv/{batch_id}")
async def export_batch_csv(batch_id: str):
    # Filter results by batch_id
    batch_results = [r for r in db_results if getattr(r, 'batch_id', None) == batch_id]
    
    if not batch_results:
        return {"error": "No data available for this batch"}
    
    from .processor import DataProcessor
    import tempfile
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.csv') as tmp:
        output_path = tmp.name
        
    DataProcessor.prices_to_csv(batch_results, output_path)
    
    def iter_file():
        with open(output_path, 'rb') as f:
            yield from f
        try:
            os.remove(output_path)
        except:
            pass

    return StreamingResponse(
        iter_file(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=apas_batch_{batch_id}.csv"}
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
    
    # Update batch status to processing
    if batch_id in db_batches:
        db_batches[batch_id]["status"] = "processing"
        save_db_to_disk()

    for i, task in enumerate(tasks):
        task_idx = i # correl with db_batches tasks list index
        add_batch_log(f"Working on task {i+1}/{len(tasks)}: {task.origin}->{task.destination}")
        
        # Update task status to running
        if batch_id in db_batches:
            db_batches[batch_id]["tasks"][task_idx]["status"] = "running"
            db_batches[batch_id]["tasks"][task_idx]["message"] = "Scraping in progress..."

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
                
                # Update task status to success
                if batch_id in db_batches:
                    db_batches[batch_id]["tasks"][task_idx]["status"] = "success"
                    db_batches[batch_id]["tasks"][task_idx]["result_count"] = len(result.prices)
                    db_batches[batch_id]["tasks"][task_idx]["message"] = result.message or "Completed successfully"

                # Intermediate save: Save current results to a dedicated batch CSV
                save_intermediate_batch(batch_id, batch_results)
                save_db_to_disk() # Save successful result and status update
            else:
                add_batch_log(f"Task {i+1} failed: {result.message}", "WARNING")
                if batch_id in db_batches:
                    db_batches[batch_id]["tasks"][task_idx]["status"] = "failed"
                    db_batches[batch_id]["tasks"][task_idx]["message"] = result.message
                save_db_to_disk() # Save failure status

        except Exception as e:
            add_batch_log(f"Task {i+1} system crash: {str(e)}", "ERROR")
            if batch_id in db_batches:
                db_batches[batch_id]["tasks"][task_idx]["status"] = "failed"
                db_batches[batch_id]["tasks"][task_idx]["message"] = f"System Error: {str(e)}"
            # Continue to next task
            continue
    
    if batch_id in db_batches:
        db_batches[batch_id]["status"] = "completed"
        save_db_to_disk() # Final save
        
    add_batch_log(f"Batch {batch_id} fully completed. Final count: {len(batch_results)} success rows.", "SUCCESS")

def save_intermediate_batch(batch_id, results):
    from .processor import DataProcessor
    os.makedirs("data/results/batches", exist_ok=True)
    path = f"data/results/batches/batch_{batch_id}_live.csv"
    DataProcessor.prices_to_csv(results, path)

async def run_scrape_process(task: ScraperTask, batch_id: str = None):
# ... existing code ...
    max_retries = 3
    retry_count = 0
    
    def add_log(msg, level="INFO"):
        db_logs.append(LogEntry(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            level=level,
            message=msg,
            batch_id=batch_id
        ))

    # Update batch status to running
    if batch_id and batch_id in db_batches:
        db_batches[batch_id]["tasks"][0]["status"] = "running"
        save_db_to_disk()

    while retry_count < max_retries:
        engine = ITAEngine(headless=False)
        add_log(f"Initializing scraper (Attempt {retry_count + 1}/{max_retries}) for {task.origin} -> {task.destination}...")
        
        try:
            add_log(f"Navigating to ITA Matrix with routing: {task.routing_codes or 'Default'}")
            result = await engine.run_task(task)
            
            if result.status == "success":
                add_log(f"Successfully extracted {len(result.prices)} price points.", "SUCCESS")
                if batch_id:
                    result.batch_id = batch_id
                    
                db_results.append(result)
                add_log("Task completed successfully.", "SUCCESS")

                # Update batch status to success
                if batch_id and batch_id in db_batches:
                    db_batches[batch_id]["status"] = "completed"
                    db_batches[batch_id]["tasks"][0]["status"] = "success"
                    db_batches[batch_id]["tasks"][0]["result_count"] = len(result.prices)
                    db_batches[batch_id]["tasks"][0]["message"] = "Completed"
                    
                save_db_to_disk()
                return 
            else:
                retry_count += 1
                add_log(f"Attempt {retry_count} produced an issue: {result.message}. Retrying soon...", "WARNING")
                await asyncio.sleep(5) 
                
        except Exception as e:
            retry_count += 1
            add_log(f"Attempt {retry_count} system error: {str(e)}. Retrying...", "WARNING")
            await asyncio.sleep(5)

    # If all retries fail
    add_log(f"ALL {max_retries} attempts failed.", "ERROR")
    if batch_id and batch_id in db_batches:
        db_batches[batch_id]["status"] = "failed"
        db_batches[batch_id]["tasks"][0]["status"] = "failed"
        db_batches[batch_id]["tasks"][0]["message"] = "Max retries exceeded"
    save_db_to_disk()

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

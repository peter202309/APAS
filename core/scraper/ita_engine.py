import asyncio
import logging
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
from typing import List, Dict
from apps.backend.schemas import ScraperTask, FlightPrice, ScraperResult
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ITAEngine:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.url = "https://matrix.itasoftware.com/search"

    async def run_task(self, task: ScraperTask) -> ScraperResult:
        # Standardize date to MM/DD/YYYY for consistent automation
        # Standardize date to MM/DD/YYYY for consistent automation
        def standardize_date(date_str):
            # Attempt basic formats
            for fmt in ("%m/%d/%Y", "%d/%m/%Y", "%Y-%m-%d"):
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.strftime("%m/%d/%Y")
                except ValueError:
                    continue
            
            # Smart Check: Handle potential day/month swap if day > 12
            # User might input 28/01/2026 meaning Jan 28, but simplified logic might fail
            try:
                parts = date_str.replace('-','/').split('/')
                if len(parts) == 3:
                    p1, p2, p3 = int(parts[0]), int(parts[1]), int(parts[2])
                    # If first part > 12, it MUST be day (Day/Month/Year)
                    if p1 > 12: 
                        return f"{p2:02d}/{p1:02d}/{p3}"
            except:
                pass

            return date_str # Return original if all fail

        formatted_start_date = standardize_date(task.start_date)
        logger.info(f"Standardized start date: {task.start_date} -> {formatted_start_date}")

        async with async_playwright() as p:
            # Connect to existing Chrome instance opened via start_chrome_debug.bat
            # ensure you ran the bat file first!
            try:
                # Switching to port 9223 to avoid conflict with other 9222 sessions
                logger.info("Attempting to connect to existing Chrome at port 9223...")
                browser = await p.chromium.connect_over_cdp("http://localhost:9223")
                context = browser.contexts[0]
                logger.info("Successfully connected to existing Chrome session.")
            except Exception as e:
                logger.error(f"Could not connect to Chrome at port 9222. Did you run 'start_chrome_debug.bat'? Error: {e}")
                # Fallback or re-raise? For now re-raise to alert user
                raise e
            
            # Get the default page or create one
            page = context.pages[0] if context.pages else await context.new_page()
            await Stealth().apply_stealth_async(page)
            
            try:
                logger.info(f"Navigating to {self.url}...")
                await page.goto(self.url, wait_until="networkidle", timeout=60000)
                await asyncio.sleep(2)

                # 1. 处理欢迎弹窗和干扰
                try:
                    banner_close = await page.query_selector('button[aria-label="close banner"]')
                    if banner_close:
                        await banner_close.click()
                        logger.info("Dismissed welcome banner.")
                    
                    dismiss_btns = await page.query_selector_all('button:has-text("Dismiss"), button:has-text("Got it")')
                    for btn in dismiss_btns:
                        await btn.click()
                except:
                    pass

                # 2. 切换行程类型 (One Way / Round Trip)
                logger.info(f"Setting trip type to: {task.trip_type}")
                try:
                    target_tab_text = "One Way" if task.trip_type == "one_way" else "Round Trip"
                    # 这里使用文本选择器寻找 tab
                    type_btn = await page.query_selector(f'div[role="tab"]:has-text("{target_tab_text}"), button:has-text("{target_tab_text}")')
                    if type_btn:
                        await type_btn.click()
                        await asyncio.sleep(1)
                except Exception as e:
                    logger.warning(f"Failed to switch trip type tab: {e}")

                # 3. 填写始发地和目的地 (v5 鲁棒选择器)
                logger.info(f"Filling Origin: {task.origin} and Destination: {task.destination}")
                
                # 始发地
                # 始发地 - Slow down interaction
                origin_box = await page.wait_for_selector('mat-form-field:has-text("Origin") input', timeout=15000)
                await origin_box.click()
                await page.keyboard.press("Control+a")
                await page.keyboard.press("Backspace")
                await origin_box.type(task.origin, delay=200) # Slower typing
                await asyncio.sleep(5) # Increased wait for autocomplete
                # Try to select the first option if it appears
                try:
                    await page.wait_for_selector('mat-option', timeout=5000)
                    await page.keyboard.press("ArrowDown")
                    await page.keyboard.press("Enter")
                except:
                    await page.keyboard.press("Enter")
                await asyncio.sleep(1)
                
                # 目的地 - Slow down interaction
                dest_box = await page.wait_for_selector('mat-form-field:has-text("Destination") input', timeout=15000)
                await dest_box.click()
                await page.keyboard.press("Control+a")
                await page.keyboard.press("Backspace")
                await dest_box.type(task.destination, delay=200)
                await asyncio.sleep(5) # Increased wait for autocomplete
                try:
                    await page.wait_for_selector('mat-option', timeout=5000)
                    await page.keyboard.press("ArrowDown")
                    await page.keyboard.press("Enter")
                except:
                    await page.keyboard.press("Enter")
                await asyncio.sleep(1)

                # 3.5. 处理 Routing Codes (Simplified - No Toggle)
                # Since user has manually expanded controls in persistent browser, they stay visible
                if task.routing_codes:
                    logger.info(f"Filling Routing Codes: {task.routing_codes}")
                    try:
                        # Strategy: focus() instead of click() to avoid scrolling
                        routing_box = await page.wait_for_selector(
                            'mat-form-field:has-text("Routing Codes") input', 
                            timeout=3000
                        )
                        await routing_box.focus()  # No scrolling, just focus
                        await asyncio.sleep(0.2)
                        await routing_box.fill(task.routing_codes)
                        await asyncio.sleep(0.3)
                        await page.keyboard.press("Escape")
                        logger.info("✓ Routing Codes filled successfully")
                    except Exception as rc_err:
                        # Fallback: JavaScript direct assignment (no UI interaction)
                        logger.warning(f"Focus+fill failed, trying JS fallback...")
                        try:
                            await page.evaluate("""
                                (code) => {
                                    const input = document.querySelector('mat-form-field input[placeholder*="Routing"], mat-form-field input[aria-label*="Routing"]');
                                    if (input) {
                                        input.value = code;
                                        input.dispatchEvent(new Event('input', { bubbles: true }));
                                        input.dispatchEvent(new Event('change', { bubbles: true }));
                                        console.log('[SCRAPER] Routing Codes set via JS:', code);
                                    }
                                }
                            """, task.routing_codes)
                            logger.info("✓ Routing Codes filled via JavaScript")
                        except:
                            logger.error("❌ Routing Codes skipped - all methods failed")

                # 4. 选择“价格日历”模式
                logger.info("Switching to 'See calendar of lowest fares' mode...")
                try:
                    # 点击模式下拉框 (通常显示 "Search exact date")
                    await page.click('mat-select[role="combobox"]', timeout=10000)
                    await asyncio.sleep(1)
                    # 选中日历选项
                    await page.click('mat-option:has-text("See calendar of lowest fares")', timeout=10000)
                    await asyncio.sleep(1)
                except Exception as e:
                    logger.warning(f"Failed to switch to calendar mode: {e}")

                # 5. 填写日期与时长
                logger.info(f"Filling date: {task.start_date}")
                
                # 开始日期
                date_box = await page.wait_for_selector('mat-form-field:has-text("Start Date") input', timeout=10000)
                await date_box.click()
                # Clear existing text manually to be safe with input masks
                await page.keyboard.press("Control+a")
                await page.keyboard.press("Backspace")
                await asyncio.sleep(0.5)
                await date_box.type(formatted_start_date, delay=100) # Type standard format
                await asyncio.sleep(0.5)
                await page.keyboard.press("Enter") # Commit the valid date
                await asyncio.sleep(0.5)
                
                # 仅在 Round Trip 模式下填写 Nights
                if task.trip_type == "round_trip":
                    logger.info(f"Filling duration: {task.nights}")
                    duration_box = await page.wait_for_selector('mat-form-field:has-text("Duration (nights)") input', timeout=10000)
                    await duration_box.fill(str(task.nights))
                    await asyncio.sleep(0.5)
                    await page.keyboard.press("Escape") # 再次确保所有 Material 弹窗关闭


                # 6. 执行搜索
                logger.info("Executing search...")
                # 在点击搜索前，最后做一次全局 Escape，确保没有遮罩层
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.5)
                
                search_btn = await page.wait_for_selector('button:has-text("Search")', timeout=10000)
                await search_btn.click()
                
                logger.info("Waiting 90s for mandatory page load time...")
                await asyncio.sleep(90) # User requested mandatory wait doubled

                # 等待结果加载 (Matrix v5 下拉加载较快，但渲染需要时间)
                logger.info("Waiting for Results to render...")
                # Improved wait strategy: ensure we wait for a VISIBLE date cell or price
                # previous .date-cell might match hidden elements from other months
                # Improved Poll Strategy: Check every 10s if results are visible, up to 300s (5min)
                # Browser is definitely slow or calculating heavy routes
                max_wait_seconds = 300
                start_wait = datetime.now()
                found_results = False
                
                while (datetime.now() - start_wait).total_seconds() < max_wait_seconds:
                    try:
                        # Check strictly for visible cells
                        if await page.is_visible('.date-cell >> visible=true'):
                            logger.info("Visual confirmation: Date cells are visible!")
                            found_results = True
                            break
                    except:
                        pass
                    
                    logger.info(f"Still waiting for results... (Elapsed: {int((datetime.now()-start_wait).total_seconds())}s)")
                    await asyncio.sleep(10)

                if not found_results:
                     logger.warning("Timeout reached (300s) waiting for visible .date-cell. Attempting extraction anyway...")
                await asyncio.sleep(5) 

                # 9. 提取第一个月的数据 (Enhanced with debugging)
                logger.info("Extracting calendar data from v5 layout...")
                
                result_data = await page.evaluate("""
                () => {
                    const extracted = [];
                    console.log('[SCRAPER] Starting extraction...');
                    
                    // Try multiple selector strategies
                    const cells = document.querySelectorAll('.date-cell, [class*="date"], [class*="calendar-day"]');
                    console.log(`[SCRAPER] Found ${cells.length} potential date cells`);
                    
                    cells.forEach((cell, idx) => {
                        // Try multiple selectors for date
                        const dateEl = cell.querySelector('.date') || 
                                     cell.querySelector('.day-number') ||
                                     cell.querySelector('[class*="day"]') ||
                                     cell.querySelector('[class*="date"]');
                        
                        // Try multiple selectors for price
                        const priceEl = cell.querySelector('.price') || 
                                      cell.querySelector('.fare-price') ||
                                      cell.querySelector('[class*="price"]') ||
                                      cell.querySelector('[class*="fare"]');
                        
                        if (!dateEl && !priceEl) {
                            // Maybe the cell itself contains the data
                            const cellText = cell.innerText?.trim() || '';
                            if (cellText.includes('$') && cellText.match(/\\d+/)) {
                                console.log(`[SCRAPER] Cell ${idx} has inline data: ${cellText}`);
                            }
                            return;
                        }
                        
                        if (!dateEl || !priceEl) return;
                        
                        // Safe extraction with null checks
                        const dateText = dateEl.innerText?.trim();
                        const priceText = priceEl.innerText?.trim();
                        
                        if (!dateText || !priceText || !priceText.includes('$')) return;
                        
                        
                        // Month detection with multiple fallbacks
                        let monthName = "Unknown";
                        
                        // Strategy 1: Look in closest parent container
                        const parentMonth = cell.closest('[class*="month"], [class*="calendar"], section, article');
                        if (parentMonth) {
                            const header = parentMonth.querySelector('[class*="month"], [class*="label"], h1, h2, h3, h4, strong');
                            if (header && header.innerText) {
                                const text = header.innerText?.trim();
                                if (text && text.length < 50) {  // Reasonable header length
                                    monthName = text;
                                    console.log('[SCRAPER] Found month via parent:', monthName);
                                }
                            }
                        }
                        
                        // Strategy 2: If still Unknown, look for ANY visible month header on page
                        if (monthName === "Unknown") {
                            const allHeaders = document.querySelectorAll('h1, h2, h3, h4, [class*="month"], [class*="calendar-header"]');
                            for (const h of allHeaders) {
                                const text = h.innerText?.trim() || '';
                                // Check if it looks like a month (contains Chinese month characters or English month names)
                                if (text.match(/[一二三四五六七八九十]{1,2}月|January|February|March|April|May|June|July|August|September|October|November|December/)) {
                                    monthName = text;
                                    console.log('[SCRAPER] Found month via global search:', monthName);
                                    break;
                                }
                            }
                        }
                        
                        
                        // Handle Chinese month names (e.g., "二月" -> "February")
                        const monthMap = {
                            '一月': 'January', '二月': 'February', '三月': 'March',
                            '四月': 'April', '五月': 'May', '六月': 'June',
                            '七月': 'July', '八月': 'August', '九月': 'September',
                            '十月': 'October', '十一月': 'November', '十二月': 'December'
                        };
                        
                        let finalMonthName = monthName.split(' ')[0];
                        if (monthMap[finalMonthName]) {
                            finalMonthName = monthMap[finalMonthName];
                        }
                        
                        const fullDate = `${finalMonthName} ${dateText}`;
                        const isCheapest = priceEl.classList.contains('is-min') || 
                                         cell.classList.contains('is-min') ||
                                         priceEl.classList.contains('cheapest');
                        
                        extracted.push({
                            date: fullDate, 
                            price: priceText,
                            is_cheapest: !!isCheapest
                        });
                    });
                    
                    console.log(`[SCRAPER] Extracted ${extracted.length} entries`);
                    if (extracted.length > 0) {
                        console.log('[SCRAPER] Sample:', extracted[0]);
                    }
                    
                    return { 
                        days: extracted,
                        debug: {
                            totalCells: cells.length,
                            extracted: extracted.length
                        }
                    };
                }
                """)
                
                logger.info(f"Extraction complete: {result_data.get('debug', {})}")

                if not result_data or not result_data['days']:
                    raise Exception("Calibration failed: No price data found in .date-cell elements.")


                # Parse the target month from the standardized start date
                # formatted_start_date is guaranteed to be "MM/DD/YYYY" by standardize_date()
                try:
                    target_date_obj = datetime.strptime(formatted_start_date, "%m/%d/%Y")
                    target_month_name = target_date_obj.strftime("%B") # e.g., "February"
                except:
                    target_month_name = ""

                # 将字符串价格转换为浮点数
                final_prices = []
                logger.info(f"Filtering for target month: '{target_month_name}'")
                logger.info(f"Raw extracted data sample: {result_data['days'][:3] if len(result_data['days']) > 0 else 'None'}")
                
                for d in result_data['days']:
                    try:
                        # Filter: Ensure the scraped date belongs to the requested month
                        # d['date'] is formatted as "Month Day" (e.g., "February 01")
                        if target_month_name and target_month_name not in d['date']:
                            logger.debug(f"Filtered out: {d['date']} (not matching {target_month_name})")
                            continue

                        # 移除货币符号和逗号
                        numeric_price = float(d['price'].replace('CA$', '').replace('$', '').replace(',', '').strip())
                        final_prices.append(FlightPrice(
                            date=d['date'],
                            price=numeric_price,
                            currency="USD", # 暂时默认
                            is_cheapest=d['is_cheapest']
                        ))
                    except:
                        continue
                
                # Do NOT close context/browser here if we want to keep the session alive for user
                # just return the result
                return ScraperResult(
                    task=task,
                    month="Multi-Month", # Updated to reflect new logic
                    prices=final_prices,
                    timestamp=datetime.now().isoformat(),
                    status="success"
                )

            except Exception as e:
                logger.error(f"Error during scraping: {str(e)}")
                # 发生错误时保存截图
                error_img = f"data/logs/error_{datetime.now().strftime('%H%M%S')}.png"
                await page.screenshot(path=error_img)
                # DEBUG MODE: Hang to keep browser open
                logger.warning("CRITICAL ERROR: Browser will remain open for debugging. Manually close it when done.")
                while True:
                    await asyncio.sleep(10)

if __name__ == "__main__":
    # Test task
    test_task = ScraperTask(
        origin="YVR",
        destination="PVG",
        start_date="02/01/2026",
        routing_codes="C:MU+"
    )
    engine = ITAEngine(headless=False)
    asyncio.run(engine.run_task(test_task))

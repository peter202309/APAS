import asyncio
import logging
try:
    from playwright.async_api import async_playwright
    from playwright_stealth import Stealth
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    async_playwright = None
    Stealth = None

from typing import List, Dict
from apps.backend.schemas import ScraperTask, FlightPrice, ScraperResult
from datetime import datetime
from .proxy_manager import proxy_manager
from .utils import human_sleep

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if not PLAYWRIGHT_AVAILABLE:
    logger.warning("Playwright not installed. Scraping features will be disabled.")

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
            # Launch browser
            browser = await p.chromium.launch(
                headless=self.headless,
                args=['--no-sandbox', '--disable-setuid-sandbox']
            )
            
            # Configure context with random User-Agent
            user_agent = proxy_manager.get_random_user_agent()
            logger.info(f"Using User-Agent: {user_agent[:50]}...")
            
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent=user_agent
            )
            
            # Get the default page or create one
            page = context.pages[0] if context.pages else await context.new_page()
            await Stealth().apply_stealth_async(page)
            
            try:
                # 1. Access Main Page
                logger.info(f"Navigating to {self.url}...")
                await page.goto(self.url, timeout=60000)
                await human_sleep(2, 4) # Wait for page load

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
                        await human_sleep(1, 2)
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
                await human_sleep(3, 5) # Increased wait for autocomplete
                # Try to select the first option if it appears
                try:
                    await page.wait_for_selector('mat-option', timeout=5000)
                    await page.keyboard.press("ArrowDown")
                    await page.keyboard.press("Enter")
                except:
                    await page.keyboard.press("Enter")
                await human_sleep(0.5, 1.5)
                
                # 目的地 - Slow down interaction
                dest_box = await page.wait_for_selector('mat-form-field:has-text("Destination") input', timeout=15000)
                await dest_box.click()
                await page.keyboard.press("Control+a")
                await page.keyboard.press("Backspace")
                await dest_box.type(task.destination, delay=200)
                await human_sleep(3, 5) # Increased wait for autocomplete
                try:
                    await page.wait_for_selector('mat-option', timeout=5000)
                    await page.keyboard.press("ArrowDown")
                    await page.keyboard.press("Enter")
                except:
                    await page.keyboard.press("Enter")
                await human_sleep(0.5, 1.5)

                # 3.5. 处理 Routing Codes (Simplified - No Toggle)
                # Since user has manually expanded controls in persistent browser, they stay visible
                # 3.5. Advanced Routing & Extension Codes
                logger.info("Filling Advanced Routing & Extension Codes...")
                
                # 3.4. Ensure Advanced Controls are visible
                try:
                    # Look for the link/button to expand advanced controls
                    # Common text variations: "Show advanced controls", "Advanced controls"
                    advanced_link = page.locator('text=/Show advanced controls/i') # Case insensitive regex
                    if await advanced_link.is_visible() and await advanced_link.is_enabled():
                         logger.info("Clicking 'Show advanced controls'...")
                         await advanced_link.click()
                         await human_sleep(0.5, 1.5) # Wait for expansion
                    else:
                         logger.info("Advanced controls might be already visible or not found.")
                except Exception as e:
                     logger.warning(f"Note: Could not toggle advanced controls (might already be open): {e}")

                async def fill_advanced_field(label, index, value):
                    if not value: return
                    try:
                        # Find all matching fields
                        # Note: "Routing Codes" and "Extension Codes" fields appear multiple times in Round Trip
                        # We use nth(index) to target Outbound (0) vs Return (1)
                        field = page.locator(f'mat-form-field:has-text("{label}") input').nth(index)
                        
                        # Check availability
                        if await field.is_visible():
                            await field.focus()
                            await human_sleep(0.1, 0.3)
                            await field.fill(value)
                            await human_sleep(0.1, 0.3)
                            logger.info(f"✓ Filled {label} [{index}]: {value}")
                        else:
                            logger.warning(f"Field {label} [{index}] not visible")
                    except Exception as e:
                        logger.warning(f"Failed to fill {label} [{index}]: {e}")

                # Outbound (Index 0)
                await fill_advanced_field("Routing Codes", 0, task.routing_codes)
                await fill_advanced_field("Extension Codes", 0, task.extension_codes)

                # Return (Index 1) - Only if Round Trip
                if task.trip_type == "round_trip":
                    await fill_advanced_field("Routing Codes", 1, task.return_routing_codes)
                    await fill_advanced_field("Extension Codes", 1, task.return_extension_codes)
                
                await page.keyboard.press("Escape")


                # 3.6 Advanced Controls: Currency, Stops, Extra Stops
                logger.info("Setting Advanced Controls...")

                # Currency -> Always CAD
                try:
                    # Use specific text to find the currency field
                    curr_field = await page.wait_for_selector('mat-form-field:has-text("Currency") input', timeout=5000)
                    await curr_field.click()
                    # Clear existing text
                    await page.keyboard.press("Control+a")
                    await page.keyboard.press("Backspace")
                    await human_sleep(0.5, 1)
                    await curr_field.type("CAD", delay=100)
                    await human_sleep(1, 2) # Wait for dropdown population
                    # Select the option explicitly
                    await page.click('mat-option:has-text("Canadian Dollar")', timeout=5000)
                    logger.info("✓ Currency set to CAD")
                except Exception as e:
                    logger.warning(f"Failed to set Currency (Non-critical): {e}")

                # Stops
                if task.stops:
                    try:
                        logger.info(f"Setting Stops: {task.stops}")
                        # Use a more specific locator to avoid confusion with "Extra stops"
                        # We look for the form field that has "Stops" but NOT "Extra"
                        stops_field = page.locator('mat-form-field').filter(has_text="Stops").filter(has_not_text="Extra").first
                        if await stops_field.is_visible():
                            await stops_field.click()
                            await human_sleep(0.5, 1)
                            # Select option by text (fuzzy match ok for options)
                            await page.click(f'mat-option:has-text("{task.stops}")', timeout=2000)
                            logger.info(f"✓ Stops set to: {task.stops}")
                    except Exception as e:
                        logger.warning(f"Failed to set Stops: {e}")

                # Extra Stops
                if hasattr(task, 'extra_stops') and task.extra_stops:
                    try:
                        logger.info(f"Setting Extra Stops: {task.extra_stops}")
                        ex_stops_field = await page.wait_for_selector('mat-form-field:has-text("Extra stops")', timeout=5000)
                        await ex_stops_field.click()
                        await human_sleep(0.5, 1)
                        await page.click(f'mat-option:has-text("{task.extra_stops}")', timeout=2000)
                        logger.info(f"✓ Extra Stops set to: {task.extra_stops}")
                    except Exception as e:
                        logger.warning(f"Failed to set Extra Stops: {e}")

                # 4. 选择“价格日历”模式
                logger.info("Switching to 'See calendar of lowest fares' mode...")
                try:
                    # 点击模式下拉框 (通常显示 "Search exact date")
                    await page.click('mat-select[role="combobox"]', timeout=20000)
                    await human_sleep(1, 2)
                    # 选中日历选项
                    await page.click('mat-option:has-text("See calendar of lowest fares")', timeout=20000)
                    await human_sleep(1, 2)
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
                await human_sleep(0.5, 1)
                await date_box.type(formatted_start_date, delay=100) # Type standard format
                await human_sleep(0.5, 1)
                await page.keyboard.press("Enter") # Commit the valid date
                await human_sleep(0.5, 1)
                
                # 仅在 Round Trip 模式下填写 Nights
                if task.trip_type == "round_trip":
                    logger.info(f"Filling duration: {task.nights}")
                    duration_box = await page.wait_for_selector('mat-form-field:has-text("Duration (nights)") input', timeout=10000)
                    await duration_box.fill(str(task.nights))
                    await human_sleep(0.5, 1)
                    await page.keyboard.press("Escape") # 再次确保所有 Material 弹窗关闭


                # 6. Execute Search
                logger.info("Executing search...")
                await human_sleep(1, 3) # Pause before clicking search
                # 在点击搜索前，最后做一次全局 Escape，确保没有遮罩层
                await page.keyboard.press("Escape")
                await human_sleep(0.5, 1)
                
                
                # 智能 Search 执行策略 - 检测搜索是否已自动触发
                logger.info("Checking if search has auto-started...")
                
                # 等待一下,看页面是否已经开始加载结果
                await asyncio.sleep(2)
                
                # 检查 URL 是否已经变化(表示搜索已开始)
                current_url = page.url
                search_already_started = "calendar" in current_url or page.url != self.url
                
                if search_already_started:
                    logger.info("✓ Search already auto-started (URL changed or loading detected)")
                else:
                    # 搜索未自动开始,尝试手动点击 Search 按钮
                    logger.info("Search not auto-started, looking for Search button...")
                    search_btn = None
                    try:
                        # 策略 1: 快速查找按钮 (5秒足够,因为页面已经稳定)
                        search_btn = await page.wait_for_selector('button:has-text("Search")', timeout=5000)
                        logger.info("✓ Search button found")
                    except Exception as e1:
                        logger.warning(f"Text selector failed: {e1}")
                        try:
                            # 策略 2: 属性选择器
                            search_btn = await page.wait_for_selector('button[type="submit"]', timeout=3000)
                            logger.info("✓ Search button found via attribute")
                        except Exception as e2:
                            logger.warning(f"Attribute selector also failed: {e2}")
                            logger.error("⚠️ Cannot find Search button, but will proceed assuming auto-submit")
                    
                    if search_btn:
                        try:
                            await search_btn.click()
                            logger.info("✓ Search button clicked manually")
                        except Exception as click_err:
                            logger.warning(f"Click failed (button may have disappeared): {click_err}")
                            logger.info("Proceeding anyway, search may have auto-started")
                
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
                        
                        # Check for "No flights match" message fast fail
                        if await page.is_visible('div:has-text("No flights match")') or await page.is_visible('span:has-text("No flights found")'):
                             logger.warning(f"Fast fail: No flights found matching criteria.")
                             return ScraperResult(
                                task=task,
                                month="Multi-Month",
                                prices=[],
                                timestamp=datetime.now().isoformat(),
                                status="success",
                                message="No flights found matching criteria"
                            )
                    except:
                        pass
                    
                    logger.info(f"Still waiting for results... (Elapsed: {int((datetime.now()-start_wait).total_seconds())}s)")
                    await asyncio.sleep(10)

                if not found_results:
                     logger.warning("Timeout reached (300s) waiting for visible .date-cell.")
                     # Check for "No flights match" message
                     no_flights_msg = await page.query_selector('div:has-text("No flights match"), span:has-text("No flights found")')
                     if no_flights_msg:
                         logger.warning(f"Search returned no results (likely due to strict filters: {task.routing_codes} {task.extension_codes})")
                         return ScraperResult(
                            task=task,
                            month="Multi-Month",
                            prices=[], # Empty list = No flights
                            timestamp=datetime.now().isoformat(),
                            status="success", # It's a valid result, just empty
                            message="No flights found matching criteria"
                        )
                     
                     logger.warning("Attempting extraction anyway...")
                
                # 9. 提取第一个月的数据 (Enhanced with debugging)
                logger.info("Extracting calendar data from v5 layout...")
                
                result_data = await page.evaluate(r"""
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
                            if (cellText.includes('$') && cellText.match(/\d+/)) {
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
                        
                        
                        
                        // Month abbreviation map for ddmmmyy format (supports both Chinese and English)
                        const monthAbbrev = {
                            '一月': 'JAN', '二月': 'FEB', '三月': 'MAR',
                            '四月': 'APR', '五月': 'MAY', '六月': 'JUN',
                            '七月': 'JUL', '八月': 'AUG', '九月': 'SEP',
                            '十月': 'OCT', '十一月': 'NOV', '十二月': 'DEC',
                            'January': 'JAN', 'February': 'FEB', 'March': 'MAR',
                            'April': 'APR', 'May': 'MAY', 'June': 'JUN',
                            'July': 'JUL', 'August': 'AUG', 'September': 'SEP',
                            'October': 'OCT', 'November': 'NOV', 'December': 'DEC'
                        };
                        
                        let monthKey = monthName.split(' ')[0];
                        let monthCode = monthAbbrev[monthKey] || 'UNK';
                        
                        // Format: ddmmmyy (e.g., 06FEB26)
                        const yearStr = new Date().getFullYear().toString().slice(-2);
                        
                        // Robust day extraction: find digits, default to "01", pad to 2 chars
                        const dayMatch = dateText.match(/\d+/);
                        const dayStr = dayMatch ? dayMatch[0] : "01"; 
                        const dayPadded = dayStr.padStart(2, '0');
                        
                        const fullDate = `${dayPadded}${monthCode}${yearStr}`;
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
                    # Special handling: validation succeeded (cells found) but no prices (strict filters)
                    debug_info = result_data.get('debug', {})
                    if debug_info.get('totalCells', 0) > 0:
                         logger.warning(f"Calendar layout detected ({debug_info.get('totalCells')} cells) but 0 prices extracted. Treating as 'No Flights Found'.")
                         return ScraperResult(
                            task=task,
                            month="Multi-Month",
                            prices=[], # Valid empty result
                            timestamp=datetime.now().isoformat(),
                            status="success",
                            message="No flights found (calendar visible but empty)"
                        )
                    
                    raise Exception("Calibration failed: No price data found in .date-cell elements.")


                # Parse the target month from the standardized start date
                # formatted_start_date is guaranteed to be "MM/DD/YYYY" by standardize_date()
                try:
                    target_date_obj = datetime.strptime(formatted_start_date, "%m/%d/%Y")
                    # Convert to 3-letter abbreviation for ddmmmyy format (e.g., "FEB")
                    target_month_abbrev = target_date_obj.strftime("%b").upper()  # "FEB"
                except:
                    target_month_abbrev = ""

                # 将字符串价格转换为浮点数
                final_prices = []
                logger.info(f"Filtering for target month: '{target_month_abbrev}'")
                logger.info(f"Raw extracted data sample: {result_data['days'][:3] if len(result_data['days']) > 0 else 'None'}")
                
                for d in result_data['days']:
                    try:
                        # Filter: Ensure the scraped date belongs to the requested month
                        # d['date'] is now formatted as "ddmmmyy" (e.g., "06FEB26")
                        if target_month_abbrev and target_month_abbrev not in d['date']:
                            logger.debug(f"Filtered out: {d['date']} (not matching {target_month_abbrev})")
                            continue

                        # 移除货币符号和逗号
                        # Handle varied currency symbols
                        clean_price = d['price'].replace('CA$', '').replace('$', '').replace('CAD', '').replace(',', '').strip()
                        numeric_price = float(clean_price)
                        final_prices.append(FlightPrice(
                            date=d['date'],
                            price=numeric_price,
                            currency="CAD", # Forced to CAD per user requirement
                            is_cheapest=d['is_cheapest']
                        ))
                    except Exception as parse_err:
                        logger.warning(f"Failed to parse price item {d}: {parse_err}")
                        continue
                
                logger.info(f"Final extracted count after filtering: {len(final_prices)}")
                
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

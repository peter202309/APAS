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
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                locale="en-US" # 强制英文环境
            )
            page = await context.new_page()
            await Stealth().apply_stealth_async(page)
            
            try:
                logger.info(f"Navigating to {self.url}...")
                await page.goto(self.url, wait_until="networkidle")
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
                origin_box = await page.wait_for_selector('mat-form-field:has-text("Origin") input', timeout=15000)
                await origin_box.fill(task.origin)
                await asyncio.sleep(1)
                await page.keyboard.press("Enter")
                
                # 目的地
                dest_box = await page.wait_for_selector('mat-form-field:has-text("Destination") input', timeout=15000)
                await dest_box.fill(task.destination)
                await asyncio.sleep(1)
                await page.keyboard.press("Enter")

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
                await date_box.fill(task.start_date)
                await asyncio.sleep(1)
                await page.keyboard.press("Escape") # 填完之后强制 Escape，确保日期选择器窗口消失
                await asyncio.sleep(0.5)
                
                # 仅在 Round Trip 模式下填写 Nights
                if task.trip_type == "round_trip":
                    logger.info(f"Filling duration: {task.nights}")
                    duration_box = await page.wait_for_selector('mat-form-field:has-text("Duration (nights)") input', timeout=10000)
                    await duration_box.fill(str(task.nights))
                    await asyncio.sleep(0.5)
                    await page.keyboard.press("Escape") # 再次确保所有 Material 弹窗关闭

                # 5. 处理 Routing Codes (高级控制)
                if task.routing_codes:
                    logger.info(f"Filling Routing Codes: {task.routing_codes}")
                    show_adv = await page.query_selector('button:has-text("Show Advanced Controls")')
                    if show_adv:
                        await show_adv.click()
                        await asyncio.sleep(1)
                    
                    # 寻找标签包含 "Routing Codes" 的 input，有的页面可能有多个，取第一个
                    routing_box = await page.wait_for_selector('mat-form-field:has-text("Routing Codes") input', timeout=5000)
                    await routing_box.fill(task.routing_codes)
                    await asyncio.sleep(0.5)
                    await page.keyboard.press("Escape")

                # 6. 执行搜索
                logger.info("Executing search...")
                # 在点击搜索前，最后做一次全局 Escape，确保没有遮罩层
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.5)
                
                search_btn = await page.wait_for_selector('button:has-text("Search")', timeout=10000)
                await search_btn.click()
                
                # 等待结果加载 (Matrix v5 下拉加载较快，但渲染需要时间)
                logger.info("Waiting for Results to render...")
                await page.wait_for_selector('.date-cell, .price', timeout=60000)
                await asyncio.sleep(5) 

                # 9. 提取第一个月的数据 (针对 v5 重写)
                logger.info("Extracting calendar data from v5 layout...")
                
                result_data = await page.evaluate("""
                () => {
                    const days = [];
                    const cells = document.querySelectorAll('.date-cell');
                    
                    cells.forEach(cell => {
                        const dateText = cell.querySelector('.date')?.innerText;
                        const priceEl = cell.querySelector('.price');
                        const priceText = priceEl ? priceEl.innerText : null;
                        
                        // v5 判定最便宜通常使用 .is-min 类或者特定颜色
                        const isCheapest = priceEl && (
                            priceEl.classList.contains('is-min') || 
                            window.getComputedStyle(priceEl).color.includes('230, 81, 0')
                        );
                        
                        if (dateText && priceText && priceText.includes('$')) {
                            days.push({
                                date: dateText.trim(),
                                price: priceText.trim(),
                                is_cheapest: !!isCheapest
                            });
                        }
                    });
                    
                    // 获取月份标题
                    const header = document.querySelector('.calendar-month-name, .month-label');
                    return { 
                        month: header ? header.innerText : null, 
                        days: days 
                    };
                }
                """)

                if not result_data or not result_data['days']:
                    raise Exception("Calibration failed: No price data found in .date-cell elements.")

                # 将字符串价格转换为浮点数
                final_prices = []
                for d in result_data['days']:
                    try:
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
                
                return ScraperResult(
                    task=task,
                    month=result_data['month'] or "Current Month",
                    prices=final_prices,
                    timestamp=datetime.now().isoformat(),
                    status="success"
                )

            except Exception as e:
                logger.error(f"Error during scraping: {str(e)}")
                # 发生错误时保存截图
                error_img = f"data/logs/error_{datetime.now().strftime('%H%M%S')}.png"
                await page.screenshot(path=error_img)
                return ScraperResult(
                    task=task,
                    month="N/A",
                    prices=[],
                    timestamp=datetime.now().isoformat(),
                    status="error",
                    message=f"{str(e)} (Screenshot saved to {error_img})"
                )
            finally:
                await browser.close()

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

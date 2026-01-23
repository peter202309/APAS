import pandas as pd
import logging
from typing import List
from .schemas import ScraperResult, FlightPrice

class DataProcessor:
    @staticmethod
    def prices_to_csv(results: List[ScraperResult], output_path: str):
        flat_data = []
        for res in results:
            for p in res.prices:
                flat_data.append({
                    "Search_Date": res.timestamp[:10],
                    "Origin": res.task.origin,
                    "Destination": res.task.destination,
                    "Airline_Filter": res.task.routing_codes,
                    "Month": res.month,
                    "Flight_Full_Date": p.date,
                    "Price": p.price,
                    "Currency": p.currency,
                    "Is_Lowest": p.is_cheapest
                })
        
        df = pd.DataFrame(flat_data)
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        
        # VERIFICATION: Read back the file immediately to prove content
        try:
            with open(output_path, 'r', encoding='utf-8-sig') as f:
                logger = logging.getLogger(__name__)
                logger.info(f"--- CSV CONTENT VERIFICATION ({output_path}) ---")
                for _ in range(3):
                    line = f.readline().strip()
                    if line: logger.info(f"CSV Line: {line}")
                logger.info("------------------------------------------------")
        except:
            pass

        return output_path

    @staticmethod
    def analyze_mu_variance(mu_results: ScraperResult, market_all_results: ScraperResult):
        """
        分析东航 (MU) 价格与全市场建议价格的差异度
        """
        mu_prices = {p.date: p.price for p in mu_results.prices}
        market_prices = {}
        
        # 统计市场每天的最低价
        for p in market_all_results.prices:
            if p.date not in market_prices or p.price < market_prices[p.date]:
                market_prices[p.date] = p.price
        
        analysis = []
        for date, mu_p in mu_prices.items():
            market_min = market_prices.get(date)
            if market_min:
                diff = mu_p - market_min
                diff_pct = (diff / market_min) * 100 if market_min > 0 else 0
                analysis.append({
                    "date": date,
                    "mu_price": mu_p,
                    "market_min": market_min,
                    "variance_abs": round(diff, 2),
                    "variance_pct": round(diff_pct, 2),
                    "status": "Competitive" if diff_pct < 5 else "High" if diff_pct > 15 else "Market Match"
                })
        
        return analysis

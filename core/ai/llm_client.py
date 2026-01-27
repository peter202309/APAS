from groq import Groq
import os
from dotenv import load_dotenv

load_dotenv()

class AIGenerator:
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY")
        # Fallback to Google Key if Groq is missing? No, user explicitly asked for Groq.
        if not self.api_key:
            # We can't raise error immediately if key is missing, to allow app startup
            # But subsequent calls will fail.
            print("Warning: GROQ_API_KEY not found in .env")
            self.client = None
        else:
            self.client = Groq(api_key=self.api_key)
            
        # Using Llama 3.3 70B for best reasoning capability
        self.model_name = 'llama-3.3-70b-versatile'

    def analyze_price_trend(self, origin, destination, prices, airline_filter=None):
        """
        Analyzes price trends using Groq (Llama 3).
        """
        if not self.client:
            return "Error: GROQ_API_KEY not configured."
            
        # Prepare data summary
        if not prices:
            return "No price data available for analysis."
            
        data_summary = f"Trace data for {origin} -> {destination}:\n"
        for p in prices[:50]: 
            data_summary += f"- {p['date']}: {p['price']}\n"
            
        system_prompt = "You are an expert aviation revenue analyst. Provide strategic insights based on flight data."
        
        user_prompt = f"""
        Analyze the following flight price data for the route {origin} to {destination}.
        
        Focus Airline: {airline_filter if airline_filter else 'General Market'}
        
        Data:
        {data_summary}
        
        Please provide a concise strategic report in Markdown format including:
        1. **Price Trend**: Is the price increasing, decreasing, or stable?
        2. **Volatility Analysis**: Are there significant price spikes?
        3. **Buying/Selling Strategy**: 
           - For passengers: Is now a good time to buy?
           - For airline (MU): Should we adjust prices? (e.g. if we are undercut by competitors)
        4. **Key Dates**: Highlight any specific dates with abnormal pricing.
        
        Keep the tone professional and data-driven. Use bullet points and bold text for readability.
        """
        
        try:
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.7,
                max_tokens=2048,
            )
            return completion.choices[0].message.content
        except Exception as e:
            return f"AI Analysis Failed (Groq): {str(e)}"

    def compare_airlines(self, comparison_data, user_prompt=None):
        """
        Comparatively analyzes price data from multiple sources/airlines.
        user_prompt: Optional custom instructions from the user.
        """
        if not self.client:
             return "Error: GROQ_API_KEY not configured."

        if not comparison_data:
             return "No data provided for comparison."

        # Summarize data
        data_summary = "Price Sampling (First 20 points per source):\n"
        for source, items in comparison_data.items():
            data_summary += f"\n--- Source: {source} ---\n"
            try:
                sorted_items = sorted(items, key=lambda x: x.get('date', ''))
                for item in sorted_items[:20]:
                     data_summary += f"{item.get('date')}: {item.get('price')}\n"
            except:
                data_summary += "(Data format error)\n"

        system_prompt = "You are a Chief Revenue Officer. Compare pricing strategies of airlines based on data."
        
        base_prompt = f"""
        Compare the pricing strategies of the following airlines/sources based on the provided data samples.
        
        Data:
        {data_summary}
        
        Please provide a Strategic Comparison Report in Markdown:
        1. **Price Leadership**: Who has the lowest prices overall?
        2. **Volatility Gap**: Which airline has more stable pricing?
        3. **Competitive Dates**: Identify dates where the price gap is largest.
        4. **Actionable Advice**: 
           - If Source A is MU (China Eastern), how should we react to the competitors?
           - Suggest a specific pricing adjustment.
        
        Format with clear headers and a comparison table if possible.
        """

        if user_prompt:
             base_prompt += f"\n\nUSER SPECIFIC INSTRUCTION:\nThe user has provided the following specific focus/instruction. You MUST prioritize answering this:\n'{user_prompt}'\n\nEnsure your response addresses this instruction directly."
        
        try:
            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": base_prompt}
                ],
                temperature=0.7,
                max_tokens=2048,
            )
            return completion.choices[0].message.content
        except Exception as e:
            return f"AI Comparison Failed (Groq): {str(e)}"

# Singleton instance
try:
    ai_client = AIGenerator()
except:
    ai_client = None

from groq import Groq
from google import genai
import os
from dotenv import load_dotenv

load_dotenv()

class AIGenerator:
    def __init__(self):
        # Groq Config
        self.groq_api_key = os.getenv("GROQ_API_KEY")
        self.groq_client = None
        if self.groq_api_key:
            try:
                self.groq_client = Groq(api_key=self.groq_api_key)
            except Exception as e:
                print(f"Warning: Groq client failed: {e}")

        # Google Config
        self.google_api_key = os.getenv("GOOGLE_API_KEY")
        self.google_client = None
        if self.google_api_key:
            try:
                self.google_client = genai.Client(api_key=self.google_api_key)
            except Exception as e:
                print(f"Warning: Google GenAI client failed: {e}")
            
        # Default model
        self.default_groq_model = 'llama-3.3-70b-versatile'
        self.default_google_model = 'gemini-flash-latest'

    def get_available_models(self):
        models = []
        if self.groq_client:
            models.append({"provider": "groq", "name": "llama-3.3-70b-versatile", "label": "Groq Llama 3.3 70B"})
            models.append({"provider": "groq", "name": "llama3-8b-8192", "label": "Groq Llama 3 8B"})
        if self.google_client:
            models.append({"provider": "google", "name": "gemini-flash-latest", "label": "Google Gemini Flash (Latest)"})
            models.append({"provider": "google", "name": "gemini-2.0-flash", "label": "Google Gemini 2.0 Flash"})
            models.append({"provider": "google", "name": "gemini-2.5-flash", "label": "Google Gemini 2.5 Flash"})
        return models

    def analyze_price_trend(self, origin, destination, prices, model_config=None):
        """
        Analyzes price trends using selected AI model.
        model_config: {"provider": "groq", "name": "..."}
        """
        provider = model_config.get("provider", "groq") if model_config else "groq"
        model_name = model_config.get("name") if model_config else None

        # Prepare data summary
        if not prices:
            return "No price data available for analysis."
            
        data_summary = f"Trace data for {origin} -> {destination}:\n"
        for p in prices[:50]: 
            data_summary += f"- {p['date']}: {p['price']}\n"
            
        system_prompt = "You are an expert aviation revenue analyst. Provide strategic insights based on flight data."
        user_prompt = f"""
        Analyze the following flight price data for the route {origin} to {destination}.
        
        Data:
        {data_summary}
        
        Please provide a concise strategic report in Markdown format including:
        1. **Price Trend**: Is the price increasing, decreasing, or stable?
        2. **Volatility Analysis**: Are there significant price spikes?
        3. **Buying/Selling Strategy**: 
           - For passengers: Is now a good time to buy?
           - For airline (MU): Should we adjust prices?
        4. **Key Dates**: Highlight any specific dates with abnormal pricing.
        """
        
        return self._generate(provider, model_name, system_prompt, user_prompt)

    def compare_airlines(self, comparison_data, user_prompt=None, model_config=None):
        """
        Comparatively analyzes price data from multiple sources.
        """
        provider = model_config.get("provider", "groq") if model_config else "groq"
        model_name = model_config.get("name") if model_config else None

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
        Compare the pricing strategies based on the provided data samples.
        
        Data:
        {data_summary}
        
        Please provide a Strategic Comparison Report in Markdown:
        1. **Price Leadership**: Who has the lowest prices overall?
        2. **Volatility Gap**: Which airline has more stable pricing?
        3. **Competitive Dates**: Identify dates where the price gap is largest.
        4. **Actionable Advice**: 
           - Suggest specific pricing adjustments.
        """

        if user_prompt:
             base_prompt += f"\n\nUSER SPECIFIC INSTRUCTION:\n{user_prompt}"
        
        return self._generate(provider, model_name, system_prompt, base_prompt)

    def _generate(self, provider, model_name, system_prompt, user_prompt):
        if provider == "groq":
            if not self.groq_client: return "Error: GROQ_API_KEY not configured."
            try:
                completion = self.groq_client.chat.completions.create(
                    model=model_name or self.default_groq_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.7,
                    max_tokens=2048,
                )
                return completion.choices[0].message.content
            except Exception as e:
                return f"Groq Generation Failed: {str(e)}"
        
        elif provider == "google":
            if not self.google_client: return "Error: GOOGLE_API_KEY not configured."
            try:
                # Google GenAI SDK usage
                response = self.google_client.models.generate_content(
                    model=model_name or self.default_google_model,
                    contents=f"{system_prompt}\n\n{user_prompt}"
                )
                return response.text
            except Exception as e:
                return f"Google Generation Failed: {str(e)}"
        
        return f"Unknown provider: {provider}"

# Singleton instance
try:
    ai_client = AIGenerator()
except Exception as e:
    print(f"Error initializing AI client: {e}")
    ai_client = None

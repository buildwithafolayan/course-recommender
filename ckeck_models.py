import os
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY:
    print("Error: GEMINI_API_KEY not found in .env file.")
    exit()

try:
    genai.configure(
        api_key=API_KEY,
        client_options={"api_endpoint": "generativelanguage.googleapis.com"}
    )
    print("Configured Gemini API. Listing models...")
    for m in genai.list_models():
        if "generateContent" in m.supported_generation_methods:
            print(f"  Model: {m.name}, Supported methods: {m.supported_generation_methods}")
except Exception as e:
    print(f"An error occurred while listing models: {e}")
    print("Please ensure your API key is correct and valid.")
import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
print(f"Using API key: {api_key[:10]}...{api_key[-4:]}")

genai.configure(api_key=api_key)

# Simple text test first
model = genai.GenerativeModel('gemini-2.5-flash')

try:
    response = model.generate_content("Say 'Hello, the API is working!' in exactly those words.")
    print("SUCCESS!")
    print(response.text)
except Exception as e:
    print(f"ERROR: {e}")

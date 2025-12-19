import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

with open("/tmp/runelite_screenshot_1766125068.png", "rb") as f:
    image_data = f.read()

image_part = {"mime_type": "image/png", "data": image_data}
prompt = "What items are on the ground near the player? Be specific."

models_to_test = ['gemini-2.0-flash-lite', 'gemini-2.5-flash-lite', 'gemini-2.0-flash']

for model_name in models_to_test:
    try:
        model = genai.GenerativeModel(model_name)
        response = model.generate_content([prompt, image_part])
        print(f"\n=== {model_name} ===")
        print(response.text[:200])
    except Exception as e:
        print(f"\n=== {model_name} === ERROR: {str(e)[:100]}")

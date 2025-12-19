import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

with open("/tmp/runelite_screenshot_1766125068.png", "rb") as f:
    image_data = f.read()

model = genai.GenerativeModel('gemini-2.0-flash-lite')
image_part = {"mime_type": "image/png", "data": image_data}

prompt = "What items are on the ground? Be brief."

response = model.generate_content([prompt, image_part])
print("gemini-2.0-flash-lite SUCCESS!")
print(response.text)

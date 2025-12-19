import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Test with the latest screenshot
with open("/tmp/runelite_screenshot_1766125068.png", "rb") as f:
    image_data = f.read()

model = genai.GenerativeModel('gemini-2.5-flash')
image_part = {"mime_type": "image/png", "data": image_data}

prompt = "What game is this? What is on the ground near the player? Keep it brief."

response = model.generate_content([prompt, image_part])
print("Image analysis SUCCESS!")
print(response.text)

import google.generativeai as genai
import os
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

with open("/tmp/runelite_screenshot_1766124659.png", "rb") as f:
    image_data = f.read()

model = genai.GenerativeModel('gemini-2.5-flash')
image_part = {"mime_type": "image/png", "data": image_data}

prompt = """Look at this OSRS bank interface. I need to find a WOODCUTTING AXE (NOT a pickaxe).

Axes have a curved blade for chopping wood. Pickaxes have a pointed pick head for mining.

Please identify EVERY item in the first 4 rows with their EXACT in-game names.
Format: Row X, Position Y: "Item Name"

Then tell me if there is any axe for woodcutting."""

response = model.generate_content([prompt, image_part])
print(response.text)

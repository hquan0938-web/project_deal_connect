import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from google import genai
from config import Config

client = genai.Client(api_key=Config.GEMINI_API_KEY)

for model in client.models.list():
    print(f"- {model.name}")
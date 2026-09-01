import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

try:
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    interaction = client.interactions.create(
        model="gemini-3.6-flash",
        input="Explain what a compiler does?"
    )
    print(interaction.output_text)

except Exception as e:
    print("API error:", e)
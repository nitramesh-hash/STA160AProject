import os
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

if not DEEPSEEK_API_KEY:
    raise ValueError("DEEPSEEK_API_KEY not found in .env file.")


client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com",
)

def ask_deepseek(messages: list[dict], temperature: float = 0.4) -> str:
    

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        temperature=temperature
    )

    return response.choices[0].message.content

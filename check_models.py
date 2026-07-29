import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
api_keys = os.getenv('GEMINI_API_KEY', '').split(',')
if not api_keys or not api_keys[0]:
    print('No API key found')
    exit(1)

genai.configure(api_key=api_keys[0].strip())
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(m.name)
except Exception as e:
    print(f'Error: {e}')

import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
print(
    "Loaded Gemini Key:",
    os.getenv("GEMINI_API_KEY")[-6:]
)


def generate_ai_response(user_text, emotion):
    try:
        model = genai.GenerativeModel("gemini-2.5-flash-lite")

        prompt = f"""
you are a helpful AI assistant inside an AI Mental Health Monitor project

user message:
{user_text}

Detected mood or emotion:
{emotion}

Answer the user's question clearly and helpfully.

if the message is related to stress, anxiety, sadness, emotions, study pressure, or mental health:

- give supportive wellness advice
- do not give medical advice
- do not suggest any mediciens
- suggest talking to a trusted people or professional help  if needed

If the message is a normal question
- answer the question clearly and helpfully

keep the answer concise and clear and do not give any medical advice or suggest any message 
keep the answer simple, friendly, and supportive
"""

        response = model.generate_content(prompt)
        return response.text

    except Exception as e:
        print("Gemini Error:", e)

        return "AI is busy right now. please try again after some time."
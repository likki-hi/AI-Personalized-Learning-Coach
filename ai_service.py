"""Talks to the Gemini API and returns parsed JSON."""
import json
import os
import re
import time

from dotenv import load_dotenv

load_dotenv()

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
_client = None


class LLMError(Exception):
    """Raised when the AI cannot give a usable answer."""


def _get_client():
    global _client
    if _client is None:
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise LLMError("GEMINI_API_KEY is missing. Add it to your .env file.")
        from google import genai
        _client = genai.Client(api_key=key)
    return _client


def _parse_json(text):
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    return json.loads(text)


def call_llm_json(prompt, retries=2):
    """Call Gemini in JSON mode. Retries on bad JSON or API errors."""
    client = _get_client()
    from google.genai import types

    last = ""
    for attempt in range(retries + 1):
        try:
            resp = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json", temperature=0.4
                ),
            )
            return _parse_json(resp.text)
        except json.JSONDecodeError:
            last = "The AI returned invalid JSON."
        except Exception as e:  # network, quota, wrong key...
            last = f"API problem: {e}"
        if attempt < retries:
            time.sleep(1)
    raise LLMError(f"The AI request failed after {retries + 1} attempts. {last}")

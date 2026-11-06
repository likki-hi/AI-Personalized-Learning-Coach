
"""Gemini API service for the AI Personalized Learning Coach."""

import json
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types


# --------------------------------------------------
# Load environment variables
# --------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")

MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

_client = None


# --------------------------------------------------
# Custom exception
# --------------------------------------------------

class LLMError(Exception):
    """Raised when the AI cannot provide a usable answer."""


# --------------------------------------------------
# Gemini client
# --------------------------------------------------

def _get_client():
    """Create and return the Gemini API client."""

    global _client

    if _client is None:

        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            raise LLMError(
                "GEMINI_API_KEY is missing. "
                "Please add it to your .env file."
            )

        try:
            _client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(
                    timeout=30000
                )
            )

        except Exception as e:
            raise LLMError(
                f"Unable to initialize Gemini client: {e}"
            ) from e

    return _client


# --------------------------------------------------
# JSON response parser
# --------------------------------------------------

def _parse_json(text):
    """Clean and parse JSON returned by Gemini."""

    if not text:
        raise LLMError("Gemini returned an empty response.")

    text = text.strip()

    # Remove Markdown code block formatting
    text = re.sub(
        r"^```(?:json)?\s*|\s*```$",
        "",
        text,
        flags=re.MULTILINE
    ).strip()

    try:
        return json.loads(text)

    except json.JSONDecodeError as e:
        raise LLMError(
            "The AI returned invalid JSON."
        ) from e


# --------------------------------------------------
# Gemini API request
# --------------------------------------------------

def call_llm_json(prompt, retries=1):
    """
    Send a prompt to Gemini and return parsed JSON.

    Features:
    - JSON response mode
    - 30-second HTTP timeout
    - Retry for temporary API errors
    - Exponential backoff
    """

    client = _get_client()

    temporary_errors = (
        "503",
        "UNAVAILABLE",
        "429",
        "RESOURCE_EXHAUSTED",
        "500",
        "INTERNAL",
        "502",
        "504",
        "TIMEOUT"
    )

    last_error = ""

    for attempt in range(retries + 1):

        try:

            response = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.4
                )
            )

            return _parse_json(response.text)

        except LLMError:
            raise

        except Exception as e:

            last_error = f"API problem: {e}"

            error_text = str(e).upper()

            # Stop immediately for non-temporary errors
            if not any(
                error in error_text
                for error in temporary_errors
            ):
                raise LLMError(last_error) from e

        # Wait before retrying
        if attempt < retries:

            wait_time = 2 ** (attempt + 1)

            time.sleep(wait_time)

    raise LLMError(
        f"The AI request failed after {retries + 1} attempts. "
        f"{last_error}"
    )

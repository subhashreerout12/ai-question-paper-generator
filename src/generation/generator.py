"""Calls the LLM (Ollama for free, or Claude) and returns validated question dicts.

Choose the provider in your .env file:
    LLM_PROVIDER=ollama            # free, runs on your laptop
    OLLAMA_MODEL=llama3.2
or
    LLM_PROVIDER=anthropic         # paid API (default)
    ANTHROPIC_API_KEY=sk-ant-...
"""

import json
import os
import re
import urllib.error
import urllib.request

from src.generation.prompts import PROMPT_BUILDERS

CLAUDE_MODEL = "claude-sonnet-5-5"


# ---------------------------------------------------------------- parsing
def parse_json(raw: str) -> list:
    """Turn the model's reply into a list of question dicts.

    Small local models often add chatter around the JSON, so this tries
    several ways to find the array before giving up.
    """
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("["), raw.rfind("]")
        if start == -1 or end <= start:
            raise
        data = json.loads(raw[start : end + 1])

    if isinstance(data, dict):  # model wrapped the list, e.g. {"questions": [...]}
        lists = [v for v in data.values() if isinstance(v, list)]
        data = lists[0] if lists else [data]
    return data


# ---------------------------------------------------------------- providers
def call_ollama(prompt: str, max_tokens: int) -> str:
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    model = os.getenv("OLLAMA_MODEL", "llama3.2")
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0.3, "num_ctx": 4096, "num_predict": max_tokens},
        }
    ).encode()
    request = urllib.request.Request(
        f"{host}/api/chat", data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(request, timeout=900) as response:
            return json.loads(response.read())["message"]["content"]
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="ignore")[:200]
        raise RuntimeError(
            f"Ollama returned an error ({e.code}): {detail}\n"
            f"If it says the model was not found, run: ollama pull {model}"
        ) from e
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        raise RuntimeError(
            f"Could not reach Ollama at {host}. Is the Ollama app running? "
            "Open the Ollama app (or run: ollama serve) and try again."
        ) from e


def call_claude(prompt: str, max_tokens: int) -> str:
    from anthropic import Anthropic  # imported here so Ollama users never need a key

    client = Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    response = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text


def call_llm(prompt: str, max_tokens: int = 3000) -> str:
    provider = os.getenv("LLM_PROVIDER", "anthropic").strip().lower()
    if provider == "ollama":
        return call_ollama(prompt, max_tokens)
    return call_claude(prompt, max_tokens)


# ---------------------------------------------------------------- validation
def _normalise_mcq(q: dict) -> bool:
    """Make the MCQ answer a single letter A-D. Returns False if it cannot be fixed."""
    options = q.get("options")
    if not isinstance(options, list) or len(options) != 4:
        return False
    options = [str(o).strip() for o in options]
    # strip leading "A) " / "B. " that some models add to the option text
    options = [re.sub(r"^[A-Da-d][\)\.:]\s+", "", o) for o in options]
    q["options"] = options

    answer = str(q.get("answer", "")).strip()
    letter = answer.upper()
    if letter[:1] in ("A", "B", "C", "D") and (len(letter) == 1 or letter[1] in ").:"):
        q["answer"] = letter[0]
        return True
    for i, option in enumerate(options):  # answer given as the option text
        if answer.lower() == option.lower():
            q["answer"] = "ABCD"[i]
            return True
    return False


def is_valid(q, qtype: str) -> bool:
    """Structure check so malformed questions never reach the paper."""
    if not isinstance(q, dict) or not str(q.get("question", "")).strip() or not q.get("answer"):
        return False
    if qtype == "mcq":
        return _normalise_mcq(q)
    return True


# ---------------------------------------------------------------- main API
def generate_questions(chunk: str, qtype: str, n: int, retries: int = 2) -> list[dict]:
    """Generate n questions of one type from a text chunk.

    Retries if the reply is not valid JSON, and drops malformed items.
    """
    prompt = PROMPT_BUILDERS[qtype](chunk, n)
    items = []
    for attempt in range(retries + 1):
        try:
            items = parse_json(call_llm(prompt))
            break
        except json.JSONDecodeError:
            if attempt == retries:
                return []
    valid = [q for q in items if is_valid(q, qtype)]
    for q in valid:
        q["type"] = qtype
    return valid

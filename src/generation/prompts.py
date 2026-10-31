"""Prompt templates for each question type."""

_JSON_RULE = "Return ONLY a JSON array, with no explanation and no code fences."


def build_mcq_prompt(chunk: str, n: int) -> str:
    return f"""You are an experienced teacher writing exam questions.

Using ONLY the text below, write {n} multiple-choice questions.

Rules:
- Each question has exactly 4 options.
- Exactly one option is correct; the other three must be plausible but clearly wrong.
- Mix difficulty: roughly 30% easy, 50% medium, 20% hard.
- Do not ask about information that is not in the text.
- {_JSON_RULE}

Each item must look like this:
{{
  "question": "...",
  "options": ["A text", "B text", "C text", "D text"],
  "answer": "A",
  "difficulty": "easy | medium | hard",
  "explanation": "one sentence on why the answer is correct"
}}

TEXT:
\"\"\"
{chunk}
\"\"\"
"""


def build_short_prompt(chunk: str, n: int) -> str:
    return f"""You are an experienced teacher writing exam questions.

Using ONLY the text below, write {n} short-answer questions.

Rules:
- Each question should be answerable in 2-4 sentences.
- Use varied question words (explain, describe, why, how, compare).
- Mix difficulty: roughly 30% easy, 50% medium, 20% hard.
- Do not ask about information that is not in the text.
- The model answer must be based only on the text.
- {_JSON_RULE}

Each item must look like this:
{{
  "question": "...",
  "answer": "model answer in 2-4 sentences",
  "marks": 3,
  "difficulty": "easy | medium | hard",
  "key_points": ["point 1", "point 2", "point 3"]
}}

TEXT:
\"\"\"
{chunk}
\"\"\"
"""


PROMPT_BUILDERS = {
    "mcq": build_mcq_prompt,
    "short": build_short_prompt,
}

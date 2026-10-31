"""
first_test.py - Day 1 prototype for the AI-Based Question Paper Generator.

What it does:
    1. Reads a PDF (one chapter is enough) with PyMuPDF
    2. Takes the first ~1000 words as a chunk
    3. Asks Claude to write MCQs from that chunk, returned as JSON
    4. Prints the questions and saves them to outputs/mcqs.json

Usage:
    python first_test.py path/to/chapter.pdf
    python first_test.py path/to/chapter.pdf --num 8 --words 1500
"""

import argparse
import json
import os
import re
import sys

import fitz  # PyMuPDF
from anthropic import Anthropic
from dotenv import load_dotenv

MODEL = "claude-sonnet-5-5"


def extract_text(pdf_path: str) -> str:
    """Return all text from the PDF as one string."""
    doc = fitz.open(pdf_path)
    pages = [page.get_text() for page in doc]
    doc.close()
    text = "\n".join(pages)
    # Collapse extra whitespace left over from PDF layout
    return re.sub(r"\s+", " ", text).strip()


def first_chunk(text: str, max_words: int) -> str:
    """Take the first max_words words as the chunk to generate from."""
    return " ".join(text.split()[:max_words])


def build_prompt(chunk: str, num_questions: int) -> str:
    return f"""You are an experienced teacher writing exam questions.

Using ONLY the text below, write {num_questions} multiple-choice questions.

Rules:
- Each question has exactly 4 options.
- Exactly one option is correct; the other three must be plausible but clearly wrong.
- Mix difficulty: roughly 30% easy, 50% medium, 20% hard.
- Do not ask about information that is not in the text.
- Return ONLY a JSON array, with no explanation and no code fences.

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


def parse_json(raw: str):
    """Parse the model's reply, tolerating stray code fences."""
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
    return json.loads(raw)


def generate_mcqs(chunk: str, num_questions: int):
    client = Anthropic()  # reads ANTHROPIC_API_KEY from the environment
    response = client.messages.create(
        model=MODEL,
        max_tokens=2500,
        messages=[{"role": "user", "content": build_prompt(chunk, num_questions)}],
    )
    return parse_json(response.content[0].text)


def print_mcqs(mcqs):
    for i, q in enumerate(mcqs, start=1):
        print(f"\nQ{i}. {q['question']}  [{q.get('difficulty', '?')}]")
        for letter, option in zip("ABCD", q["options"]):
            print(f"   {letter}. {option}")
        print(f"   Answer: {q['answer']}")
        if q.get("explanation"):
            print(f"   Why: {q['explanation']}")


def main():
    parser = argparse.ArgumentParser(description="Generate MCQs from a PDF chapter.")
    parser.add_argument("pdf", help="path to the PDF file")
    parser.add_argument("--num", type=int, default=5, help="number of MCQs (default 5)")
    parser.add_argument("--words", type=int, default=1000, help="words of text to use (default 1000)")
    args = parser.parse_args()

    load_dotenv()
    if not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY not found. Add it to your .env file.")
    if not os.path.exists(args.pdf):
        sys.exit(f"PDF not found: {args.pdf}")

    print("Reading PDF...")
    text = extract_text(args.pdf)
    if len(text.split()) < 100:
        sys.exit("Very little text found. The PDF may be scanned; it needs OCR first.")
    chunk = first_chunk(text, args.words)
    print(f"Extracted {len(text.split())} words; using the first {len(chunk.split())}.")

    print("Generating questions...")
    try:
        mcqs = generate_mcqs(chunk, args.num)
    except json.JSONDecodeError:
        sys.exit("The model did not return valid JSON. Run again, or lower --num.")

    print_mcqs(mcqs)

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/mcqs.json", "w", encoding="utf-8") as f:
        json.dump(mcqs, f, indent=2, ensure_ascii=False)
    print("\nSaved to outputs/mcqs.json")


if __name__ == "__main__":
    main()

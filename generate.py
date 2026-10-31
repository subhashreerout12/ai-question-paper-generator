"""
generate.py - entry point: PDF in, questions out (saved to the question bank).

Usage:
    python generate.py chapter.pdf --topic photosynthesis
    python generate.py chapter.pdf --topic photosynthesis --mcq 8 --short 4
    python generate.py chapter.pdf --topic photosynthesis --all     # every chunk of the chapter
    python generate.py chapter.pdf --chunk 2                        # only the 3rd chunk
"""

import argparse
import json
import os
import sys

from dotenv import load_dotenv

from src.assembly.question_bank import add_questions, connect, summary
from src.generation.generator import generate_questions
from src.ingestion.pdf_reader import chunk_text, extract_text


def print_questions(questions: list[dict]) -> None:
    for i, q in enumerate(questions, start=1):
        print(f"\nQ{i}. [{q['type'].upper()} | {q.get('difficulty', '?')}] {q['question']}")
        if q["type"] == "mcq":
            for letter, option in zip("ABCD", q["options"]):
                print(f"   {letter}. {option}")
            print(f"   Answer: {q['answer']}")
            if q.get("explanation"):
                print(f"   Why: {q['explanation']}")
        else:
            print(f"   Marks: {q.get('marks', '?')}")
            print(f"   Model answer: {q['answer']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate questions from a PDF chapter.")
    parser.add_argument("pdf", help="path to the PDF file")
    parser.add_argument("--topic", default="general", help="label saved with each question, e.g. photosynthesis")
    parser.add_argument("--mcq", type=int, default=5, help="MCQs per chunk (default 5)")
    parser.add_argument("--short", type=int, default=3, help="short-answer questions per chunk (default 3)")
    parser.add_argument("--words", type=int, default=1000, help="words per chunk (default 1000)")
    parser.add_argument("--chunk", type=int, default=0, help="which chunk to use, starting at 0")
    parser.add_argument("--all", action="store_true", help="use every chunk of the PDF")
    parser.add_argument("--no-save", action="store_true", help="do not save to the question bank")
    args = parser.parse_args()

    load_dotenv(override=True)  # values in .env win over anything set on the computer
    provider = os.getenv("LLM_PROVIDER", "anthropic").strip().lower()
    if provider == "anthropic" and not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY not found. Add it to .env, or use the free option: LLM_PROVIDER=ollama")
    print(f"LLM provider: {provider}" + (f" ({os.getenv('OLLAMA_MODEL', 'llama3.2')})" if provider == "ollama" else ""))
    if not os.path.exists(args.pdf):
        sys.exit(f"PDF not found: {args.pdf}")

    print("Reading PDF...")
    text = extract_text(args.pdf)
    chunks = chunk_text(text, args.words)
    if not chunks or len(text.split()) < 100:
        sys.exit("Very little text found. The PDF may be scanned; it needs OCR first.")

    if args.all:
        selected = list(enumerate(chunks))
    elif args.chunk < len(chunks):
        selected = [(args.chunk, chunks[args.chunk])]
    else:
        sys.exit(f"Only {len(chunks)} chunk(s) available; use --chunk 0 to {len(chunks) - 1}.")
    print(f"{len(text.split())} words in {len(chunks)} chunk(s); using {len(selected)}.")

    questions: list[dict] = []
    try:
        for index, chunk in selected:
            if args.mcq:
                print(f"Chunk {index}: generating {args.mcq} MCQs...")
                questions += generate_questions(chunk, "mcq", args.mcq)
            if args.short:
                print(f"Chunk {index}: generating {args.short} short-answer questions...")
                questions += generate_questions(chunk, "short", args.short)
    except RuntimeError as e:  # e.g. Ollama is not running
        sys.exit(str(e))

    if not questions:
        sys.exit("No valid questions came back. Run again.")

    print_questions(questions)

    os.makedirs("outputs", exist_ok=True)
    with open("outputs/questions.json", "w", encoding="utf-8") as f:
        json.dump(questions, f, indent=2, ensure_ascii=False)
    print(f"\nSaved {len(questions)} questions to outputs/questions.json")

    if not args.no_save:
        conn = connect()
        added = add_questions(conn, questions, topic=args.topic)
        print(f"Question bank: {added} new, {len(questions) - added} duplicates skipped.")
        print("Bank contents (topic, type, difficulty, count):")
        for row in summary(conn):
            print("  ", *row)


if __name__ == "__main__":
    main()

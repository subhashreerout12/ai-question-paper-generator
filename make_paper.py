"""
make_paper.py - build a question paper (and answer key) from the question bank.

Usage:
    python make_paper.py --title "Unit Test 1" --subject "Science" --mcq 10 --short 4
    python make_paper.py --mcq 10 --short 4 --seed 1      # Set A
    python make_paper.py --mcq 10 --short 4 --seed 2      # Set B (different questions)
    python make_paper.py --topic photosynthesis --mcq 5 --short 2
"""

import argparse
import sys

from src.assembly.paper_builder import build_paper
from src.assembly.question_bank import connect, get_questions
from src.export.docx_export import export_docx


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a question paper from the question bank.")
    parser.add_argument("--title", default="Question Paper")
    parser.add_argument("--subject", default="")
    parser.add_argument("--duration", default="1 Hour")
    parser.add_argument("--mcq", type=int, default=10, help="number of MCQs (default 10)")
    parser.add_argument("--short", type=int, default=4, help="number of short-answer questions (default 4)")
    parser.add_argument("--topic", default=None, help="only use questions saved under this topic")
    parser.add_argument("--seed", type=int, default=None, help="same seed = same paper; change it for another set")
    parser.add_argument("--out", default="outputs/paper", help="output file name without extension")
    args = parser.parse_args()

    conn = connect()
    bank = get_questions(conn, topic=args.topic)
    if not bank:
        sys.exit("The question bank is empty. Run generate.py first to add questions.")

    paper = build_paper(bank, args.mcq, args.short, seed=args.seed)
    for warning in paper["warnings"]:
        print("Warning:", warning)
    if not paper["mcq"] and not paper["short"]:
        sys.exit("No questions could be selected.")

    settings = dict(title=args.title, subject=args.subject, duration=args.duration)
    export_docx(paper, args.out + ".docx", **settings)
    export_docx(paper, args.out + "_key.docx", include_answers=True, **settings)

    print(f"Paper: {len(paper['mcq'])} MCQs + {len(paper['short'])} short answers = {paper['total_marks']} marks")
    print(f"Saved {args.out}.docx and {args.out}_key.docx")


if __name__ == "__main__":
    main()

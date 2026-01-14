#!/usr/bin/env python3
import argparse
import sys
from pathlib import Path
from router import AIRouter

def main() -> None:
    parser = argparse.ArgumentParser(description="AI Router CLI")
    parser.add_argument("--prompt", required=True, help="Prompt to send")
    parser.add_argument("--tier", choices=["local", "cheap", "expensive", "auto"], default="auto")
    parser.add_argument("--model", help="Override model")
    parser.add_argument("--file", help="File to include as context")
    args = parser.parse_args()

    try:
        prompt = args.prompt
        if args.file:
            path = Path(args.file)
            if not path.exists():
                print(f"Error: File {args.file} not found", file=sys.stderr)
                sys.exit(1)
            prompt = f"Context from {args.file}:\n```\n{path.read_text()}\n```\n\nTask: {args.prompt}"

        router = AIRouter()
        result = router.chat(
            messages=[{"role": "user", "content": prompt}],
            tier=args.tier,
            model_override=args.model
        )

        if result.error:
            print(f"Error: {result.error}", file=sys.stderr)
            sys.exit(1)

        print(result.text)
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

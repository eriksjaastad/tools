import argparse
import sys
import os
from pathlib import Path

# Add parent dir to path if not there
sys.path.append(str(Path(__file__).parent.parent))
from router import AIRouter

def main() -> None:
    parser = argparse.ArgumentParser(description="AI Router CLI")
    parser.add_argument("--prompt", help="Prompt to send")
    parser.add_argument("--tier", choices=["local", "cheap", "expensive", "auto"], default="auto")
    parser.add_argument("--model", help="Override model")
    parser.add_argument("--file", help="File to include as context")
    parser.add_argument("--project", default="cli", help="Project name for tracking")
    parser.add_argument("--unlocked", action="store_true", help="Allow expensive models")
    parser.add_argument("--stats", action="store_true", help="Show performance stats")
    parser.add_argument("--usage", action="store_true", help="Show usage breakdown")
    args = parser.parse_args()

    try:
        router = AIRouter()

        if args.stats:
            print(router.get_performance_summary())
            return
            
        if args.usage:
            print(router.get_project_usage())
            return

        if not args.prompt:
            parser.print_help()
            sys.exit(1)

        prompt = args.prompt
        if args.file:
            path = Path(args.file)
            if not path.exists():
                print(f"Error: File {args.file} not found", file=sys.stderr)
                sys.exit(1)
            prompt = f"Context from {args.file}:\n```\n{path.read_text()}\n```\n\nTask: {args.prompt}"

        result = router.chat(
            messages=[{"role": "user", "content": prompt}],
            tier=args.tier,
            model_override=args.model,
            project=args.project,
            unlocked=args.unlocked
        )

        if result.error:
            print(f"Error ({result.model}): {result.error}", file=sys.stderr)
            sys.exit(1)

        print(result.text)
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Claude CLI - A simple command-line interface for Claude
Note: This requires an Anthropic API key to actually work with Claude
"""

import os
import sys
import argparse
import json
from typing import Optional

def get_api_key() -> Optional[str]:
    """Get API key from environment variable or prompt user."""
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("⚠️  No ANTHROPIC_API_KEY environment variable found.")
        print("To use this CLI tool, you need to:")
        print("1. Get an API key from https://console.anthropic.com/")
        print("2. Set it as an environment variable:")
        print("   export ANTHROPIC_API_KEY='your-key-here'")
        print("   or add it to your ~/.zshrc file")
        return None
    return api_key

def claude_chat(message: str, api_key: str) -> str:
    """Send a message to Claude via API."""
    try:
        import anthropic
        
        client = anthropic.Anthropic(api_key=api_key)
        
        response = client.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=1000,
            messages=[{"role": "user", "content": message}]
        )
        
        return response.content[0].text
        
    except ImportError:
        print("❌ The 'anthropic' package is not installed.")
        print("Install it with: pip3 install anthropic")
        return None
    except Exception as e:
        print(f"❌ Error communicating with Claude: {e}")
        return None

def interactive_mode(api_key: str):
    """Run Claude CLI in interactive mode."""
    print("🤖 Claude CLI - Interactive Mode")
    print("Type 'quit' or 'exit' to end the session")
    print("Type 'help' for available commands")
    print("-" * 50)
    
    while True:
        try:
            user_input = input("\n💬 You: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                print("👋 Goodbye!")
                break
            elif user_input.lower() == 'help':
                print("Available commands:")
                print("  help     - Show this help message")
                print("  quit/exit - End the session")
                print("  clear    - Clear the screen")
                print("  Any other text will be sent to Claude")
            elif user_input.lower() == 'clear':
                os.system('clear')
                continue
            elif not user_input:
                continue
            else:
                print("\n🤖 Claude: ", end="")
                response = claude_chat(user_input, api_key)
                if response:
                    print(response)
                else:
                    print("Sorry, I couldn't get a response from Claude.")
                    
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except EOFError:
            print("\n👋 Goodbye!")
            break

def main():
    parser = argparse.ArgumentParser(description="Claude CLI - Chat with Claude from the terminal")
    parser.add_argument("message", nargs="?", help="Message to send to Claude")
    parser.add_argument("-i", "--interactive", action="store_true", help="Run in interactive mode")
    
    args = parser.parse_args()
    
    # Check for API key
    api_key = get_api_key()
    if not api_key:
        sys.exit(1)
    
    if args.interactive or not args.message:
        interactive_mode(api_key)
    else:
        # Single message mode
        print("🤖 Claude: ", end="")
        response = claude_chat(args.message, api_key)
        if response:
            print(response)
        else:
            sys.exit(1)

if __name__ == "__main__":
    main()


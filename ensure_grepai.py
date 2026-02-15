#!/usr/bin/env python3
import subprocess
import sys
import time

def is_grepai_running():
    try:
        result = subprocess.run(["grepai", "watch", "--status"], capture_output=True, text=True)
        return "Status: running" in result.stdout
    except Exception:
        return False

def start_grepai():
    print("Starting grepai watch daemon...")
    try:
        # Run in background mode as per TODO.md instructions
        subprocess.run(["grepai", "watch", "--background"], check=True)
        # Give it a second to initialize
        time.sleep(1)
        if is_grepai_running():
            print("✅ grepai watch is now running in the background.")
            return True
        else:
            print("❌ Failed to start grepai watch.")
            return False
    except subprocess.CalledProcessError as e:
        print(f"❌ Error starting grepai: {e}")
        return False

def main():
    if is_grepai_running():
        # print("✅ grepai watch is already running.")
        sys.exit(0)
    else:
        if start_grepai():
            sys.exit(0)
        else:
            sys.exit(1)

if __name__ == "__main__":
    main()

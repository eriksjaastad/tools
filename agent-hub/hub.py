import os
import shutil
from swarm import Swarm, Agent
from litellm import completion

# 1. DEFINE TOOLS (The "Hands")
def list_files(directory="."):
    """Lists files in the given directory."""
    try:
        files = os.listdir(directory)
        return "\n".join(files) if files else "Directory is empty."
    except Exception as e:
        return f"Error listing files: {str(e)}"

def read_file(filepath):
    """Reads the content of a file."""
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                return f.read()
        return f"Error: File '{filepath}' not found."
    except Exception as e:
        return f"Error reading file: {str(e)}"

def write_file(filepath, content):
    """Writes content to a file. Creates directories if they don't exist."""
    try:
        os.makedirs(os.path.dirname(os.path.abspath(filepath)), exist_ok=True)
        with open(filepath, 'w') as f:
            f.write(content)
        return f"Successfully wrote to {filepath}"
    except Exception as e:
        return f"Error writing file: {str(e)}"

def move_file(src, dst):
    """Moves a file from src to dst."""
    try:
        shutil.move(src, dst)
        return f"Successfully moved {src} to {dst}"
    except Exception as e:
        return f"Error moving file: {str(e)}"

# 2. DEFINE AGENTS

# The Worker - Local, runs on Ollama
# Instructions: You are a local file assistant. Use your tools to help the Manager.
worker_agent = Agent(
    name="Worker",
    model="ollama/qwen2.5-coder:7b",
    instructions="You are a fast, efficient coding assistant. You read/write files and execute simple tasks immediately. You are running locally on the user's machine.",
    functions=[list_files, read_file, write_file, move_file]
)

# The Manager - Cloud (Or Smart Model)
# Instructions: You are the Hub. You plan and delegate.

def transfer_to_worker():
    """Handoff any file manipulation or local execution tasks to the Worker agent."""
    return worker_agent

manager_agent = Agent(
    name="Manager",
    model="gpt-4o",
    instructions="""You are the Orchestrator (The Hub). 
1. Analyze the user's request.
2. If it requires file manipulation, reading code, or simple execution, hand off the task to the 'Worker' agent.
3. If it requires high-level planning or architecture, handle that yourself.
4. Always summarize what was done for the user.""",
    functions=[transfer_to_worker]
)

# 3. CUSTOM CLIENT FOR SWARM (To route to Ollama)
class LiteLLMClient:
    def __init__(self):
        self.chat = self.Chat()
        
    class Chat:
        def __init__(self):
            self.completions = self.Completions()
            
        class Completions:
            def create(self, **kwargs):
                # If model is ollama, ensure we point to the local instance
                if kwargs.get("model", "").startswith("ollama/"):
                    # Use the user-provided Ollama base URL
                    kwargs["api_base"] = "http://localhost:11434/v1"
                
                # Filter out swarm-specific kwargs that litellm might not like
                # (Swarm usually passes model, messages, tools, tool_choice, etc. which LiteLLM handles)
                return completion(**kwargs)

# 4. THE REPL LOOP
if __name__ == "__main__":
    client = LiteLLMClient()
    swarm_client = Swarm(client=client)

    print("🤖 Agent Hub Foundation Online.")
    print("Manager: gpt-4o | Worker: ollama/qwen2.5-coder:7b")
    print("(Ctrl+C to quit)\n")
    
    messages = []
    
    while True:
        try:
            user_input = input("User: ")
            if not user_input.strip():
                continue
            
            messages.append({"role": "user", "content": user_input})
            
            # Swarm handles the delegation and tool calls automatically
            response = swarm_client.run(
                agent=manager_agent,
                messages=messages,
            )
            
            # Print response and update message history
            last_message = response.messages[-1]
            if last_message.get("content"):
                print(f"\n{response.agent.name}: {last_message['content']}\n")
            
            messages = response.messages
            
        except KeyboardInterrupt:
            print("\n\nShutting down Agent Hub. Goodbye!")
            break
        except Exception as e:
            print(f"\n[ERROR] {str(e)}\n")

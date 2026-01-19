import asyncio
import logging
import sys
from mcp.server import Server
from mcp.server.stdio import stdio_server
import mcp.types as types
from .ssh_ops import run_ssh_command, load_hosts

# Set up logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("ssh-agent-mcp")

# Initialize MCP server
server = Server("ssh-agent")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available SSH tools."""
    return [
        types.Tool(
            name="ssh_execute",
            description="Execute command on a remote host via SSH",
            inputSchema={
                "type": "object",
                "properties": {
                    "host": {
                        "type": "string",
                        "description": "Host alias from ssh_hosts.yaml (e.g., 'runpod')"
                    },
                    "command": {
                        "type": "string",
                        "description": "Shell command to execute"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds",
                        "default": 120
                    }
                },
                "required": ["host", "command"]
            }
        ),
        types.Tool(
            name="ssh_list_hosts",
            description="List configured SSH hosts",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(
    name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool execution requests."""
    try:
        if not arguments:
            arguments = {}

        if name == "ssh_execute":
            host = arguments.get("host")
            command = arguments.get("command")
            timeout = arguments.get("timeout", 120)

            if not host or not command:
                return [types.TextContent(type="text", text="Error: host and command are required.")]

            logger.info(f"Executing command on {host}: {command}")
            # run_ssh_command is blocking, so we run it in a thread
            stdout, stderr, exit_status = await asyncio.to_thread(
                run_ssh_command, host, command, timeout
            )
            
            result_text = f"STDOUT:\n{stdout}\n"
            if stderr:
                result_text += f"STDERR:\n{stderr}\n"
            result_text += f"EXIT STATUS: {exit_status}"
            
            return [types.TextContent(type="text", text=result_text)]

        elif name == "ssh_list_hosts":
            hosts = load_hosts()
            host_info = "\n".join([f"- {h}: {v.get('hostname')}" for h, v in hosts.items()])
            return [types.TextContent(type="text", text=f"Configured Hosts:\n{host_info}")]

        else:
            raise ValueError(f"Unknown tool: {name}")
            
    except Exception as e:
        logger.error(f"Error executing tool {name}: {e}")
        return [types.TextContent(type="text", text=f"Error: {str(e)}")]

async def run():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )

def main():
    asyncio.run(run())

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Message Listener - The new main loop for Agent Hub.
Replaces watcher.sh file polling with MCP message subscription.
"""
import os
import sys
import time
import json
import logging
import threading
from pathlib import Path
from typing import Callable, Dict, List, Optional
from datetime import datetime, timezone

from .mcp_client import MCPClient, MCPError
from .hub_client import HubClient
from .proposal_converter import convert_proposal
from .watchdog import load_contract, save_contract, transition, log_transition, HUB_SERVER_PATH

# Configure logging to console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MessageListener")

class MessageListener:
    def __init__(self, agent_id: str, hub_path: Path):
        self.agent_id = agent_id
        self.hub_path = hub_path
        self.running = False
        self.handlers = {}  # message_type -> handler function
        self.last_check_timestamp = None
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def register_handler(self, msg_type: str, handler: Callable):
        """Register a handler for a specific message type."""
        self.handlers[msg_type] = handler
        logger.info(f"Registered handler for {msg_type}")

    def start(self):
        """
        Main loop:
        1. Connect to hub
        2. Emit heartbeat every 30 seconds
        3. Check for messages every 5 seconds
        4. Dispatch to registered handlers
        """
        logger.info(f"Starting MessageListener for {self.agent_id}...")
        
        try:
            with MCPClient(self.hub_path) as mcp:
                hub = HubClient(mcp)
                if not hub.connect(self.agent_id):
                    logger.error(f"Failed to connect to hub at {self.hub_path}")
                    sys.exit(1)
                
                logger.info("Connected to MCP Hub")
                self.running = True
                
                # Start heartbeat thread
                self._stop_event.clear()
                self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, args=(hub,), daemon=True)
                self._heartbeat_thread.start()
                
                while self.running:
                    try:
                        messages = hub.receive_messages(since=self.last_check_timestamp)
                        for msg in messages:
                            self._dispatch(msg)
                            self.last_check_timestamp = msg.get("timestamp")
                    except Exception as e:
                        logger.error(f"Error receiving messages: {e}")
                    
                    time.sleep(5) # Check every 5 seconds
                    
        except MCPError as e:
            logger.error(f"MCP Hub not reachable: {e}")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Unexpected error in listener loop: {e}")
            sys.exit(1)

    def _heartbeat_loop(self, hub: HubClient):
        """Emits heartbeat every 30 seconds."""
        while not self._stop_event.is_set():
            try:
                hub.emit_heartbeat("listening")
                logger.debug("Heartbeat emitted")
            except Exception as e:
                logger.warning(f"Failed to emit heartbeat: {e}")
            
            # Wait 30s but check stop_event frequently
            for _ in range(30):
                if self._stop_event.is_set():
                    break
                time.sleep(1)

    def _dispatch(self, message: dict):
        """Dispatches message to the correct handler and logs it."""
        msg_type = message.get("type")
        logger.info(f"Received message: {msg_type} from {message.get('from')}")
        
        # Log to transition.ndjson
        self._log_to_ndjson(message)
        
        handler = self.handlers.get(msg_type)
        if handler:
            try:
                handler(message)
            except Exception as e:
                logger.error(f"Error in handler for {msg_type}: {e}")
        else:
            logger.warning(f"No handler registered for message type: {msg_type}")

    def _log_to_ndjson(self, message: dict):
        """Logs message to transition.ndjson for audit trail."""
        log_dir = Path("_handoff")
        if not log_dir.exists():
            log_dir.mkdir(parents=True, exist_ok=True)
            
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_id": self.agent_id,
            "event": "message_received",
            "message_id": message.get("id"),
            "message_type": message.get("type"),
            "from": message.get("from"),
            "payload": message.get("payload")
        }
        
        log_file = log_dir / "transition.ndjson"
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to log message to ndjson: {e}")

    def stop(self):
        """Graceful shutdown."""
        logger.info("Stopping MessageListener...")
        self.running = False
        self._stop_event.set()
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=5)
        logger.info("MessageListener stopped.")

    def handle_proposal_ready(self, message: dict):
        """
        Handler for PROPOSAL_READY:
        1. Read proposal from message['payload']['proposal_path']
        2. Convert to contract
        3. Start implementation pipeline
        """
        payload = message.get("payload", {})
        proposal_path = Path(payload.get("proposal_path", ""))
        handoff_dir = Path("_handoff")
        
        if not proposal_path.exists():
            logger.error(f"Proposal file not found: {proposal_path}")
            return
            
        logger.info(f"Processing proposal: {proposal_path}")
        contract_path = convert_proposal(proposal_path, handoff_dir)
        
        if contract_path:
            logger.info(f"Proposal converted to contract: {contract_path}")
            # Starting implementation pipeline: usually involves setup-task then run-implementer
            # Here we might just signal that we're ready or trigger the next step.
            # In Phase 8, we likely want to automate the transition.
            # For now, we'll log it. 
        else:
            logger.error(f"Failed to convert proposal: {proposal_path}")

    def handle_stop_task(self, message: dict):
        """
        Handler for STOP_TASK:
        1. Log the stop request
        2. Halt current operation
        3. Clean up resources
        """
        payload = message.get("payload", {})
        reason = payload.get("reason", "No reason provided")
        logger.warning(f"STOP_TASK received: {reason}")
        # In a real system, we'd need to find the running task and kill it.
        # For now, we'll just log and potentially stop the listener if it's task-specific?
        # Usually STOP_TASK would target a specific task implementation process.

    def handle_question(self, message: dict):
        """
        Handler for QUESTION from Super Manager:
        1. Present options to Floor Manager logic
        2. Select best option (or escalate to Erik)
        3. Send ANSWER back
        """
        payload = message.get("payload", {})
        question = payload.get("question")
        options = payload.get("options", [])
        question_id = message.get("id")
        
        logger.info(f"QUESTION received: {question}")
        logger.info(f"Options: {options}")
        
        # Floor Manager logic to select best option
        # For now, we'll simulate a selection (option 0) or escalate.
        # In a real system, this might invoke a brain like Gemini.
        selected_index = 0 
        
        try:
            with MCPClient(self.hub_path) as mcp:
                hub = HubClient(mcp)
                hub.connect(self.agent_id)
                hub.send_answer(question_id, selected_index)
                logger.info(f"Sent ANSWER for {question_id}: option {selected_index}")
        except Exception as e:
            logger.error(f"Failed to send answer: {e}")

def main():
    listener = MessageListener("floor_manager", HUB_SERVER_PATH)

    # Register handlers
    listener.register_handler("PROPOSAL_READY", listener.handle_proposal_ready)
    listener.register_handler("STOP_TASK", listener.handle_stop_task)
    listener.register_handler("QUESTION", listener.handle_question)

    # Run until interrupted
    try:
        listener.start()
    except KeyboardInterrupt:
        listener.stop()

if __name__ == "__main__":
    main()

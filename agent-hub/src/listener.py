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
from .watchdog import load_contract, save_contract, transition, log_transition
from .draft_gate import handle_draft_submission, apply_draft, reject_draft, GateDecision
from .config import get_config

# Configure logging to console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MessageListener")

class MessageListener:
    def __init__(self, agent_id: str, hub_path: Path, handoff_dir: Path = Path("_handoff")):
        self.agent_id = agent_id
        self.hub_path = hub_path
        self.handoff_dir = handoff_dir
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
        log_dir = self.handoff_dir
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

    def _send_message(self, to_agent: str, msg_type: str, payload: dict):
        """Helper to send a message via the hub."""
        try:
            with MCPClient(self.hub_path) as mcp:
                hub = HubClient(mcp)
                hub.connect(self.agent_id)
                hub.send_message(to_agent, msg_type, payload)
        except Exception as e:
            logger.error(f"Failed to send message {msg_type} to {to_agent}: {e}")

    def _log_transition(self, event: str, task_id: str):
        """Helper to log an event to ndjson."""
        # We can either use watchdog.log_transition if we have a contract,
        # or just log a simple event to ndjson. 
        # For draft events, we just log the received message which is already done by _dispatch.
        # But we'll add an explicit log entry for the decision.
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_id": self.agent_id,
            "event": event,
            "task_id": task_id
        }
        log_file = self.handoff_dir / "transition.ndjson"
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to log transition {event}: {e}")

    def handle_draft_ready(self, message: dict) -> None:
        """
        Handle DRAFT_READY message from a worker.

        Args:
            message: The MCP message with draft submission info
        """
        payload = message.get("payload", {})
        task_id = payload.get("task_id")

        if not task_id:
            logger.error("DRAFT_READY missing task_id")
            return

        logger.info(f"Processing DRAFT_READY for task: {task_id}")

        # Run the gate
        result = handle_draft_submission(task_id)

        if result.decision == GateDecision.ACCEPT:
            logger.info(f"Draft ACCEPTED: {result.diff_summary}")
            if apply_draft(task_id):
                self._log_transition("draft_accepted", task_id)
                # Notify worker of success
                self._send_message(
                    message.get("from", "worker"),
                    "DRAFT_ACCEPTED",
                    {"task_id": task_id, "summary": result.diff_summary}
                )
            else:
                logger.error("Failed to apply accepted draft")
                self._log_transition("draft_apply_failed", task_id)

        elif result.decision == GateDecision.REJECT:
            logger.warning(f"Draft REJECTED: {result.reason}")
            reject_draft(task_id, result.reason)
            self._log_transition("draft_rejected", task_id)
            # Notify worker of rejection
            self._send_message(
                message.get("from", "worker"),
                "DRAFT_REJECTED",
                {"task_id": task_id, "reason": result.reason}
            )

        elif result.decision == GateDecision.ESCALATE:
            logger.warning(f"Draft ESCALATED: {result.reason}")
            self._log_transition("draft_escalated", task_id)
            # Notify Erik
            self._send_message(
                "super_manager",
                "DRAFT_ESCALATED",
                {
                    "task_id": task_id,
                    "reason": result.reason,
                    "diff_summary": result.diff_summary
                }
            )

    def handle_proposal_ready(self, message: dict):
        """
        Handler for PROPOSAL_READY:
        1. Read proposal from message['payload']['proposal_path']
        2. Convert to contract
        3. Start implementation pipeline
        """
        payload = message.get("payload", {})
        proposal_path = Path(payload.get("proposal_path", ""))
        handoff_dir = self.handoff_dir
        
        if not proposal_path.exists():
            logger.error(f"Proposal file not found: {proposal_path}")
            return
            
        logger.info(f"Processing proposal: {proposal_path}")
        contract_path = convert_proposal(proposal_path, handoff_dir)
        
        if contract_path:
            logger.info(f"Proposal converted to contract: {contract_path}")
            # Start the pipeline in a background thread
            pipeline_thread = threading.Thread(
                target=self._run_pipeline,
                args=(contract_path,),
                daemon=True
            )
            pipeline_thread.start()
        else:
            logger.error(f"Failed to convert proposal: {proposal_path}")

    def _run_pipeline(self, contract_path: Path):
        """Runs the full watchdog pipeline for a contract."""
        import subprocess
        
        commands = [
            ["python", "-m", "src.watchdog", "setup-task", "--contract", str(contract_path)],
            ["python", "-m", "src.watchdog", "run-implementer", "--contract", str(contract_path)],
            ["python", "-m", "src.watchdog", "run-local-review", "--contract", str(contract_path)],
            ["python", "-m", "src.watchdog", "report-judge", "--contract", str(contract_path)],
            ["python", "-m", "src.watchdog", "finalize-task", "--contract", str(contract_path)]
        ]

        logger.info(f"Starting pipeline for {contract_path.name}")
        
        for cmd in commands:
            logger.info(f"Executing: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            
            if result.returncode != 0:
                logger.error(f"Command failed: {' '.join(cmd)}")
                logger.error(f"Error: {result.stderr}")
                break
            
            logger.info(f"Command succeeded: {cmd[3]}")
            
        logger.info(f"Pipeline finished for {contract_path.name}")

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
    config = get_config()
    listener = MessageListener(config.agent_id, config.hub_path, config.handoff_dir)

    # Register handlers
    listener.register_handler("PROPOSAL_READY", listener.handle_proposal_ready)
    listener.register_handler("DRAFT_READY", listener.handle_draft_ready)
    listener.register_handler("STOP_TASK", listener.handle_stop_task)
    listener.register_handler("QUESTION", listener.handle_question)

    # Run until interrupted
    try:
        listener.start()
    except KeyboardInterrupt:
        listener.stop()

if __name__ == "__main__":
    main()

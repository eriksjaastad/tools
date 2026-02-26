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
import subprocess
from pathlib import Path
from typing import Callable, Dict, List, Optional
from datetime import datetime, timezone
from dataclasses import dataclass

from .mcp_client import MCPClient, MCPError
from .hub_client import HubClient
from .proposal_converter import convert_proposal
from .watchdog import load_contract, save_contract, transition, log_transition
from .draft_gate import handle_draft_submission, apply_draft, reject_draft, GateDecision
from .config import get_config
from . import adaptive_poller
from .utils import feature_flags, atomic_write

# Configure logging to console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("MessageListener")

@dataclass
class PipelineContext:
    task_id: str
    contract_path: Path
    thread: Optional[threading.Thread] = None
    process: Optional[subprocess.Popen] = None
    cancelled: bool = False
    cancel_reason: str = ""
    cancellation_recorded: bool = False

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
        self.poller = adaptive_poller.create_poller(adaptive=feature_flags.use_adaptive_polling())
        self._active_pipelines: Dict[str, PipelineContext] = {}
        self._pipeline_lock = threading.Lock()

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
                    had_activity = False
                    try:
                        messages = hub.receive_messages(since=self.last_check_timestamp)
                        if messages:
                            had_activity = True
                            for msg in messages:
                                self._dispatch(msg)
                                self.last_check_timestamp = msg.get("timestamp")
                    except Exception as e:
                        logger.error(f"Error receiving messages: {e}")
                    
                    self.poller.wait(had_activity)
                    
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
        self.handoff_dir.mkdir(parents=True, exist_ok=True)
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
            task_id = self._extract_task_id(contract_path)
            context = PipelineContext(task_id=task_id, contract_path=contract_path)
            with self._pipeline_lock:
                existing = self._active_pipelines.get(task_id)
                if existing and existing.thread and existing.thread.is_alive():
                    logger.warning(f"Pipeline already active for task {task_id}; ignoring duplicate PROPOSAL_READY.")
                    return
                self._active_pipelines[task_id] = context
            # Start the pipeline in a background thread
            pipeline_thread = threading.Thread(
                target=self._run_pipeline,
                args=(context,),
                daemon=True
            )
            context.thread = pipeline_thread
            pipeline_thread.start()
        else:
            logger.error(f"Failed to convert proposal: {proposal_path}")

    def _extract_task_id(self, contract_path: Path) -> str:
        """Best-effort task_id extraction for pipeline tracking."""
        try:
            contract = load_contract(contract_path)
            task_id = contract.get("task_id")
            if task_id:
                return str(task_id)
        except Exception as e:
            logger.warning(f"Failed to read task_id from {contract_path}: {e}")
        return contract_path.stem

    def _record_stop_cancellation(self, context: PipelineContext):
        """Record STOP_TASK cancellation once per pipeline."""
        with self._pipeline_lock:
            if context.cancellation_recorded:
                return
            context.cancellation_recorded = True
            reason = context.cancel_reason or "STOP_TASK requested"

        self._mark_contract_cancelled(context.contract_path, reason)
        self._log_transition("stop_task_cancelled", context.task_id)

    def _run_pipeline(self, context: PipelineContext):
        """Runs the full watchdog pipeline for a contract."""
        contract_path = context.contract_path
        
        commands = [
            ["uv", "run", "python", "-m", "src.watchdog", "setup-task", "--contract", str(contract_path)],
            ["uv", "run", "python", "-m", "src.watchdog", "run-implementer", "--contract", str(contract_path)],
            ["uv", "run", "python", "-m", "src.watchdog", "run-local-review", "--contract", str(contract_path)],
            ["uv", "run", "python", "-m", "src.watchdog", "report-judge", "--contract", str(contract_path)],
            ["uv", "run", "python", "-m", "src.watchdog", "finalize-task", "--contract", str(contract_path)]
        ]

        logger.info(f"Starting pipeline for {contract_path.name} ({context.task_id})")
        try:
            for cmd in commands:
                with self._pipeline_lock:
                    if context.cancelled:
                        logger.warning(f"Pipeline cancelled before command start: {context.task_id}")
                        break

                if "--contract" in cmd:
                    command_name = cmd[cmd.index("--contract") - 1]
                else:
                    command_name = cmd[-1]
                logger.info(f"Executing: {' '.join(cmd)}")
                process = None
                try:
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )
                    with self._pipeline_lock:
                        context.process = process

                    stdout, stderr = process.communicate(timeout=600)

                    with self._pipeline_lock:
                        was_cancelled = context.cancelled

                    if was_cancelled:
                        logger.warning(f"Command interrupted by STOP_TASK: {command_name}")
                        break

                    if process.returncode != 0:
                        logger.error(f"Command failed: {' '.join(cmd)}")
                        logger.error(f"Error output: {stderr}")
                        self._mark_contract_failed(
                            contract_path,
                            f"Pipeline step failed: {command_name}",
                            stderr or stdout or f"Exit code {process.returncode}"
                        )
                        break

                    logger.info(f"Command succeeded: {command_name}")
                except subprocess.TimeoutExpired:
                    logger.error(f"Command timed out: {' '.join(cmd)}")
                    if process:
                        process.kill()
                        _, stderr = process.communicate()
                    else:
                        stderr = "No process handle available"
                    self._mark_contract_failed(
                        contract_path,
                        f"Pipeline step timed out: {command_name}",
                        stderr or "Timeout after 600s"
                    )
                    break
                except Exception as e:
                    logger.error(f"Unexpected pipeline command failure: {e}")
                    self._mark_contract_failed(
                        contract_path,
                        f"Pipeline step failed: {command_name}",
                        str(e)
                    )
                    break
                finally:
                    with self._pipeline_lock:
                        if context.process is process:
                            context.process = None

            with self._pipeline_lock:
                cancelled = context.cancelled
            if cancelled:
                self._record_stop_cancellation(context)
        finally:
            with self._pipeline_lock:
                current = self._active_pipelines.get(context.task_id)
                if current is context:
                    self._active_pipelines.pop(context.task_id, None)
            logger.info(f"Pipeline finished for {contract_path.name} ({context.task_id})")

    def _mark_contract_failed(self, contract_path: Path, reason: str, details: str):
        """Mark a contract as failed and log the reason.

        Writes the canonical contract status field and preserves
        failure_reason/failure_details. Uses atomic write.
        """
        try:
            if contract_path.exists():
                contract = json.loads(contract_path.read_text())
                # Use canonical status field (not deprecated 'state')
                # Choose a valid status to represent failure escalation.
                contract["status"] = "erik_consultation"
                contract["failure_reason"] = reason
                contract["failure_details"] = details
                atomic_write(contract_path, json.dumps(contract, indent=2))
                logger.warning(f"Contract marked as failed: {reason}")
        except Exception as e:
            logger.error(f"Failed to update contract state: {e}")

    def _mark_contract_cancelled(self, contract_path: Path, reason: str):
        """Mark a contract as cancelled via STOP_TASK."""
        try:
            if contract_path.exists():
                contract = json.loads(contract_path.read_text())
                contract["status"] = "erik_consultation"
                contract["status_reason"] = f"STOP_TASK cancellation: {reason}"
                contract["failure_reason"] = "STOP_TASK cancellation"
                contract["failure_details"] = reason
                atomic_write(contract_path, json.dumps(contract, indent=2))
                logger.warning(f"Contract marked as cancelled: {reason}")
        except Exception as e:
            logger.error(f"Failed to mark contract cancelled: {e}")

    def handle_stop_task(self, message: dict):
        """
        Handler for STOP_TASK:
        1. Log the stop request
        2. Halt current operation
        3. Clean up resources
        """
        payload = message.get("payload", {})
        reason = payload.get("reason", "No reason provided")
        target_task_id = payload.get("task_id")
        target_contract_path = payload.get("contract_path")
        broadcast = bool(payload.get("broadcast")) or bool(payload.get("all_tasks"))
        if not target_task_id and not target_contract_path:
            broadcast = True

        logger.warning(
            f"STOP_TASK received: reason={reason}; task_id={target_task_id}; contract_path={target_contract_path}; "
            f"broadcast={broadcast}"
        )

        contract_match_path = str(Path(target_contract_path).resolve()) if target_contract_path else None
        with self._pipeline_lock:
            contexts = list(self._active_pipelines.values())
            matched_contexts: List[PipelineContext] = []
            targets: List[PipelineContext] = []
            for context in contexts:
                context_path = str(context.contract_path.resolve())
                if broadcast:
                    matches = True
                else:
                    matches = False
                    if target_task_id and context.task_id == target_task_id:
                        matches = True
                    if contract_match_path and context_path == contract_match_path:
                        matches = True

                if not matches:
                    continue
                matched_contexts.append(context)

                if context.cancelled:
                    continue

                context.cancelled = True
                if not context.cancel_reason:
                    context.cancel_reason = reason
                targets.append(context)

        if not matched_contexts:
            logger.info("STOP_TASK matched no active pipeline.")
            self._log_transition("stop_task_no_active_pipeline", target_task_id or "broadcast")
            return
        if not targets:
            logger.info("STOP_TASK matched pipelines already marked cancelled; no new action required.")
            return

        for context in targets:
            process = None
            with self._pipeline_lock:
                process = context.process

            if process and process.poll() is None:
                try:
                    process.terminate()
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    logger.warning(f"STOP_TASK force-killing process for {context.task_id}")
                    process.kill()
                    process.wait(timeout=2)
                except Exception as e:
                    logger.error(f"Failed to terminate process for {context.task_id}: {e}")

            self._record_stop_cancellation(context)

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

"""
UAS Hub - Main entry point and component orchestrator.
"""

import logging
from pathlib import Path
from typing import Optional

from .environment import get_adapter, detect_environment
from .cost_logger import CostLogger
from .message_bus import MessageBus
from .router import Router
from .budget_manager import BudgetManager
from .bidirectional import BidirectionalMessenger
from .adaptive_poller import create_poller
from .preflight import PreFlightChecker

logger = logging.getLogger("UAS.Hub")

class Hub:
    """
    Unified Agent System Hub.
    Integrates all UAS components.
    """

    def __init__(self, agent_id: str = "hub-agent", data_dir: str = "data"):
        self.agent_id = agent_id
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. Detect environment
        self.adapter = get_adapter()
        self.env = detect_environment()
        logger.info(f"Detected environment: {self.env.value}")

        # 2. Initialize CostLogger
        self.cost_logger = CostLogger(
            log_file=self.data_dir / "audit.ndjson",
            persist_file=self.data_dir / "budget_state.json"
        )

        # 3. Initialize MessageBus
        self.message_bus = MessageBus(db_path=self.data_dir / "hub.db")

        # 4. Initialize Router
        # Using default config path 'config/routing.yaml'
        self.router = Router()

        # 5. Initialize BudgetManager
        self.budget_manager = BudgetManager(self.cost_logger)

        # 6. Initialize BidirectionalMessenger
        self.messenger = BidirectionalMessenger(self.message_bus)

        # 7. Initialize PreFlightChecker
        self.preflight = PreFlightChecker(self.budget_manager, self.router)

        # 8. Initialize AdaptivePoller
        # In a real run, we'd use feature flags for 'adaptive'
        self.poller = create_poller(adaptive=True)

    def start(self):
        """
        Starts the UAS hub activity loop.
        """
        logger.info(f"UAS Hub {self.agent_id} started.")
        # Actual message loop would be here, similar to listener.py
        # But for this prompt, we are just wiring them together.

    def dry_run(self):
        """
        Verify all components are initialized.
        """
        status = self.budget_manager.get_status()
        logger.info("Dry run successful.")
        logger.info(f"Budget Status: {status}")
        return True

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    hub = Hub()
    hub.dry_run()

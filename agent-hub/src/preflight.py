"""
Pre-Flight Checks - Budget and capability verification before execution.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from pathlib import Path
from .budget_manager import BudgetManager
from .router import Router

logger = logging.getLogger(__name__)

class PreFlightResult:
    def __init__(self, approved: bool, model: str, estimated_cost: float, warnings: List[str], halt_reason: str = ""):
        self.approved = approved
        self.model = model
        self.estimated_cost = estimated_cost
        self.warnings = warnings
        self.halt_reason = halt_reason

class PreFlightChecker:
    """
    FR-4.2: Ensure execution is within budget and models are available.
    """

    def __init__(self, budget_manager: BudgetManager, router: Router):
        self.budget = budget_manager
        self.router = router

    def check(self, task_type: str, complexity: str, estimated_tokens: int, allow_override: bool = False) -> PreFlightResult:
        """
        Sequence: Route -> Estimate -> Check Budget.
        """
        # 1. Route to get model selection
        selection = self.router.route(task_type, complexity, estimated_tokens)
        model = selection.model
        
        # 2. Estimate cost
        # input_tokens = estimated_tokens, estimated_output_tokens = 500 (default)
        estimated_cost = self.budget.estimate_cost(model, estimated_tokens, 500)
        
        # 3. Check budget
        budget_check = self.budget.can_afford(estimated_cost)
        
        approved = budget_check["allowed"]
        halt_reason = ""
        warnings = []
        
        if not approved:
            if allow_override:
                warnings.append(f"Budget exceeded but override allowed: {budget_check['reason']}")
                approved = True
            else:
                halt_reason = budget_check["reason"]
                self._create_halt_file(task_type, complexity, estimated_cost, budget_check["remaining_budget"], halt_reason)

        return PreFlightResult(
            approved=approved,
            model=model,
            estimated_cost=estimated_cost,
            warnings=warnings,
            halt_reason=halt_reason
        )

    def _create_halt_file(self, task: str, complexity: str, cost: float, remaining: float, context: str):
        halt_path = Path("ERIK_HALT.md")
        timestamp = datetime.now(timezone.utc).isoformat()
        
        content = f"""# Agent Halt: Budget Exceeded

**Time:** {timestamp}
**Task:** {task} ({complexity})
**Estimated Cost:** ${cost:.4f}
**Session Remaining:** ${remaining:.4f}

## Context
{context}

## Options
1. Override and continue: `hub override {cost}`
2. Reduce scope
3. Wait for daily reset
"""
        with open(halt_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.error(f"Execution HALTED. Details in {halt_path}")

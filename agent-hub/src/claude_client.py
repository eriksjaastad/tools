from typing import List, Dict, Any
from .mcp_client import MCPClient

class ClaudeClient:
    def __init__(self, mcp_client: MCPClient):
        self.mcp = mcp_client

    def judge_review(self, contract_path: str, working_dir: str) -> dict:
        """
        Request architectural review from Claude.
        Returns: {success, verdict, report_path, blocking_issues}
        """
        return self.mcp.call_tool("claude_judge_review", {
            "contract_path": contract_path,
            "working_dir": working_dir
        })

    def validate_proposal(self, proposal_path: str) -> dict:
        """
        Check if proposal is complete before conversion.
        Returns: {valid, issues}
        """
        return self.mcp.call_tool("claude_validate_proposal", {
            "proposal_path": proposal_path
        })

    def security_audit(self, files: List[str], working_dir: str) -> dict:
        """
        Deep security review of specific files.
        Returns: {findings: [{severity, file, line, description, recommendation}]}
        """
        return self.mcp.call_tool("claude_security_audit", {
            "files": files,
            "working_dir": working_dir
        })

    def resolve_conflict(self, contract_path: str, rebuttal_path: str,
                         judge_report_path: str) -> dict:
        """
        Decide who's right when Floor Manager and Judge disagree.
        Returns: {side: 'floor_manager'|'judge', reasoning, recommendation}
        """
        return self.mcp.call_tool("claude_resolve_conflict", {
            "contract_path": contract_path,
            "rebuttal_path": rebuttal_path,
            "judge_report_path": judge_report_path
        })

    def health_check(self) -> bool:
        """Verify claude-mcp is responsive."""
        try:
            result = self.mcp.call_tool("claude_health", {})
            return result.get("available", False)
        except Exception:
            return False

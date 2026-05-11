"""
Sentinel MCP Server

Exposes Sentinel's multi-agent PR review as MCP tools so any MCP client
(Claude Desktop, Cursor, etc.) can trigger and approve reviews directly.

Run:
    python mcp_server.py

Configure in Claude Desktop (~/.claude/claude_desktop_config.json):
    {
      "mcpServers": {
        "sentinel": {
          "command": "python",
          "args": ["/path/to/Sentinel/mcp_server.py"],
          "env": { ...same env vars as .env... }
        }
      }
    }
"""

import uuid

from mcp.server.fastmcp import FastMCP

from graph.workflow import graph
from tools.github_tool import (
    get_file_content,
    get_installation_token,
    get_pr_diff,
    get_pr_files,
    get_pr_head_sha,
)

mcp = FastMCP("sentinel")


@mcp.tool()
def review_pr(repo: str, pr_number: int) -> dict:
    """Run Sentinel multi-agent review (security, docs, performance) on a GitHub PR.

    Args:
        repo: GitHub repo in owner/name format, e.g. "acme/api"
        pr_number: Pull request number

    Returns run_id and the supervisor's ranked markdown review.
    Call approve_review(run_id) to post the comment to GitHub.
    """
    token = get_installation_token()
    diff = get_pr_diff(repo, pr_number, token)
    files_changed = get_pr_files(repo, pr_number, token)
    head_sha = get_pr_head_sha(repo, pr_number, token)

    files_content = {}
    for path in files_changed:
        content = get_file_content(repo, path, head_sha, token)
        if content:
            files_content[path] = content

    run_id = str(uuid.uuid4())
    state = {
        "pr_number": pr_number,
        "repo": repo,
        "diff": diff,
        "files_changed": files_changed,
        "files_content": files_content,
        "security_findings": [],
        "docs_findings": [],
        "performance_findings": [],
        "supervisor_summary": "",
        "human_approved": False,
        "run_id": run_id,
    }

    cfg = {"configurable": {"thread_id": run_id}}
    result = graph.invoke(state, config=cfg)

    return {
        "run_id": run_id,
        "review": result.get("supervisor_summary", "No findings."),
    }


@mcp.tool()
def approve_review(run_id: str) -> dict:
    """Post a Sentinel review comment to GitHub.

    Args:
        run_id: The run_id returned by review_pr

    Must be called after review_pr. Posts the ranked review as a PR comment.
    """
    cfg = {"configurable": {"thread_id": run_id}}
    graph.invoke(None, config=cfg)
    return {"status": "posted", "run_id": run_id}


if __name__ == "__main__":
    mcp.run()

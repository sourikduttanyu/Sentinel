import hashlib
import hmac
import json
import uuid

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request

from config import GITHUB_WEBHOOK_SECRET
from graph.workflow import graph
from tools.github_tool import get_file_content, get_installation_token, get_pr_diff, get_pr_files

router = APIRouter()


def verify_signature(payload: bytes, signature: str) -> bool:
    expected = hmac.new(
        GITHUB_WEBHOOK_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)


def run_graph(state: dict) -> None:
    run_id = state["run_id"]
    config = {"configurable": {"thread_id": run_id}}
    try:
        graph.invoke(state, config=config)
    except Exception as e:
        print(f"[Graph] stopped at interrupt or error: {e}")


@router.post("/webhook")
async def webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: str = Header(None),
    x_github_event: str = Header(None),
):
    payload = await request.body()

    if not x_hub_signature_256 or not verify_signature(payload, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature")

    if x_github_event != "pull_request":
        return {"status": "ignored", "event": x_github_event}

    data = json.loads(payload)
    action = data.get("action")

    if action not in ("opened", "synchronize", "reopened"):
        return {"status": "ignored", "action": action}

    repo = data["repository"]["full_name"]
    pr_number = data["pull_request"]["number"]
    head_sha = data["pull_request"]["head"]["sha"]

    print(f"\n[Webhook] PR #{pr_number} {action} on {repo}")

    token = get_installation_token()
    diff = get_pr_diff(repo, pr_number, token)
    files_changed = get_pr_files(repo, pr_number, token)

    files_content = {}
    for path in files_changed:
        content = get_file_content(repo, path, head_sha, token)
        if content:
            files_content[path] = content

    print(f"[Webhook] Files changed: {files_changed}")
    print(f"[Webhook] Diff length: {len(diff)} chars")

    run_id = str(uuid.uuid4())
    state = {
        "pr_number": pr_number,
        "repo": repo,
        "diff": diff,
        "files_changed": files_changed,
        "files_content": files_content,
        "security_findings": [],
        "docs_findings": [],
        "supervisor_summary": "",
        "human_approved": False,
        "run_id": run_id,
    }

    print(f"[Webhook] Starting graph run: {run_id}")
    background_tasks.add_task(run_graph, state)

    return {"status": "processing", "pr": pr_number, "repo": repo, "run_id": run_id}


@router.post("/approve/{run_id}")
async def approve(run_id: str):
    config = {"configurable": {"thread_id": run_id}}
    try:
        result = graph.invoke(None, config=config)
        return {"status": "approved", "run_id": run_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

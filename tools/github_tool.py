import time
import jwt
import httpx
from config import (
    GITHUB_APP_ID,
    GITHUB_APP_PRIVATE_KEY_PATH,
    GITHUB_INSTALLATION_ID,
)


def _load_private_key() -> str:
    with open(GITHUB_APP_PRIVATE_KEY_PATH, "r") as f:
        return f.read()


def get_installation_token() -> str:
    private_key = _load_private_key()
    now = int(time.time())
    payload = {"iat": now - 60, "exp": now + 600, "iss": GITHUB_APP_ID}
    encoded_jwt = jwt.encode(payload, private_key, algorithm="RS256")

    resp = httpx.post(
        f"https://api.github.com/app/installations/{GITHUB_INSTALLATION_ID}/access_tokens",
        headers={
            "Authorization": f"Bearer {encoded_jwt}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    resp.raise_for_status()
    return resp.json()["token"]


def get_pr_diff(repo: str, pr_number: int, token: str) -> str:
    resp = httpx.get(
        f"https://api.github.com/repos/{repo}/pulls/{pr_number}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3.diff",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    resp.raise_for_status()
    return resp.text


def get_pr_files(repo: str, pr_number: int, token: str) -> list[str]:
    resp = httpx.get(
        f"https://api.github.com/repos/{repo}/pulls/{pr_number}/files",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    resp.raise_for_status()
    return [f["filename"] for f in resp.json()]


def get_file_content(repo: str, path: str, ref: str, token: str) -> str | None:
    import base64
    resp = httpx.get(
        f"https://api.github.com/repos/{repo}/contents/{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        params={"ref": ref},
    )
    if resp.status_code != 200:
        return None
    data = resp.json()
    if data.get("encoding") != "base64":
        return None
    return base64.b64decode(data["content"]).decode("utf-8", errors="replace")


def post_review_comment(repo: str, pr_number: int, body: str, token: str) -> None:
    resp = httpx.post(
        f"https://api.github.com/repos/{repo}/pulls/{pr_number}/reviews",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        json={"body": body, "event": "COMMENT"},
    )
    resp.raise_for_status()

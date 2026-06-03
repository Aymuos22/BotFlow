#!/usr/bin/env python3
"""
scripts/ec2_setup.py
--------------------
Full first-time EC2 deploy + Caddy nip.io HTTPS setup.

Steps:
  1. Install Docker on the server (via ec2-bootstrap.sh)
  2. Pack & upload the project (tar over SSH, no GitHub credentials needed)
  3. Copy .env to the deploy directory
  4. Build the Docker image and start the stack (deploy-remote.sh)
  5. Run Alembic migrations
  6. Install Caddy with nip.io HTTPS
  7. Print the final Twilio webhook URL

Usage:
    python scripts/ec2_setup.py [--caddy-only] [--deploy-only]

Options:
    --caddy-only    Skip steps 1-5; just install/reload Caddy (already deployed).
    --deploy-only   Skip Caddy setup (steps 1-5 only).
"""
import argparse
import io
import os
import subprocess
import sys
import tarfile
import time
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
EC2_IP      = "54.252.233.98"
SSH_USER    = "ubuntu"
KEY_FILE    = Path(__file__).parent.parent / "secrets" / "sec-key.pem"
PROJECT_DIR = Path(__file__).parent.parent.resolve()
DEPLOY_PATH = "/opt/chatbot-engine"

# Files/dirs to exclude from the tarball upload
EXCLUDE = {
    ".git", "__pycache__", ".pytest_cache", ".mypy_cache",
    "*.pyc", "*.pyo", ".env",           # .env is copied separately
    "secrets",                           # never upload keys
    "node_modules", ".venv", "venv",
}

SSH_OPTS = [
    "-o", "StrictHostKeyChecking=accept-new",
    "-o", "ConnectTimeout=15",
    "-i", str(KEY_FILE),
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def log(msg: str) -> None:
    print(f"[setup] {msg}", flush=True)


def ssh(cmd: str, *, sudo: bool = False, check: bool = True) -> subprocess.CompletedProcess:
    if sudo:
        cmd = f"sudo {cmd}"
    full = ["ssh"] + SSH_OPTS + [f"{SSH_USER}@{EC2_IP}", cmd]
    log(f"ssh> {cmd[:100]}")
    return subprocess.run(full, text=True, check=check)


def ssh_out(cmd: str) -> str:
    """Run SSH command and return stdout."""
    full = ["ssh"] + SSH_OPTS + [f"{SSH_USER}@{EC2_IP}", cmd]
    r = subprocess.run(full, capture_output=True, text=True)
    return r.stdout.strip()


def scp_to(local: Path, remote: str, *, strip_cr: bool = False) -> None:
    """SCP a file to the remote server. strip_cr=True converts CRLF to LF first."""
    if strip_cr and local.suffix in (".sh", ".py", ".txt", ""):
        # Write a temp copy with Unix line endings so bash scripts work on the server
        content = local.read_bytes().replace(b"\r\n", b"\n")
        tmp = local.parent / f".tmp_{local.name}"
        tmp.write_bytes(content)
        try:
            full = ["scp"] + SSH_OPTS + [str(tmp), f"{SSH_USER}@{EC2_IP}:{remote}"]
            log(f"scp {local.name} (LF-converted) -> {remote}")
            subprocess.run(full, check=True)
        finally:
            tmp.unlink(missing_ok=True)
    else:
        full = ["scp"] + SSH_OPTS + [str(local), f"{SSH_USER}@{EC2_IP}:{remote}"]
        log(f"scp {local.name} -> {remote}")
        subprocess.run(full, check=True)


def _should_exclude(path: str) -> bool:
    import fnmatch
    parts = Path(path).parts
    for part in parts:
        if part in EXCLUDE:
            return True
        for pat in EXCLUDE:
            if "*" in pat and fnmatch.fnmatch(part, pat):
                return True
    return False


def make_tarball() -> bytes:
    """Create an in-memory tar.gz of the project (excluding junk/secrets).

    CRLF stripping is done on the server after extraction via sed.
    """
    log("Creating project tarball (this may take a moment) ...")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for item in sorted(PROJECT_DIR.rglob("*")):
            rel = item.relative_to(PROJECT_DIR)
            if _should_exclude(str(rel)):
                continue
            # Use forward slashes for the archive name (required on Linux)
            arcname = "chatbot-engine/" + rel.as_posix()
            tar.add(str(item), arcname=arcname, recursive=False)
    size_mb = buf.tell() / 1024 / 1024
    log(f"Tarball size: {size_mb:.1f} MB")
    return buf.getvalue()


def upload_project() -> None:
    """Pack project locally and stream it directly into tar on the remote."""
    log("Uploading project to server ...")
    tarball = make_tarball()

    # Write tarball to a temp file, then scp it
    tmp = Path(PROJECT_DIR) / ".tmp_upload.tar.gz"
    tmp.write_bytes(tarball)
    try:
        scp_to(tmp, "/tmp/chatbot-engine.tar.gz")
    finally:
        tmp.unlink(missing_ok=True)

    ssh(f"sudo mkdir -p {DEPLOY_PATH} && sudo chown $(id -u):$(id -g) {DEPLOY_PATH}")
    # Strip the top-level "chatbot-engine/" prefix so files land in DEPLOY_PATH directly
    ssh(f"tar -xzf /tmp/chatbot-engine.tar.gz -C {DEPLOY_PATH} --strip-components=1 && rm /tmp/chatbot-engine.tar.gz")
    # Strip Windows CRLF line endings from all shell scripts and Python files
    ssh(r"find " + DEPLOY_PATH + r" -type f \( -name '*.sh' -o -name '*.py' \) -exec sed -i 's/\r//' {} \;")
    ssh(f"find {DEPLOY_PATH} -name '*.sh' -exec chmod +x {{}} \\;")
    log("Project uploaded and extracted.")


def poll_api_healthy(timeout: int = 300, interval: int = 10) -> bool:
    log(f"Polling API health over SSH (up to {timeout}s) ...")
    deadline = time.time() + timeout
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        out = ssh_out("curl -sf http://127.0.0.1:8000/health && echo HEALTHY || echo NOT_READY")
        if "HEALTHY" in out:
            log("API is healthy!")
            return True
        remaining = int(deadline - time.time())
        log(f"  attempt {attempt} — not ready yet, retrying in {interval}s ({remaining}s left)")
        time.sleep(interval)
    return False


# ── Steps ─────────────────────────────────────────────────────────────────────

def step_bootstrap_docker() -> None:
    log("--- Step 1: Bootstrap Docker ---")
    has_docker = ssh_out("command -v docker && echo YES || echo NO")
    if "YES" in has_docker:
        log("Docker already installed, skipping.")
        return

    log("Docker not found — uploading and running bootstrap script ...")
    bootstrap = PROJECT_DIR / "scripts" / "ec2-bootstrap.sh"
    scp_to(bootstrap, "/tmp/ec2-bootstrap.sh", strip_cr=True)
    ssh("bash /tmp/ec2-bootstrap.sh", sudo=True)
    log("Docker installed.")


def step_upload_project() -> None:
    log("--- Step 2: Upload project ---")
    has_full = ssh_out(
        f"ls {DEPLOY_PATH}/scripts/deploy-remote.sh 2>/dev/null && echo YES || echo NO"
    )
    if "YES" in has_full:
        log(f"{DEPLOY_PATH} already fully deployed — skipping upload.")
        return
    upload_project()


def step_copy_env() -> None:
    log("--- Step 3: Copy .env ---")
    env_file = PROJECT_DIR / ".env"
    if not env_file.exists():
        log("ERROR: .env file not found in project root.")
        sys.exit(1)
    scp_to(env_file, f"{DEPLOY_PATH}/.env")
    ssh(f"chmod 600 {DEPLOY_PATH}/.env")
    log(".env copied.")


def step_deploy() -> None:
    log("--- Step 4: Build & start Docker stack ---")
    ssh(f"bash {DEPLOY_PATH}/scripts/deploy-remote.sh HEAD")
    log("Deploy script finished.")


def step_caddy() -> None:
    log("--- Step 5: Install Caddy with nip.io HTTPS ---")
    ssh(f"PUBLIC_IP={EC2_IP} bash {DEPLOY_PATH}/deploy/https/install-caddy-nip.sh", sudo=True)
    domain  = f"{EC2_IP}.nip.io"
    webhook = f"https://{domain}/api/v1/webhooks/twilio/messages"
    print("\n" + "=" * 64)
    print("  [DONE] Caddy is running -- HTTPS is live!")
    print(f"  nip.io domain  : {domain}")
    print(f"  Health check   : https://{domain}/health")
    print(f"  Twilio webhook : {webhook}")
    print()
    print("  Paste the webhook URL into Twilio Console:")
    print("    Messaging -> Senders -> WhatsApp senders")
    print("    -> your number -> 'A message comes in' (HTTP POST)")
    print("=" * 64, flush=True)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--caddy-only",   action="store_true",
                        help="Skip deploy; only install/reload Caddy")
    parser.add_argument("--deploy-only",  action="store_true",
                        help="Skip Caddy; only bootstrap + upload + deploy")
    args = parser.parse_args()

    if not KEY_FILE.exists():
        sys.exit(f"[error] Key file not found: {KEY_FILE}")

    print("=" * 64, flush=True)
    print(f"  EC2 target  : {EC2_IP}")
    print(f"  SSH user    : {SSH_USER}")
    print(f"  SSH key     : {KEY_FILE.name}")
    print(f"  Deploy path : {DEPLOY_PATH}")
    print("=" * 64, flush=True)

    if args.caddy_only:
        step_caddy()
        return

    step_bootstrap_docker()
    step_upload_project()
    step_copy_env()
    step_deploy()

    if not args.deploy_only:
        log("Waiting for API to be healthy before installing Caddy ...")
        healthy = poll_api_healthy(timeout=300, interval=10)
        if not healthy:
            log("WARNING: API not responding after 5 minutes.")
            ans = input("Continue with Caddy install anyway? [y/N] ").strip().lower()
            if ans != "y":
                sys.exit("Aborted.")
        step_caddy()


if __name__ == "__main__":
    main()

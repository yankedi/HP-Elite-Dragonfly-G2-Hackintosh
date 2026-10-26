#!/usr/bin/env python3
"""Serialize explicit-path local commits across independent engineering units."""
import fcntl
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
message, *paths = sys.argv[1:]
if not message or not paths:
    raise SystemExit("message and explicit paths required")
for path in paths:
    p = (root / path).resolve()
    if not p.is_relative_to(root) or path.startswith("-"):
        raise SystemExit("paths must be inside this worktree")

def git(*args):
    return subprocess.check_output(["git", "-C", str(root), *args], text=True)

with (root / ".git/ga42-unit.lock").open("a") as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    if git("diff", "--cached", "--name-only").strip():
        raise SystemExit("unexpected staged files: inspect manually")
    subprocess.run(["git", "-C", str(root), "diff", "--check", "--", *paths], check=True)
    print(git("status", "--short", "--", *paths))
    subprocess.run(["git", "-C", str(root), "add", "--", *paths], check=True)
    subprocess.run(["git", "-C", str(root), "diff", "--cached", "--check"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-m", message], check=True)
    print(git("rev-parse", "HEAD").strip())

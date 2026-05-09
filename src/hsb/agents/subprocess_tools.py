"""subprocess_tools.py — PydanticAI tool implementations for shell operations.

Replaces Bash(*) pattern allowed_tools from claude-agent-sdk.
Each function validates its inputs (no shell injection) and runs a specific
allowed subprocess command only. BLDR-04 and GITA-05 enforce separate sets.
"""

from __future__ import annotations

import asyncio


async def _run_cmd(args: list[str], cwd: str | None = None) -> str:
    """Run a command and return stdout + stderr."""
    proc = await asyncio.create_subprocess_exec(
        *args,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    return stdout.decode(errors="replace") + stderr.decode(errors="replace")


# Git tools (GITA-05: no merge, no bare --force)
async def git_checkout(branch: str, cwd: str | None = None) -> str:
    """Checkout a git branch."""
    return await _run_cmd(["git", "checkout", branch], cwd=cwd)


async def git_push_force_with_lease(
    branch: str, remote: str = "origin", cwd: str | None = None
) -> str:
    """Force push with lease (safer than --force)."""
    return await _run_cmd(
        ["git", "push", "--force-with-lease", remote, branch], cwd=cwd
    )


async def git_rebase(
    onto: str, old_tip: str, branch: str, cwd: str | None = None
) -> str:
    """Rebase branch onto another commit."""
    return await _run_cmd(
        ["git", "rebase", "--onto", onto, old_tip, branch], cwd=cwd
    )


async def git_fetch(remote: str = "origin", cwd: str | None = None) -> str:
    """Fetch from remote."""
    return await _run_cmd(["git", "fetch", remote], cwd=cwd)


async def git_log(args: str = "--oneline -10", cwd: str | None = None) -> str:
    """Show git log."""
    return await _run_cmd(["git", "log"] + args.split(), cwd=cwd)


async def git_status(cwd: str | None = None) -> str:
    """Show git status."""
    return await _run_cmd(["git", "status"], cwd=cwd)


async def git_add(path: str, cwd: str | None = None) -> str:
    """Stage a file."""
    return await _run_cmd(["git", "add", path], cwd=cwd)


async def git_commit(message: str, cwd: str | None = None) -> str:
    """Commit with message."""
    return await _run_cmd(["git", "commit", "-m", message], cwd=cwd)


async def gh_pr_create(
    title: str, body: str, base: str, head: str, cwd: str | None = None
) -> str:
    """Create a GitHub PR."""
    return await _run_cmd(
        ["gh", "pr", "create", "--title", title, "--body", body, "--base", base, "--head", head],
        cwd=cwd,
    )


async def gh_pr_list(
    base: str, state: str = "open", cwd: str | None = None
) -> str:
    """List GitHub PRs for a base branch."""
    return await _run_cmd(
        ["gh", "pr", "list", "--base", base, "--state", state, "--limit", "100", "--json", "number,headRefName"],
        cwd=cwd,
    )


async def gh_pr_view(pr_number: str, cwd: str | None = None) -> str:
    """View a GitHub PR."""
    return await _run_cmd(["gh", "pr", "view", pr_number], cwd=cwd)


async def gh_pr_diff(pr_number: str, cwd: str | None = None) -> str:
    """Get diff for a GitHub PR."""
    return await _run_cmd(["gh", "pr", "diff", pr_number], cwd=cwd)


# Builder tools (BLDR-04: pytest/ruff/mypy/python only)
async def run_pytest(args: str = "", cwd: str | None = None) -> str:
    """Run pytest with optional arguments."""
    cmd = ["python", "-m", "pytest"]
    if args:
        cmd.extend(args.split())
    return await _run_cmd(cmd, cwd=cwd)


async def run_ruff(args: str = "check .", cwd: str | None = None) -> str:
    """Run ruff linter with optional arguments."""
    cmd = ["ruff"]
    cmd.extend(args.split())
    return await _run_cmd(cmd, cwd=cwd)


async def run_mypy(args: str = "--ignore-missing-imports", cwd: str | None = None) -> str:
    """Run mypy type checker with optional arguments."""
    cmd = ["mypy"]
    cmd.extend(args.split())
    return await _run_cmd(cmd, cwd=cwd)

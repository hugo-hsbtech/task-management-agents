"""Interactive setup wizard for Gemini Vertex AI (OAuth2 ADC).

Walks the user through every prerequisite:
  1. gcloud CLI installed
  2. Authenticated with Google
  3. GCP project selected (or created)
  4. Vertex AI API enabled
  5. ADC credentials saved
  6. Smoke test

Usage:
  uv run python scripts/setup_gemini_adc.py
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def _ok(msg: str) -> None:
    print(f"  {GREEN}✅ {msg}{RESET}")


def _warn(msg: str) -> None:
    print(f"  {YELLOW}⚠️  {msg}{RESET}")


def _fail(msg: str) -> None:
    print(f"  {RED}❌ {msg}{RESET}")


def _info(msg: str) -> None:
    print(f"  {CYAN}ℹ️  {msg}{RESET}")


def _step(n: int, title: str) -> None:
    print(f"\n{BOLD}Step {n}: {title}{RESET}")
    print("─" * 50)


def _run(cmd: list[str], *, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        check=check,
    )


def _ask_yes_no(prompt: str, default: bool = True) -> bool:
    suffix = "[Y/n]" if default else "[y/N]"
    answer = input(f"  {prompt} {suffix} ").strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes", "s", "sim")


def _ask_input(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    answer = input(f"  {prompt}{suffix}: ").strip()
    return answer or default


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------


def step1_check_gcloud() -> str:
    """Check gcloud CLI is installed and return its path."""
    _step(1, "Checking gcloud CLI")

    gcloud = shutil.which("gcloud")
    if not gcloud:
        _fail("gcloud CLI not found in PATH")
        print()
        _info("Install it from: https://cloud.google.com/sdk/docs/install")
        _info("Or via brew: brew install google-cloud-sdk")
        sys.exit(1)

    result = _run([gcloud, "version", "--format=json"])
    version_info = json.loads(result.stdout)
    sdk_version = version_info.get("Google Cloud SDK", "unknown")
    _ok(f"gcloud CLI found: v{sdk_version}")
    return gcloud


def step2_check_auth(gcloud: str) -> str:
    """List all authenticated accounts and let the user pick one."""
    _step(2, "Checking Google authentication")

    result = _run([gcloud, "auth", "list", "--format=json"])
    accounts = json.loads(result.stdout)

    if not accounts:
        _warn("No Google accounts found")
        if _ask_yes_no("Run 'gcloud auth login' now?"):
            _run([gcloud, "auth", "login"], capture=False, check=False)
            result = _run([gcloud, "auth", "list", "--format=json"])
            accounts = json.loads(result.stdout)
        if not accounts:
            _fail("Authentication required. Run: gcloud auth login")
            sys.exit(1)

    # Show all accounts + "add new" option
    active_account = None
    print()
    for i, acc in enumerate(accounts, 1):
        email = acc["account"]
        status = acc.get("status", "")
        marker = f" {GREEN}← active{RESET}" if status == "ACTIVE" else ""
        print(f"    {CYAN}{i}.{RESET} {email}{marker}")
        if status == "ACTIVE":
            active_account = email
    new_idx = len(accounts) + 1
    print(f"    {CYAN}{new_idx}.{RESET} {YELLOW}Login with another account{RESET}")
    print()

    # Let user pick
    default_choice = (
        str(accounts.index(next(a for a in accounts if a.get("status") == "ACTIVE")) + 1)
        if active_account else "1"
    )
    choice = _ask_input(
        "Which account to use?",
        default=default_choice,
    )

    try:
        idx = int(choice) - 1
    except ValueError:
        idx = -1  # treat as email input

    # Handle "login with another account"
    if idx == len(accounts):
        _info("Opening browser to login with a new account...")
        _run([gcloud, "auth", "login"], capture=False, check=False)
        result = _run([gcloud, "auth", "list", "--format=json"])
        accounts = json.loads(result.stdout)
        active = [a for a in accounts if a.get("status") == "ACTIVE"]
        if active:
            chosen = active[0]["account"]
            _ok(f"Logged in as: {chosen}")
        else:
            _fail("Login failed")
            sys.exit(1)
    elif 0 <= idx < len(accounts):
        chosen = accounts[idx]["account"]
    else:
        chosen = choice  # Assume they typed an email

    # Switch active account if needed
    if chosen != active_account:
        _info(f"Switching active account to {chosen}...")
        _run([gcloud, "config", "set", "account", chosen], check=False)
        _ok(f"Active account: {chosen}")
    else:
        _ok(f"Using: {chosen}")

    # Show gcloud configurations tip
    _show_config_tip(gcloud, accounts)

    return chosen


def _show_config_tip(gcloud: str, accounts: list) -> None:
    """Show tip about gcloud configurations if multiple accounts exist."""
    if len(accounts) < 2:
        return

    result = _run([gcloud, "config", "configurations", "list", "--format=json"], check=False)
    try:
        configs = json.loads(result.stdout)
    except json.JSONDecodeError:
        configs = []

    if len(configs) <= 1:
        print()
        _info(f"{BOLD}Tip:{RESET} You have multiple accounts. Use gcloud configurations")
        _info("to switch between them easily:")
        print()
        print(f"    {CYAN}# Create a config per account/project{RESET}")
        print(f"    gcloud config configurations create work")
        print(f"    gcloud config set account work@company.com")
        print(f"    gcloud config set project my-work-project")
        print()
        print(f"    gcloud config configurations create personal")
        print(f"    gcloud config set account me@gmail.com")
        print(f"    gcloud config set project my-personal-project")
        print()
        print(f"    {CYAN}# Switch between them{RESET}")
        print(f"    gcloud config configurations activate work")
        print(f"    gcloud config configurations activate personal")
        print()
    else:
        print()
        _info("Your gcloud configurations:")
        for c in configs:
            name = c.get("name", "")
            active = c.get("is_active", False)
            account = c.get("properties", {}).get("core", {}).get("account", "—")
            project = c.get("properties", {}).get("core", {}).get("project", "—")
            marker = f" {GREEN}← active{RESET}" if active else ""
            print(f"    • {BOLD}{name}{RESET}: {account} / {project}{marker}")
        print()
        _info(f"Switch with: gcloud config configurations activate <name>")


def step3_select_project(gcloud: str) -> str:
    """Select or create a GCP project."""
    _step(3, "Selecting GCP project")

    # Check current project
    result = _run([gcloud, "config", "get-value", "project"], check=False)
    current = result.stdout.strip()
    if current and current != "(unset)":
        _ok(f"Current project: {current}")
        if _ask_yes_no(f"Use project '{current}'?"):
            return current

    # List existing projects
    _info("Fetching your GCP projects...")
    result = _run([gcloud, "projects", "list", "--format=json", "--limit=20"], check=False)
    try:
        projects = json.loads(result.stdout)
    except json.JSONDecodeError:
        projects = []

    if projects:
        print()
        for i, p in enumerate(projects, 1):
            state = p.get("lifecycleState", "")
            if state == "ACTIVE":
                print(f"    {CYAN}{i}.{RESET} {p['projectId']}  ({p.get('name', '')})")

        choice = _ask_input("Enter project number or ID (or 'new' to create one)", "1")
        if choice.lower() == "new":
            return _create_project(gcloud)
        try:
            idx = int(choice) - 1
            project_id = projects[idx]["projectId"]
        except (ValueError, IndexError):
            project_id = choice  # Assume they typed a project ID

        _run([gcloud, "config", "set", "project", project_id], check=False)
        _ok(f"Project set to: {project_id}")
        return project_id
    else:
        _warn("No existing projects found")
        return _create_project(gcloud)


def _create_project(gcloud: str) -> str:
    """Create a new GCP project."""
    project_id = _ask_input("Enter a project ID (e.g., 'my-gemini-agents')")
    if not project_id:
        _fail("Project ID is required")
        sys.exit(1)

    _info(f"Creating project '{project_id}'...")
    result = _run(
        [gcloud, "projects", "create", project_id, f"--name={project_id}"],
        check=False,
    )
    if result.returncode != 0:
        _fail(f"Failed to create project: {result.stderr.strip()}")
        _info("You can create one manually at: https://console.cloud.google.com/projectcreate")
        sys.exit(1)

    _run([gcloud, "config", "set", "project", project_id], check=False)
    _ok(f"Project created and set: {project_id}")
    return project_id


def step4_enable_vertex_api(gcloud: str, project_id: str) -> None:
    """Enable the Vertex AI API on the project."""
    _step(4, "Enabling Vertex AI API")

    # Check if already enabled
    result = _run(
        [gcloud, "services", "list", "--enabled", "--format=json",
         f"--project={project_id}", "--filter=name:aiplatform.googleapis.com"],
        check=False,
    )
    try:
        services = json.loads(result.stdout)
    except json.JSONDecodeError:
        services = []

    if services:
        _ok("Vertex AI API already enabled")
        return

    _warn("Vertex AI API is not enabled on this project")
    if _ask_yes_no("Enable it now? (may require billing)"):
        _info("Enabling aiplatform.googleapis.com...")
        result = _run(
            [gcloud, "services", "enable", "aiplatform.googleapis.com",
             f"--project={project_id}"],
            check=False,
            capture=False,
        )
        if result.returncode != 0:
            _fail("Failed to enable Vertex AI API")
            _info("This usually means billing is not set up.")
            _info(f"Enable billing: https://console.cloud.google.com/billing?project={project_id}")
            _info(f"Then enable API: https://console.cloud.google.com/apis/library/aiplatform.googleapis.com?project={project_id}")
            sys.exit(1)
        _ok("Vertex AI API enabled")
    else:
        _fail("Vertex AI API is required for the ADC backend")
        sys.exit(1)


def step5_setup_adc(gcloud: str) -> None:
    """Set up Application Default Credentials."""
    _step(5, "Setting up Application Default Credentials (ADC)")

    adc_path = Path.home() / ".config" / "gcloud" / "application_default_credentials.json"
    if adc_path.exists():
        _ok(f"ADC file found: {adc_path}")
        if not _ask_yes_no("Re-authenticate?", default=False):
            return

    _info("Opening browser for authentication...")
    _run([gcloud, "auth", "application-default", "login"], capture=False, check=False)

    if adc_path.exists():
        _ok("ADC credentials saved successfully")
    else:
        _fail("ADC credentials not found after login")
        sys.exit(1)


def step6_smoke_test(project_id: str) -> None:
    """Run a quick smoke test."""
    _step(6, "Running smoke test")

    import os
    os.environ["GOOGLE_CLOUD_PROJECT"] = project_id

    try:
        from llm_providers import ProviderRegistry, resolve_auth
        auth = resolve_auth("gemini", "oauth2_adc")
        _ok(f"Auth resolved: {auth.kind}")

        provider = ProviderRegistry.build("gemini", auth=auth)
        _ok(f"Provider built: {provider.name} ({type(provider._backend).__name__})")
        _ok(f"Project: {project_id}")

        print()
        _info("Ready to query! Run:")
        print(f"\n    export GOOGLE_CLOUD_PROJECT=\"{project_id}\"")
        print("    uv run python scripts/test_gemini_live.py --adc\n")

    except Exception as e:
        _fail(f"Smoke test failed: {e}")
        sys.exit(1)


def step_write_env(project_id: str) -> None:
    """Optionally write the project to .env."""
    env_file = Path(".env")
    key = "GOOGLE_CLOUD_PROJECT"

    if env_file.exists():
        content = env_file.read_text()
        if key in content:
            _info(f"{key} already in .env")
            return

    if _ask_yes_no(f"Add {key}={project_id} to .env?"):
        with open(env_file, "a") as f:
            f.write(f"\n# Gemini Vertex AI project\n{key}={project_id}\n")
        _ok(f"Added to .env")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    print(f"\n{BOLD}{'='*50}")
    print("  Gemini Vertex AI (ADC) Setup Wizard")
    print(f"{'='*50}{RESET}\n")
    print("This wizard will guide you through setting up")
    print("Google Cloud for the Gemini Vertex AI backend.\n")

    gcloud = step1_check_gcloud()
    step2_check_auth(gcloud)
    project_id = step3_select_project(gcloud)
    step4_enable_vertex_api(gcloud, project_id)
    step5_setup_adc(gcloud)
    step_write_env(project_id)
    step6_smoke_test(project_id)

    print(f"\n{GREEN}{BOLD}{'='*50}")
    print("  Setup complete! 🎉")
    print(f"{'='*50}{RESET}\n")


if __name__ == "__main__":
    main()

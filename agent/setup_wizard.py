"""First-run Agent Setup & Role Configuration Wizard.

Implements Section 11 of the ProjectPulse AI Master Architecture:
- Interactive role selection (Developer, Tester, QA)
- Project folder configuration & validation
- Backend connection verification & instant registration
"""

import argparse
import os
import platform
import sys
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.config import DEFAULT_CONFIG_PATH, AgentConfig
from agent.registration import RegistrationClient
from shared.event_types import UserRole


def print_banner():
    print("=" * 45)
    print("           PROJECTPULSE AGENT")
    print("      Role Configuration & Setup")
    print("=" * 45)


def run_setup(args=None):
    print_banner()

    parser = argparse.ArgumentParser(description="ProjectPulse Agent First-Run Setup")
    parser.add_argument("--role", choices=["DEVELOPER", "TESTER", "QA", "PROJECT_MANAGER"], help="Agent role")
    parser.add_argument("--agent-id", help="Unique Agent ID (e.g. AGENT-DEV-001)")
    parser.add_argument("--project-folder", help="Target project folder path to monitor")
    parser.add_argument("--project-id", default="DLX", help="Project ID")
    parser.add_argument("--project-name", default="DLX E-Commerce Platform", help="Project Name")
    parser.add_argument("--user-id", help="User ID associated with this agent")
    parser.add_argument("--user-name", help="User display name")
    parser.add_argument("--backend-url", default="http://127.0.0.1:8000", help="Backend API URL")
    parser.add_argument("--output-config", help="Custom path to save the config JSON")
    parser.add_argument("--non-interactive", action="store_true", help="Run without interactive prompts")

    parsed = parser.parse_args(args)

    # 1. Role Selection
    role = parsed.role
    if not role:
        if parsed.non_interactive:
            role = "DEVELOPER"
        else:
            print("\nSelect your role:")
            print("  [ 1 ] DEVELOPER (Watches files, Git commits, builds)")
            print("  [ 2 ] TESTER    (Watches test runs, test suites, pass/fail)")
            print("  [ 3 ] QA        (Logs defects, verifies builds, regression)")
            choice = input("\nEnter choice [1-3] (default 1): ").strip()
            role_map = {"1": "DEVELOPER", "2": "TESTER", "3": "QA"}
            role = role_map.get(choice, "DEVELOPER")

    print(f"\n[+] Role selected: {role}")

    # Role defaults
    default_user_ids = {
        "DEVELOPER": ("DEV-001", "Alex Rivera (Developer)", "AGENT-DEV-001"),
        "TESTER": ("TEST-001", "Dave Miller (Tester)", "AGENT-TEST-001"),
        "QA": ("QA-001", "Liam Johnson (QA)", "AGENT-QA-001"),
    }
    def_uid, def_uname, def_aid = default_user_ids.get(role, ("USER-001", "Team Member", "AGENT-001"))

    # 2. Project Folder
    folder = parsed.project_folder
    if not folder:
        if parsed.non_interactive:
            folder = str(ROOT)
        else:
            prompt_folder = input(f"\nSelect Project Folder to monitor [default: {ROOT}]: ").strip()
            folder = prompt_folder if prompt_folder else str(ROOT)

    resolved_folder = str(Path(folder).resolve())
    print(f"[+] Monitored project folder: {resolved_folder}")

    # 3. Connection & Identifiers
    project_id = parsed.project_id
    project_name = parsed.project_name
    backend_url = parsed.backend_url
    user_id = parsed.user_id or def_uid
    user_name = parsed.user_name or def_uname
    agent_id = parsed.agent_id or def_aid

    if not parsed.non_interactive:
        p_in = input(f"Project ID [default: {project_id}]: ").strip()
        if p_in:
            project_id = p_in
        u_in = input(f"User ID [default: {user_id}]: ").strip()
        if u_in:
            user_id = u_in
        a_in = input(f"Agent ID [default: {agent_id}]: ").strip()
        if a_in:
            agent_id = a_in
        b_in = input(f"Backend URL [default: {backend_url}]: ").strip()
        if b_in:
            backend_url = b_in

    target_config = Path(parsed.output_config) if parsed.output_config else DEFAULT_CONFIG_PATH

    cfg = AgentConfig(
        agent_id=agent_id,
        user_id=user_id,
        user_name=user_name,
        project_id=project_id,
        project_name=project_name,
        role=role,
        machine_name=platform.node(),
        machine_id=f"MACH-{abs(hash(platform.node())) % 10000:04d}",
        project_folder=resolved_folder,
        backend_url=backend_url,
        frontend_url="http://127.0.0.1:5173",
        monitoring_active=True,
        config_file_path=target_config,
    )

    cfg.save(target_config)
    print(f"\n[+] Configuration saved to: {target_config}")

    # 4. Immediate Registration Attempt
    print("\nAttempting registration with central backend...")
    client = RegistrationClient(cfg)
    success = client.register()
    if success:
        print("[OK] Agent registered successfully with ProjectPulse backend!")
        hb = client.heartbeat()
        if hb:
            print("[OK] Heartbeat confirmed: Agent is now marked ONLINE.")
    else:
        print("[WARN] Backend is currently offline or unreachable.")
        print("       The agent configuration is saved and will auto-register as soon as the backend starts.")

    print("\n" + "=" * 45)
    print("Setup Complete! You can run this agent using:")
    print(f"  python -m agent.main")
    print("=" * 45)
    return cfg


if __name__ == "__main__":
    run_setup()

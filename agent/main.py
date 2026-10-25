"""ProjectPulse AI — Role-Aware Background Agent Entry Point."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.config import AgentConfig
from agent.tray_app import TrayApp


def main():
    parser = argparse.ArgumentParser(description="ProjectPulse AI Windows Background Agent")
    parser.add_argument(
        "--config",
        "-c",
        type=str,
        default=None,
        help="Path to custom agent configuration JSON file (e.g. for multi-instance simulation)",
    )
    parser.add_argument(
        "--minimized",
        "-m",
        action="store_true",
        help="Start agent minimized in the system tray without opening the desktop window",
    )
    args = parser.parse_args()

    custom_path = Path(args.config).resolve() if args.config else None
    config = AgentConfig.load(custom_path)
    print(f"[*] Starting ProjectPulse Agent: ID={config.agent_id} | Role={config.role} | Project={config.project_id}")

    app = TrayApp(config)
    app.run(show_window_on_start=not args.minimized)


if __name__ == "__main__":
    main()
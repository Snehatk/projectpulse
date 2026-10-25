"""Windows Platform Integration: Shortcuts, Autostart Registry, and Silent Launchers."""

import logging
import os
from pathlib import Path
import subprocess
import sys

logger = logging.getLogger(__name__)

RUN_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "ProjectPulseAIAgent"


def get_desktop_path() -> Path:
    """Find the user's Windows Desktop directory reliably."""
    # Check OneDrive Desktop first if present, then standard UserProfile Desktop
    userprofile = os.environ.get("USERPROFILE")
    if userprofile:
        onedrive_desktop = Path(userprofile) / "OneDrive" / "Desktop"
        if onedrive_desktop.exists():
            return onedrive_desktop
        normal_desktop = Path(userprofile) / "Desktop"
        if normal_desktop.exists():
            return normal_desktop
    return Path.home() / "Desktop"


def set_autostart_with_windows(enable: bool, command: str | None = None) -> bool:
    """Register or unregister agent auto-start in Windows CurrentUser Run registry."""
    if os.name != "nt":
        return False

    import winreg

    try:
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            RUN_KEY_PATH,
            0,
            winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE,
        )
    except Exception as exc:
        logger.error("Failed to open Windows Run registry key: %s", exc)
        return False

    try:
        if enable:
            if not command:
                # Default to launcher script or pythonw
                root = Path(__file__).resolve().parent.parent
                vbs_launcher = root / "agent" / "launcher.vbs"
                if vbs_launcher.exists():
                    command = f'wscript.exe "{vbs_launcher}"'
                else:
                    python_exe = sys.executable
                    pythonw = Path(python_exe).parent / "pythonw.exe"
                    exe = str(pythonw) if pythonw.exists() else str(python_exe)
                    command = f'"{exe}" -m agent.main'

            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
            logger.info("Registered auto-start with Windows: %s", command)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
                logger.info("Removed auto-start from Windows registry.")
            except FileNotFoundError:
                pass
        return True
    except Exception as exc:
        logger.error("Failed to update auto-start registry: %s", exc)
        return False
    finally:
        winreg.CloseKey(key)


def is_autostart_enabled() -> bool:
    """Check if ProjectPulse AI Agent is set to run at Windows startup."""
    if os.name != "nt":
        return False

    import winreg

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY_PATH, 0, winreg.KEY_READ)
        try:
            val, _ = winreg.QueryValueEx(key, APP_NAME)
            return bool(val)
        except FileNotFoundError:
            return False
        finally:
            winreg.CloseKey(key)
    except Exception:
        return False


def create_desktop_shortcut(
    target_cmd: str | None = None,
    shortcut_name: str = "ProjectPulse AI Agent.lnk",
    icon_path: str | None = None,
) -> Path | None:
    """Create a Windows desktop shortcut (.lnk) using PowerShell COM object."""
    if os.name != "nt":
        return None

    desktop = get_desktop_path()
    shortcut_path = desktop / shortcut_name
    root = Path(__file__).resolve().parent.parent

    # Point to launcher.vbs or pythonw
    launcher_vbs = root / "agent" / "launcher.vbs"
    target = "wscript.exe"
    args = f'"{launcher_vbs}"'
    working_dir = str(root)

    # PowerShell snippet to create .lnk
    ps_cmd = f"""
    $WshShell = New-Object -comObject WScript.Shell
    $Shortcut = $WshShell.CreateShortcut('{str(shortcut_path)}')
    $Shortcut.TargetPath = '{target}'
    $Shortcut.Arguments = '{args}'
    $Shortcut.WorkingDirectory = '{working_dir}'
    $Shortcut.Description = 'ProjectPulse AI Background Telemetry & Project Intelligence Agent'
    $Shortcut.Save()
    """

    try:
        res = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_cmd],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode == 0 and shortcut_path.exists():
            logger.info("Created desktop shortcut: %s", shortcut_path)
            return shortcut_path
        else:
            logger.warning("PowerShell shortcut creation error: %s", res.stderr)
    except Exception as exc:
        logger.error("Failed to create desktop shortcut: %s", exc)

    return None


def generate_silent_launchers() -> None:
    """Ensure agent/launcher.vbs and run_agent_silent.bat exist in agent directory."""
    root = Path(__file__).resolve().parent.parent
    agent_dir = root / "agent"
    agent_dir.mkdir(parents=True, exist_ok=True)

    # 1. VBScript launcher (completely headless, 0 console window)
    vbs_path = agent_dir / "launcher.vbs"
    vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "{root}"
WshShell.Run """{sys.executable}"" -m agent.main", 0, False
'''
    vbs_path.write_text(vbs_content, encoding="utf-8")

    # 2. Batch launcher
    bat_path = root / "start_agent.bat"
    bat_content = f'''@echo off
cd /d "{root}"
start "" "{sys.executable}" -m agent.main
'''
    bat_path.write_text(bat_content, encoding="utf-8")
    logger.info("Generated launchers at %s and %s", vbs_path, bat_path)

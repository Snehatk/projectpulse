# ProjectPulse AI — Windows Background Desktop Agent Guide

## 1. Overview & Architecture

The **ProjectPulse AI Windows Background Agent** is a lightweight, privacy-preserving desktop telemetry and intelligence agent built natively for Windows. It observes real developer, tester, and QA activity inside approved project workspaces and synchronizes with the ProjectPulse AI backend or operates independently in **Local Only — Not Synced** mode.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        WINDOWS DESKTOP AGENT                           │
│                                                                        │
│   ┌──────────────────────┐              ┌──────────────────────────┐   │
│   │   System Tray Icon   │ <──────────> │   Native Tkinter Window  │   │
│   │  (pystray + WinLock) │              │   (Overview/Search/Time) │   │
│   └──────────────────────┘              └──────────────────────────┘   │
│              │                                        │                │
│              ▼                                        ▼                │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │                    Session & Telemetry Engine                  │   │
│   │  • Win32 GetLastInputInfo (Idle Detection >5m)                 │   │
│   │  • VS Code Process (Code.exe) Workspace Scanner                │   │
│   │  • Watchdog File Watcher (Create, Edit, Delete, Move)          │   │
│   │  • Git Reflog & Push Verifier (Commit, Branch, Push)           │   │
│   │  • Report Watcher (JUnit, TestNG, Cobertura XML)               │   │
│   └────────────────────────────────────────────────────────────────┘   │
│                                  │                                     │
│                                  ▼                                     │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │           Persistent Local SQLite (agent_queue.db)             │   │
│   │  • queued_events: FIFO Outbound Network Dispatch               │   │
│   │  • local_event_history: Searchable Permanent Event Log         │   │
│   │  • work_sessions: Observed vs. Active vs. Idle Time Tracking   │   │
│   └────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ HTTPS / REST (Bearer Device Token)
                                   ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        FASTAPI BACKEND CORE                            │
│   • Ingestion: POST /api/events & POST /api/agents/heartbeat           │
│   • Auth: Role-Based Access Control (RBAC) & Device Tokens             │
│   • Unified Database: Users, Projects, ChangeSets, Errors, Evidence    │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Launching & Desktop Integration

### Launch Options
1. **Desktop Shortcut:** Double-click the **`ProjectPulse AI Agent.lnk`** shortcut on your Windows Desktop. This silently launches the agent via `agent/launcher.vbs` without opening a terminal window.
2. **Batch Script:** Run `start_agent.bat` in the repository root.
3. **Command Line:** Run `python -m agent.main` (or `.venv\Scripts\python.exe -m agent.main`).
4. **Headless / Minimized Mode:** Run `python -m agent.main --minimized` (used when launching automatically via Windows Startup).

### Window & Tray Controls
* **Minimize-to-Tray:** Clicking the standard Windows close button (`X`) on the agent window **minimizes it to the system tray by default**. The background telemetry watchers and session trackers remain active.
* **Restoring Window:** Double-click the system tray icon or right-click and select **`Open Desktop Window`**.
* **System Tray Context Menu:**
  * **Open Desktop Window:** Restores the main control interface.
  * **Open Web Dashboard:** Launches your default browser to your role-specific dashboard (`http://localhost:5173/developer`, `/tester`, or `/manager`).
  * **Quick Status Popup:** Displays a lightweight activity card near the taskbar.
  * **Pause Monitoring / Resume Monitoring:** Temporarily suspends or restarts filesystem watchers.
  * **Settings:** Opens the Settings tab in the desktop window.
  * **Exit Agent:** Safely flushes queues, stops collectors, releases the kernel file lock, and exits the process.

---

## 3. The 6 Agent Status Indicators

The tray icon and desktop window dynamically reflect the agent's real-time state:

| Status Key | Tray Color | Meaning |
| :--- | :--- | :--- |
| **`STARTING`** | Amber | Agent process is initializing database connections, locking process, and configuring collectors. |
| **`CONNECTING`** | Blue | Agent is attempting to contact the FastAPI backend health and registration endpoints. |
| **`RUNNING`** | Green | Monitoring is active on the approved workspace and heartbeats are verified by the central server. |
| **`PAUSED`** | Orange | The user explicitly paused monitoring. File watchers and telemetry emitters are halted. |
| **`OFFLINE`** | Slate Gray | **Local Only — Not Synced** mode. The backend is unreachable; all events and sessions are securely persisted in local SQLite and will automatically sync once connectivity returns. |
| **`ERROR`** | Red | Collector exception, file permission failure, or invalid workspace path. |

---

## 4. Time Tracking & Productivity Integrity

ProjectPulse AI strictly separates four distinct dimensions of time to prevent inaccurate or inflated productivity claims:

1. **Observed VS Code Session Time:**  
   The wall-clock duration during which `Code.exe` was running with the approved workspace open.
2. **Measured Active Interaction Time:**  
   Session time minus detected Windows user idle periods (measured via `ctypes.windll.user32.GetLastInputInfo` whenever user inactivity exceeds 5 minutes).
3. **Estimated Editing Time:**  
   The aggregated time windows surrounding debounced file modifications and AST symbol diffs.
4. **Explicitly Verified Task Time:**  
   Time intervals backed by concrete Git commits, verified remote pushes, and test executions directly linked to a Jira or PM task key (e.g. `KAN-4`).

> **Rule:** Observed session duration is **never** presented as raw productive coding time.

---

## 5. Local Persistence & Offline Resilience

All activity is recorded to `agent/config/agent_queue.db`:
* **`queued_events`:** FIFO queue of outbound events. Records are **only deleted** after receiving an HTTP 200/201 confirmation from the backend.
* **`local_event_history`:** Searchable permanent event archive. Users can filter by free-text query, event type (`FILE_CREATED`, `FILE_MODIFIED`, `FILE_DELETED`, `GIT_COMMIT`, `GIT_PUSH`), and date range directly within the Desktop Agent window.
* **`work_sessions`:** Persisted session intervals tracking observed, active, idle, and editing seconds across system reboots.

---

## 6. Privacy Boundaries

The Windows Desktop Agent enforces strict local privacy filters:
* **Strict Workspace Containment:** Only files inside the explicitly configured `project_folder` are observed.
* **Default Directory Exclusions:** `.git`, `.venv`, `venv`, `node_modules`, `__pycache__`, `.pytest_cache`, `dist`, `build`, and system temporary folders are permanently excluded.
* **Configurable Custom Exclusions:** Additional patterns (e.g. `secret_dir`, `*.key`) can be configured in the Settings tab.
* **Zero Keylogging & Screen Capture:** No keystroke logging, clipboard inspection, webcam, microphone, or external application tracking.

---

## 7. Troubleshooting

### 1. "Another instance of ProjectPulse Agent is already running"
* **Cause:** The single-instance kernel file lock `agent/config/.agent.lock` is held by an active background process.
* **Solution:** Check the system tray near the clock for the ProjectPulse icon. If a previous instance hung, terminate python processes in Task Manager or delete `agent/config/.agent.lock`.

### 2. Status displays "Local Only — Not Synced"
* **Cause:** The FastAPI backend is not running at `http://127.0.0.1:8000`.
* **Solution:** Start the backend with `start_all.bat` or `.venv\Scripts\python.exe -m uvicorn backend.main:app --port 8000`. The agent will automatically detect the backend and flush all queued events.

### 3. Desktop Shortcut Missing
* **Solution:** Open the agent desktop window, navigate to the **Settings** tab, and click **`Create Desktop Shortcut`**.

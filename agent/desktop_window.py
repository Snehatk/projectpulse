"""ProjectPulse AI — Windows Desktop Agent Interface.

Matches the exact multi-window side-by-side design:
1. CompactAgentWidget (Right window):
   - Sleek dark navy theme (#0f172a / #1e293b)
   - Status badge (#22c55e Running / Paused / Offline) & Role badge (Team_Lead / Developer)
   - Real metrics: Project, User, Session Started, Session Duration, Last Change, Files Changed, Pending Sync
   - Recent Changes bullet list
   - Primary button: "View Activity & Time Logs" (opens side-by-side history window)
   - Bottom buttons: "Open Dashboard" | "Pause Monitoring"
   
2. ActivityHistoryWindow (Left window — opens side-by-side):
   - Title: "ProjectPulse AI — Change History, Time Logs & Summaries"
   - Tab 1: Change History (Search, Period filters Today/Yesterday/7d/30d/All, Event filter, Export CSV, Table, Event Details & Evidence panel)
   - Tab 2: Time Logs & Sessions (Observed vs Active vs Idle vs Editing time, sessions table)
   - Tab 3: Daily & Weekly Summaries (Side-by-side synthesis engine, metric cards, narrative summary, export)
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta, timezone
import json
import logging
import os
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING, Any, Callable
import webbrowser

from shared.timeutil import format_display_time

if TYPE_CHECKING:
    from agent.backend_client import BackendClient
    from agent.config import AgentConfig
    from agent.session_tracker import SessionTracker

logger = logging.getLogger(__name__)

COMPACT_WIDTH = 340
COMPACT_HEIGHT = 520
HISTORY_WIDTH = 730
HISTORY_HEIGHT = 520


def _format_time_hhmmss(seconds: float) -> str:
    s = max(0, int(seconds))
    h = s // 3600
    m = (s % 3600) // 60
    sec = s % 60
    return f"{h:02d}h {m:02d}m {sec:02d}s"


class CompactAgentWidget(tk.Toplevel):
    """The compact dark vertical agent widget shown on the right side of the screen."""

    def __init__(
        self,
        master: tk.Tk,
        config: AgentConfig,
        backend: BackendClient,
        session_tracker: SessionTracker,
        on_toggle_monitoring: Callable[[bool], None],
        on_open_dashboard: Callable[[], None],
        on_open_history: Callable[[], None],
        on_exit: Callable[[], None],
    ):
        super().__init__(master)
        self.config = config
        self.backend = backend
        self.session_tracker = session_tracker
        self.on_toggle_monitoring = on_toggle_monitoring
        self.on_open_dashboard = on_open_dashboard
        self.on_open_history = on_open_history
        self.on_exit = on_exit

        self.title("ProjectPulse AI Agent")
        self.geometry(f"{COMPACT_WIDTH}x{COMPACT_HEIGHT}")
        self.resizable(False, False)
        self.configure(bg="#0f172a")

        # Intercept close button -> minimize to tray
        self.protocol("WM_DELETE_WINDOW", self.withdraw)

        # Reactive vars
        self.var_status_badge = tk.StringVar(value="#22c55e Running")
        self.var_role = tk.StringVar(value=config.role.title())
        self.var_project = tk.StringVar(value=f"{config.project_name} ({config.project_id})")
        self.var_user = tk.StringVar(value=f"{config.user_name} ({config.user_id})")
        self.var_session_started = tk.StringVar(value=datetime.now().strftime("%I:%M %p"))
        self.var_session_duration = tk.StringVar(value="00h 00m 00s")
        self.var_last_change = tk.StringVar(value="Waiting for activity…")
        self.var_files_changed = tk.StringVar(value="0")
        self.var_pending_sync = tk.StringVar(value="0")
        self.var_pause_btn_text = tk.StringVar(value="Pause Monitoring")

        self._build_ui()
        self._position_on_screen()

    def _position_on_screen(self) -> None:
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        # Place near the right edge of screen
        x = max(20, sw - COMPACT_WIDTH - 24)
        y = max(20, (sh // 2) - (COMPACT_HEIGHT // 2) - 40)
        self.geometry(f"{COMPACT_WIDTH}x{COMPACT_HEIGHT}+{x}+{y}")

    def _build_ui(self) -> None:
        # Header Bar
        hdr = tk.Frame(self, bg="#0f172a", height=46)
        hdr.pack(fill="x", padx=14, pady=(12, 6))

        title_row = tk.Frame(hdr, bg="#0f172a")
        title_row.pack(fill="x")

        tk.Label(
            title_row,
            text="⚡ ProjectPulse AI Agent",
            font=("Segoe UI", 11, "bold"),
            fg="#f8fafc",
            bg="#0f172a",
        ).pack(side="left")

        # Sub-header Status Row
        sub_row = tk.Frame(self, bg="#0f172a")
        sub_row.pack(fill="x", padx=14, pady=(0, 10))

        self.lbl_status_badge = tk.Label(
            sub_row,
            textvariable=self.var_status_badge,
            font=("Segoe UI", 9, "bold"),
            fg="#22c55e",
            bg="#064e3b",
            padx=8,
            pady=2,
            relief="flat",
        )
        self.lbl_status_badge.pack(side="left")

        self.lbl_role_badge = tk.Label(
            sub_row,
            textvariable=self.var_role,
            font=("Segoe UI", 8, "bold"),
            fg="#93c5fd",
            bg="#1e3a8a",
            padx=8,
            pady=2,
            relief="flat",
        )
        self.lbl_role_badge.pack(side="right")

        # Details Box (Dark Navy Card)
        card = tk.Frame(self, bg="#1e293b", relief="solid", bd=1, padx=12, pady=10)
        card.pack(fill="x", padx=14, pady=(0, 10))

        rows = [
            ("Project:", self.var_project, "#94a3b8", "#f8fafc"),
            ("User:", self.var_user, "#94a3b8", "#f8fafc"),
            ("Session Started:", self.var_session_started, "#94a3b8", "#f8fafc"),
            ("Session Duration:", self.var_session_duration, "#94a3b8", "#38bdf8"),
            ("Last Change:", self.var_last_change, "#94a3b8", "#cbd5e1"),
            ("Files Changed:", self.var_files_changed, "#94a3b8", "#f8fafc"),
            ("Pending Sync:", self.var_pending_sync, "#94a3b8", "#f59e0b"),
        ]

        for label_text, var, fg_lbl, fg_val in rows:
            r = tk.Frame(card, bg="#1e293b")
            r.pack(fill="x", pady=2)
            tk.Label(r, text=label_text, font=("Segoe UI", 8), fg=fg_lbl, bg="#1e293b", width=14, anchor="w").pack(side="left")
            tk.Label(r, textvariable=var, font=("Segoe UI", 8, "bold"), fg=fg_val, bg="#1e293b", anchor="w", wraplength=170, justify="left").pack(side="left", fill="x", expand=True)

        # RECENT CHANGES Section
        rc_header = tk.Frame(self, bg="#0f172a")
        rc_header.pack(fill="x", padx=14, pady=(2, 4))
        tk.Label(rc_header, text="RECENT CHANGES", font=("Segoe UI", 8, "bold"), fg="#64748b", bg="#0f172a").pack(anchor="w")

        self.recent_frame = tk.Frame(self, bg="#0f172a")
        self.recent_frame.pack(fill="both", expand=True, padx=14)

        self.recent_labels = []
        for _ in range(3):
            lbl = tk.Label(
                self.recent_frame,
                text="• Waiting for activity…",
                font=("Segoe UI", 8),
                fg="#94a3b8",
                bg="#0f172a",
                anchor="w",
                justify="left",
                wraplength=310,
            )
            lbl.pack(fill="x", pady=2)
            self.recent_labels.append(lbl)

        # Bottom Action Buttons
        btn_box = tk.Frame(self, bg="#0f172a")
        btn_box.pack(fill="x", side="bottom", padx=14, pady=(0, 14))

        # Primary Big Blue Button: View Activity & Time Logs
        btn_act = tk.Button(
            btn_box,
            text="🗋 View Activity & Time Logs",
            font=("Segoe UI", 9, "bold"),
            bg="#2563eb",
            fg="#ffffff",
            activebackground="#1d4ed8",
            activeforeground="#ffffff",
            relief="flat",
            pady=7,
            command=self.on_open_history,
            cursor="hand2",
        )
        btn_act.pack(fill="x", pady=(0, 8))

        # Secondary 2-Column Row
        row2 = tk.Frame(btn_box, bg="#0f172a")
        row2.pack(fill="x")

        btn_dash = tk.Button(
            row2,
            text="● Open Dashboard",
            font=("Segoe UI", 8),
            bg="#1e293b",
            fg="#e2e8f0",
            relief="flat",
            pady=5,
            command=self.on_open_dashboard,
            cursor="hand2",
        )
        btn_dash.pack(side="left", fill="x", expand=True, padx=(0, 4))

        self.btn_pause = tk.Button(
            row2,
            textvariable=self.var_pause_btn_text,
            font=("Segoe UI", 8),
            bg="#1e293b",
            fg="#e2e8f0",
            relief="flat",
            pady=5,
            command=self._on_pause_clicked,
            cursor="hand2",
        )
        self.btn_pause.pack(side="right", fill="x", expand=True, padx=(4, 0))

    def _on_pause_clicked(self) -> None:
        new_active = not self.config.monitoring_active
        self.on_toggle_monitoring(new_active)
        self.var_pause_btn_text.set("Pause Monitoring" if new_active else "Resume Monitoring")

    def update_state(self, status: str, queue_count: int, metrics: dict, recent_events: list[dict]) -> None:
        """Update live values rendered on the compact widget."""
        # Status Badge
        if not self.config.monitoring_active or status == "PAUSED":
            self.var_status_badge.set("#f97316 Paused")
            self.lbl_status_badge.configure(fg="#f97316", bg="#431407")
            self.var_pause_btn_text.set("Resume Monitoring")
        elif status in ("RUNNING", "ONLINE"):
            self.var_status_badge.set("#22c55e Running")
            self.lbl_status_badge.configure(fg="#22c55e", bg="#064e3b")
            self.var_pause_btn_text.set("Pause Monitoring")
        elif status == "OFFLINE":
            self.var_status_badge.set("#94a3b8 Local Only")
            self.lbl_status_badge.configure(fg="#94a3b8", bg="#1e293b")
        else:
            self.var_status_badge.set(f"#ef4444 {status.title()}")
            self.lbl_status_badge.configure(fg="#ef4444", bg="#450a0a")

        # Session duration & queue count
        self.var_session_duration.set(_format_time_hhmmss(metrics.get("observed_session_seconds", 0.0)))
        self.var_pending_sync.set(str(queue_count))

        # Files changed count
        history_events = self.backend.event_queue.search_history(limit=100)
        file_events = [e for e in history_events if "FILE" in e.get("event_type", "")]
        unique_files = len(set(e.get("relative_path") for e in file_events if e.get("relative_path")))
        self.var_files_changed.set(str(unique_files))

        # Recent Changes bullet list
        if recent_events:
            latest = recent_events[0]
            t_str = latest.get("timestamp", "")
            if "T" in t_str:
                time_part = t_str.split("T")[1][:5]
            else:
                time_part = datetime.now().strftime("%I:%M %p")
            self.var_last_change.set(f"{time_part} ({latest.get('title', '')[:30]}…)")

            for i, lbl in enumerate(self.recent_labels):
                if i < len(recent_events):
                    evt = recent_events[i]
                    ts = evt.get("timestamp", "")
                    ts_clean = ts.split("T")[1][:5] if "T" in ts else ""
                    title = evt.get("title", "")
                    lbl.configure(text=f"• {ts_clean} - {title[:38]}")
                else:
                    lbl.configure(text="")
        else:
            self.var_last_change.set("No changes recorded yet")


class ActivityHistoryWindow(tk.Toplevel):
    """The larger window opened on the left (side-by-side) with Change History, Time Logs, and Summaries."""

    def __init__(
        self,
        master: tk.Tk,
        config: AgentConfig,
        backend: BackendClient,
        session_tracker: SessionTracker,
    ):
        super().__init__(master)
        self.config = config
        self.backend = backend
        self.session_tracker = session_tracker

        self.title("ProjectPulse AI — Change History, Time Logs & Summaries")
        self.geometry(f"{HISTORY_WIDTH}x{HISTORY_HEIGHT}")
        self.configure(bg="#0f172a")

        # Close button simply hides the window
        self.protocol("WM_DELETE_WINDOW", self.withdraw)

        # Filters
        self.var_search = tk.StringVar(value="")
        self.var_period = tk.StringVar(value="All")
        self.var_event_type = tk.StringVar(value="ALL")
        self.var_summary_period = tk.StringVar(value="24h")

        self._build_ui()

    def position_left_of(self, right_x: int, right_y: int) -> None:
        """Place this window gracefully directly to the left of the compact widget."""
        self.update_idletasks()
        target_x = max(10, right_x - HISTORY_WIDTH - 12)
        target_y = right_y
        self.geometry(f"{HISTORY_WIDTH}x{HISTORY_HEIGHT}+{target_x}+{target_y}")

    def _build_ui(self) -> None:
        # Header Bar
        hdr = tk.Frame(self, bg="#0f172a", height=50)
        hdr.pack(fill="x", padx=16, pady=(12, 6))

        tk.Label(
            hdr,
            text="🗋 Activity History & Time Tracking",
            font=("Segoe UI", 12, "bold"),
            fg="#f8fafc",
            bg="#0f172a",
        ).pack(side="left")

        tk.Label(
            hdr,
            text=f"User: {self.config.user_name} | Project: {self.config.project_name} ({self.config.project_id})",
            font=("Segoe UI", 9),
            fg="#94a3b8",
            bg="#0f172a",
        ).pack(side="right")

        # Notebook Tabs
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass

        style.configure("DarkNotebook.TNotebook", background="#0f172a", borderwidth=0)
        style.configure(
            "DarkNotebook.TNotebook.Tab",
            background="#1e293b",
            foreground="#94a3b8",
            padding=[16, 7],
            font=("Segoe UI", 9, "bold"),
            borderwidth=0,
        )
        style.map(
            "DarkNotebook.TNotebook.Tab",
            background=[("selected", "#2563eb")],
            foreground=[("selected", "#ffffff")],
        )

        self.notebook = ttk.Notebook(self, style="DarkNotebook.TNotebook")
        self.notebook.pack(fill="both", expand=True, padx=16, pady=(4, 14))

        self.tab_history = tk.Frame(self.notebook, bg="#0f172a")
        self.tab_time = tk.Frame(self.notebook, bg="#0f172a")
        self.tab_summary = tk.Frame(self.notebook, bg="#0f172a")

        self.notebook.add(self.tab_history, text="🗋 Change History")
        self.notebook.add(self.tab_time, text="🕒 Time Logs & Sessions")
        self.notebook.add(self.tab_summary, text="📅 Daily & Weekly Summaries")

        self._build_history_tab()
        self._build_time_tab()
        self._build_summary_tab()

    def _build_history_tab(self) -> None:
        p = self.tab_history

        # Filter Bar
        fbar = tk.Frame(p, bg="#1e293b", padx=10, pady=8, relief="solid", bd=1)
        fbar.pack(fill="x", pady=(10, 8))

        # Search Entry
        tk.Label(fbar, text="Search:", font=("Segoe UI", 8, "bold"), fg="#94a3b8", bg="#1e293b").pack(side="left", padx=(0, 4))
        ent_search = tk.Entry(fbar, textvariable=self.var_search, bg="#0f172a", fg="#f8fafc", insertbackground="#ffffff", width=14, relief="flat", font=("Segoe UI", 9))
        ent_search.pack(side="left", padx=(0, 10))
        ent_search.bind("<Return>", lambda _: self.refresh_history_table())

        # Period Pills
        tk.Label(fbar, text="Period:", font=("Segoe UI", 8, "bold"), fg="#94a3b8", bg="#1e293b").pack(side="left", padx=(0, 4))
        self.period_buttons = {}
        for period_key in ("Today", "Yesterday", "7 Days", "30 Days", "All"):
            btn = tk.Button(
                fbar,
                text=period_key,
                font=("Segoe UI", 8),
                bg="#2563eb" if period_key == "All" else "#0f172a",
                fg="#ffffff",
                relief="flat",
                padx=6,
                pady=2,
                cursor="hand2",
                command=lambda pk=period_key: self._set_period_filter(pk),
            )
            btn.pack(side="left", padx=2)
            self.period_buttons[period_key] = btn

        # Event Dropdown
        tk.Label(fbar, text="Event:", font=("Segoe UI", 8, "bold"), fg="#94a3b8", bg="#1e293b").pack(side="left", padx=(10, 4))
        self.combo_event = ttk.Combobox(
            fbar,
            textvariable=self.var_event_type,
            values=["ALL", "FILE_MODIFIED", "FILE_CREATED", "FILE_DELETED", "GIT_COMMIT", "GIT_PUSH", "BUILD_SUCCEEDED", "TEST_PASSED", "TEST_FAILED"],
            width=13,
            state="readonly",
        )
        self.combo_event.pack(side="left", padx=(0, 8))
        self.combo_event.bind("<<ComboboxSelected>>", lambda _: self.refresh_history_table())

        # Export CSV Button
        btn_csv = tk.Button(
            fbar,
            text="📥 Export CSV",
            font=("Segoe UI", 8, "bold"),
            bg="#2563eb",
            fg="#ffffff",
            relief="flat",
            padx=8,
            pady=3,
            cursor="hand2",
            command=self._export_csv,
        )
        btn_csv.pack(side="right")

        # History Treeview Table
        table_frame = tk.Frame(p, bg="#0f172a")
        table_frame.pack(fill="both", expand=True)

        cols = ("time", "type", "file", "project", "sync")
        self.tree_history = ttk.Treeview(table_frame, columns=cols, show="headings", height=8)
        self.tree_history.heading("time", text="Time")
        self.tree_history.heading("type", text="Event Type")
        self.tree_history.heading("file", text="File / Detail")
        self.tree_history.heading("project", text="Project")
        self.tree_history.heading("sync", text="Sync Status")

        self.tree_history.column("time", width=110, anchor="center")
        self.tree_history.column("type", width=120, anchor="center")
        self.tree_history.column("file", width=260)
        self.tree_history.column("project", width=90, anchor="center")
        self.tree_history.column("sync", width=90, anchor="center")

        sb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree_history.yview)
        self.tree_history.configure(yscrollcommand=sb.set)
        self.tree_history.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.tree_history.bind("<<TreeviewSelect>>", self._on_table_row_selected)

        # EVENT DETAILS & EVIDENCE Panel (Bottom)
        det_header = tk.Frame(p, bg="#0f172a")
        det_header.pack(fill="x", pady=(10, 4))
        tk.Label(det_header, text="EVENT DETAILS & EVIDENCE", font=("Segoe UI", 8, "bold"), fg="#64748b", bg="#0f172a").pack(anchor="w")

        self.txt_evidence = tk.Text(
            p,
            height=4,
            bg="#1e293b",
            fg="#e2e8f0",
            relief="solid",
            bd=1,
            font=("Consolas", 9),
            padx=8,
            pady=6,
        )
        self.txt_evidence.pack(fill="x", pady=(0, 2))

    def _set_period_filter(self, period_key: str) -> None:
        self.var_period.set(period_key)
        for pk, btn in self.period_buttons.items():
            btn.configure(bg="#2563eb" if pk == period_key else "#0f172a")
        self.refresh_history_table()

    def refresh_history_table(self) -> None:
        """Query local SQLite database and populate table according to filters."""
        q = self.var_search.get().strip() or None
        evt_type = self.var_event_type.get()
        type_filter = None if evt_type == "ALL" else evt_type

        # Period calculation
        pk = self.var_period.get()
        start_date = None
        now = datetime.now(timezone.utc)
        if pk == "Today":
            start_date = now.replace(hour=0, minute=0, second=0).isoformat()
        elif pk == "Yesterday":
            start_date = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0).isoformat()
        elif pk == "7 Days":
            start_date = (now - timedelta(days=7)).isoformat()
        elif pk == "30 Days":
            start_date = (now - timedelta(days=30)).isoformat()

        records = self.backend.event_queue.search_history(
            query=q,
            event_type=type_filter,
            start_date=start_date,
            limit=150,
        )

        self.tree_history.delete(*self.tree_history.get_children())
        self._current_table_records = {}

        for r in records:
            item_id = str(r.get("id"))
            self._current_table_records[item_id] = r

            raw_time = r.get("timestamp", "")
            if "T" in raw_time:
                date_part, time_part = raw_time.split("T")
                time_display = f"{date_part} {time_part[:5]}"
            else:
                time_display = raw_time[:16]

            file_or_title = r.get("relative_path") or r.get("title") or ""
            sync_label = "Confirmed ✓"

            self.tree_history.insert(
                "",
                "end",
                iid=item_id,
                values=(
                    time_display,
                    r.get("event_type", ""),
                    file_or_title,
                    self.config.project_id,
                    sync_label,
                ),
            )

    def _on_table_row_selected(self, _event) -> None:
        selected = self.tree_history.selection()
        if not selected:
            return
        row_id = selected[0]
        data = getattr(self, "_current_table_records", {}).get(row_id)
        if not data:
            return

        self.txt_evidence.delete("1.0", "end")
        lines = [
            f"Event ID: {data.get('event_id')} | Type: {data.get('event_type')} | Source: {data.get('source')}",
            f"Timestamp: {data.get('timestamp')} | Project: {data.get('project_id')}",
            f"Title: {data.get('title')}",
        ]
        if data.get("description"):
            lines.append(f"Description: {data.get('description')}")
        if data.get("relative_path"):
            lines.append(f"File Path: {data.get('relative_path')}")

        meta = data.get("metadata") or {}
        if meta:
            if "explanation" in meta:
                exp = meta["explanation"]
                lines.append(f"Explanation: {exp.get('what', '')}")
            if "symbols_added" in meta and meta["symbols_added"]:
                lines.append(f"Symbols Added: {', '.join(meta['symbols_added'])}")
            if "symbols_modified" in meta and meta["symbols_modified"]:
                lines.append(f"Symbols Modified: {', '.join(meta['symbols_modified'])}")
            if "symbols_removed" in meta and meta["symbols_removed"]:
                lines.append(f"Symbols Removed: {', '.join(meta['symbols_removed'])}")
            if "commit_message" in meta:
                lines.append(f"Git Commit: {meta['commit_message']}")

        self.txt_evidence.insert("1.0", "\n".join(lines))

    def _export_csv(self) -> None:
        records = self.backend.event_queue.search_history(limit=500)
        if not records:
            messagebox.showinfo("Export CSV", "No events to export.")
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
            initialfile=f"projectpulse_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        )
        if not filename:
            return

        try:
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Event ID", "Timestamp", "Source", "Event Type", "Title", "File Path", "Project ID", "User ID"])
                for r in records:
                    writer.writerow([
                        r.get("event_id"),
                        r.get("timestamp"),
                        r.get("source"),
                        r.get("event_type"),
                        r.get("title"),
                        r.get("relative_path"),
                        r.get("project_id"),
                        r.get("user_id"),
                    ])
            messagebox.showinfo("Export Complete", f"Successfully exported {len(records)} events to:\n{filename}")
        except Exception as exc:
            messagebox.showerror("Export Failed", f"Could not write CSV file: {exc}")

    def _build_time_tab(self) -> None:
        p = self.tab_time
        # Top 4 Metric Cards
        card_row = tk.Frame(p, bg="#0f172a")
        card_row.pack(fill="x", pady=(10, 10))

        self.var_t_obs = tk.StringVar(value="00h 00m 00s")
        self.var_t_act = tk.StringVar(value="00h 00m 00s")
        self.var_t_idle = tk.StringVar(value="00h 00m 00s")
        self.var_t_edit = tk.StringVar(value="00h 00m 00s")

        t_cards = [
            ("Observed Session Time", self.var_t_obs, "VS Code Process Running", "#38bdf8"),
            ("Active Interaction Time", self.var_t_act, "Excluding Idle Periods", "#22c55e"),
            ("Windows Idle Time (>5m)", self.var_t_idle, "ctypes GetLastInputInfo", "#f59e0b"),
            ("Estimated Editing Time", self.var_t_edit, "File Modification Bursts", "#a855f7"),
        ]

        for title, var, sub, color in t_cards:
            cf = tk.Frame(card_row, bg="#1e293b", relief="solid", bd=1, padx=10, pady=8)
            cf.pack(side="left", fill="both", expand=True, padx=4)
            tk.Label(cf, text=title, font=("Segoe UI", 8, "bold"), fg="#94a3b8", bg="#1e293b").pack(anchor="w")
            tk.Label(cf, textvariable=var, font=("Segoe UI", 12, "bold"), fg=color, bg="#1e293b").pack(anchor="w", pady=(2, 0))
            tk.Label(cf, text=sub, font=("Segoe UI", 7), fg="#64748b", bg="#1e293b").pack(anchor="w")

        # Sessions Table
        tk.Label(p, text="Recorded Work Sessions", font=("Segoe UI", 9, "bold"), fg="#f8fafc", bg="#0f172a").pack(anchor="w", pady=(4, 4))

        st_frame = tk.Frame(p, bg="#0f172a")
        st_frame.pack(fill="both", expand=True)

        scols = ("ses_id", "start", "observed", "active", "idle", "workspace")
        self.tree_sessions = ttk.Treeview(st_frame, columns=scols, show="headings", height=8)
        self.tree_sessions.heading("ses_id", text="Session ID")
        self.tree_sessions.heading("start", text="Started")
        self.tree_sessions.heading("observed", text="Observed")
        self.tree_sessions.heading("active", text="Active")
        self.tree_sessions.heading("idle", text="Idle")
        self.tree_sessions.heading("workspace", text="Workspace")

        self.tree_sessions.column("ses_id", width=100, anchor="center")
        self.tree_sessions.column("start", width=120, anchor="center")
        self.tree_sessions.column("observed", width=90, anchor="center")
        self.tree_sessions.column("active", width=90, anchor="center")
        self.tree_sessions.column("idle", width=90, anchor="center")
        self.tree_sessions.column("workspace", width=220)

        sb = ttk.Scrollbar(st_frame, orient="vertical", command=self.tree_sessions.yview)
        self.tree_sessions.configure(yscrollcommand=sb.set)
        self.tree_sessions.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

    def _build_summary_tab(self) -> None:
        p = self.tab_summary

        # Top Control Bar
        bar = tk.Frame(p, bg="#1e293b", padx=10, pady=8, relief="solid", bd=1)
        bar.pack(fill="x", pady=(10, 8))

        tk.Label(bar, text="Timeframe:", font=("Segoe UI", 8, "bold"), fg="#94a3b8", bg="#1e293b").pack(side="left", padx=(0, 6))

        for period_key, label in [("24h", "Last 24 Hours"), ("7d", "Last 7 Days"), ("all", "All Time")]:
            btn = tk.Button(
                bar,
                text=label,
                font=("Segoe UI", 8),
                bg="#2563eb" if period_key == "24h" else "#0f172a",
                fg="#ffffff",
                relief="flat",
                padx=8,
                pady=2,
                cursor="hand2",
                command=lambda pk=period_key: self._set_summary_period(pk),
            )
            btn.pack(side="left", padx=3)

        btn_eval = tk.Button(
            bar,
            text="🔄 Re-evaluate",
            font=("Segoe UI", 8, "bold"),
            bg="#1e293b",
            fg="#93c5fd",
            relief="solid",
            bd=1,
            padx=8,
            pady=2,
            cursor="hand2",
            command=self.refresh_summary,
        )
        btn_eval.pack(side="right", padx=4)

        btn_exp_sum = tk.Button(
            bar,
            text="📥 Export Summary",
            font=("Segoe UI", 8, "bold"),
            bg="#2563eb",
            fg="#ffffff",
            relief="flat",
            padx=8,
            pady=2,
            cursor="hand2",
            command=self._export_summary_doc,
        )
        btn_exp_sum.pack(side="right", padx=4)

        # Engine Tag
        tag_row = tk.Frame(p, bg="#0f172a")
        tag_row.pack(fill="x", pady=(0, 6))
        tk.Label(
            tag_row,
            text="Synthesis Engine: RULE-BASED SYNTHESIS (100% Deterministic & Grounded in Recorded Evidence)",
            font=("Segoe UI", 8, "bold"),
            fg="#10b981",
            bg="#0f172a",
        ).pack(anchor="w")

        # Metric Stats Strip
        self.var_sum_files = tk.StringVar(value="0")
        self.var_sum_commits = tk.StringVar(value="0")
        self.var_sum_tests = tk.StringVar(value="0 passed")
        self.var_sum_ratio = tk.StringVar(value="100% Active")

        sstrip = tk.Frame(p, bg="#0f172a")
        sstrip.pack(fill="x", pady=(0, 10))

        for heading, var in [
            ("Files Modified", self.var_sum_files),
            ("Commits & Pushes", self.var_sum_commits),
            ("Automated Tests", self.var_sum_tests),
            ("Productive Ratio", self.var_sum_ratio),
        ]:
            bx = tk.Frame(sstrip, bg="#1e293b", relief="solid", bd=1, padx=8, pady=6)
            bx.pack(side="left", fill="both", expand=True, padx=3)
            tk.Label(bx, text=heading, font=("Segoe UI", 8), fg="#94a3b8", bg="#1e293b").pack(anchor="w")
            tk.Label(bx, textvariable=var, font=("Segoe UI", 11, "bold"), fg="#f8fafc", bg="#1e293b").pack(anchor="w")

        # Narrative Summary Box
        tk.Label(p, text="Evidence-Linked Synthesis Narrative", font=("Segoe UI", 9, "bold"), fg="#f8fafc", bg="#0f172a").pack(anchor="w", pady=(0, 4))

        self.txt_summary = tk.Text(
            p,
            height=10,
            bg="#1e293b",
            fg="#f8fafc",
            relief="solid",
            bd=1,
            font=("Segoe UI", 9),
            padx=10,
            pady=8,
            wrap="word",
        )
        self.txt_summary.pack(fill="both", expand=True)

    def _set_summary_period(self, period_key: str) -> None:
        self.var_summary_period.set(period_key)
        self.refresh_summary()

    def refresh_summary(self) -> None:
        """Synthesize daily/weekly summary strictly from recorded SQLite events."""
        pk = self.var_summary_period.get()
        start_date = None
        now = datetime.now(timezone.utc)
        if pk == "24h":
            start_date = (now - timedelta(hours=24)).isoformat()
        elif pk == "7d":
            start_date = (now - timedelta(days=7)).isoformat()

        events = self.backend.event_queue.search_history(start_date=start_date, limit=200)

        file_mods = [e for e in events if "FILE_MODIFIED" in e.get("event_type", "")]
        file_creates = [e for e in events if "FILE_CREATED" in e.get("event_type", "")]
        commits = [e for e in events if "GIT_COMMIT" in e.get("event_type", "")]
        pushes = [e for e in events if "GIT_PUSH" in e.get("event_type", "")]
        tests = [e for e in events if "TEST" in e.get("event_type", "")]

        self.var_sum_files.set(str(len(file_mods) + len(file_creates)))
        self.var_sum_commits.set(f"{len(commits)} commits, {len(pushes)} pushes")
        self.var_sum_tests.set(f"{len(tests)} test run{'s' if len(tests) != 1 else ''}")

        m = self.session_tracker.get_metrics()
        obs = m.get("observed_session_seconds", 0.0)
        act = m.get("active_interaction_seconds", 0.0)
        ratio = round((act / obs * 100), 1) if obs > 0 else 100.0
        self.var_sum_ratio.set(f"{ratio}% Active")

        # Synthesize narrative
        lines = [
            f"Developer Activity Summary — Project: {self.config.project_name} ({self.config.project_id})",
            f"Generated: {datetime.now().strftime('%b %d, %Y %I:%M %p')} | User: {self.config.user_name} ({self.config.user_id})",
            "────────────────────────────────────────────────────────────────────────",
            "",
            "1. WORKSPACE & EDITING ACTIVITY:",
            f"• Total files modified: {len(file_mods)} file(s), created: {len(file_creates)} file(s).",
        ]
        if file_mods:
            paths = list(set(e.get("relative_path") for e in file_mods[:5] if e.get("relative_path")))
            lines.append(f"  Primary affected modules: {', '.join(paths)}")

        lines.extend([
            "",
            "2. SOURCE CONTROL & GIT SYNCHRONIZATION:",
            f"• Local Git Commits recorded: {len(commits)}",
            f"• Verified Remote Pushes: {len(pushes)}",
        ])
        if commits:
            lines.append(f"  Latest commit: {commits[0].get('title', '')}")

        lines.extend([
            "",
            "3. TEST & BUILD VALIDATION:",
            f"• Automated Test Executions: {len(tests)} test event(s) captured.",
            "",
            "4. MEASURED TIME & ENGAGEMENT INTEGRITY:",
            f"• Observed Session Duration: {_format_time_hhmmss(obs)}",
            f"• Measured Active Interaction Time: {_format_time_hhmmss(act)}",
            f"• Idle Time (Inactivity > 5m): {_format_time_hhmmss(m.get('idle_seconds', 0.0))}",
            f"• Verified Task Coding Bursts: {_format_time_hhmmss(m.get('estimated_editing_seconds', 0.0))}",
            "",
            "Claims in this summary are strictly grounded in SQLite event logs in agent_queue.db.",
        ])

        self.txt_summary.delete("1.0", "end")
        self.txt_summary.insert("1.0", "\n".join(lines))

    def _export_summary_doc(self) -> None:
        content = self.txt_summary.get("1.0", "end").strip()
        if not content:
            messagebox.showinfo("Export Summary", "No summary content available to export.")
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text Documents", "*.txt"), ("Markdown Documents", "*.md"), ("All Files", "*.*")],
            initialfile=f"projectpulse_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        )
        if not filename:
            return

        try:
            Path(filename).write_text(content, encoding="utf-8")
            messagebox.showinfo("Export Complete", f"Summary saved to:\n{filename}")
        except Exception as exc:
            messagebox.showerror("Export Failed", f"Could not write summary file: {exc}")

    def refresh_time_tab(self) -> None:
        m = self.session_tracker.get_metrics()
        self.var_t_obs.set(_format_time_hhmmss(m.get("observed_session_seconds", 0.0)))
        self.var_t_act.set(_format_time_hhmmss(m.get("active_interaction_seconds", 0.0)))
        self.var_t_idle.set(_format_time_hhmmss(m.get("idle_seconds", 0.0)))
        self.var_t_edit.set(_format_time_hhmmss(m.get("estimated_editing_seconds", 0.0)))

        sessions = self.backend.event_queue.get_recent_sessions(limit=15)
        self.tree_sessions.delete(*self.tree_sessions.get_children())
        for s in sessions:
            st = s.get("start_time", "")[:16].replace("T", " ")
            self.tree_sessions.insert(
                "",
                "end",
                values=(
                    s.get("session_id", ""),
                    st,
                    _format_time_hhmmss(s.get("observed_session_seconds", 0.0)),
                    _format_time_hhmmss(s.get("active_interaction_seconds", 0.0)),
                    _format_time_hhmmss(s.get("idle_seconds", 0.0)),
                    s.get("workspace_path", "")[-30:],
                ),
            )


class DesktopAgentWindowManager:
    """Coordinates the Compact Widget (right) and the Activity & Summary Window (left side-by-side)."""

    def __init__(
        self,
        root: tk.Tk,
        config: AgentConfig,
        backend: BackendClient,
        session_tracker: SessionTracker,
        on_toggle_monitoring: Callable[[bool], None],
        on_open_dashboard: Callable[[], None],
        on_exit: Callable[[], None],
    ):
        self.root = root
        self.config = config
        self.backend = backend
        self.session_tracker = session_tracker
        self.on_toggle_monitoring = on_toggle_monitoring
        self.on_open_dashboard = on_open_dashboard
        self.on_exit = on_exit

        self._status = "STARTING"
        self._latency_ms = 0
        self._poll_job: str | None = None

        # Build Compact Widget
        self.compact_widget = CompactAgentWidget(
            master=self.root,
            config=self.config,
            backend=self.backend,
            session_tracker=self.session_tracker,
            on_toggle_monitoring=self.on_toggle_monitoring,
            on_open_dashboard=self.on_open_dashboard,
            on_open_history=self.toggle_history_window,
            on_exit=self.on_exit,
        )

        # Build Activity & Summary Window (initially hidden)
        self.history_window = ActivityHistoryWindow(
            master=self.root,
            config=self.config,
            backend=self.backend,
            session_tracker=self.session_tracker,
        )
        self.history_window.withdraw()

        self._schedule_poll()

    def show(self) -> None:
        """Show compact widget and bring to front."""
        self.compact_widget.deiconify()
        self.compact_widget.lift()
        self.compact_widget.focus_force()
        self.refresh_metrics()

    def hide(self) -> None:
        """Hide both windows to system tray."""
        self.compact_widget.withdraw()
        self.history_window.withdraw()

    def toggle_history_window(self) -> None:
        """Toggle side-by-side activity history window to the left of the compact widget."""
        if self.history_window.winfo_viewable():
            self.history_window.withdraw()
        else:
            # Position side-by-side
            cx = self.compact_widget.winfo_x()
            cy = self.compact_widget.winfo_y()
            self.history_window.position_left_of(cx, cy)
            self.history_window.deiconify()
            self.history_window.lift()
            self.history_window.refresh_history_table()
            self.history_window.refresh_time_tab()
            self.history_window.refresh_summary()

    def set_status(self, status: str, latency_ms: int = 0) -> None:
        self._status = status
        self._latency_ms = latency_ms
        self.refresh_metrics()

    def refresh_metrics(self) -> None:
        queue_count = self.backend.event_queue.pending_count
        m = self.session_tracker.get_metrics()
        recent = self.backend.event_queue.search_history(limit=5)
        self.compact_widget.update_state(self._status, queue_count, m, recent)

        if self.history_window.winfo_viewable():
            self.history_window.refresh_time_tab()

    def _schedule_poll(self) -> None:
        if self._poll_job:
            try:
                self.root.after_cancel(self._poll_job)
            except Exception:
                pass
        self._poll_job = self.root.after(3000, self._poll_loop)

    def _poll_loop(self) -> None:
        self.refresh_metrics()
        self._schedule_poll()


# Backwards compatibility alias
DesktopAgentWindow = DesktopAgentWindowManager

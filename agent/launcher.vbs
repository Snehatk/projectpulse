Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "C:\Users\kingn\OneDrive\Desktop\projectpulse\projectpulse"
WshShell.Run """C:\Users\kingn\OneDrive\Desktop\projectpulse\projectpulse\.venv\Scripts\python.exe"" -m agent.main", 0, False

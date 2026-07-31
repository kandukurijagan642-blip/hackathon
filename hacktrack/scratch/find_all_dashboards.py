import os

search_dir = r"c:\Users\ADMIN"
print("Scanning C:\\Users\\ADMIN for all dashboard.html files...")
matches = []
for root, dirs, files in os.walk(search_dir):
    # Skip AppData, virtualenvs, .gemini, etc. to prevent long scans
    if any(p in root.lower() for p in ["appdata", ".gemini", "node_modules", "site-packages", "venv", ".git", ".idea", ".vscode"]):
        continue
    for file in files:
        if file == "dashboard.html":
            path = os.path.join(root, file)
            try:
                size = os.path.getsize(path)
                matches.append((path, size))
                print(f"Found: {path} (Size: {size} bytes)")
            except:
                pass

print(f"\nScan completed. Found {len(matches)} files.")

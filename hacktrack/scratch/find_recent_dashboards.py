import os

target_folders = [
    r"c:\Users\ADMIN\Documents",
    r"c:\Users\ADMIN\Downloads",
    r"c:\Users\ADMIN\Desktop"
]

print("Scanning targeted folders for dashboard.html files...")
matches = []
for folder in target_folders:
    if not os.path.exists(folder):
        continue
    for root, dirs, files in os.walk(folder):
        if any(p in root.lower() for p in ["appdata", ".gemini", "node_modules", "venv", ".git"]):
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

print(f"\nTargeted scan completed. Found {len(matches)} files.")

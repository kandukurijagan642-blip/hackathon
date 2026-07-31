import os

workspace = r"c:\Users\ADMIN\Documents\hackathon"
print("Scanning workspace for dashboard.html files:")
for root, dirs, files in os.walk(workspace):
    for file in files:
        if file == "dashboard.html":
            path = os.path.join(root, file)
            print(f"Path: {path}")
            print(f"Size: {os.path.getsize(path)} bytes")
            print("--- First 30 lines: ---")
            with open(path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in lines[:30]:
                    print(line.strip())
            print("==================================\n")

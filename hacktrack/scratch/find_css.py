import os

workspace = r"c:\Users\ADMIN\Documents\hackathon"
print("Scanning workspace for CSS files:")
for root, dirs, files in os.walk(workspace):
    for file in files:
        if file.endswith(".css"):
            path = os.path.join(root, file)
            print(f"Path: {path}")
            print(f"Size: {os.path.getsize(path)} bytes")
            print("==================================\n")

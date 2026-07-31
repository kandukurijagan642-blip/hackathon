path = r"c:\Users\ADMIN\Documents\hackathon\hacktrack\templates\organizer\dashboard.html"
with open(path, "r", encoding="utf-8") as f:
    lines = f.readlines()

for idx in range(29, min(110, len(lines))):
    print(f"{idx+1}: {lines[idx]}", end="")

path = r"c:\Users\ADMIN\Documents\hackathon\hacktrack\templates\organizer\dashboard.html"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

print(f"Total occurrences of 'Round 1': {content.count('Round 1')}")
# Print the lines containing 'Round 1' with line numbers
lines = content.splitlines()
for idx, line in enumerate(lines):
    if "Round 1" in line:
        print(f"Line {idx+1}: {line.strip()}")

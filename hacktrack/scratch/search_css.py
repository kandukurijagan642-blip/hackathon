path = r"c:\Users\ADMIN\Documents\hackathon\hacktrack\static\css\style.css"
with open(path, "r", encoding="utf-8") as f:
    css = f.read()

print("Is 'btn-xs' in style.css?", "btn-xs" in css)
# If it exists, find lines containing it
lines = css.splitlines()
for idx, line in enumerate(lines):
    if "btn-xs" in line:
        print(f"Line {idx+1}: {line.strip()}")

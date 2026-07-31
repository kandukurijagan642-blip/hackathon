path = r"c:\Users\ADMIN\Documents\hackathon\hacktrack\models.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Locate SystemSetting class
start = content.find("class SystemSetting")
if start != -1:
    print(content[start:start+1000])
else:
    print("SystemSetting class not found!")

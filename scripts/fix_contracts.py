import re
with open('src/eitaa_bridge/providers/contracts.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = re.sub(r'if hint and not any\(marker in hint.*?\):', 'if False:', content)
with open('src/eitaa_bridge/providers/contracts.py', 'w', encoding='utf-8') as f:
    f.write(content)

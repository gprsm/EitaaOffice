with open('ui/src/App.tsx', 'r', encoding='utf-8') as f:
    content = f.read()
idx = content.find("function initials")
print(content[idx-200:idx])

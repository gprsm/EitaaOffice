with open('ui/src/App.tsx', 'r', encoding='utf-8') as f:
    content = f.read()
idx = content.find("date-range/sync")
print(content[idx:idx+800])

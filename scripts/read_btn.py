with open('ui/src/utils/helpers.tsx', 'r', encoding='utf-8') as f:
    content = f.read()
idx = content.find("SyncRounded")
print(content[idx-50:idx+250])

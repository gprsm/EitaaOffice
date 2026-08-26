with open('ui/src/App.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

idx = content.find("const toggleFavorite = async (item: DialogItem) => {")
print(content[idx:idx+500])

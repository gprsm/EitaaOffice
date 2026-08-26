import re

with open('ui/src/App.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

pattern = r"(const toggleFavorite = async \(item: DialogItem\) => \{)([\s\S]*?)(\n  \}\n)"

replacement = r'''\1
    const originalDialogs = dialogs;
    const targetState = !item.favorite;
    applyDialogs(dialogs.map(entry => entry.peer_key === item.peer_key ? { ...entry, favorite: targetState } : entry));
    try {
      const response = await api<{ dialog: DialogItem }>('POST', '/api/v1/dialogs/favorite', { site_key: siteKey, peer_key: item.peer_key, favorite: targetState })
      applyDialogs(originalDialogs.map(entry => entry.peer_key === item.peer_key ? response.dialog : entry))
    } catch (e) {
      applyDialogs(originalDialogs);
      toast.error(e instanceof Error ? e.message : 'خطا در ثبت منتخب')
    }\3'''

new_content = re.sub(pattern, replacement, content, count=1)

with open('ui/src/App.tsx', 'w', encoding='utf-8') as f:
    f.write(new_content)
print("SUCCESS")

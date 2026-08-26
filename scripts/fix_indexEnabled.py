with open('ui/src/App.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'indexEnabled={Boolean(dialog && dialog.favorite)}',
    'indexEnabled={Boolean(dialog && (dialog.display_kind === \"channel\" || dialog.display_kind === \"group\") && tab === \"favorite\")}'
)

with open('ui/src/App.tsx', 'w', encoding='utf-8') as f:
    f.write(content)

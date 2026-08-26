with open('ui/src/ConversationListPage.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

old_sx = "sx={{ minHeight: 68, px: 1.25, gap: 0.5, borderBottom: 1, borderColor: 'divider', '&.Mui-selected': { borderInlineStart: 3, borderInlineStartColor: 'primary.main' } }}"
new_sx = "sx={{ minHeight: 68, px: 1.25, gap: 0.5, borderBottom: 1, borderColor: 'divider', '&.Mui-selected': { bgcolor: 'action.selected', borderInlineStart: 4, borderInlineStartColor: 'text.secondary' } }}"

content = content.replace(old_sx, new_sx)
with open('ui/src/ConversationListPage.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("UPDATED STYLING")

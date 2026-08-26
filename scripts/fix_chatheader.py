with open('ui/src/ChatHeader.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Add padding to the Toolbar to prevent icons from hiding under the FAB on mobile
old_sx = '''    sx={{
      minHeight: 'unset !important',
      px: { xs: 0.75, sm: 1.5 },
      py: 0.75,
      gap: 1,
      flexWrap: 'wrap',
      borderBottom: 1,
      borderColor: 'divider',
      bgcolor: 'background.paper',
    }}'''

new_sx = '''    sx={{
      minHeight: 'unset !important',
      px: { xs: 0.75, sm: 1.5 },
      paddingInlineEnd: { xs: '64px', md: '12px' }, /* Prevent hiding under floating FAB */
      py: 0.75,
      gap: 1,
      flexWrap: 'wrap',
      borderBottom: 1,
      borderColor: 'divider',
      bgcolor: 'background.paper',
    }}'''

content = content.replace(old_sx, new_sx)

with open('ui/src/ChatHeader.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("FIXED PADDING")

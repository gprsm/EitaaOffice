with open('ui/src/App.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

old_str = "zIndex: theme => theme.zIndex.drawer + 1, bgcolor: 'rgba(0,0,0,.42)', backdropFilter: 'blur(1px)'"
new_str = "zIndex: theme => theme.zIndex.drawer - 1, bgcolor: 'rgba(0,0,0,.42)', backdropFilter: 'blur(1px)'"

content = content.replace(old_str, new_str)
with open('ui/src/App.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("FIXED ZINDEX")

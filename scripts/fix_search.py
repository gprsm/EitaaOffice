with open('ui/src/HeaderMessageSearch.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('''    const handleScroll = () => {
      setExpanded(false)
    }''', '')

content = content.replace("document.addEventListener('scroll', handleScroll, { passive: true, capture: true })", '')
content = content.replace("document.removeEventListener('scroll', handleScroll, { capture: true })", '')

with open('ui/src/HeaderMessageSearch.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("FIXED SEARCH")

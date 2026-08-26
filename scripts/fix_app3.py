with open('ui/src/App.tsx', 'r', encoding='utf-8') as f:
    content = f.read()
content = content.replace("import {\nimport {\n", "import {\n")
with open('ui/src/App.tsx', 'w', encoding='utf-8') as f:
    f.write(content)

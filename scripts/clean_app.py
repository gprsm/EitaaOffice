import re

with open('ui/src/App.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

bad_line = "{ FormEvent, lazy, ReactNode, Suspense, useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'\n"

if bad_line in content:
    content = content.replace(bad_line, "")

# Remove duplicate imports
def remove_duplicate_lines(text):
    lines = text.split('\n')
    new_lines = []
    seen = set()
    for line in lines:
        if line.startswith("import ") and line in seen:
            continue
        if line.startswith("import "):
            seen.add(line)
        new_lines.append(line)
    return '\n'.join(new_lines)

# Wait, the duplicate imports are exactly the same?
with open('ui/src/App.tsx', 'w', encoding='utf-8') as f:
    f.write(remove_duplicate_lines(content))
print("CLEANED")

import re

with open('ui/src/App.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update function signature
old_func = "const loadFromJalaliDate = useCallback(async (selectedValue?: string, selectedMode?: 'day' | 'from') => {"
new_func = "const loadFromJalaliDate = useCallback(async (selectedValue?: string, selectedMode?: 'day' | 'from', forceSync?: boolean) => {"
if old_func in content:
    content = content.replace(old_func, new_func)

# 2. Update logic
pattern = r'(let source = \'[^\']+\'\s*if \(\!response\.messages\.length\))'
match = re.search(pattern, content)
if match:
    old_logic = match.group(1)
    new_logic = old_logic.replace('if (!response.messages.length)', 'if (!response.messages.length || forceSync) { if (forceSync) toast.info("در حال همگام‌سازی عمیق با سرور ایتا... (این فرآیند ممکن است کمی طول بکشد)");')
    # wait, we need to match the brace {
    
pattern = r'(let source = \'[^\']+\'\s*if \(\!response\.messages\.length\) \{)'
match = re.search(pattern, content)
if match:
    old_logic = match.group(1)
    new_logic = old_logic.replace('if (!response.messages.length) {', 'if (!response.messages.length || forceSync) {\n          if (forceSync) toast.info("در حال همگام‌سازی عمیق با سرور ایتا... (لطفاً منتظر بمانید)");')
    content = content.replace(old_logic, new_logic)

# 3. Update call in component
old_call = "onSelect={(value, mode) => void loadFromJalaliDate(value, mode)}"
new_call = "onSelect={(value, mode, forceSync) => void loadFromJalaliDate(value, mode, forceSync)}"
if old_call in content:
    content = content.replace(old_call, new_call)

with open('ui/src/App.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("FIXED APP")

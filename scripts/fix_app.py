with open('ui/src/App.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

old_func = "const loadFromJalaliDate = useCallback(async (selectedValue?: string, selectedMode?: 'day' | 'from') => {"
new_func = "const loadFromJalaliDate = useCallback(async (selectedValue?: string, selectedMode?: 'day' | 'from', forceSync?: boolean) => {"
content = content.replace(old_func, new_func)

old_logic = '''        let source = 'حافظه محلی'
        if (!response.messages.length) {
          await api('POST', '/api/v1/messages/date-range/sync', {'''

new_logic = '''        let source = 'حافظه محلی'
        if (!response.messages.length || forceSync) {
          if (forceSync) toast.info('در حال همگام‌سازی عمیق با سرور ایتا... (این فرآیند ممکن است کمی طول بکشد)')
          await api('POST', '/api/v1/messages/date-range/sync', {'''

content = content.replace(old_logic, new_logic)

old_call = "onSelect={(value, mode) => void loadFromJalaliDate(value, mode)}"
new_call = "onSelect={(value, mode, forceSync) => void loadFromJalaliDate(value, mode, forceSync)}"
content = content.replace(old_call, new_call)

with open('ui/src/App.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("FIXED APP")

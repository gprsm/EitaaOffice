import re

with open('ui/src/utils/helpers.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the specific stack
pattern = r'(<Stack direction="row" justifyContent="space-between">\s*<Button size="small" onClick=\{\(\) => \{ setYear\(now\.year\); setMonth\(now\.month\) \}\}>.*?</Button>\s*\{props\.value && <Button size="small" color="error".*?</Button>\}\s*</Stack>)'

match = re.search(pattern, content, flags=re.DOTALL)
if match:
    old_stack = match.group(1)
    new_stack = '''<Stack direction="column" spacing={1}>
            <Button size="small" variant="outlined" color="primary" onClick={() => { if (props.value) { props.onSelect(props.value, props.mode, true); setOpen(false); } else { toast.warning('ابتدا یک روز را در تقویم انتخاب کنید') } }} startIcon={<SyncRounded />}>همگام‌سازی عمیق از تاریخ انتخاب شده</Button>
            ''' + old_stack + '''
          </Stack>'''
    content = content.replace(old_stack, new_stack)
    
    # Also add import
    if "SyncRounded" not in content[:1000]:
        content = content.replace("import CalendarMonthRounded from '@mui/icons-material/CalendarMonthRounded'", "import CalendarMonthRounded from '@mui/icons-material/CalendarMonthRounded'\nimport SyncRounded from '@mui/icons-material/SyncRounded'")
        content = content.replace("import { CalendarMonthRounded, ChevronLeftRounded, ChevronRightRounded } from '@mui/icons-material'", "import { CalendarMonthRounded, ChevronLeftRounded, ChevronRightRounded, SyncRounded } from '@mui/icons-material'")
        # Wait, in helpers.tsx it is usually imported like:
        # import ChevronRightRounded from '@mui/icons-material/ChevronRightRounded'
        # Let's just append it to the top.
        content = "import SyncRounded from '@mui/icons-material/SyncRounded'\n" + content

    with open('ui/src/utils/helpers.tsx', 'w', encoding='utf-8') as f:
        f.write(content)
    print("FIXED")
else:
    print("NOT FOUND")

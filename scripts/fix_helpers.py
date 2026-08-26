with open('ui/src/utils/helpers.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

old_prop = "onSelect: (value: string, mode: 'day' | 'from') => void"
new_prop = "onSelect: (value: string, mode: 'day' | 'from', forceSync?: boolean) => void"
content = content.replace(old_prop, new_prop)

old_btn = "onClick={() => { props.onSelect(value, props.mode); setOpen(false) }}"
new_btn = "onClick={() => { props.onSelect(value, props.mode); setOpen(false) }}"
# wait, I need to add a "Deep Sync" button.

old_stack = '''          <Stack direction="row" justifyContent="space-between">
            <Button size="small" onClick={() => { setYear(now.year); setMonth(now.month) }}>امروز</Button>
            {props.value && <Button size="small" color="error" onClick={() => { props.onClear(); setOpen(false) }}>پاک کردن فیلتر</Button>}
          </Stack>'''

new_stack = '''          <Stack direction="column" spacing={1}>
            <Button size="small" variant="outlined" color="primary" onClick={() => { if (props.value) { props.onSelect(props.value, props.mode, true); setOpen(false); } else { toast.warning('ابتدا یک روز را انتخاب کنید') } }} startIcon={<SyncRounded />}>همگام‌سازی عمیق از تاریخ انتخاب شده</Button>
            <Stack direction="row" justifyContent="space-between">
              <Button size="small" onClick={() => { setYear(now.year); setMonth(now.month) }}>امروز</Button>
              {props.value && <Button size="small" color="error" onClick={() => { props.onClear(); setOpen(false) }}>پاک کردن فیلتر</Button>}
            </Stack>
          </Stack>'''

content = content.replace(old_stack, new_stack)
content = content.replace("import { CalendarMonthRounded, ChevronLeftRounded, ChevronRightRounded } from '@mui/icons-material'", "import { CalendarMonthRounded, ChevronLeftRounded, ChevronRightRounded, SyncRounded } from '@mui/icons-material'")

with open('ui/src/utils/helpers.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
print("FIXED HELPERS")

with open('ui/src/App.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

start_str = "const TEMPORAL_YEAR_OFFSET = 3_000_000_000"
end_str = "function initials(title: string) {"

start_idx = content.find(start_str)
end_idx = content.find(end_str, start_idx)

if start_idx != -1 and end_idx != -1:
    import_stmt = "import { jalaliDayLabel, jalaliDayKey, temporalIndexPredictions, JalaliDatePicker, TEMPORAL_MONTH_OFFSET, TEMPORAL_YEAR_OFFSET } from './utils/jalali'\n"
    
    # We must also remove 'IndexPrediction' from the App.tsx import to avoid conflict.
    # It is imported from './lib/types'.
    new_body = content[:start_idx] + content[end_idx:]
    
    # Do not double import, jalali.tsx export shouldn't conflict if we don't import it twice.
    # Actually wait, temporalIndexPredictions uses it. We don't import IndexPrediction from jalali.
    
    new_content = import_stmt + new_body
    with open('ui/src/App.tsx', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("SUCCESS")
else:
    print(f"NOT FOUND: start={start_idx} end={end_idx}")

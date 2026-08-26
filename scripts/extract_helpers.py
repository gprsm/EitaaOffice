import re

with open('ui/src/App.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

start_str = "const TEMPORAL_YEAR_OFFSET = 3_000_000_000"
end_str = "function initials(title: string) {"

start_idx = content.find(start_str)
end_idx = content.find(end_str, start_idx)

if start_idx != -1 and end_idx != -1:
    block = content[start_idx:end_idx]
    
    # We must add imports to helpers.tsx
    header = '''import { Box, Button, ButtonBase, CircularProgress, IconButton, Popover, Stack, ToggleButton, ToggleButtonGroup, Tooltip, Typography } from '@mui/material'
import CalendarMonthRounded from '@mui/icons-material/CalendarMonthRounded'
import ChevronLeftRounded from '@mui/icons-material/ChevronLeftRounded'
import ChevronRightRounded from '@mui/icons-material/ChevronRightRounded'
import { useEffect, useMemo, useRef, useState } from 'react'
import { stableMessageKey } from './lib/scrollMath'
import type { DialogItem, DisplayKind, MessageItem, PeerType, Term, IndexPrediction } from './lib/types'

'''
    # We need to make these functions and consts exported
    exports = [
        "TEMPORAL_YEAR_OFFSET", "TEMPORAL_MONTH_OFFSET", "PERSIAN_MONTHS",
        "LOCALIZED_LOGIN_CODE_DIGITS", "normalizeLoginCodeInput", "messageKey",
        "titleFor", "displayKindLabel", "CategoryTreeRow", "categoryTree",
        "STORAGE", "readStored", "writeStored", "REMOTE_MESSAGE_TTL_MS",
        "AUTO_NEWER_TTL_MS", "TERM_CACHE_TTL_MS", "mediaUrl", "JALALI_DAY_LABEL_FORMATTER",
        "JALALI_DAY_KEY_FORMATTER", "parseSourceKey", "jalaliDayLabel", "jalaliDayKey",
        "temporalIndexPredictions", "div", "mod", "jalCal", "g2d", "d2g", "j2d",
        "jalaliToGregorian", "parseJalaliDate", "jalaliParts", "jalaliYmd",
        "jalaliMonthLength", "jalaliMonths", "jalaliWeekdays", "JalaliDatePicker"
    ]
    
    for exp in exports:
        block = re.sub(r'^(const|function|type)\s+' + exp + r'\b', r'export \1 ' + exp, block, flags=re.MULTILINE)
    
    with open('ui/src/utils/helpers.tsx', 'w', encoding='utf-8') as f:
        f.write(header + block)
        
    # Replace in App.tsx
    import_stmt = f"import {{ {', '.join(exports)} }} from './utils/helpers'\n"
    new_content = content[:start_idx] + content[end_idx:]
    
    # Put import stmt just before the relative imports
    import_idx = new_content.find("import { toast } from './MaterialToast'")
    if import_idx != -1:
        new_content = new_content[:import_idx] + import_stmt + new_content[import_idx:]
    else:
        new_content = import_stmt + new_content

    with open('ui/src/App.tsx', 'w', encoding='utf-8') as f:
        f.write(new_content)
        
    print("SUCCESS")
else:
    print(f"NOT FOUND: {start_idx} {end_idx}")

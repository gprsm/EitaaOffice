const fs = require('fs');
let code = fs.readFileSync('ui/src/ContentIndexDialog.tsx', 'utf8');

code = code.replace(/<Alert severity="success">[\s\S]*?<\/Alert>/, '');
code = code.replace(/<Typography variant="h6">ایندکس‌گذاری محتوا<\/Typography>/, '<Typography variant="h6" sx={{ display: \\'flex\\', alignItems: \\'center\\', gap: 1 }}>ایندکس‌گذاری محتوا<Tooltip title="دسته‌های وردپرس مبنای اصلی‌اند؛ برچسب‌های وردپرس و ایندکس‌های سفارشی نیز می‌توانند هم‌زمان به هر پیام یا گالری افزوده شوند. سال و ماه شمسی نیز خودکار ثبت می‌شوند."><IconButton size="small"><InfoOutlinedIcon fontSize="small" /></IconButton></Tooltip></Typography>');
code = code.replace("import CloseRounded from '@mui/icons-material/CloseRounded'", "import CloseRounded from '@mui/icons-material/CloseRounded'\nimport InfoOutlinedIcon from '@mui/icons-material/InfoOutlined'");
code = code.replace("import {", "import { Tooltip, ");

fs.writeFileSync('ui/src/ContentIndexDialog.tsx', code);

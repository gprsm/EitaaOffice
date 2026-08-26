import re
with open('ui/src/AppUserManagementPanel.tsx', 'r', encoding='utf-8') as f:
    file = f.read()

if 'DialogTitle' not in file[:300]:
    file = file.replace(
        "import {\n  Alert,",
        "import {\n  Alert,\n  Dialog,\n  DialogTitle,\n  DialogContent,\n  DialogActions,"
    )
    with open('ui/src/AppUserManagementPanel.tsx', 'w', encoding='utf-8') as f:
        f.write(file)

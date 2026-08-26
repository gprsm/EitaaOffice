const fs = require('fs');
let file = fs.readFileSync('ui/src/AppUserManagementPanel.tsx', 'utf8');

const regex = /<Divider \/>\s*<Box component="form" onSubmit=\{create\}>[\s\S]*?<\/Box>/m;

const dialogCode = 
    <Divider />
    <Box>
      <Typography variant="subtitle1" sx={{ mb: 1.5 }}>ایجاد کاربر جدید</Typography>
      <Button variant="outlined" onClick={() => setCreateDialogOpen(true)}>
        افزودن حساب کاربری (AppUser)
      </Button>
    </Box>

    <Dialog open={createDialogOpen} onClose={() => setCreateDialogOpen(false)} fullWidth maxWidth="sm">
      <Box component="form" onSubmit={create}>
        <DialogTitle>افزودن حساب کاربری</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <TextField
              label="نام نمایشی"
              value={displayName}
              onChange={event => setDisplayName(event.target.value)}
              autoComplete="off"
            />
            <TextField
              label="نام کاربری نرم‌افزار"
              value={username}
              onChange={event => setUsername(event.target.value)}
              autoComplete="off"
              inputProps={{ dir: 'ltr', spellCheck: false }}
            />
            <TextField
              label="رمز عبور"
              type="password"
              value={password}
              onChange={event => setPassword(event.target.value)}
              autoComplete="new-password"
              inputProps={{ minLength: 4, maxLength: 128 }}
            />
            <TextField
              select
              label="نقش کاربری"
              value={role}
              onChange={event => setRole(event.target.value as 'admin' | 'user')}
            >
              <MenuItem value="user">کاربر عادی</MenuItem>
              <MenuItem value="admin">مدیر</MenuItem>
            </TextField>
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setCreateDialogOpen(false)} disabled={busy === 'create'}>انصراف</Button>
          <Button
            type="submit"
            variant="contained"
            disabled={
              busy === 'create'
              || !displayName.trim()
              || !username.trim()
              || password.length < 4
            }
          >
            {busy === 'create' ? 'در حال ایجاد...' : 'ایجاد کاربر'}
          </Button>
        </DialogActions>
      </Box>
    </Dialog>
;

file = file.replace(regex, dialogCode);
file = file.replace(
  "const [role, setRole] = useState<'admin' | 'user'>('user')",
  "const [role, setRole] = useState<'admin' | 'user'>('user')\n  const [createDialogOpen, setCreateDialogOpen] = useState(false)"
);
file = file.replace(
  "setMessage('کاربر جدید ساخته شد.')",
  "setMessage('کاربر جدید ساخته شد.')\n      setCreateDialogOpen(false)"
);

if (!file.includes('DialogContent')) {
  file = file.replace(
    "import {\\n  Alert,",
    "import {\\n  Alert,\\n  Dialog,\\n  DialogTitle,\\n  DialogContent,\\n  DialogActions,"
  );
}

fs.writeFileSync('ui/src/AppUserManagementPanel.tsx', file, 'utf8');

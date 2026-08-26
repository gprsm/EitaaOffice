import re
with open('ui/src/AppUserManagementPanel.tsx', 'r', encoding='utf-8') as f:
    file = f.read()

regex = r'<Divider />\s*<Box component="form" onSubmit={create}>[\s\S]*?</Box>'

dialogCode = '''
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
'''

file = re.sub(regex, dialogCode, file)

file = file.replace(
    "const [role, setRole] = useState<'admin' | 'user'>('user')",
    "const [role, setRole] = useState<'admin' | 'user'>('user')\n  const [createDialogOpen, setCreateDialogOpen] = useState(false)"
)

# For setMessage replace, be safe
file = file.replace(
    "await load()",
    "setCreateDialogOpen(false)\n      await load()"
)

if 'DialogContent' not in file:
    file = file.replace(
        "import {\n  Alert,",
        "import {\n  Alert,\n  Dialog,\n  DialogTitle,\n  DialogContent,\n  DialogActions,"
    )

with open('ui/src/AppUserManagementPanel.tsx', 'w', encoding='utf-8') as f:
    f.write(file)

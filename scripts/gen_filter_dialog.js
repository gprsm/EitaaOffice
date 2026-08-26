const fs = require('fs');
const original = fs.readFileSync('ui/src/MaterialIndexWorkbench.tsx', 'utf8');

// Extract imports
const imports = original.match(/import[\s\S]+?from '[^']+'/g).join('\n');

const types = `
export type MaterialIndexDefinition = {
  id: number
  name: string
  aliases: string[]
  kind: 'wordpress-category' | 'wordpress-tag' | 'custom'
  wordpressCategoryId?: number | null
}

type NamedId = { id: number; name: string }

type Props = {
  open: boolean
  close: () => void
  showWordPressUsed: boolean
  setShowWordPressUsed: (value: boolean) => void
  selectedIndexLabel: number | null
  setSelectedIndexLabel: (value: number | null) => void
  selectedSenderKey: string | null
  setSelectedSenderKey: (value: string | null) => void
  indexFilterLabels: NamedId[]
  senderFilterOptions: SenderFilterOption[]
  senderResolutionState: 'idle' | 'syncing' | 'ready' | 'failed'
  unresolvedSenderCount: number
  filteredMessageCount: number
}
`;

const component = `
export function MessageFilterDialog(props: Props) {
  const theme = useTheme()
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'))

  return <Dialog
    open={props.open}
    onClose={props.close}
    fullScreen={fullScreen}
    maxWidth="sm"
    fullWidth
    aria-labelledby="content-index-title"
  >
    <DialogTitle id="content-index-title" sx={{ pb: 1 }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" gap={2}>
        <Box minWidth={0}>
          <Typography variant="h6">فیلتر نمایش پیام‌ها</Typography>
          <Typography variant="body2" color="text.secondary">فیلترها فقط نمای محلی را تغییر می‌دهند.</Typography>
        </Box>
        <IconButton aria-label="بستن" onClick={props.close}><CloseRounded /></IconButton>
      </Stack>
    </DialogTitle>
    <DialogContent dividers sx={{ bgcolor: 'background.default' }}>
      <Stack spacing={2}>
        {props.senderResolutionState === 'syncing' && <Alert
          severity="info"
          icon={<CircularProgress color="inherit" size={18} />}
        >
          در حال دریافت نام {props.unresolvedSenderCount.toLocaleString('fa-IR')} نویسنده از تاریخچه پیام‌های ایتا؛ فهرست پس از تکمیل خودکار تازه می‌شود.
        </Alert>}
        {props.senderResolutionState === 'failed' && props.unresolvedSenderCount > 0 && <Alert severity="warning">
          نام برخی نویسندگان هنوز در نمایه محلی موجود نیست. شناسه فقط برای همین مواردِ حل‌نشده به‌عنوان جایگزین نمایش داده می‌شود.
        </Alert>}
        <Paper variant="outlined" sx={{ p: { xs: 1.5, sm: 2 } }}>
          <Stack spacing={2}>
            <FormControlLabel
              control={<Switch checked={props.showWordPressUsed} onChange={event => props.setShowWordPressUsed(event.target.checked)} />}
              label="مطالب استفاده‌شده در وردپرس نمایش داده شوند"
            />
            <FormControl disabled={!props.indexFilterLabels.length} fullWidth>
              <InputLabel>ایندکس</InputLabel>
              <Select<string> label="ایندکس" value={props.selectedIndexLabel == null ? '' : String(props.selectedIndexLabel)} onChange={event => props.setSelectedIndexLabel(event.target.value ? Number(event.target.value) : null)}>
                <MenuItem value="">همه ایندکس‌ها</MenuItem>
                {props.indexFilterLabels.map(item => <MenuItem key={item.id} value={String(item.id)}>{item.name}</MenuItem>)}
              </Select>
            </FormControl>
            <FormControl fullWidth>
              <InputLabel>فرستنده</InputLabel>
              <Select label="فرستنده" value={props.selectedSenderKey ?? ''} onChange={event => props.setSelectedSenderKey(String(event.target.value) || null)}>
                <MenuItem value="">همه فرستنده‌ها</MenuItem>
                {props.senderFilterOptions.map(sender => <MenuItem key={sender.key} value={sender.key}>
                  <Box sx={{ display: 'flex', minWidth: 0, width: '100%', alignItems: 'center', gap: 0.75 }}>
                    <Typography
                      component="span"
                      noWrap
                      fontWeight={sender.isEitaaContact ? 800 : 600}
                      color={sender.isEitaaContact ? 'primary.main' : 'text.primary'}
                    >
                      {sender.label}
                    </Typography>
                    {sender.isEitaaContact && <Chip label="مخاطب ایتا" color="primary" size="small" variant="outlined" />}
                    {sender.username && <Typography component="span" variant="caption" color="text.secondary" noWrap>
                      @{sender.username}
                    </Typography>}
                  </Box>
                </MenuItem>)}
              </Select>
            </FormControl>
          </Stack>
        </Paper>
        <Paper variant="outlined" sx={{ p: 2 }}>
          <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" alignItems={{ xs: 'stretch', sm: 'center' }} gap={1.5}>
            <Typography fontWeight={800}>{props.filteredMessageCount.toLocaleString('fa-IR')} پیام در نمای فعلی</Typography>
            <Button variant="outlined" startIcon={<RestartAltRounded />} onClick={() => {
              props.setShowWordPressUsed(true)
              props.setSelectedIndexLabel(null)
              props.setSelectedSenderKey(null)
            }}>پاک‌کردن فیلترها</Button>
          </Stack>
        </Paper>
      </Stack>
    </DialogContent>
    <DialogActions sx={{ px: { xs: 1.25, sm: 2.25 }, py: 1.5 }}>
      <Button onClick={props.close}>بستن</Button>
    </DialogActions>
  </Dialog>
}
`;

fs.writeFileSync('ui/src/MessageFilterDialog.tsx', imports + '\n\n' + types + '\n\n' + component);

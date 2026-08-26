import { useMemo, useState } from 'react'
import {
  Box,
  Button,
  Checkbox,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  IconButton,
  List,
  ListItem,
  ListItemText,
  Stack,
  TextField,
  Typography,
  useMediaQuery,
  useTheme,
} from '@mui/material'
import CloseRounded from '@mui/icons-material/CloseRounded'

type Definition = { id: number; name: string; kind: 'wordpress-category' | 'wordpress-tag' | 'custom' }

type Props = {
  open: boolean
  messageLabel: string
  definitions: Definition[]
  selectedIds: number[]
  setSelectedIds: (ids: number[]) => void
  saving: boolean
  close: () => void
  save: () => void
}

export function MessageIndexEditor(props: Props) {
  const theme = useTheme()
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'))
  const [search, setSearch] = useState('')
  const filtered = useMemo(() => {
    const needle = search.trim().toLocaleLowerCase('fa')
    const source = needle ? props.definitions.filter(item => item.name.toLocaleLowerCase('fa').includes(needle)) : props.definitions
    return source.slice(0, 500)
  }, [props.definitions, search])

  return <Dialog open={props.open} onClose={props.saving ? undefined : props.close} fullScreen={fullScreen} maxWidth="sm">
    <DialogTitle>
      <Stack direction="row" alignItems="center" justifyContent="space-between" gap={2}>
        <Box>
          <Typography variant="h6">اصلاح ایندکس {props.messageLabel}</Typography>
          <Typography variant="body2" color="text.secondary">هر محتوا می‌تواند هم‌زمان چند ایندکس داشته باشد. اصلاح شما برای آموزش محلی ثبت می‌شود.</Typography>
        </Box>
        <IconButton onClick={props.close} disabled={props.saving}><CloseRounded /></IconButton>
      </Stack>
    </DialogTitle>
    <DialogContent dividers sx={{ bgcolor: 'background.default' }}>
      <Stack spacing={1.5}>
        <TextField label="جست‌وجوی ایندکس" value={search} onChange={event => setSearch(event.target.value)} />
        <List disablePadding sx={{ bgcolor: 'background.paper', border: 1, borderColor: 'divider', borderRadius: 2, overflow: 'hidden' }}>
          {filtered.map((definition, index) => <ListItem key={definition.id} divider={index < filtered.length - 1} disablePadding>
            <FormControlLabel
              sx={{ width: '100%', m: 0, px: 1.5, py: .5, alignItems: 'flex-start' }}
              control={<Checkbox
                checked={props.selectedIds.includes(definition.id)}
                onChange={event => props.setSelectedIds(event.target.checked
                  ? [...new Set([...props.selectedIds, definition.id])]
                  : props.selectedIds.filter(id => id !== definition.id))}
              />}
              label={<ListItemText
                primary={definition.name}
                secondary={definition.kind === 'wordpress-category' ? 'دسته وردپرس' : definition.kind === 'wordpress-tag' ? 'برچسب وردپرس' : 'ایندکس سفارشی'}
              />}
            />
          </ListItem>)}
        </List>
        {props.definitions.length > 500 && <Typography variant="caption" color="text.secondary">برای حفظ سرعت، ۵۰۰ نتیجه نخست نمایش داده می‌شود؛ برای یافتن موارد دیگر جست‌وجو کنید.</Typography>}
      </Stack>
    </DialogContent>
    <DialogActions>
      <Button onClick={props.close} disabled={props.saving}>انصراف</Button>
      <Button variant="contained" onClick={props.save} disabled={props.saving}>{props.saving ? 'در حال ثبت…' : 'ثبت اصلاح'}</Button>
    </DialogActions>
  </Dialog>
}

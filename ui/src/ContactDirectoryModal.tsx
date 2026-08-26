import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { toast } from './MaterialToast'
import {
  Alert, Avatar, Box, Button, Checkbox, Chip, CircularProgress, Dialog, DialogActions,
  DialogContent, DialogTitle, Divider, FormControl, FormControlLabel, Grid, IconButton,
  InputLabel, LinearProgress, MenuItem, Pagination, Paper, Select, Skeleton, Stack, Switch, Tab,
  Tabs, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, TextField,
  Tooltip, Typography, useMediaQuery, useTheme,
} from '@mui/material'
import CloseRounded from '@mui/icons-material/CloseRounded'
import EditOutlined from '@mui/icons-material/EditOutlined'
import ArchiveOutlined from '@mui/icons-material/ArchiveOutlined'
import UploadFileRounded from '@mui/icons-material/UploadFileRounded'
import PersonAddAltRounded from '@mui/icons-material/PersonAddAltRounded'
import RefreshRounded from '@mui/icons-material/RefreshRounded'
import DeleteOutlineRounded from '@mui/icons-material/DeleteOutlineRounded'
import SyncRounded from '@mui/icons-material/SyncRounded'
import ContactsRounded from '@mui/icons-material/ContactsRounded'
import LabelRounded from '@mui/icons-material/LabelRounded'
import SendRounded from '@mui/icons-material/SendRounded'
import { api, query } from './lib/api'
import { loadDialogAvatar, peekDialogAvatar } from './lib/avatarLoader'
import { useMessengerAccounts } from './MessengerAccountGate'

type ContactCategory = { id: number; name: string; member_count: number }
type EitaaCategoryOperation = 'add' | 'remove' | 'replace'
type LocalContact = {
  id: number
  first_name: string
  last_name: string
  phones: string[]
  username: string
  organization: string
  notes: string
  source: string
  sendable: boolean
  opt_out: boolean
  categories: Array<{ id: number; name: string }>
  created_at: string
  updated_at: string
  created_by_app_user_id?: string | null
  updated_by_app_user_id?: string | null
  selected_account_binding?: {
    provider: string
    reachability: string
    updated_at: string
  } | null
}
type EitaaContact = {
  user_id: number
  peer_key: string
  peer_file: string | null
  access_hash_present: boolean
  first_name: string
  last_name: string
  display_name: string
  username: string
  phone: string
  mutual: boolean
  is_mutual_contact: boolean
  local_contact_id?: number | null
  local_categories: Array<{ id: number; name: string }>
  status?: { kind?: string; expires_at?: string | null; was_online_at?: string | null } | null
}
type ContactDraft = {
  id?: number
  first_name: string
  last_name: string
  phones: string
  username: string
  organization: string
  notes: string
  sendable: boolean
  opt_out: boolean
  category_ids: number[]
}
type ImportPreview = { file_name: string; headers: string[]; rows: string[][]; row_count: number; preview_truncated: boolean }
type ImportJob = {
  job_id: string
  kind?: string
  state: string
  progress: Record<string, number | boolean | string | null>
  error?: { message?: string; error_code?: string; error_type?: string }
}
type ResolvedPhoneList = {
  id: string
  name: string
  status: string
  total_rows: number
  resolved_count: number
  pending_count: number
  not_found_count: number
  failed_count: number
}
type TargetResult = {
  targets: Array<{ contact_id: number; phone: string; name: string }>
  target_count: number
  omitted: Record<string, number>
  truncated?: boolean
  max_targets?: number
}

const EMPTY_CONTACT: ContactDraft = {
  first_name: '', last_name: '', phones: '', username: '', organization: '', notes: '',
  sendable: true, opt_out: false, category_ids: [],
}
function fileBase64(file: File) {
  return file.arrayBuffer().then(buffer => {
    const bytes = new Uint8Array(buffer)
    let binary = ''
    for (let offset = 0; offset < bytes.length; offset += 32_768) {
      binary += String.fromCharCode(...bytes.subarray(offset, offset + 32_768))
    }
    return btoa(binary)
  })
}

function autoMapping(headers: string[]) {
  const normalized = headers.map(value => value.trim().toLocaleLowerCase('fa'))
  const find = (...needles: string[]) => {
    const index = normalized.findIndex(value => needles.some(needle => value.includes(needle)))
    return index >= 0 ? String(index) : ''
  }
  const firstNameIndex = normalized.findIndex(value => (
    !value.includes('خانوادگی')
    && !value.includes('کاربری')
    && (
      value === 'نام'
      || value.includes('نام کوچک')
      || value.includes('first name')
      || value.includes('firstname')
    )
  ))
  return {
    first_name: firstNameIndex >= 0 ? String(firstNameIndex) : '',
    last_name: find('نام خانوادگی', 'خانوادگی', 'last'),
    phone: find('شماره', 'تلفن', 'موبایل', 'phone', 'mobile'),
    category: find('دسته', 'گروه مخاطب', 'category'),
    organization: find('سازمان', 'واحد', 'organization'),
    notes: find('توضیح', 'یادداشت', 'note'),
    username: find('نام کاربری', 'username'),
  }
}

function EitaaContactAvatar({ contact, siteKey }: { contact: EitaaContact; siteKey: string }) {
  const ref = useRef<HTMLDivElement | null>(null)
  const [src, setSrc] = useState<string | null | undefined>(() => peekDialogAvatar(siteKey, contact.peer_key))
  useEffect(() => { setSrc(peekDialogAvatar(siteKey, contact.peer_key)) }, [contact.peer_key, siteKey])
  useEffect(() => {
    const node = ref.current
    if (!node || !contact.peer_key || src !== undefined) return
    let active = true
    const observer = new IntersectionObserver(entries => {
      if (!entries.some(entry => entry.isIntersecting)) return
      observer.disconnect()
      void loadDialogAvatar(siteKey, contact.peer_key)
        .then(value => { if (active) setSrc(value) })
        .catch(() => { if (active) setSrc(null) })
    }, { rootMargin: '180px' })
    observer.observe(node)
    return () => { active = false; observer.disconnect() }
  }, [contact.peer_key, siteKey, src])
  return <Box ref={ref}>
    {src === undefined
      ? <Skeleton variant="circular" animation="wave" width={40} height={40} />
      : <Avatar src={src || undefined} imgProps={{ loading: 'lazy', decoding: 'async' }}>{contact.display_name.trim().slice(0, 1) || 'م'}</Avatar>}
  </Box>
}

export function ContactDirectoryModal({ siteKey, close, handoffTargets, handoffContact }: {
  siteKey: string
  close: () => void
  handoffTargets: (phones: string[]) => void
  handoffContact: (contact: EitaaContact) => void
}) {
  const messengerAccounts = useMessengerAccounts()
  const canReadProviderContacts = !messengerAccounts.featureEnabled || messengerAccounts.hasCapability('contacts.read')
  const canWriteProviderContacts = !messengerAccounts.featureEnabled || messengerAccounts.hasCapability('contacts.write')
  const [tab, setTab] = useState<'eitaa' | 'local' | 'categories' | 'import' | 'targets'>('eitaa')
  const [categories, setCategories] = useState<ContactCategory[]>([])
  const [busy, setBusy] = useState(false)
  const localRequestSequence = useRef(0)
  const eitaaRequestSequence = useRef(0)
  const eitaaLoadingRef = useRef(false)
  const eitaaContactsRef = useRef<EitaaContact[]>([])
  const targetRequestSequence = useRef(0)

  const [eitaaContacts, setEitaaContacts] = useState<EitaaContact[]>([])
  const [eitaaLoading, setEitaaLoading] = useState(false)
  const [eitaaSearch, setEitaaSearch] = useState('')
  const [eitaaTotal, setEitaaTotal] = useState(0)
  const [eitaaHasMore, setEitaaHasMore] = useState(true)
  const [eitaaSelectedIds, setEitaaSelectedIds] = useState<number[]>([])
  const [eitaaAssignCategoryIds, setEitaaAssignCategoryIds] = useState<number[]>([])
  const [eitaaCategoryOperation, setEitaaCategoryOperation] = useState<EitaaCategoryOperation>('add')
  const [eitaaCategorizing, setEitaaCategorizing] = useState(false)
  const [eitaaCategoryProgress, setEitaaCategoryProgress] = useState(0)
  const [eitaaCategoryIds, setEitaaCategoryIds] = useState<number[]>([])
  const [pushToEitaaCategoryIds, setPushToEitaaCategoryIds] = useState<number[]>([])
  const [eitaaDraft, setEitaaDraft] = useState({ first_name: '', last_name: '', phone: '' })

  const [contacts, setContacts] = useState<LocalContact[]>([])
  const [contactLimit, setContactLimit] = useState(250)
  const [contactPage, setContactPage] = useState(1)
  const [contactTotal, setContactTotal] = useState(0)
  const [search, setSearch] = useState('')
  const [filterCategoryIds, setFilterCategoryIds] = useState<number[]>([])
  const [draft, setDraft] = useState<ContactDraft>(EMPTY_CONTACT)
  const [addManualToEitaa, setAddManualToEitaa] = useState(false)

  const [categoryName, setCategoryName] = useState('')
  const [editingCategoryId, setEditingCategoryId] = useState<number | null>(null)

  const [importContent, setImportContent] = useState('')
  const [preview, setPreview] = useState<ImportPreview | null>(null)
  const [mapping, setMapping] = useState<Record<string, string>>({})
  const [importCategoryIds, setImportCategoryIds] = useState<number[]>([])
  const [importAddToEitaa, setImportAddToEitaa] = useState(false)
  const [importJob, setImportJob] = useState<ImportJob | null>(null)
  const [phoneLists, setPhoneLists] = useState<ResolvedPhoneList[]>([])

  const [targetCategoryIds, setTargetCategoryIds] = useState<number[]>([])
  const [targetContacts, setTargetContacts] = useState<LocalContact[]>([])
  const [targetSearch, setTargetSearch] = useState('')
  const [targetPage, setTargetPage] = useState(1)
  const [targetTotal, setTargetTotal] = useState(0)
  const [targetIncludeIds, setTargetIncludeIds] = useState<number[]>([])
  const [targetExcludeIds, setTargetExcludeIds] = useState<number[]>([])
  const [targetResult, setTargetResult] = useState<TargetResult | null>(null)

  const loadCategories = useCallback(async () => {
    const response = await api<{ categories: ContactCategory[] }>('GET', '/api/v1/contacts/categories')
    setCategories(response.categories)
  }, [])
  const loadContacts = useCallback(async () => {
    const requestId = ++localRequestSequence.current
    const response = await api<{ contacts: LocalContact[]; total: number }>('POST', '/api/v1/contacts/list', {
      search, category_ids: filterCategoryIds, limit: contactLimit, offset: (contactPage - 1) * contactLimit,
    })
    if (requestId !== localRequestSequence.current) return
    setContacts(response.contacts)
    setContactTotal(response.total)
  }, [contactLimit, contactPage, filterCategoryIds, search])
  const targetPageSize = 100
  const loadTargetContacts = useCallback(async () => {
    const requestId = ++targetRequestSequence.current
    if (!targetCategoryIds.length) {
      setTargetContacts([])
      setTargetTotal(0)
      return
    }
    const response = await api<{ contacts: LocalContact[]; total: number }>('POST', '/api/v1/contacts/list', {
      search: targetSearch, category_ids: targetCategoryIds, limit: targetPageSize, offset: (targetPage - 1) * targetPageSize,
    })
    if (requestId !== targetRequestSequence.current) return
    setTargetContacts(response.contacts)
    setTargetTotal(response.total)
  }, [targetCategoryIds, targetPage, targetSearch])
  const eitaaPageSize = 50
  const loadEitaaContacts = useCallback(async (refresh = false, syncLocal = false, append = false) => {
    if (!siteKey || !canReadProviderContacts) return
    if (append && eitaaLoadingRef.current) return
    const requestId = ++eitaaRequestSequence.current
    const offset = append ? eitaaContactsRef.current.length : 0
    eitaaLoadingRef.current = true
    setEitaaLoading(true)
    try {
      const response = await api<{ contacts: EitaaContact[]; total: number; has_more?: boolean; synced_local?: number }>('POST', '/api/v1/eitaa-contacts/list', {
        site_key: siteKey, refresh, sync_local: syncLocal, category_ids: eitaaCategoryIds,
        search: eitaaSearch, limit: eitaaPageSize, offset,
      })
      if (requestId !== eitaaRequestSequence.current) return
      setEitaaContacts(current => {
        const next = append
          ? [...current, ...response.contacts.filter(item => !current.some(existing => existing.user_id === item.user_id))]
          : response.contacts
        eitaaContactsRef.current = next
        return next
      })
      setEitaaTotal(response.total)
      setEitaaHasMore(Boolean(response.has_more))
      if (syncLocal) {
        toast.success(`${Number(response.synced_local || 0).toLocaleString('fa-IR')} مخاطب دارای شماره در دفترچه محلی همگام شد.`)
        await Promise.all([loadContacts(), loadCategories()])
      }
    } catch (error) {
      if (requestId === eitaaRequestSequence.current) toast.error(error instanceof Error ? error.message : 'خواندن مخاطبان ایتا ناموفق بود.')
    } finally {
      if (requestId === eitaaRequestSequence.current) {
        eitaaLoadingRef.current = false
        setEitaaLoading(false)
      }
    }
  }, [canReadProviderContacts, eitaaCategoryIds, eitaaSearch, loadCategories, loadContacts, siteKey])
  const loadPhoneLists = useCallback(async () => {
    if (!siteKey) return
    const response = await api<{ phone_lists: ResolvedPhoneList[] }>('GET', query('/api/v1/phone-lists', { site_key: siteKey, limit: 1000 }))
    setPhoneLists(response.phone_lists)
  }, [siteKey])

  useEffect(() => { void loadCategories() }, [loadCategories])
  useEffect(() => {
    if (!canReadProviderContacts && tab === 'eitaa') setTab('local')
  }, [canReadProviderContacts, tab])
  useEffect(() => {
    if (tab !== 'eitaa') return
    const timer = window.setTimeout(() => void loadEitaaContacts(false, false), 250)
    return () => window.clearTimeout(timer)
  }, [loadEitaaContacts, tab])
  useEffect(() => {
    const timer = window.setTimeout(() => void loadContacts(), 250)
    return () => window.clearTimeout(timer)
  }, [loadContacts])
  useEffect(() => { setContactPage(1) }, [contactLimit, filterCategoryIds, search])
  useEffect(() => {
    eitaaContactsRef.current = []
    setEitaaContacts([])
    setEitaaHasMore(true)
    setEitaaSelectedIds([])
  }, [eitaaSearch])
  useEffect(() => {
    setTargetPage(1)
    setTargetIncludeIds([])
    setTargetExcludeIds([])
    setTargetResult(null)
  }, [targetCategoryIds])
  useEffect(() => { setTargetPage(1) }, [targetSearch])
  useEffect(() => {
    if (tab !== 'targets') return
    const timer = window.setTimeout(() => void loadTargetContacts(), 250)
    return () => window.clearTimeout(timer)
  }, [loadTargetContacts, tab])
  useEffect(() => { if (tab === 'import') void loadPhoneLists().catch(() => undefined) }, [loadPhoneLists, tab])
  useEffect(() => {
    if (!importJob || !['queued', 'running', 'cancelling'].includes(importJob.state)) return
    const timer = window.setInterval(() => {
      void api<{ job: ImportJob }>('GET', query('/api/v1/contacts/import/status', { job_id: importJob.job_id }))
        .then(response => {
          setImportJob(response.job)
          if (response.job.state === 'completed') {
            toast.success('عملیات مخاطبان کامل شد.')
            void Promise.all([loadContacts(), loadCategories(), loadEitaaContacts(true, false)])
          } else if (response.job.state === 'failed') toast.error(response.job.error?.message || 'عملیات مخاطبان ناموفق بود.')
        }).catch(() => undefined)
    }, 1000)
    return () => window.clearInterval(timer)
  }, [importJob, loadCategories, loadContacts, loadEitaaContacts])

  const categoryChecks = (selected: number[], change: (next: number[]) => void) => (
    <Stack direction="row" gap={0.5} flexWrap="wrap">
      {categories.map(category => <FormControlLabel key={category.id} sx={{ m: 0, ml: 1 }} control={<Checkbox size="small" checked={selected.includes(category.id)} onChange={event => change(event.target.checked ? [...selected, category.id] : selected.filter(id => id !== category.id))} />} label={`${category.name} (${category.member_count.toLocaleString('fa-IR')})`} />)}
    </Stack>
  )

  const editContact = (contact: LocalContact) => {
    setDraft({
      id: contact.id, first_name: contact.first_name, last_name: contact.last_name,
      phones: contact.phones.join('، '), username: contact.username, organization: contact.organization,
      notes: contact.notes, sendable: contact.sendable, opt_out: contact.opt_out,
      category_ids: contact.categories.map(item => item.id),
    })
    setTab('local')
  }
  const saveContact = async () => {
    if (addManualToEitaa && !canWriteProviderContacts) {
      toast.info('افزودن مخاطب به حساب انتخاب‌شده پشتیبانی نمی‌شود.')
      return
    }
    setBusy(true)
    try {
      const response = await api<{ contact: LocalContact; eitaa_contact?: unknown }>('POST', '/api/v1/contacts/upsert', {
        site_key: siteKey,
        add_to_eitaa: addManualToEitaa && !draft.id,
        duplicate_policy: draft.id ? 'update' : 'skip',
        contact: {
          ...draft,
          phones: draft.phones.split(/[،,;\n]+/).map(value => value.trim()).filter(Boolean),
          source: draft.id ? 'manual-edit' : 'manual',
        },
      })
      if ((response.contact as LocalContact & { duplicate?: boolean }).duplicate) toast.info('این شماره قبلاً ثبت شده بود؛ رکورد تکراری ساخته نشد.')
      else toast.success(addManualToEitaa && !draft.id ? 'مخاطب در دفترچه محلی و ایتا ذخیره شد.' : 'مخاطب ذخیره شد.')
      setDraft(EMPTY_CONTACT)
      setAddManualToEitaa(false)
      await Promise.all([loadContacts(), loadCategories(), addManualToEitaa ? loadEitaaContacts(true, false) : Promise.resolve()])
    } catch (error) { toast.error(error instanceof Error ? error.message : 'ذخیره مخاطب ناموفق بود.') }
    finally { setBusy(false) }
  }
  const addEitaaContact = async () => {
    if (!canWriteProviderContacts) { toast.info('افزودن مخاطب برای این حساب پشتیبانی نمی‌شود.'); return }
    if (!eitaaDraft.phone.trim() || !eitaaDraft.first_name.trim()) return
    setBusy(true)
    try {
      await api('POST', '/api/v1/eitaa-contacts/add', {
        site_key: siteKey, ...eitaaDraft, save_local: true, category_ids: eitaaCategoryIds,
      })
      toast.success('مخاطب به دفترچه ایتا افزوده شد و نسخه محلی آن نیز نگهداری شد.')
      setEitaaDraft({ first_name: '', last_name: '', phone: '' })
      await Promise.all([loadEitaaContacts(true, false), loadContacts(), loadCategories()])
    } catch (error) { toast.error(error instanceof Error ? error.message : 'افزودن مخاطب ایتا ناموفق بود.') }
    finally { setBusy(false) }
  }
  const pushLocalCategoriesToEitaa = async () => {
    if (!canWriteProviderContacts) { toast.info('افزودن مخاطب برای این حساب پشتیبانی نمی‌شود.'); return }
    if (!pushToEitaaCategoryIds.length) { toast.info('حداقل یک دسته محلی را انتخاب کنید.'); return }
    const response = await api<{ job: ImportJob }>('POST', '/api/v1/contacts/add-to-messenger/start', {
      site_key: siteKey, category_ids: pushToEitaaCategoryIds,
    })
    setImportJob(response.job)
    toast.info('افزودن مخاطبان دسته‌های انتخابی به دفترچه ایتا در پس‌زمینه آغاز شد.')
  }
  const pushLocalContactToSelectedAccount = async (contact: LocalContact) => {
    if (!canWriteProviderContacts) { toast.info('افزودن مخاطب برای این حساب پشتیبانی نمی‌شود.'); return }
    if (!contact.phones.length || !contact.first_name.trim()) {
      toast.info('برای افزودن به پیام‌رسان، نام و شمارهٔ مخاطب لازم است.')
      return
    }
    const response = await api<{ job: ImportJob }>('POST', '/api/v1/contacts/add-to-messenger/start', {
      site_key: siteKey, contact_ids: [contact.id],
    })
    setImportJob(response.job)
    toast.info('افزودن مخاطب فقط با حساب پیام‌رسان انتخاب‌شده آغاز شد.')
  }
  const categorizeSelectedEitaaContacts = async () => {
    if (!canWriteProviderContacts) { toast.info('تغییر مخاطبان برای این حساب پشتیبانی نمی‌شود.'); return }
    const selected = eitaaContacts.filter(contact => eitaaSelectedIds.includes(contact.user_id))
    if (!selected.length) { toast.info('حداقل یک مخاطب ایتا را انتخاب کنید.'); return }
    if (!eitaaAssignCategoryIds.length) { toast.info('حداقل یک دسته محلی را انتخاب کنید.'); return }
    setEitaaCategorizing(true)
    setEitaaCategoryProgress(0)
    try {
      const batchSize = 250
      const updatedByUserId = new Map<number, {
        user_id: number
        local_contact_id: number | null
        local_categories: Array<{ id: number; name: string }>
      }>()
      let processed = 0
      for (let offset = 0; offset < selected.length; offset += batchSize) {
        const batch = selected.slice(offset, offset + batchSize)
        const response = await api<{
          categorized_count: number
          contacts: Array<{
            user_id: number
            local_contact_id: number | null
            local_categories: Array<{ id: number; name: string }>
          }>
        }>('POST', '/api/v1/eitaa-contacts/categorize', {
          site_key: siteKey,
          operation: eitaaCategoryOperation,
          category_ids: eitaaAssignCategoryIds,
          contacts: batch.map(contact => ({
            user_id: contact.user_id,
            phone: contact.phone,
            first_name: contact.first_name,
            last_name: contact.last_name,
            username: contact.username,
          })),
        })
        response.contacts.forEach(contact => updatedByUserId.set(contact.user_id, contact))
        processed += response.categorized_count
        setEitaaCategoryProgress(Math.round(processed / selected.length * 100))
      }
      setEitaaContacts(current => {
        const next = current.map(contact => {
          const updated = updatedByUserId.get(contact.user_id)
          return updated ? { ...contact, ...updated } : contact
        })
        eitaaContactsRef.current = next
        return next
      })
      setEitaaSelectedIds([])
      const resultMessage = eitaaCategoryOperation === 'remove'
        ? 'از دسته‌های انتخاب‌شده حذف شد'
        : eitaaCategoryOperation === 'replace'
          ? 'به دسته‌های انتخاب‌شده منتقل شد'
          : 'به دسته‌های انتخاب‌شده افزوده شد'
      toast.success(`${processed.toLocaleString('fa-IR')} مخاطب ${resultMessage}.`)
      await Promise.all([loadCategories(), loadContacts()])
    } catch (error) {
      toast.error(error instanceof Error ? error.message : 'دسته‌بندی مخاطبان ایتا ناموفق بود.')
    } finally {
      setEitaaCategorizing(false)
      setEitaaCategoryProgress(0)
    }
  }

  const removeEitaaContact = async (contact: EitaaContact) => {
    if (!canWriteProviderContacts) { toast.info('حذف مخاطب برای این حساب پشتیبانی نمی‌شود.'); return }
    if (!contact.phone) { toast.info('شماره این مخاطب از طرف ایتا نمایش داده نشده است.'); return }
    if (!window.confirm(`مخاطب «${contact.display_name}» از دفترچه مخاطبان ایتا حذف شود؟ نسخه محلی حذف نخواهد شد.`)) return
    await api('POST', '/api/v1/eitaa-contacts/remove', { site_key: siteKey, phone: contact.phone, confirm: true })
    toast.info('مخاطب از دفترچه ایتا حذف شد.')
    await loadEitaaContacts(true, false)
  }
  const archiveContact = async (contact: LocalContact) => {
    if (!window.confirm(`مخاطب «${contact.first_name} ${contact.last_name}» بایگانی شود؟`)) return
    await api('POST', '/api/v1/contacts/archive', { contact_id: contact.id, confirm: true })
    toast.info('مخاطب بایگانی شد.')
    await Promise.all([loadContacts(), loadCategories()])
  }
  const saveCategory = async () => {
    if (!categoryName.trim()) return
    await api('POST', '/api/v1/contacts/categories/save', { category_id: editingCategoryId, name: categoryName })
    setCategoryName(''); setEditingCategoryId(null)
    await loadCategories()
  }
  const deleteCategory = async (category: ContactCategory) => {
    if (!window.confirm(`دسته «${category.name}» حذف شود؟ هیچ مخاطبی حذف نخواهد شد.`)) return
    await api('POST', '/api/v1/contacts/categories/delete', { category_id: category.id, confirm: true })
    await Promise.all([loadCategories(), loadContacts()])
  }
  const chooseFile = async (file?: File) => {
    if (!file) return
    setBusy(true)
    try {
      const content_base64 = await fileBase64(file)
      const response = await api<ImportPreview>('POST', '/api/v1/contacts/import/preview', { file_name: file.name, content_base64 })
      setImportContent(content_base64)
      setPreview(response)
      setMapping(autoMapping(response.headers))
      toast.success(`${response.row_count.toLocaleString('fa-IR')} ردیف برای بازبینی خوانده شد.`)
    } catch (error) { toast.error(error instanceof Error ? error.message : 'خواندن فایل ناموفق بود.') }
    finally { setBusy(false) }
  }
  const startImport = async () => {
    if (!preview || !mapping.phone) { toast.error('ستون شماره تماس را مشخص کنید.'); return }
    if (importAddToEitaa && !canWriteProviderContacts) {
      toast.info('افزودن مخاطب برای این حساب پشتیبانی نمی‌شود.')
      return
    }
    if (importAddToEitaa && !mapping.first_name) {
      toast.error('برای ثبت نام صحیح در ایتا، ستون «نام» را نیز مشخص کنید.')
      return
    }
    const response = await api<{ job: ImportJob }>('POST', '/api/v1/contacts/import/start', {
      site_key: siteKey, file_name: preview.file_name, content_base64: importContent, mapping,
      category_ids: importCategoryIds, add_to_eitaa: importAddToEitaa,
    })
    setImportJob(response.job)
  }
  const startPhoneListImport = async (list: ResolvedPhoneList) => {
    const response = await api<{ job: ImportJob }>('POST', '/api/v1/contacts/import/phone-list/start', {
      site_key: siteKey, list_id: list.id, category_ids: importCategoryIds,
    })
    setImportJob(response.job)
    toast.info('انتقال شماره‌های شناسایی‌شده به دفترچه محلی آغاز شد.')
  }
  const previewTargets = async () => {
    if (!targetCategoryIds.length && !targetIncludeIds.length) {
      toast.info('حداقل یک دسته یا یک مخاطب صریح را انتخاب کنید.')
      return
    }
    const response = await api<TargetResult & { ok: true }>('POST', '/api/v1/contacts/targets/preview', {
      category_ids: targetCategoryIds, include_contact_ids: targetIncludeIds,
      exclude_contact_ids: targetExcludeIds, max_targets: 10_000,
    })
    setTargetResult(response)
  }

  const visibleEitaa = eitaaContacts
  const selectedEitaaCount = eitaaSelectedIds.length
  const allLoadedEitaaSelected = Boolean(
    visibleEitaa.length && visibleEitaa.every(contact => eitaaSelectedIds.includes(contact.user_id))
  )
  const someLoadedEitaaSelected = visibleEitaa.some(contact => eitaaSelectedIds.includes(contact.user_id))
  const targetPageCount = Math.max(1, Math.ceil(targetTotal / targetPageSize))

  const importFields = useMemo(() => [
    ['first_name', 'نام'], ['last_name', 'نام خانوادگی'], ['phone', 'شماره تماس *'],
    ['category', 'دسته'], ['organization', 'سازمان'], ['notes', 'توضیحات'], ['username', 'نام کاربری'],
  ], [])
  const importActive = Boolean(importJob && ['queued', 'running', 'cancelling'].includes(importJob.state))
  const theme = useTheme()
  const fullScreen = useMediaQuery(theme.breakpoints.down('sm'))
  const tabItems = [
    ['eitaa', 'مخاطبان ایتا'], ['local', 'دفترچه محلی'], ['categories', 'دسته‌ها'], ['import', 'ورود و انتقال'], ['targets', 'مخاطبان هدف'],
  ] as const

  return <Dialog open onClose={importActive ? undefined : close} fullScreen={fullScreen} fullWidth maxWidth="xl" PaperProps={{ sx: { minHeight: { sm: '78vh' } } }}>
    <DialogTitle sx={{ pb: 1 }}>
      <Stack direction="row" alignItems="center" justifyContent="space-between" gap={2}>
        <Stack direction="row" alignItems="center" gap={1.25} minWidth={0}>
          <Avatar sx={{ bgcolor: 'primary.main' }}><ContactsRounded /></Avatar>
          <Box minWidth={0}>
            <Typography variant="h6">مدیریت مخاطبان</Typography>
            <Typography variant="body2" color="text.secondary">دفترچه واقعی ایتا، دفترچه دائمی محلی و ساخت آسان مخاطبان هدف</Typography>
          </Box>
        </Stack>
        <IconButton onClick={close} disabled={importActive} aria-label="بستن"><CloseRounded /></IconButton>
      </Stack>
    </DialogTitle>
    <Box sx={{ px: { xs: 1, sm: 2 }, borderBottom: 1, borderColor: 'divider' }}>
      <Tabs value={tab} onChange={(_, value) => setTab(value)} variant="scrollable" scrollButtons="auto" allowScrollButtonsMobile>
        {tabItems.map(item => <Tab key={item[0]} value={item[0]} label={item[1]} disabled={item[0] === 'eitaa' && !canReadProviderContacts} />)}
      </Tabs>
    </Box>
    <DialogContent sx={{ bgcolor: 'background.default', p: { xs: 1, sm: 2 } }}>
      {importJob && <Paper variant="outlined" sx={{ p: 1.25, mb: 1.5, borderColor: importJob.state === 'failed' ? 'error.main' : 'primary.main' }}>
        <Stack spacing={1}>
          <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" alignItems={{ xs: 'stretch', sm: 'center' }} gap={1}>
            <Box><Typography fontWeight={900}>{importJob.state === 'completed' ? 'عملیات مخاطبان کامل شد' : importJob.state === 'failed' ? 'عملیات مخاطبان ناموفق بود' : importJob.state === 'cancelled' ? 'عملیات مخاطبان لغو شد' : 'عملیات مخاطبان در حال اجراست'}</Typography><Typography variant="caption" color="text.secondary">پردازش‌شده: {Number(importJob.progress.processed || 0).toLocaleString('fa-IR')} از {Number(importJob.progress.total || 0).toLocaleString('fa-IR')}</Typography></Box>
            {importActive && <Button variant="outlined" color="warning" disabled={importJob.state === 'cancelling'} onClick={() => void api<{ job: ImportJob }>('POST', '/api/v1/contacts/import/cancel', { job_id: importJob.job_id }).then(response => setImportJob(response.job))}>لغو ایمن</Button>}
          </Stack>
          {importActive && <LinearProgress variant={Number(importJob.progress.total || 0) ? 'determinate' : 'indeterminate'} value={Number(importJob.progress.total || 0) ? Number(importJob.progress.processed || 0) / Number(importJob.progress.total || 1) * 100 : undefined} />}
          {importJob.error?.message && <Alert severity="error">{importJob.error.message}</Alert>}
          {importJob.error?.error_code && <Typography variant="caption" color="text.secondary">کد پیگیری: {importJob.error.error_code}</Typography>}
          {Number(importJob.progress.eitaa_failed || 0) > 0 && importJob.state === 'completed' && <Alert severity="warning">
            عملیات پایان یافت، اما افزودن {Number(importJob.progress.eitaa_failed).toLocaleString('fa-IR')} مخاطب به ایتا ناموفق بود. جزئیات امن در لاگ عملیات ثبت شده است.
          </Alert>}
          {(importJob.progress.eitaa_total !== undefined || importJob.progress.eitaa_added !== undefined) && <Typography variant="body2" color="text.secondary">
            ایتا: {Number(importJob.progress.eitaa_added || 0).toLocaleString('fa-IR')} افزوده‌شده · {Number(importJob.progress.eitaa_updated || 0).toLocaleString('fa-IR')} به‌روزشده · {Number(importJob.progress.eitaa_existing || 0).toLocaleString('fa-IR')} موجود · {Number(importJob.progress.eitaa_failed || 0).toLocaleString('fa-IR')} ناموفق
          </Typography>}
        </Stack>
      </Paper>}
      {tab === 'eitaa' && <Grid container spacing={2}>
        <Grid size={{ xs: 12, lg: 4 }}>
          <Paper variant="outlined" sx={{ p: { xs: 1.5, sm: 2 } }}><Stack spacing={1.5}>
            <Box><Typography fontWeight={900}>افزودن مستقیم به مخاطبان ایتا</Typography><Typography variant="body2" color="text.secondary">مخاطب هم‌زمان در ایتا و دفترچه محلی ذخیره می‌شود تا دوباره‌کاری ایجاد نشود.</Typography></Box>
            <TextField label="شماره تماس" value={eitaaDraft.phone} onChange={event => setEitaaDraft(current => ({ ...current, phone: event.target.value }))} inputMode="tel" />
            <Grid container spacing={1.25}><Grid size={{ xs: 12, sm: 6, lg: 12, xl: 6 }}><TextField label="نام" value={eitaaDraft.first_name} onChange={event => setEitaaDraft(current => ({ ...current, first_name: event.target.value }))} /></Grid><Grid size={{ xs: 12, sm: 6, lg: 12, xl: 6 }}><TextField label="نام خانوادگی" value={eitaaDraft.last_name} onChange={event => setEitaaDraft(current => ({ ...current, last_name: event.target.value }))} /></Grid></Grid>
            <Box><Typography variant="subtitle2">دسته محلی اختیاری</Typography>{categoryChecks(eitaaCategoryIds, setEitaaCategoryIds)}</Box>
            <Button variant="contained" startIcon={<PersonAddAltRounded />} disabled={!canWriteProviderContacts || busy || !eitaaDraft.phone.trim() || !eitaaDraft.first_name.trim()} onClick={() => void addEitaaContact()}>افزودن به ایتا</Button>
            <Divider />
            <Alert severity="info">دکمه همگام‌سازی، مخاطبان دارای شماره را بدون ساخت رکورد تکراری به دفترچه محلی اضافه یا به‌روزرسانی می‌کند.</Alert>
            <Button variant="outlined" startIcon={<SyncRounded />} disabled={eitaaLoading} onClick={() => void loadEitaaContacts(true, true)}>همگام‌سازی با دفترچه محلی</Button>
            <Divider />
            <Box><Typography fontWeight={900}>افزودن دسته‌های محلی به ایتا</Typography><Typography variant="body2" color="text.secondary">برای شماره‌های تکراری رکورد تازه ساخته نمی‌شود. عملیات پس‌زمینه و قابل لغو است.</Typography></Box>
            {categoryChecks(pushToEitaaCategoryIds, setPushToEitaaCategoryIds)}
            <Button variant="contained" color="secondary" startIcon={<SyncRounded />} disabled={!canWriteProviderContacts || !pushToEitaaCategoryIds.length || importActive} onClick={() => void pushLocalCategoriesToEitaa()}>افزودن دسته‌ها به حساب انتخاب‌شده</Button>
          </Stack></Paper>
        </Grid>
        <Grid size={{ xs: 12, lg: 8 }}>
          <Paper variant="outlined" sx={{ p: { xs: 1.5, sm: 2 } }}><Stack spacing={1.5}>
            <Grid container spacing={1.25} alignItems="center"><Grid size={{ xs: 12, sm: 9 }}><TextField label="جست‌وجوی مخاطبان ایتا" value={eitaaSearch} onChange={event => setEitaaSearch(event.target.value)} /></Grid><Grid size={{ xs: 12, sm: 3 }}><Button fullWidth variant="outlined" startIcon={eitaaLoading ? <CircularProgress size={18} /> : <RefreshRounded />} disabled={eitaaLoading} onClick={() => void loadEitaaContacts(true, false)}>تازه‌سازی</Button></Grid></Grid>
            <Typography variant="caption" color="text.secondary">
              {visibleEitaa.length.toLocaleString('fa-IR')} از {eitaaTotal.toLocaleString('fa-IR')} مخاطب بارگیری شده است؛ ادامه فهرست با نزدیک‌شدن به انتهای اسکرول دریافت می‌شود.
            </Typography>
            <Paper variant="outlined" sx={{ p: 1.25, bgcolor: 'background.default' }}>
              <Stack spacing={1}>
                <Stack direction={{ xs: 'column', sm: 'row' }} alignItems={{ xs: 'stretch', sm: 'center' }} justifyContent="space-between" gap={1}>
                  <FormControlLabel
                    sx={{ m: 0 }}
                    control={<Checkbox
                      checked={allLoadedEitaaSelected}
                      indeterminate={!allLoadedEitaaSelected && someLoadedEitaaSelected}
                      onChange={event => {
                        const loadedIds = visibleEitaa.map(contact => contact.user_id)
                        setEitaaSelectedIds(current => event.target.checked
                          ? [...new Set([...current, ...loadedIds])]
                          : current.filter(id => !loadedIds.includes(id)))
                      }}
                    />}
                    label="انتخاب همه مخاطبان بارگیری‌شده"
                  />
                  <Typography variant="body2" color={selectedEitaaCount ? 'primary.main' : 'text.secondary'}>
                    {selectedEitaaCount.toLocaleString('fa-IR')} مخاطب انتخاب شده
                  </Typography>
                </Stack>
                {categories.length ? <>
                  <FormControl fullWidth size="small">
                    <InputLabel id="eitaa-category-operation-label">نوع تغییر دسته</InputLabel>
                    <Select
                      labelId="eitaa-category-operation-label"
                      value={eitaaCategoryOperation}
                      label="نوع تغییر دسته"
                      onChange={event => setEitaaCategoryOperation(event.target.value as EitaaCategoryOperation)}
                    >
                      <MenuItem value="add">افزودن — حفظ دسته‌های قبلی</MenuItem>
                      <MenuItem value="remove">حذف — فقط از دسته‌های انتخابی</MenuItem>
                      <MenuItem value="replace">انتقال — جایگزینی همه دسته‌های قبلی</MenuItem>
                    </Select>
                  </FormControl>
                  <Box>
                    <Typography variant="subtitle2">
                      {eitaaCategoryOperation === 'remove'
                        ? 'دسته‌هایی که مخاطبان از آن‌ها حذف می‌شوند'
                        : eitaaCategoryOperation === 'replace'
                          ? 'دسته‌های مقصد (جایگزین دسته‌های قبلی)'
                          : 'دسته‌هایی که به مخاطبان افزوده می‌شوند'}
                    </Typography>
                    {categoryChecks(eitaaAssignCategoryIds, setEitaaAssignCategoryIds)}
                  </Box>
                  {eitaaCategorizing && <Box>
                    <LinearProgress variant="determinate" value={eitaaCategoryProgress} />
                    <Typography variant="caption" color="text.secondary">
                      {eitaaCategoryProgress.toLocaleString('fa-IR')}٪ انجام شده
                    </Typography>
                  </Box>}
                  <Button
                    variant="contained"
                    startIcon={eitaaCategorizing ? <CircularProgress size={18} color="inherit" /> : <LabelRounded />}
                    disabled={eitaaCategorizing || !selectedEitaaCount || !eitaaAssignCategoryIds.length}
                    onClick={() => void categorizeSelectedEitaaContacts()}
                  >
                    {eitaaCategoryOperation === 'remove'
                      ? 'حذف از دسته برای '
                      : eitaaCategoryOperation === 'replace'
                        ? 'انتقال دسته‌ای '
                        : 'ثبت دسته برای '}
                    {selectedEitaaCount.toLocaleString('fa-IR')} مخاطب
                  </Button>
                </> : <Alert severity="info" action={<Button color="inherit" size="small" onClick={() => setTab('categories')}>ساخت دسته</Button>}>ابتدا یک دسته محلی بسازید.</Alert>}
              </Stack>
            </Paper>
            <Stack
              spacing={1}
              role="feed"
              aria-label="فهرست پیمایشی مخاطبان ایتا"
              aria-busy={eitaaLoading}
              onScroll={event => {
                const node = event.currentTarget
                if (eitaaHasMore && !eitaaLoadingRef.current && node.scrollHeight - node.scrollTop - node.clientHeight < 240) {
                  void loadEitaaContacts(false, false, true)
                }
              }}
              sx={{ maxHeight: { xs: '52vh', md: '60vh' }, overflowY: 'auto', overscrollBehavior: 'contain', pr: .5 }}
            >
              {visibleEitaa.map(contact => {
                const selected = eitaaSelectedIds.includes(contact.user_id)
                return <Paper key={contact.user_id} component="article" variant="outlined" sx={{ p: 1.25, borderColor: selected ? 'primary.main' : 'divider', bgcolor: selected ? 'action.selected' : 'background.paper' }}>
                  <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" gap={1.25}>
                    <Stack direction="row" gap={1} minWidth={0} alignItems="flex-start">
                      <Checkbox
                        size="small"
                        checked={selected}
                        inputProps={{ 'aria-label': `انتخاب ${contact.display_name}` }}
                        onChange={event => setEitaaSelectedIds(current => event.target.checked ? [...current, contact.user_id] : current.filter(id => id !== contact.user_id))}
                      />
                      <EitaaContactAvatar contact={contact} siteKey={siteKey} />
                      <Box minWidth={0}>
                        <Typography fontWeight={900}>{contact.display_name}</Typography>
                        <Typography variant="body2" color="text.secondary" sx={{ overflowWrap: 'anywhere' }}>{contact.phone || 'شماره توسط ایتا نمایش داده نشده'}{contact.username ? ` · @${contact.username}` : ''}</Typography>
                        <Stack direction="row" gap={.5} mt={.5} flexWrap="wrap">
                          {contact.mutual && <Chip size="small" color="success" label="دوطرفه" />}
                          {contact.status?.kind && <Chip size="small" label={contact.status.kind === 'online' ? 'برخط' : 'وضعیت محدود'} />}
                          {(contact.local_categories || []).map(category => <Chip key={category.id} size="small" color="secondary" variant="outlined" icon={<LabelRounded />} label={category.name} />)}
                        </Stack>
                      </Box>
                    </Stack>
                    <Stack direction="row" gap={.5} flexWrap="wrap" alignSelf={{ xs: 'stretch', sm: 'center' }}>
                      <Tooltip title={contact.peer_file ? 'بازکردن گفت‌وگوی مستقیم و فرم ارسال پیام' : 'اطلاعات فنی گفت‌وگو در دسترس نیست'}>
                        <span><Button size="small" variant="outlined" startIcon={<SendRounded />} disabled={!contact.peer_file} onClick={() => handoffContact(contact)}>ارسال پیام</Button></span>
                      </Tooltip>
                      <Tooltip title={contact.phone ? 'حذف فقط از دفترچه ایتا؛ نسخه محلی باقی می‌ماند' : 'شماره برای حذف در دسترس نیست'}>
                        <span><Button size="small" color="error" startIcon={<DeleteOutlineRounded />} disabled={!canWriteProviderContacts || !contact.phone} onClick={() => void removeEitaaContact(contact)}>حذف از ایتا</Button></span>
                      </Tooltip>
                    </Stack>
                  </Stack>
                </Paper>
              })}
              {!visibleEitaa.length && !eitaaLoading && <Alert severity="info">مخاطبی یافت نشد.</Alert>}
              {eitaaLoading && <Stack alignItems="center" py={1.5}><CircularProgress size={24} /><Typography variant="caption" color="text.secondary">در حال بارگیری مخاطبان بیشتر…</Typography></Stack>}
              {!eitaaLoading && visibleEitaa.length > 0 && <Typography textAlign="center" variant="caption" color="text.secondary" py={1}>{eitaaHasMore ? 'برای دریافت ادامه فهرست، به پایین اسکرول کنید.' : 'به پایان فهرست مخاطبان رسیدید.'}</Typography>}
            </Stack>
          </Stack></Paper>
        </Grid>
      </Grid>}

      {tab === 'local' && <Grid container spacing={2}>
        <Grid size={{ xs: 12, lg: 4 }}><Paper variant="outlined" sx={{ p: { xs: 1.5, sm: 2 } }}><Stack spacing={1.5}>
          <Alert severity="info">این دفترچه و دسته‌های آن میان کاربران نرم‌افزار مشترک است؛ افزودن به پیام‌رسان فقط با حسابی انجام می‌شود که در بالای برنامه انتخاب کرده‌اید.</Alert>
          <Box><Typography fontWeight={900}>{draft.id ? 'ویرایش مخاطب محلی' : 'مخاطب محلی جدید'}</Typography><Typography variant="body2" color="text.secondary">شماره‌ها را با ویرگول یا خط جدید جدا کنید.</Typography></Box>
          <Grid container spacing={1.25}><Grid size={{ xs: 12, sm: 6, lg: 12, xl: 6 }}><TextField label="نام" value={draft.first_name} onChange={event => setDraft(current => ({ ...current, first_name: event.target.value }))} /></Grid><Grid size={{ xs: 12, sm: 6, lg: 12, xl: 6 }}><TextField label="نام خانوادگی" value={draft.last_name} onChange={event => setDraft(current => ({ ...current, last_name: event.target.value }))} /></Grid><Grid size={{ xs: 12 }}><TextField label="شماره تماس" value={draft.phones} onChange={event => setDraft(current => ({ ...current, phones: event.target.value }))} multiline minRows={2} /></Grid><Grid size={{ xs: 12, sm: 6, lg: 12 }}><TextField label="نام کاربری" value={draft.username} onChange={event => setDraft(current => ({ ...current, username: event.target.value }))} /></Grid><Grid size={{ xs: 12, sm: 6, lg: 12 }}><TextField label="سازمان یا واحد" value={draft.organization} onChange={event => setDraft(current => ({ ...current, organization: event.target.value }))} /></Grid><Grid size={{ xs: 12 }}><TextField label="یادداشت" value={draft.notes} onChange={event => setDraft(current => ({ ...current, notes: event.target.value }))} multiline minRows={2} /></Grid></Grid>
          <Box><Typography variant="subtitle2">دسته‌ها</Typography>{categoryChecks(draft.category_ids, category_ids => setDraft(current => ({ ...current, category_ids })))}</Box>
          {!draft.id && <FormControlLabel control={<Switch checked={addManualToEitaa} disabled={!canWriteProviderContacts} onChange={event => setAddManualToEitaa(event.target.checked)} />} label="این شماره به حساب پیام‌رسان انتخاب‌شده نیز افزوده شود" />}
          <Stack direction={{ xs: 'column', sm: 'row' }} gap={1}><FormControlLabel control={<Checkbox checked={draft.sendable} onChange={event => setDraft(current => ({ ...current, sendable: event.target.checked }))} />} label="قابل ارسال" /><FormControlLabel control={<Checkbox checked={draft.opt_out} onChange={event => setDraft(current => ({ ...current, opt_out: event.target.checked }))} />} label="عدم تمایل به دریافت" /></Stack>
          <Stack direction={{ xs: 'column', sm: 'row' }} gap={1} justifyContent="flex-end">{draft.id && <Button onClick={() => setDraft(EMPTY_CONTACT)}>انصراف</Button>}<Button variant="contained" disabled={busy || !draft.phones.trim()} onClick={() => void saveContact()}>{busy ? 'در حال ذخیره…' : 'ذخیره مخاطب'}</Button></Stack>
        </Stack></Paper></Grid>
        <Grid size={{ xs: 12, lg: 8 }}><Paper variant="outlined" sx={{ p: { xs: 1.5, sm: 2 } }}><Stack spacing={1.5}>
          <Grid container spacing={1.25}><Grid size={{ xs: 12, md: 7 }}><TextField label="جست‌وجوی نام، شماره یا سازمان" value={search} onChange={event => setSearch(event.target.value)} /></Grid><Grid size={{ xs: 12, sm: 6, md: 3 }}><FormControl><InputLabel>تعداد در صفحه</InputLabel><Select label="تعداد در صفحه" value={String(contactLimit)} onChange={event => setContactLimit(Number(event.target.value))}><MenuItem value="50">۵۰</MenuItem><MenuItem value="100">۱۰۰</MenuItem><MenuItem value="250">۲۵۰</MenuItem></Select></FormControl></Grid><Grid size={{ xs: 12, sm: 6, md: 2 }}><Button fullWidth variant="outlined" onClick={() => { setSearch(''); setFilterCategoryIds([]) }}>پاک‌کردن</Button></Grid></Grid>
          <Box>{categoryChecks(filterCategoryIds, setFilterCategoryIds)}</Box>
          <Stack spacing={1} sx={{ maxHeight: { xs: '52vh', md: '58vh' }, overflow: 'auto', pr: .5 }}>{contacts.length ? contacts.map(contact => <Paper key={contact.id} variant="outlined" sx={{ p: 1.25, opacity: contact.opt_out || !contact.sendable ? .62 : 1 }}><Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" gap={1.25}><Box minWidth={0}><Typography fontWeight={900}>{`${contact.first_name} ${contact.last_name}`.trim() || contact.username || 'بدون نام'}</Typography><Typography variant="body2" color="text.secondary" sx={{ overflowWrap: 'anywhere' }}>{contact.phones.join('، ') || 'بدون شماره'}{contact.organization ? ` · ${contact.organization}` : ''}</Typography><Stack direction="row" gap={.5} flexWrap="wrap" mt={.75}><Chip size="small" variant="outlined" label="مشترک" />{contact.categories.map(item => <Chip key={item.id} size="small" label={item.name} />)}{contact.source.includes('eitaa') && <Chip size="small" color="primary" label="ایتایی" />}{contact.selected_account_binding?.reachability === 'reachable' && <Chip size="small" color="success" label="در حساب انتخاب‌شده موجود است" />}{contact.opt_out && <Chip size="small" color="warning" label="عدم تمایل" />}</Stack><Typography variant="caption" color="text.secondary">آخرین تغییر: {new Date(contact.updated_at).toLocaleString('fa-IR')}</Typography></Box><Stack direction="row" gap={.5} flexWrap="wrap" alignSelf={{ xs: 'stretch', sm: 'center' }}><Button size="small" variant="outlined" startIcon={<PersonAddAltRounded />} disabled={!canWriteProviderContacts || importActive || !contact.phones.length || !contact.first_name.trim()} onClick={() => void pushLocalContactToSelectedAccount(contact)}>افزودن به حساب انتخاب‌شده</Button><Button size="small" variant="outlined" startIcon={<EditOutlined />} onClick={() => editContact(contact)}>ویرایش</Button><Button size="small" color="warning" startIcon={<ArchiveOutlined />} onClick={() => void archiveContact(contact)}>بایگانی</Button></Stack></Stack></Paper>) : <Alert severity="info">مخاطبی با این فیلتر وجود ندارد.</Alert>}</Stack>
          {Math.ceil(contactTotal / contactLimit) > 1 && <Pagination sx={{ alignSelf: 'center' }} count={Math.ceil(contactTotal / contactLimit)} page={contactPage} onChange={(_, value) => setContactPage(value)} color="primary" />}
        </Stack></Paper></Grid>
      </Grid>}

      {tab === 'categories' && <Paper variant="outlined" sx={{ p: { xs: 1.5, sm: 2 } }}><Stack spacing={2}><Alert severity="info">دسته‌ها نیز مانند دفترچهٔ محلی، مشترک و قابل استفاده برای همهٔ کاربران نرم‌افزار هستند.</Alert><Grid container spacing={1.5} alignItems="center"><Grid size={{ xs: 12, sm: 8 }}><TextField label="نام دسته" value={categoryName} onChange={event => setCategoryName(event.target.value)} /></Grid><Grid size={{ xs: 12, sm: 4 }}><Button fullWidth variant="contained" onClick={() => void saveCategory()} disabled={!categoryName.trim()}>{editingCategoryId ? 'ذخیره تغییر نام' : 'ساخت دسته'}</Button></Grid></Grid><Stack spacing={1}>{categories.map(category => <Paper key={category.id} variant="outlined" sx={{ p: 1.25 }}><Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" gap={1}><Box><Typography fontWeight={800}>{category.name}</Typography><Typography variant="caption" color="text.secondary">{category.member_count.toLocaleString('fa-IR')} مخاطب</Typography></Box><Stack direction="row" gap={1}><Button size="small" variant="outlined" onClick={() => { setEditingCategoryId(category.id); setCategoryName(category.name) }}>تغییر نام</Button><Button size="small" color="error" onClick={() => void deleteCategory(category)}>حذف</Button></Stack></Stack></Paper>)}</Stack></Stack></Paper>}

      {tab === 'import' && <Stack spacing={2}>
        <Paper variant="outlined" sx={{ p: { xs: 1.5, sm: 2 } }}><Stack spacing={2}><Alert severity="info">Excel، CSV یا TXT ابتدا پیش‌نمایش می‌شود. شمارهٔ تکراری مخاطب تازه نمی‌سازد؛ نام‌های جدید به‌روزرسانی و دسته‌های فایل‌های مختلف با همان مخاطب ادغام می‌شوند. برای افزودن به پیام‌رسان، ستون نام الزامی است.</Alert><Button component="label" variant="outlined" startIcon={<UploadFileRounded />} disabled={busy || importActive}>انتخاب فایل<input hidden type="file" accept=".xlsx,.csv,.txt" onChange={event => void chooseFile(event.target.files?.[0])} /></Button>{preview && <><Grid container spacing={1.25}>{importFields.map(([field, label]) => <Grid key={field} size={{ xs: 12, sm: 6, md: 4 }}><FormControl><InputLabel>{label}</InputLabel><Select label={label} value={mapping[field] || ''} onChange={event => setMapping(current => ({ ...current, [field]: String(event.target.value) }))}><MenuItem value="">نادیده گرفته شود</MenuItem>{preview.headers.map((header, index) => <MenuItem key={index} value={String(index)}>{header}</MenuItem>)}</Select></FormControl></Grid>)}</Grid><Box><Typography variant="subtitle2">افزودن به دسته‌های:</Typography>{categoryChecks(importCategoryIds, setImportCategoryIds)}</Box><FormControlLabel control={<Switch checked={importAddToEitaa} onChange={event => setImportAddToEitaa(event.target.checked)} />} label="پس از ورود محلی، شماره‌ها به حساب انتخاب‌شده نیز افزوده شوند" /><TableContainer component={Paper} variant="outlined" sx={{ maxHeight: 300 }}><Table stickyHeader size="small"><TableHead><TableRow>{preview.headers.map((header, index) => <TableCell key={index}>{header}</TableCell>)}</TableRow></TableHead><TableBody>{preview.rows.slice(0, 12).map((row, rowIndex) => <TableRow key={rowIndex}>{preview.headers.map((_, columnIndex) => <TableCell key={columnIndex}>{row[columnIndex]}</TableCell>)}</TableRow>)}</TableBody></Table></TableContainer></>}{importJob && <Paper variant="outlined" sx={{ p: 1.5 }}><Stack spacing={1}><Stack direction="row" justifyContent="space-between"><Typography fontWeight={800}>{importJob.state === 'completed' ? 'کامل شد' : importJob.state === 'failed' ? 'ناموفق' : 'در حال پردازش'}</Typography><Typography>{Number(importJob.progress.processed || 0).toLocaleString('fa-IR')} / {Number(importJob.progress.total || 0).toLocaleString('fa-IR')}</Typography></Stack><LinearProgress variant="determinate" value={Number(importJob.progress.total || 0) ? Number(importJob.progress.processed || 0) / Number(importJob.progress.total || 1) * 100 : 0} /></Stack></Paper>}<Stack direction="row" justifyContent="flex-end">{importActive ? <Button variant="outlined" color="warning" disabled={importJob?.state === 'cancelling'} onClick={() => importJob && void api<{ job: ImportJob }>('POST', '/api/v1/contacts/import/cancel', { job_id: importJob.job_id }).then(response => setImportJob(response.job))}>لغو ایمن</Button> : <Button variant="contained" disabled={!preview || !mapping.phone} onClick={() => void startImport()}>شروع ورود</Button>}</Stack></Stack></Paper>
        <Paper variant="outlined" sx={{ p: { xs: 1.5, sm: 2 } }}><Stack spacing={1.5}><Typography fontWeight={900}>فهرست‌های شماره شناسایی‌شده قبلی</Typography><Typography variant="body2" color="text.secondary">شماره‌هایی که قبلاً در ایتا شناسایی‌شده‌اند بدون حذف پس از کمپین، به دفترچه محلی منتقل می‌شوند.</Typography><Grid container spacing={1.25}>{phoneLists.length ? phoneLists.map(list => <Grid key={list.id} size={{ xs: 12, md: 6 }}><Paper variant="outlined" sx={{ p: 1.5, height: '100%' }}><Stack spacing={1}><Typography fontWeight={900}>{list.name || 'فهرست بدون نام'}</Typography><Typography variant="body2" color="text.secondary">شناسایی‌شده: {Number(list.resolved_count || 0).toLocaleString('fa-IR')} از {Number(list.total_rows || 0).toLocaleString('fa-IR')}</Typography><Button variant="outlined" disabled={!list.resolved_count || importActive} onClick={() => void startPhoneListImport(list)}>افزودن به دفترچه دائمی</Button></Stack></Paper></Grid>) : <Grid size={{ xs: 12 }}><Alert severity="info">فهرست شناسایی‌شده‌ای وجود ندارد.</Alert></Grid>}</Grid></Stack></Paper>
      </Stack>}

      {tab === 'targets' && <Paper variant="outlined" sx={{ p: { xs: 1.5, sm: 2 } }}>
        <Stack spacing={2}>
          <Alert severity="info">فقط مخاطبان دسته‌های علامت‌خورده نمایش داده می‌شوند. برداشتن تیک یک دسته، اعضای اختصاصی همان دسته را فوراً از فهرست و انتخاب‌های دستی خارج می‌کند.</Alert>
          <Box><Typography variant="subtitle2">دسته‌های هدف</Typography>{categoryChecks(targetCategoryIds, setTargetCategoryIds)}</Box>
          {!targetCategoryIds.length ? <Alert severity="warning">برای نمایش مخاطبان هدف، حداقل یک دسته را انتخاب کنید.</Alert> : <>
            <Grid container spacing={1.25} alignItems="center">
              <Grid size={{ xs: 12, md: 8 }}><TextField label="جست‌وجو در دسته‌های انتخاب‌شده" value={targetSearch} onChange={event => setTargetSearch(event.target.value)} /></Grid>
              <Grid size={{ xs: 12, md: 4 }}><Typography variant="body2" color="text.secondary">{targetTotal.toLocaleString('fa-IR')} مخاطب منطبق</Typography></Grid>
            </Grid>
            <Stack spacing={1} sx={{ maxHeight: '42vh', overflow: 'auto' }}>
              {targetContacts.length ? targetContacts.map(contact => <Paper key={contact.id} variant="outlined" sx={{ p: 1 }}>
                <Stack direction={{ xs: 'column', sm: 'row' }} justifyContent="space-between" gap={1}>
                  <Box><Typography fontWeight={800}>{`${contact.first_name} ${contact.last_name}`.trim() || contact.username || `مخاطب ${contact.id.toLocaleString('fa-IR')}`}</Typography><Typography variant="caption" color="text.secondary">{contact.phones.join('، ') || 'بدون شماره'}</Typography></Box>
                  <Stack direction={{ xs: 'column', sm: 'row' }} gap={1}>
                    <Button size="small" variant={targetIncludeIds.includes(contact.id) ? 'contained' : 'outlined'} onClick={() => { setTargetIncludeIds(current => current.includes(contact.id) ? current.filter(id => id !== contact.id) : [...current, contact.id]); setTargetExcludeIds(current => current.filter(id => id !== contact.id)) }}>افزودن صریح</Button>
                    <Button size="small" color="error" variant={targetExcludeIds.includes(contact.id) ? 'contained' : 'text'} onClick={() => { setTargetExcludeIds(current => current.includes(contact.id) ? current.filter(id => id !== contact.id) : [...current, contact.id]); setTargetIncludeIds(current => current.filter(id => id !== contact.id)) }}>حذف از هدف</Button>
                  </Stack>
                </Stack>
              </Paper>) : <Alert severity="info">در این صفحه مخاطبی با فیلتر انتخابی وجود ندارد.</Alert>}
            </Stack>
            {targetPageCount > 1 && <Pagination sx={{ alignSelf: 'center' }} count={targetPageCount} page={Math.min(targetPage, targetPageCount)} onChange={(_, value) => setTargetPage(value)} color="primary" />}
          </>}
          <Button variant="contained" disabled={!targetCategoryIds.length && !targetIncludeIds.length} onClick={() => void previewTargets()}>ساخت پیش‌نمایش نهایی</Button>
          {targetResult && <Stack spacing={1.5}>
            <Alert severity={targetResult.truncated ? 'warning' : 'success'}>{targetResult.target_count.toLocaleString('fa-IR')} گیرنده یکتا · عدم تمایل: {(targetResult.omitted.opt_out || 0).toLocaleString('fa-IR')} · تکراری: {(targetResult.omitted.duplicate_phone || 0).toLocaleString('fa-IR')}</Alert>
            <TableContainer component={Paper} variant="outlined" sx={{ maxHeight: 280 }}><Table stickyHeader size="small"><TableHead><TableRow><TableCell>نام</TableCell><TableCell>شماره</TableCell></TableRow></TableHead><TableBody>{targetResult.targets.slice(0, 200).map(target => <TableRow key={`${target.contact_id}:${target.phone}`}><TableCell>{target.name || `مخاطب ${target.contact_id.toLocaleString('fa-IR')}`}</TableCell><TableCell>{target.phone}</TableCell></TableRow>)}</TableBody></Table></TableContainer>
            <Button variant="contained" color="secondary" disabled={!targetResult.target_count} onClick={() => handoffTargets(targetResult.targets.map(target => target.phone))}>انتقال {targetResult.target_count.toLocaleString('fa-IR')} گیرنده به فرم ارسال</Button>
          </Stack>}
        </Stack>
      </Paper>}
    </DialogContent>
    <Divider />
    <DialogActions sx={{ px: { xs: 1.5, sm: 2.5 }, py: 1.5 }}><Button onClick={close} disabled={importActive}>بستن</Button></DialogActions>
  </Dialog>
}

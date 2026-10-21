import React, { useEffect, useMemo, useState } from 'react'
import {
  Alert,
  Autocomplete,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  Divider,
  FormControl,
  IconButton,
  InputAdornment,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Tooltip,
  Typography,
  Switch,
  FormControlLabel,
} from '@mui/material'
import CloseRounded from '@mui/icons-material/CloseRounded'
import AddRounded from '@mui/icons-material/AddRounded'
import EditRounded from '@mui/icons-material/EditRounded'
import DeleteOutlineRounded from '@mui/icons-material/DeleteOutlineRounded'
import SearchRounded from '@mui/icons-material/SearchRounded'
import AccountBalanceRounded from '@mui/icons-material/AccountBalanceRounded'
import PersonRounded from '@mui/icons-material/PersonRounded'
import RefreshRounded from '@mui/icons-material/RefreshRounded'
import BarChartRounded from '@mui/icons-material/BarChartRounded'
import ContactPhoneRounded from '@mui/icons-material/ContactPhoneRounded'
import MenuBookRounded from '@mui/icons-material/MenuBookRounded'
import { api } from '../lib/api'
import {
  type ProgramCatalogItem,
  fetchProgramCatalog,
  saveProgramCatalogItem,
  toggleProgramActive,
} from '../lib/indicators'
import { LiaisonAuthorDialog } from './LiaisonAuthorDialog'

export interface JudicialUnitItem {
  unit_id: string
  name: string
  county: string
  unit_type: string
  display_name: string
  kind: 'provincial_hq' | 'judicial_domain' | string
  notes?: string
  source?: string
  created_at?: string
  updated_at?: string
}

export interface LiaisonItem {
  liaison_id: string
  unit_id: string
  full_name: string
  eitaa_username?: string
  eitaa_user_id?: string
  sender_key?: string
  phone?: string
  match_keywords?: string
  notes?: string
  unit_display_name?: string
  county?: string
  created_at?: string
  updated_at?: string
}

export interface UnitBaselineItem {
  unit_id: string
  staff_count: number
  family_multiplier: number
  imams_count: number
  prayer_rooms_count: number
  honored_count: number
  notes?: string
  updated_at?: string
}

export interface ImamItem {
  imam_id: string
  unit_id: string
  full_name: string
  position?: string
  source_kind?: string
  status?: string
  personnel_no?: string
  notes?: string
  created_at?: string
}

export interface VenueItem {
  venue_id: string
  unit_id: string
  name: string
  notes?: string
  created_at?: string
}

export interface PersonItem {
  person_id: string
  kind: 'employee' | 'family' | string
  full_name: string
  personnel_no?: string
  national_id?: string
  phone?: string
  relation?: string
  related_personnel_no?: string
  unit_id?: string
  gender?: string
  birth_year?: string
  notes?: string
  created_at?: string
}

interface Props {
  open: boolean
  onClose: () => void
  onDataChanged?: () => void
  initialTab?: number
}

const COMMON_UNIT_TYPES = [
  'دادگستری',
  'دادسرا',
  'شورای حل اختلاف',
  'اداره کل',
  'دادگاه‌های تجدیدنظر',
  'دادگاه عمومی بخش',
]

export function JudicialUnitsManagementModal({ open, onClose, onDataChanged, initialTab = 0 }: Props) {
  const [tab, setTab] = useState(initialTab)
  const [loading, setLoading] = useState(false)
  const [errorText, setErrorText] = useState('')
  const [successText, setSuccessText] = useState('')

  const [units, setUnits] = useState<JudicialUnitItem[]>([])
  const [counties, setCounties] = useState<string[]>([])
  const [liaisons, setLiaisons] = useState<LiaisonItem[]>([])
  const [programs, setPrograms] = useState<ProgramCatalogItem[]>([])
  const [baselines, setBaselines] = useState<UnitBaselineItem[]>([])
  const [imams, setImams] = useState<ImamItem[]>([])
  const [venues, setVenues] = useState<VenueItem[]>([])
  const [persons, setPersons] = useState<PersonItem[]>([])
  const [baselineSubTab, setBaselineSubTab] = useState<'capacity' | 'imams' | 'venues' | 'persons'>('capacity')
  const [baselineSearch, setBaselineSearch] = useState('')

  // Baseline Edit Dialog
  const [baselineModalOpen, setBaselineModalOpen] = useState(false)
  const [editingBaseline, setEditingBaseline] = useState<Partial<UnitBaselineItem> | null>(null)
  const [savingBaseline, setSavingBaseline] = useState(false)

  // Imam Modal
  const [imamModalOpen, setImamModalOpen] = useState(false)
  const [editingImam, setEditingImam] = useState<Partial<ImamItem> | null>(null)
  const [savingImam, setSavingImam] = useState(false)

  // Venue Modal
  const [venueModalOpen, setVenueModalOpen] = useState(false)
  const [editingVenue, setEditingVenue] = useState<Partial<VenueItem> | null>(null)
  const [savingVenue, setSavingVenue] = useState(false)

  // Person Modal
  const [personModalOpen, setPersonModalOpen] = useState(false)
  const [editingPerson, setEditingPerson] = useState<Partial<PersonItem> | null>(null)
  const [savingPerson, setSavingPerson] = useState(false)

  // Filters
  const [unitSearch, setUnitSearch] = useState('')
  const [unitCountyFilter, setUnitCountyFilter] = useState('')
  const [liaisonSearch, setLiaisonSearch] = useState('')
  const [programSearch, setProgramSearch] = useState('')
  const [programActiveFilter, setProgramActiveFilter] = useState<'all' | 'active' | 'inactive'>('all')

  // Edit / Add Unit Dialog
  const [unitModalOpen, setUnitModalOpen] = useState(false)
  const [editingUnit, setEditingUnit] = useState<Partial<JudicialUnitItem> | null>(null)

  // Edit / Add Liaison Dialog
  const [liaisonModalOpen, setLiaisonModalOpen] = useState(false)
  const [editingLiaison, setEditingLiaison] = useState<Partial<LiaisonItem> | null>(null)
  const [selectedLiaisonForProfile, setSelectedLiaisonForProfile] = useState<LiaisonItem | null>(null)

  // Edit / Add Program Catalog Item Dialog
  const [programModalOpen, setProgramModalOpen] = useState(false)
  const [editingProgram, setEditingProgram] = useState<Partial<ProgramCatalogItem> | null>(null)
  const [savingProgram, setSavingProgram] = useState(false)

  // Contact sync states
  const [syncingAll, setSyncingAll] = useState(false)
  const [syncingLiaisonId, setSyncingLiaisonId] = useState<string | null>(null)
  const [phonePromptLiaison, setPhonePromptLiaison] = useState<LiaisonItem | null>(null)
  const [phonePromptValue, setPhonePromptValue] = useState('')

  const handleSyncEitaaContact = async (l: LiaisonItem, customPhone?: string) => {
    const targetPhone = (customPhone ?? l.phone ?? '').trim()
    if (!targetPhone) {
      setPhonePromptLiaison(l)
      setPhonePromptValue('')
      return
    }
    setSyncingLiaisonId(l.liaison_id)
    setErrorText('')
    setSuccessText('')
    try {
      const res = await api<{
        ok: boolean
        message?: string
        full_name: string
        contact_display_name: string
        phone: string
      }>('POST', `/api/v3/reporting/liaisons/${l.liaison_id}/sync-eitaa-contact`, {
        phone: targetPhone,
      })
      setSuccessText(res.message || `رابط فرهنگی «${res.full_name}» با موفقیت با عنوان «${res.contact_display_name}» در مخاطبین ایتا ثبت شد.`)
      setPhonePromptLiaison(null)
      await loadData()
      onDataChanged?.()
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : 'خطا در ثبت مخاطب در ایتا')
    } finally {
      setSyncingLiaisonId(null)
    }
  }

  const handleSyncAllEitaaContacts = async () => {
    setSyncingAll(true)
    setErrorText('')
    setSuccessText('')
    try {
      const res = await api<{
        ok: boolean
        message?: string
        synced_count: number
        total: number
      }>('POST', '/api/v3/reporting/liaisons/sync-all-eitaa-contacts')
      setSuccessText(res.message || `${res.synced_count} رابط فرهنگی در مخاطبین ایتا ثبت شدند.`)
      await loadData()
      onDataChanged?.()
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : 'خطا در ثبت گروهی رابطین در ایتا')
    } finally {
      setSyncingAll(false)
    }
  }

  // Load data
  const loadData = async () => {
    setLoading(true)
    setErrorText('')
    try {
      const unitsRes = await api<{ units: JudicialUnitItem[]; counties: string[] }>('GET', '/api/v3/reporting/units')
      setUnits(unitsRes.units || [])
      setCounties(unitsRes.counties || [])

      const liaisonsRes = await api<{ liaisons: LiaisonItem[] }>('GET', '/api/v3/reporting/liaisons')
      setLiaisons(liaisonsRes.liaisons || [])

      const catalogRes = await fetchProgramCatalog({ include_inactive: true })
      setPrograms(catalogRes)

      try {
        const baseRes = await api<{ baselines: UnitBaselineItem[] }>('GET', '/api/v3/reporting/units/baselines')
        setBaselines(baseRes.baselines || [])
      } catch {}

      try {
        const imamRes = await api<{ imams: ImamItem[] }>('GET', '/api/v3/reporting/imams')
        setImams(imamRes.imams || [])
      } catch {}

      try {
        const venueRes = await api<{ venues: VenueItem[] }>('GET', '/api/v3/reporting/venues')
        setVenues(venueRes.venues || [])
      } catch {}

      try {
        const personRes = await api<{ persons: PersonItem[] }>('GET', '/api/v3/reporting/persons')
        setPersons(personRes.persons || [])
      } catch {}
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : 'خطا در بارگذاری اطلاعات')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (open) {
      setTab(initialTab)
      loadData()
    }
  }, [open, initialTab])

  // Filtered Units
  const filteredUnits = useMemo(() => {
    return units.filter(u => {
      const matchesCounty = !unitCountyFilter || u.county === unitCountyFilter
      const text = `${u.county} ${u.unit_type} ${u.display_name} ${u.name}`.toLowerCase()
      const matchesSearch = !unitSearch || text.includes(unitSearch.trim().toLowerCase())
      return matchesCounty && matchesSearch
    })
  }, [units, unitCountyFilter, unitSearch])

  // Filtered Liaisons
  const filteredLiaisons = useMemo(() => {
    return liaisons.filter(l => {
      const text = `${l.full_name} ${l.eitaa_username || ''} ${l.phone || ''} ${l.unit_display_name || ''} ${l.match_keywords || ''}`.toLowerCase()
      return !liaisonSearch || text.includes(liaisonSearch.trim().toLowerCase())
    })
  }, [liaisons, liaisonSearch])

  // Filtered Programs
  const filteredPrograms = useMemo(() => {
    return programs.filter(p => {
      if (programActiveFilter === 'active' && !p.is_active) return false
      if (programActiveFilter === 'inactive' && p.is_active) return false
      if (!programSearch.trim()) return true
      const term = programSearch.trim().toLowerCase()
      return (
        p.program_code.toLowerCase().includes(term) ||
        p.title.toLowerCase().includes(term) ||
        (p.canonical_macro && p.canonical_macro.toLowerCase().includes(term)) ||
        (p.workbook_sheet && p.workbook_sheet.toLowerCase().includes(term))
      )
    })
  }, [programs, programActiveFilter, programSearch])

  // Handle Toggle Program Active (Soft-Deprecation)
  const handleToggleProgramActive = async (p: ProgramCatalogItem) => {
    try {
      const newActive = !p.is_active
      await toggleProgramActive(p.program_code, newActive)
      setSuccessText(
        newActive
          ? `سرفصل برنامه «${p.title} (${p.program_code})» مجدداً فعال شد.`
          : `سرفصل برنامه «${p.title} (${p.program_code})» بدون حذف سوابق گذشته، از چرخه عملیاتی جاری خارج و بایگانی شد.`
      )
      await loadData()
      onDataChanged?.()
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : 'خطا در تغییر وضعیت برنامه')
    }
  }

  // Handlers for Baseline Banks
  const handleSaveBaseline = async () => {
    if (!editingBaseline || !editingBaseline.unit_id) return
    setSavingBaseline(true)
    setErrorText('')
    try {
      await api('POST', `/api/v3/reporting/units/${encodeURIComponent(editingBaseline.unit_id)}/baseline`, {
        staff_count: Number(editingBaseline.staff_count) || 0,
        family_multiplier: Number(editingBaseline.family_multiplier) || 2.5,
        imams_count: Number(editingBaseline.imams_count) || 0,
        prayer_rooms_count: Number(editingBaseline.prayer_rooms_count) || 0,
        honored_count: Number(editingBaseline.honored_count) || 0,
        notes: (editingBaseline.notes || '').trim(),
      })
      setSuccessText(`مشخصات ظرفیت و اطلاعات پایه حوزه «${editingBaseline.unit_id}» با موفقیت ذخیره شد.`)
      setBaselineModalOpen(false)
      setEditingBaseline(null)
      await loadData()
      onDataChanged?.()
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : 'خطا در ذخیره اطلاعات پایه')
    } finally {
      setSavingBaseline(false)
    }
  }

  const handleSaveImam = async () => {
    if (!editingImam || !editingImam.full_name || !editingImam.unit_id) {
      setErrorText('نام امام جماعت و حوزه قضایی الزامی است.')
      return
    }
    setSavingImam(true)
    setErrorText('')
    try {
      await api('POST', '/api/v3/reporting/imams', editingImam)
      setSuccessText(`امام جماعت «${editingImam.full_name}» ذخیره شد.`)
      setImamModalOpen(false)
      setEditingImam(null)
      await loadData()
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : 'خطا در ذخیره امام جماعت')
    } finally {
      setSavingImam(false)
    }
  }

  const handleDeleteImam = async (imamId: string) => {
    if (!window.confirm('آیا از حذف این امام جماعت اطمینان دارید؟')) return
    try {
      await api('DELETE', `/api/v3/reporting/imams/${imamId}`)
      setSuccessText('امام جماعت حذف شد.')
      await loadData()
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : 'خطا در حذف امام جماعت')
    }
  }

  const handleSaveVenue = async () => {
    if (!editingVenue || !editingVenue.name || !editingVenue.unit_id) {
      setErrorText('نام نمازخانه و حوزه قضایی الزامی است.')
      return
    }
    setSavingVenue(true)
    setErrorText('')
    try {
      await api('POST', '/api/v3/reporting/venues', editingVenue)
      setSuccessText(`نمازخانه «${editingVenue.name}» ذخیره شد.`)
      setVenueModalOpen(false)
      setEditingVenue(null)
      await loadData()
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : 'خطا در ذخیره نمازخانه')
    } finally {
      setSavingVenue(false)
    }
  }

  const handleDeleteVenue = async (venueId: string) => {
    if (!window.confirm('آیا از حذف این نمازخانه اطمینان دارید؟')) return
    try {
      await api('DELETE', `/api/v3/reporting/venues/${venueId}`)
      setSuccessText('نمازخانه حذف شد.')
      await loadData()
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : 'خطا در حذف نمازخانه')
    }
  }

  const handleSavePerson = async () => {
    if (!editingPerson || !editingPerson.full_name) {
      setErrorText('نام و نام خانوادگی الزامی است.')
      return
    }
    setSavingPerson(true)
    setErrorText('')
    try {
      await api('POST', '/api/v3/reporting/persons', editingPerson)
      setSuccessText(`شخص «${editingPerson.full_name}» در بانک پرسنلی ذخیره شد.`)
      setPersonModalOpen(false)
      setEditingPerson(null)
      await loadData()
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : 'خطا در ذخیره شخص')
    } finally {
      setSavingPerson(false)
    }
  }

  const handleDeletePerson = async (personId: string) => {
    if (!window.confirm('آیا از حذف این شخص از بانک اطلاعات اطمینان دارید؟')) return
    try {
      await api('DELETE', `/api/v3/reporting/persons/${personId}`)
      setSuccessText('شخص از بانک اطلاعات حذف شد.')
      await loadData()
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : 'خطا در حذف شخص')
    }
  }

  // Handle Save Program Catalog Item
  const handleSaveProgram = async () => {
    if (!editingProgram) return
    const code = (editingProgram.program_code || '').trim()
    const title = (editingProgram.title || '').trim()
    if (!code || !title) {
      setErrorText('کد برنامه و عنوان برنامه الزامی هستند.')
      return
    }
    setSavingProgram(true)
    setErrorText('')
    try {
      await saveProgramCatalogItem({
        program_code: code,
        title,
        canonical_macro: (editingProgram.canonical_macro || title).trim(),
        kind: editingProgram.kind || 'operational',
        workbook_sheet: (editingProgram.workbook_sheet || '').trim(),
        valid_from_year: Number(editingProgram.valid_from_year) || 1404,
        valid_to_year: editingProgram.valid_to_year ? Number(editingProgram.valid_to_year) : undefined,
        is_active: editingProgram.is_active !== false,
        display_order: Number(editingProgram.display_order) || 100,
        description: (editingProgram.description || '').trim(),
      })
      setSuccessText(`برنامه عملیاتی «${title} (${code})» با موفقیت ذخیره شد.`)
      setProgramModalOpen(false)
      setEditingProgram(null)
      await loadData()
      onDataChanged?.()
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : 'خطا در ذخیره برنامه در کاتالوگ')
    } finally {
      setSavingProgram(false)
    }
  }

  // Handle Save Unit
  const handleSaveUnit = async () => {
    if (!editingUnit) return
    const county = (editingUnit.county || '').trim()
    const unitType = (editingUnit.unit_type || '').trim()
    const name = (editingUnit.name || (county && unitType ? `${county} - ${unitType}` : '')).trim()
    const displayName = (editingUnit.display_name || name).trim()

    if (!county && !name) {
      setErrorText('نام شهرستان یا نام واحد الزامی است.')
      return
    }

    try {
      await api('POST', '/api/v3/reporting/units', {
        unit_id: editingUnit.unit_id || '',
        name,
        county,
        unit_type: unitType,
        display_name: displayName,
        kind: editingUnit.kind || 'judicial_domain',
        notes: editingUnit.notes || '',
      })
      setSuccessText('واحد قضایی با موفقیت ذخیره شد.')
      setUnitModalOpen(false)
      setEditingUnit(null)
      await loadData()
      onDataChanged?.()
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : 'خطا در ذخیره واحد قضایی')
    }
  }

  // Handle Delete Unit
  const handleDeleteUnit = async (unit: JudicialUnitItem) => {
    if (!window.confirm(`آیا از حذف حوزه قضایی «${unit.display_name || unit.name}» اطمینان دارید؟`)) return
    try {
      try {
        await api('DELETE', `/api/v3/reporting/units/${unit.unit_id}`)
      } catch {
        await api('POST', `/api/v3/reporting/units/${unit.unit_id}/delete`, {})
      }
      setSuccessText('واحد قضایی حذف شد.')
      await loadData()
      onDataChanged?.()
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : 'خطا در حذف واحد قضایی')
    }
  }

  // Handle Save Liaison
  const handleSaveLiaison = async () => {
    if (!editingLiaison) return
    if (!editingLiaison.full_name?.trim()) {
      setErrorText('نام و نام خانوادگی رابط الزامی است.')
      return
    }
    if (!editingLiaison.unit_id?.trim()) {
      setErrorText('انتخاب واحد قضایی متصل الزامی است.')
      return
    }

    try {
      await api('POST', '/api/v3/reporting/liaisons', {
        liaison_id: editingLiaison.liaison_id || '',
        unit_id: editingLiaison.unit_id,
        full_name: editingLiaison.full_name.trim(),
        eitaa_username: editingLiaison.eitaa_username?.trim().replace(/^@/, '') || '',
        eitaa_user_id: editingLiaison.eitaa_user_id?.trim() || '',
        sender_key: editingLiaison.sender_key?.trim() || '',
        phone: editingLiaison.phone?.trim() || '',
        match_keywords: editingLiaison.match_keywords?.trim() || '',
        notes: editingLiaison.notes?.trim() || '',
      })
      setSuccessText('رابط فرهنگی با موفقیت ذخیره شد.')
      setLiaisonModalOpen(false)
      setEditingLiaison(null)
      await loadData()
      onDataChanged?.()
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : 'خطا در ذخیره رابط فرهنگی')
    }
  }

  // Handle Delete Liaison
  const handleDeleteLiaison = async (liaison: LiaisonItem) => {
    if (!window.confirm(`آیا از حذف رابط فرهنگی «${liaison.full_name}» اطمینان دارید؟`)) return
    try {
      try {
        await api('DELETE', `/api/v3/reporting/liaisons/${liaison.liaison_id}`)
      } catch {
        await api('POST', `/api/v3/reporting/liaisons/${liaison.liaison_id}/delete`, {})
      }
      setSuccessText('رابط فرهنگی حذف شد.')
      await loadData()
      onDataChanged?.()
    } catch (err) {
      setErrorText(err instanceof Error ? err.message : 'خطا در حذف رابط فرهنگی')
    }
  }

  return (
    <>
      <Dialog open={open} onClose={onClose} fullWidth maxWidth="lg">
        <DialogTitle sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', pb: 1 }}>
          <Stack direction="row" spacing={1.5} alignItems="center">
            <AccountBalanceRounded color="primary" />
            <Typography variant="h6" fontWeight={800}>
              مدیریت حوزه‌های قضایی، رابطین و سرفصل‌های برنامه‌ها
            </Typography>
          </Stack>
          <IconButton onClick={onClose} aria-label="بستن"><CloseRounded /></IconButton>
        </DialogTitle>

        <Divider />

        <Box sx={{ px: 3, pt: 1, bgcolor: 'background.paper' }}>
          <Tabs value={tab} onChange={(_, val) => { setTab(val); setErrorText(''); setSuccessText('') }}>
            <Tab
              icon={<AccountBalanceRounded sx={{ mr: 1, verticalAlign: 'middle' }} />}
              iconPosition="start"
              label={`حوزه‌ها و واحدهای قضایی (${units.length})`}
            />
            <Tab
              icon={<PersonRounded sx={{ mr: 1, verticalAlign: 'middle' }} />}
              iconPosition="start"
              label={`رابطین فرهنگی (${liaisons.length})`}
            />
            <Tab
              icon={<MenuBookRounded sx={{ mr: 1, verticalAlign: 'middle' }} />}
              iconPosition="start"
              label={`کاتالوگ و سرفصل‌های برنامه‌ها (${programs.length})`}
            />
            <Tab
              icon={<BarChartRounded sx={{ mr: 1, verticalAlign: 'middle' }} />}
              iconPosition="start"
              label="بانک اطلاعات پایه و ظرفیت‌سنجی حوزه‌ها"
            />
          </Tabs>
        </Box>

        <DialogContent sx={{ p: 3, bgcolor: 'background.default', minHeight: 460 }}>
          {errorText && <Alert severity="error" onClose={() => setErrorText('')} sx={{ mb: 2 }}>{errorText}</Alert>}
          {successText && <Alert severity="success" onClose={() => setSuccessText('')} sx={{ mb: 2 }}>{successText}</Alert>}

          {/* TAB 0: JUDICIAL UNITS */}
          {tab === 0 && (
            <Stack spacing={2}>
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems="center" justifyContent="space-between">
                <Stack direction="row" spacing={2} sx={{ flex: 1, width: { xs: '100%', sm: 'auto' } }}>
                  <TextField
                    size="small"
                    placeholder="جستجو بر اساس نام شهرستان، واحد یا نوع..."
                    value={unitSearch}
                    onChange={e => setUnitSearch(e.target.value)}
                    InputProps={{
                      startAdornment: <InputAdornment position="start"><SearchRounded fontSize="small" /></InputAdornment>,
                    }}
                    sx={{ flex: 1 }}
                  />
                  <FormControl size="small" sx={{ minWidth: 160 }}>
                    <Select
                      value={unitCountyFilter}
                      onChange={e => setUnitCountyFilter(e.target.value)}
                      displayEmpty
                    >
                      <MenuItem value="">همه شهرستان‌ها</MenuItem>
                      {counties.map(c => <MenuItem key={c} value={c}>{c}</MenuItem>)}
                    </Select>
                  </FormControl>
                </Stack>
                <Stack direction="row" spacing={1}>
                  <Button
                    variant="outlined"
                    startIcon={<RefreshRounded />}
                    onClick={loadData}
                    disabled={loading}
                  >
                    تازه‌سازی
                  </Button>
                  <Button
                    variant="contained"
                    startIcon={<AddRounded />}
                    onClick={() => {
                      setEditingUnit({
                        county: unitCountyFilter || 'ساری',
                        unit_type: 'دادگستری',
                        display_name: '',
                        kind: 'judicial_domain',
                        notes: '',
                      })
                      setUnitModalOpen(true)
                    }}
                  >
                    واحد جدید
                  </Button>
                </Stack>
              </Stack>

              {loading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}><CircularProgress /></Box>
              ) : (
                <TableContainer component={Paper} variant="outlined" sx={{ maxHeight: 440 }}>
                  <Table stickyHeader size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 800 }}>شهرستان</TableCell>
                        <TableCell sx={{ fontWeight: 800 }}>نوع واحد</TableCell>
                        <TableCell sx={{ fontWeight: 800 }}>نام نمایشی (حوزه قضایی)</TableCell>
                        <TableCell sx={{ fontWeight: 800 }}>رده سازمانی</TableCell>
                        <TableCell sx={{ fontWeight: 800, textAlign: 'center' }}>عملیات</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {filteredUnits.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={5} align="center" sx={{ py: 4, color: 'text.secondary' }}>
                            موردی یافت نشد.
                          </TableCell>
                        </TableRow>
                      ) : (
                        filteredUnits.map(u => (
                          <TableRow key={u.unit_id} hover>
                            <TableCell sx={{ fontWeight: 600 }}>{u.county || '—'}</TableCell>
                            <TableCell>{u.unit_type || '—'}</TableCell>
                            <TableCell sx={{ fontWeight: 700, color: 'primary.main' }}>
                              {u.display_name || u.name}
                            </TableCell>
                            <TableCell>
                              <Chip
                                size="small"
                                label={u.kind === 'provincial_hq' ? 'ستاد استانی' : 'حوزه قضایی'}
                                color={u.kind === 'provincial_hq' ? 'primary' : 'default'}
                                variant="outlined"
                              />
                            </TableCell>
                            <TableCell align="center">
                              <Tooltip title="ویرایش">
                                <IconButton
                                  size="small"
                                  onClick={() => {
                                    setEditingUnit({ ...u })
                                    setUnitModalOpen(true)
                                  }}
                                >
                                  <EditRounded fontSize="small" />
                                </IconButton>
                              </Tooltip>
                              <Tooltip title="حذف">
                                <IconButton
                                  size="small"
                                  color="error"
                                  onClick={() => handleDeleteUnit(u)}
                                >
                                  <DeleteOutlineRounded fontSize="small" />
                                </IconButton>
                              </Tooltip>
                            </TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </Stack>
          )}

          {/* TAB 1: CULTURAL LIAISONS */}
          {tab === 1 && (
            <Stack spacing={2}>
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems="center" justifyContent="space-between">
                <TextField
                  size="small"
                  placeholder="جستجو بر اساس نام رابط، نام کاربری ایتا، واحد قضایی..."
                  value={liaisonSearch}
                  onChange={e => setLiaisonSearch(e.target.value)}
                  InputProps={{
                    startAdornment: <InputAdornment position="start"><SearchRounded fontSize="small" /></InputAdornment>,
                  }}
                  sx={{ flex: 1, width: { xs: '100%', sm: 'auto' } }}
                />
                <Stack direction="row" spacing={1} flexWrap="wrap" gap={1}>
                  <Button
                    variant="outlined"
                    color="secondary"
                    startIcon={syncingAll ? <CircularProgress size={16} color="inherit" /> : <ContactPhoneRounded />}
                    onClick={handleSyncAllEitaaContacts}
                    disabled={loading || syncingAll}
                  >
                    {syncingAll ? 'در حال ثبت...' : 'ثبت همه در مخاطبین ایتا'}
                  </Button>
                  <Button
                    variant="outlined"
                    startIcon={<RefreshRounded />}
                    onClick={loadData}
                    disabled={loading}
                  >
                    تازه‌سازی
                  </Button>
                  <Button
                    variant="contained"
                    startIcon={<AddRounded />}
                    onClick={() => {
                      setEditingLiaison({
                        unit_id: units[0]?.unit_id || '',
                        full_name: '',
                        eitaa_username: '',
                        phone: '',
                        match_keywords: '',
                        notes: '',
                      })
                      setLiaisonModalOpen(true)
                    }}
                  >
                    رابط جدید
                  </Button>
                </Stack>
              </Stack>

              {loading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}><CircularProgress /></Box>
              ) : (
                <TableContainer component={Paper} variant="outlined" sx={{ maxHeight: 440 }}>
                  <Table stickyHeader size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 800 }}>نام و نام خانوادگی رابط</TableCell>
                        <TableCell sx={{ fontWeight: 800 }}>حوزه قضایی متصل</TableCell>
                        <TableCell sx={{ fontWeight: 800 }}>نام کاربری ایتا</TableCell>
                        <TableCell sx={{ fontWeight: 800 }}>شماره تماس</TableCell>
                        <TableCell sx={{ fontWeight: 800 }}>کلمات کلیدی تطبیق خودکار</TableCell>
                        <TableCell sx={{ fontWeight: 800, textAlign: 'center' }}>عملیات</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {filteredLiaisons.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={6} align="center" sx={{ py: 4, color: 'text.secondary' }}>
                            رابطی یافت نشد.
                          </TableCell>
                        </TableRow>
                      ) : (
                        filteredLiaisons.map(l => (
                          <TableRow key={l.liaison_id} hover>
                            <TableCell sx={{ fontWeight: 700, color: 'primary.main' }}>
                              <Stack spacing={0.25}>
                                <Typography variant="body2" fontWeight={800} color="primary.main">
                                  {l.full_name}
                                </Typography>
                                {l.unit_display_name && (
                                  <Typography variant="caption" color="text.secondary">
                                    {`${l.full_name} - حوزه قضایی ${l.unit_display_name}`}
                                  </Typography>
                                )}
                              </Stack>
                            </TableCell>
                            <TableCell sx={{ fontWeight: 600 }}>
                              {l.unit_display_name || '—'}
                            </TableCell>
                            <TableCell dir="ltr" align="right">
                              {l.eitaa_username ? `@${l.eitaa_username}` : '—'}
                            </TableCell>
                            <TableCell dir="ltr" align="right">{l.phone || '—'}</TableCell>
                            <TableCell sx={{ maxWidth: 220, fontSize: '0.8rem', color: 'text.secondary' }}>
                              {l.match_keywords || '—'}
                            </TableCell>
                            <TableCell align="center">
                              <Tooltip title="ثبت در مخاطبین ایتا با عنوان رسمی">
                                <IconButton
                                  size="small"
                                  color="success"
                                  onClick={() => handleSyncEitaaContact(l)}
                                  disabled={syncingLiaisonId === l.liaison_id}
                                >
                                  {syncingLiaisonId === l.liaison_id ? (
                                    <CircularProgress size={16} color="inherit" />
                                  ) : (
                                    <ContactPhoneRounded fontSize="small" />
                                  )}
                                </IconButton>
                              </Tooltip>
                              <Tooltip title="مشاهده کارنامه و پروفایل فعالیت">
                                <IconButton
                                  size="small"
                                  color="primary"
                                  onClick={() => setSelectedLiaisonForProfile(l)}
                                >
                                  <BarChartRounded fontSize="small" />
                                </IconButton>
                              </Tooltip>
                              <Tooltip title="ویرایش">
                                <IconButton
                                  size="small"
                                  onClick={() => {
                                    setEditingLiaison({ ...l })
                                    setLiaisonModalOpen(true)
                                  }}
                                >
                                  <EditRounded fontSize="small" />
                                </IconButton>
                              </Tooltip>
                              <Tooltip title="حذف">
                                <IconButton
                                  size="small"
                                  color="error"
                                  onClick={() => handleDeleteLiaison(l)}
                                >
                                  <DeleteOutlineRounded fontSize="small" />
                                </IconButton>
                              </Tooltip>
                            </TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </Stack>
          )}

          {/* TAB 2: PROGRAM CATALOG */}
          {tab === 2 && (
            <Stack spacing={2}>
              <Stack direction={{ xs: 'column', sm: 'row' }} spacing={2} alignItems="center" justifyContent="space-between">
                <Stack direction="row" spacing={2} sx={{ flex: 1, width: { xs: '100%', sm: 'auto' } }}>
                  <TextField
                    size="small"
                    placeholder="جستجو در کد، عنوان، شاخصه کلی یا برگه اکسل..."
                    value={programSearch}
                    onChange={e => setProgramSearch(e.target.value)}
                    InputProps={{
                      startAdornment: <InputAdornment position="start"><SearchRounded fontSize="small" /></InputAdornment>,
                    }}
                    sx={{ flex: 1 }}
                  />
                  <FormControl size="small" sx={{ minWidth: 160 }}>
                    <Select
                      value={programActiveFilter}
                      onChange={e => setProgramActiveFilter(e.target.value as 'all' | 'active' | 'inactive')}
                    >
                      <MenuItem value="all">همه برنامه‌ها</MenuItem>
                      <MenuItem value="active">فقط برنامه‌های فعال</MenuItem>
                      <MenuItem value="inactive">بایگانی شده / غیرفعال</MenuItem>
                    </Select>
                  </FormControl>
                </Stack>
                <Stack direction="row" spacing={1}>
                  <Button
                    variant="outlined"
                    startIcon={<RefreshRounded />}
                    onClick={loadData}
                    disabled={loading}
                  >
                    تازه‌سازی
                  </Button>
                  <Button
                    variant="contained"
                    startIcon={<AddRounded />}
                    onClick={() => {
                      setEditingProgram({
                        program_code: '',
                        title: '',
                        canonical_macro: '',
                        kind: 'operational',
                        workbook_sheet: '',
                        valid_from_year: 1404,
                        is_active: true,
                        display_order: (programs.length + 1) * 10,
                        description: '',
                      })
                      setProgramModalOpen(true)
                    }}
                  >
                    تعریف برنامه جدید
                  </Button>
                </Stack>
              </Stack>

              {loading ? (
                <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}><CircularProgress /></Box>
              ) : (
                <TableContainer component={Paper} variant="outlined" sx={{ maxHeight: 440 }}>
                  <Table stickyHeader size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 800 }}>کد برنامه</TableCell>
                        <TableCell sx={{ fontWeight: 800 }}>عنوان سرفصل برنامه</TableCell>
                        <TableCell sx={{ fontWeight: 800 }}>شاخصه کلی متناظر</TableCell>
                        <TableCell sx={{ fontWeight: 800 }}>برگه کارنامه اکسل</TableCell>
                        <TableCell sx={{ fontWeight: 800 }}>دوره اعتبار</TableCell>
                        <TableCell sx={{ fontWeight: 800, textAlign: 'center' }}>وضعیت عملیاتی</TableCell>
                        <TableCell sx={{ fontWeight: 800, textAlign: 'center' }}>عملیات</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {filteredPrograms.length === 0 ? (
                        <TableRow>
                          <TableCell colSpan={7} align="center" sx={{ py: 4, color: 'text.secondary' }}>
                            برنامه‌ای با این مشخصات یافت نشد.
                          </TableCell>
                        </TableRow>
                      ) : (
                        filteredPrograms.map(p => (
                          <TableRow key={p.program_code} hover sx={{ opacity: p.is_active ? 1 : 0.65 }}>
                            <TableCell>
                              <Chip
                                size="small"
                                label={p.program_code}
                                color={p.program_code === '00000' ? 'default' : 'primary'}
                                variant={p.is_active ? 'filled' : 'outlined'}
                                sx={{ fontFamily: 'monospace', fontWeight: 700 }}
                              />
                            </TableCell>
                            <TableCell sx={{ fontWeight: 700 }}>
                              {p.title}
                              {p.description && (
                                <Typography variant="caption" display="block" color="text.secondary">
                                  {p.description}
                                </Typography>
                              )}
                            </TableCell>
                            <TableCell sx={{ color: 'text.secondary', fontWeight: 600 }}>
                              {p.canonical_macro || '—'}
                            </TableCell>
                            <TableCell>
                              {p.workbook_sheet ? (
                                <Chip size="small" label={p.workbook_sheet} variant="outlined" />
                              ) : (
                                '—'
                              )}
                            </TableCell>
                            <TableCell sx={{ fontSize: '0.85rem' }}>
                              {p.valid_to_year
                                ? `${p.valid_from_year} تا ${p.valid_to_year}`
                                : `از ${p.valid_from_year} (جاری)`}
                            </TableCell>
                            <TableCell align="center">
                              <Tooltip
                                title={
                                  p.is_active
                                    ? 'برنامه فعال است (جهت خروج از رده و بایگانی بدون حذف کلیک کنید)'
                                    : 'برنامه غیرفعال / بایگانی شده (جهت فعال‌سازی مجدد کلیک کنید)'
                                }
                              >
                                <FormControlLabel
                                  control={
                                    <Switch
                                      checked={Boolean(p.is_active)}
                                      onChange={() => handleToggleProgramActive(p)}
                                      color="success"
                                      size="small"
                                    />
                                  }
                                  label={Boolean(p.is_active) ? 'فعال' : 'بایگانی'}
                                  sx={{ m: 0 }}
                                />
                              </Tooltip>
                            </TableCell>
                            <TableCell align="center">
                              <Tooltip title="ویرایش اطلاعات برنامه">
                                <IconButton
                                  size="small"
                                  onClick={() => {
                                    setEditingProgram({ ...p })
                                    setProgramModalOpen(true)
                                  }}
                                >
                                  <EditRounded fontSize="small" />
                                </IconButton>
                              </Tooltip>
                            </TableCell>
                          </TableRow>
                        ))
                      )}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}
            </Stack>
          )}

          {/* TAB 3: MASTER BASELINE BANKS & CAPACITY */}
          {tab === 3 && (
            <Stack spacing={2.5}>
              <Paper variant="outlined" sx={{ p: 1.5, borderRadius: 2 }}>
                <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} justifyContent="space-between" alignItems="center">
                  <Stack direction="row" spacing={1} sx={{ flexWrap: 'wrap', gap: 1 }}>
                    <Button
                      variant={baselineSubTab === 'capacity' ? 'contained' : 'outlined'}
                      size="small"
                      onClick={() => setBaselineSubTab('capacity')}
                    >
                      ظرفیت و داده‌های پایه حوزه‌ها ({units.length})
                    </Button>
                    <Button
                      variant={baselineSubTab === 'imams' ? 'contained' : 'outlined'}
                      size="small"
                      onClick={() => setBaselineSubTab('imams')}
                    >
                      بانک ائمه جماعات ({imams.length})
                    </Button>
                    <Button
                      variant={baselineSubTab === 'venues' ? 'contained' : 'outlined'}
                      size="small"
                      onClick={() => setBaselineSubTab('venues')}
                    >
                      بانک نمازخانه‌ها ({venues.length})
                    </Button>
                    <Button
                      variant={baselineSubTab === 'persons' ? 'contained' : 'outlined'}
                      size="small"
                      onClick={() => setBaselineSubTab('persons')}
                    >
                      بانک کارکنان و افراد ({persons.length})
                    </Button>
                  </Stack>
                  <TextField
                    size="small"
                    placeholder="جستجو در اطلاعات پایه..."
                    value={baselineSearch}
                    onChange={e => setBaselineSearch(e.target.value)}
                    InputProps={{
                      startAdornment: <InputAdornment position="start"><SearchRounded fontSize="small" /></InputAdornment>,
                    }}
                    sx={{ width: { xs: '100%', sm: 240 } }}
                  />
                </Stack>
              </Paper>

              {/* SubTab: CAPACITY */}
              {baselineSubTab === 'capacity' && (
                <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 2 }}>
                  <Table size="small">
                    <TableHead sx={{ bgcolor: 'grey.50' }}>
                      <TableRow>
                        <TableCell sx={{ fontWeight: 700 }}>نام واحد / حوزه قضایی</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>شهرستان</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>تعداد کارکنان</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>ضریب عائله</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>ظرفیت تخمینی جامعه</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>ائمه جماعات</TableCell>
                        <TableCell sx={{ fontWeight: 700 }}>نمازخانه‌ها</TableCell>
                        <TableCell align="center" sx={{ fontWeight: 700 }}>عملیات</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {units
                        .filter(u => !baselineSearch || u.display_name.includes(baselineSearch) || u.county.includes(baselineSearch))
                        .map(u => {
                          const base = baselines.find(b => b.unit_id === u.display_name || b.unit_id === u.name || b.unit_id === u.unit_id) || {
                            unit_id: u.display_name,
                            staff_count: 0,
                            family_multiplier: 2.5,
                            imams_count: 0,
                            prayer_rooms_count: 0,
                            honored_count: 0,
                          }
                          const staff = Number(base.staff_count) || 0
                          const mul = Number(base.family_multiplier) || 2.5
                          const totalCap = Math.round(staff * mul)
                          return (
                            <TableRow key={u.unit_id} hover>
                              <TableCell sx={{ fontWeight: 600 }}>{u.display_name}</TableCell>
                              <TableCell>{u.county}</TableCell>
                              <TableCell>{staff > 0 ? `${staff} نفر` : <Typography variant="caption" color="text.secondary">ثبت‌نشده</Typography>}</TableCell>
                              <TableCell>{mul}x</TableCell>
                              <TableCell>{totalCap > 0 ? `${totalCap} نفر` : '-'}</TableCell>
                              <TableCell>{base.imams_count || '-'}</TableCell>
                              <TableCell>{base.prayer_rooms_count || '-'}</TableCell>
                              <TableCell align="center">
                                <Button
                                  size="small"
                                  variant="outlined"
                                  startIcon={<EditRounded />}
                                  onClick={() => {
                                    setEditingBaseline({
                                      unit_id: u.display_name,
                                      staff_count: staff,
                                      family_multiplier: mul,
                                      imams_count: base.imams_count || 0,
                                      prayer_rooms_count: base.prayer_rooms_count || 0,
                                      honored_count: base.honored_count || 0,
                                      notes: base.notes || '',
                                    })
                                    setBaselineModalOpen(true)
                                  }}
                                >
                                  ویرایش ظرفیت
                                </Button>
                              </TableCell>
                            </TableRow>
                          )
                        })}
                    </TableBody>
                  </Table>
                </TableContainer>
              )}

              {/* SubTab: IMAMS */}
              {baselineSubTab === 'imams' && (
                <Stack spacing={1.5}>
                  <Stack direction="row" justifyContent="space-between" alignItems="center">
                    <Typography variant="subtitle2" fontWeight={700}>فهرست ائمه جماعات استان ({imams.length} نفر)</Typography>
                    <Button
                      size="small"
                      variant="contained"
                      startIcon={<AddRounded />}
                      onClick={() => {
                        setEditingImam({
                          full_name: '',
                          unit_id: units[0]?.unit_id || '',
                          position: 'امام جماعت ظهر و عصر',
                          source_kind: 'staff_cleric',
                          status: 'employed',
                        })
                        setImamModalOpen(true)
                      }}
                    >
                      ثبت امام جماعت جدید
                    </Button>
                  </Stack>
                  <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 2 }}>
                    <Table size="small">
                      <TableHead sx={{ bgcolor: 'grey.50' }}>
                        <TableRow>
                          <TableCell sx={{ fontWeight: 700 }}>نام امام جماعت</TableCell>
                          <TableCell sx={{ fontWeight: 700 }}>حوزه قضایی</TableCell>
                          <TableCell sx={{ fontWeight: 700 }}>سمت / وعده</TableCell>
                          <TableCell sx={{ fontWeight: 700 }}>نوع منشأ</TableCell>
                          <TableCell sx={{ fontWeight: 700 }}>وضعیت</TableCell>
                          <TableCell sx={{ fontWeight: 700 }}>شماره پرسنلی</TableCell>
                          <TableCell sx={{ fontWeight: 700 }}>توضیحات</TableCell>
                          <TableCell align="center" sx={{ fontWeight: 700 }}>عملیات</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {imams.length === 0 ? (
                          <TableRow>
                            <TableCell colSpan={8} align="center" sx={{ py: 3, color: 'text.secondary' }}>
                              هنوز امام جماعتی در سیستم ثبت نشده است.
                            </TableCell>
                          </TableRow>
                        ) : (
                          imams
                            .filter(i => !baselineSearch || i.full_name.includes(baselineSearch) || (i.position && i.position.includes(baselineSearch)))
                            .map(i => {
                              const u = units.find(unit => unit.unit_id === i.unit_id)
                              return (
                                <TableRow key={i.imam_id} hover>
                                  <TableCell sx={{ fontWeight: 600 }}>{i.full_name}</TableCell>
                                  <TableCell>{u ? u.display_name : i.unit_id}</TableCell>
                                  <TableCell>{i.position || '-'}</TableCell>
                                  <TableCell>
                                    <Chip
                                      size="small"
                                      label={i.source_kind === 'staff_cleric' ? 'روحانی پرسنل' : i.source_kind === 'invited_external' ? 'مدعو بیرونی' : 'نامشخص'}
                                      color={i.source_kind === 'staff_cleric' ? 'primary' : 'default'}
                                    />
                                  </TableCell>
                                  <TableCell>
                                    <Chip
                                      size="small"
                                      label={i.status === 'employed' ? 'شاغل' : 'غیرشاغل / آزاد'}
                                      color={i.status === 'employed' ? 'success' : 'default'}
                                    />
                                  </TableCell>
                                  <TableCell>{i.personnel_no || '-'}</TableCell>
                                  <TableCell>{i.notes || '-'}</TableCell>
                                  <TableCell align="center">
                                    <IconButton size="small" color="error" onClick={() => handleDeleteImam(i.imam_id)}>
                                      <DeleteOutlineRounded fontSize="small" />
                                    </IconButton>
                                  </TableCell>
                                </TableRow>
                              )
                            })
                        )}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </Stack>
              )}

              {/* SubTab: VENUES */}
              {baselineSubTab === 'venues' && (
                <Stack spacing={1.5}>
                  <Stack direction="row" justifyContent="space-between" alignItems="center">
                    <Typography variant="subtitle2" fontWeight={700}>فهرست نمازخانه‌ها و امکانات اقامه نماز ({venues.length} مکان)</Typography>
                    <Button
                      size="small"
                      variant="contained"
                      startIcon={<AddRounded />}
                      onClick={() => {
                        setEditingVenue({
                          name: '',
                          unit_id: units[0]?.unit_id || '',
                          notes: '',
                        })
                        setVenueModalOpen(true)
                      }}
                    >
                      ثبت نمازخانه جدید
                    </Button>
                  </Stack>
                  <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 2 }}>
                    <Table size="small">
                      <TableHead sx={{ bgcolor: 'grey.50' }}>
                        <TableRow>
                          <TableCell sx={{ fontWeight: 700 }}>نام نمازخانه / مکان</TableCell>
                          <TableCell sx={{ fontWeight: 700 }}>حوزه قضایی میزبان</TableCell>
                          <TableCell sx={{ fontWeight: 700 }}>توضیحات و مشخصات ظرفیت</TableCell>
                          <TableCell align="center" sx={{ fontWeight: 700 }}>عملیات</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {venues.length === 0 ? (
                          <TableRow>
                            <TableCell colSpan={4} align="center" sx={{ py: 3, color: 'text.secondary' }}>
                              هنوز نمازخانه‌ای در سیستم ثبت نشده است.
                            </TableCell>
                          </TableRow>
                        ) : (
                          venues
                            .filter(v => !baselineSearch || v.name.includes(baselineSearch))
                            .map(v => {
                              const u = units.find(unit => unit.unit_id === v.unit_id)
                              return (
                                <TableRow key={v.venue_id} hover>
                                  <TableCell sx={{ fontWeight: 600 }}>{v.name}</TableCell>
                                  <TableCell>{u ? u.display_name : v.unit_id}</TableCell>
                                  <TableCell>{v.notes || '-'}</TableCell>
                                  <TableCell align="center">
                                    <IconButton size="small" color="error" onClick={() => handleDeleteVenue(v.venue_id)}>
                                      <DeleteOutlineRounded fontSize="small" />
                                    </IconButton>
                                  </TableCell>
                                </TableRow>
                              )
                            })
                        )}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </Stack>
              )}

              {/* SubTab: PERSONS */}
              {baselineSubTab === 'persons' && (
                <Stack spacing={1.5}>
                  <Stack direction="row" justifyContent="space-between" alignItems="center">
                    <Typography variant="subtitle2" fontWeight={700}>بانک جامع پرسنل، تقدیرشدگان و خانواده ({persons.length} نفر)</Typography>
                    <Button
                      size="small"
                      variant="contained"
                      startIcon={<AddRounded />}
                      onClick={() => {
                        setEditingPerson({
                          full_name: '',
                          kind: 'employee',
                          unit_id: units[0]?.unit_id || '',
                        })
                        setPersonModalOpen(true)
                      }}
                    >
                      ثبت شخص جدید
                    </Button>
                  </Stack>
                  <TableContainer component={Paper} variant="outlined" sx={{ borderRadius: 2 }}>
                    <Table size="small">
                      <TableHead sx={{ bgcolor: 'grey.50' }}>
                        <TableRow>
                          <TableCell sx={{ fontWeight: 700 }}>نام و نام خانوادگی</TableCell>
                          <TableCell sx={{ fontWeight: 700 }}>نوع عضویت</TableCell>
                          <TableCell sx={{ fontWeight: 700 }}>نسبت</TableCell>
                          <TableCell sx={{ fontWeight: 700 }}>شماره پرسنلی</TableCell>
                          <TableCell sx={{ fontWeight: 700 }}>کد ملی</TableCell>
                          <TableCell sx={{ fontWeight: 700 }}>شماره تماس</TableCell>
                          <TableCell sx={{ fontWeight: 700 }}>حوزه قضایی</TableCell>
                          <TableCell sx={{ fontWeight: 700 }}>یادداشت / سوابق تشویق</TableCell>
                          <TableCell align="center" sx={{ fontWeight: 700 }}>عملیات</TableCell>
                        </TableRow>
                      </TableHead>
                      <TableBody>
                        {persons.length === 0 ? (
                          <TableRow>
                            <TableCell colSpan={9} align="center" sx={{ py: 3, color: 'text.secondary' }}>
                              هنوز اطلاعات پرسنلی در این بانک ثبت نشده است.
                            </TableCell>
                          </TableRow>
                        ) : (
                          persons
                            .filter(p => !baselineSearch || p.full_name.includes(baselineSearch) || (p.personnel_no && p.personnel_no.includes(baselineSearch)))
                            .map(p => {
                              const u = units.find(unit => unit.unit_id === p.unit_id)
                              return (
                                <TableRow key={p.person_id} hover>
                                  <TableCell sx={{ fontWeight: 600 }}>{p.full_name}</TableCell>
                                  <TableCell>
                                    <Chip
                                      size="small"
                                      label={p.kind === 'employee' ? 'همکار شاغل' : 'عضو خانواده'}
                                      color={p.kind === 'employee' ? 'primary' : 'secondary'}
                                    />
                                  </TableCell>
                                  <TableCell>{p.relation || 'خود همکار'}</TableCell>
                                  <TableCell>{p.personnel_no || '-'}</TableCell>
                                  <TableCell>{p.national_id || '-'}</TableCell>
                                  <TableCell>{p.phone || '-'}</TableCell>
                                  <TableCell>{u ? u.display_name : p.unit_id || '-'}</TableCell>
                                  <TableCell>{p.notes || '-'}</TableCell>
                                  <TableCell align="center">
                                    <IconButton size="small" color="error" onClick={() => handleDeletePerson(p.person_id)}>
                                      <DeleteOutlineRounded fontSize="small" />
                                    </IconButton>
                                  </TableCell>
                                </TableRow>
                              )
                            })
                        )}
                      </TableBody>
                    </Table>
                  </TableContainer>
                </Stack>
              )}
            </Stack>
          )}
        </DialogContent>

        <DialogActions sx={{ p: 2 }}>
          <Button onClick={onClose} variant="outlined">بستن</Button>
        </DialogActions>
      </Dialog>

      {/* MODAL: ADD / EDIT UNIT */}
      <Dialog open={unitModalOpen} onClose={() => setUnitModalOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: 800 }}>
          {editingUnit?.unit_id ? 'ویرایش حوزه قضایی' : 'افزودن حوزه یا واحد قضایی جدید'}
        </DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2.5} sx={{ pt: 1 }}>
            <Autocomplete
              freeSolo
              options={counties}
              value={editingUnit?.county || ''}
              onChange={(_, val) => {
                const c = val || ''
                const t = editingUnit?.unit_type || ''
                setEditingUnit(prev => ({
                  ...prev,
                  county: c,
                  display_name: c && t ? `${c} - ${t}` : prev?.display_name || '',
                }))
              }}
              onInputChange={(_, val) => {
                const c = val || ''
                const t = editingUnit?.unit_type || ''
                setEditingUnit(prev => ({
                  ...prev,
                  county: c,
                  display_name: c && t ? `${c} - ${t}` : prev?.display_name || '',
                }))
              }}
              renderInput={params => (
                <TextField {...params} label="نام شهرستان" placeholder="مثال: ساری، بابل، نور..." required fullWidth />
              )}
            />

            <Autocomplete
              freeSolo
              options={COMMON_UNIT_TYPES}
              value={editingUnit?.unit_type || ''}
              onChange={(_, val) => {
                const t = val || ''
                const c = editingUnit?.county || ''
                setEditingUnit(prev => ({
                  ...prev,
                  unit_type: t,
                  display_name: c && t ? `${c} - ${t}` : prev?.display_name || '',
                }))
              }}
              onInputChange={(_, val) => {
                const t = val || ''
                const c = editingUnit?.county || ''
                setEditingUnit(prev => ({
                  ...prev,
                  unit_type: t,
                  display_name: c && t ? `${c} - ${t}` : prev?.display_name || '',
                }))
              }}
              renderInput={params => (
                <TextField {...params} label="نوع واحد قضایی" placeholder="مثال: دادگستری، دادسرا، شورای حل اختلاف، اداره کل..." required fullWidth />
              )}
            />

            <TextField
              label="نام کامل نمایشی (در فرم ثبت و گزینش)"
              value={editingUnit?.display_name || ''}
              onChange={e => setEditingUnit(prev => ({ ...prev, display_name: e.target.value }))}
              helperText="مثال: ساری - دادسرا / نور - دادگستری / ساری - اداره کل"
              fullWidth
              required
            />

            <FormControl fullWidth size="small">
              <Select
                value={editingUnit?.kind || 'judicial_domain'}
                onChange={e => setEditingUnit(prev => ({ ...prev, kind: e.target.value as any }))}
              >
                <MenuItem value="judicial_domain">حوزه قضایی شهرستان / بخش</MenuItem>
                <MenuItem value="provincial_hq">ستاد اداره کل استان</MenuItem>
              </Select>
            </FormControl>

            <TextField
              label="یادداشت و توضیحات"
              value={editingUnit?.notes || ''}
              onChange={e => setEditingUnit(prev => ({ ...prev, notes: e.target.value }))}
              multiline
              rows={2}
              fullWidth
            />
          </Stack>
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setUnitModalOpen(false)}>انصراف</Button>
          <Button onClick={handleSaveUnit} variant="contained" color="primary">ذخیره واحد</Button>
        </DialogActions>
      </Dialog>

      {/* MODAL: ADD / EDIT LIAISON */}
      <Dialog open={liaisonModalOpen} onClose={() => setLiaisonModalOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: 800 }}>
          {editingLiaison?.liaison_id ? 'ویرایش رابط فرهنگی' : 'افزودن رابط فرهنگی جدید'}
        </DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2.5} sx={{ pt: 1 }}>
            <TextField
              label="نام و نام خانوادگی رابط فرهنگی"
              value={editingLiaison?.full_name || ''}
              onChange={e => setEditingLiaison(prev => ({ ...prev, full_name: e.target.value }))}
              placeholder="مثال: قاسمی شورابی / دیوسالار / مهدوی"
              required
              fullWidth
            />

            <Autocomplete
              options={units}
              getOptionLabel={option => option.display_name || option.name}
              value={units.find(u => u.unit_id === editingLiaison?.unit_id) || null}
              onChange={(_, val) => setEditingLiaison(prev => ({ ...prev, unit_id: val?.unit_id || '' }))}
              renderInput={params => (
                <TextField {...params} label="حوزه قضایی منتسب به رابط" placeholder="انتخاب از لیست واحدهای قضایی..." required fullWidth />
              )}
            />

            <TextField
              label="نام کاربری ایتا (اختیاری)"
              value={editingLiaison?.eitaa_username || ''}
              onChange={e => setEditingLiaison(prev => ({ ...prev, eitaa_username: e.target.value }))}
              placeholder="بدون @، مثال: mahdavi_cul"
              dir="ltr"
              fullWidth
              helperText="برای تشخیص و تکمیل خودکار فیلدها هنگام ارسال پیام در ایتا"
            />

            <TextField
              label="شماره تماس (اختیاری)"
              value={editingLiaison?.phone || ''}
              onChange={e => setEditingLiaison(prev => ({ ...prev, phone: e.target.value }))}
              placeholder="0911..."
              dir="ltr"
              fullWidth
            />

            <TextField
              label="کلمات کلیدی تطبیق خودکار (Match Keywords)"
              value={editingLiaison?.match_keywords || ''}
              onChange={e => setEditingLiaison(prev => ({ ...prev, match_keywords: e.target.value }))}
              placeholder="با ویرگول جدا کنید، مثال: مهدوی,سوادکوه,روابط عمومی سوادکوه"
              fullWidth
              helperText="اگر پیام یا فرستنده شامل این کلمات باشد، این رابط و حوزه قضایی آن خودکار انتخاب می‌شود"
            />

            <TextField
              label="یادداشت"
              value={editingLiaison?.notes || ''}
              onChange={e => setEditingLiaison(prev => ({ ...prev, notes: e.target.value }))}
              multiline
              rows={2}
              fullWidth
            />
          </Stack>
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setLiaisonModalOpen(false)}>انصراف</Button>
          <Button onClick={handleSaveLiaison} variant="contained" color="primary">ذخیره رابط</Button>
        </DialogActions>
      </Dialog>

      {/* PHONE PROMPT DIALOG */}
      <Dialog
        open={Boolean(phonePromptLiaison)}
        onClose={() => setPhonePromptLiaison(null)}
        maxWidth="xs"
        fullWidth
      >
        <DialogTitle sx={{ fontWeight: 800 }}>
          ثبت رابط در مخاطبین ایتا
        </DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2} sx={{ pt: 1 }}>
            <Typography variant="body2" color="text.secondary">
              برای ثبت رسمی رابط فرهنگی «<strong>{phonePromptLiaison?.full_name}</strong>» در مخاطبین ایتا، لطفاً شماره تماس ایشان را وارد فرمایید:
            </Typography>
            <TextField
              autoFocus
              label="شماره تماس"
              placeholder="0911..."
              value={phonePromptValue}
              onChange={e => setPhonePromptValue(e.target.value)}
              fullWidth
              dir="ltr"
              InputProps={{
                startAdornment: <InputAdornment position="start"><ContactPhoneRounded fontSize="small" /></InputAdornment>,
              }}
            />
          </Stack>
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setPhonePromptLiaison(null)}>انصراف</Button>
          <Button
            variant="contained"
            color="primary"
            disabled={!phonePromptValue.trim()}
            onClick={() => {
              if (phonePromptLiaison) {
                void handleSyncEitaaContact(phonePromptLiaison, phonePromptValue.trim())
              }
            }}
          >
            ثبت در مخاطبین ایتا
          </Button>
        </DialogActions>
      </Dialog>

      {selectedLiaisonForProfile && (
        <LiaisonAuthorDialog
          open={Boolean(selectedLiaisonForProfile)}
          onClose={() => setSelectedLiaisonForProfile(null)}
          authorName={selectedLiaisonForProfile.full_name}
          authorUsername={selectedLiaisonForProfile.eitaa_username}
          authorUserId={selectedLiaisonForProfile.eitaa_user_id}
          senderKey={selectedLiaisonForProfile.sender_key}
          onLiaisonUpdated={loadData}
        />
      )}

      {/* MODAL: ADD / EDIT PROGRAM CATALOG ITEM */}
      <Dialog open={programModalOpen} onClose={() => setProgramModalOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: 800 }}>
          {editingProgram?.program_code && programs.some(p => p.program_code === editingProgram.program_code)
            ? `ویرایش برنامه عملیاتی: ${editingProgram.program_code}`
            : 'تعریف سرفصل برنامه عملیاتی جدید'}
        </DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2.5} sx={{ pt: 1 }}>
            <TextField
              label="کد رسمی برنامه (۵ رقمی)"
              value={editingProgram?.program_code || ''}
              onChange={e => setEditingProgram(prev => ({ ...prev, program_code: e.target.value.trim() }))}
              placeholder="مثال: 80501 یا 80701"
              required
              fullWidth
              dir="ltr"
              disabled={Boolean(
                editingProgram?.program_code &&
                programs.some(p => p.program_code === editingProgram?.program_code)
              )}
              helperText="کد برنامه شناسه یکتای آماری است و پس از ثبت نباید تغییر کند؛ در صورت تغییر کد در سال جدید، کد جدید تعریف شده و کد قدیم بایگانی می‌شود."
            />

            <TextField
              label="عنوان رسمی برنامه"
              value={editingProgram?.title || ''}
              onChange={e => setEditingProgram(prev => ({ ...prev, title: e.target.value }))}
              placeholder="مثال: ترویج و توسعه فرهنگ اقامه نماز"
              required
              fullWidth
            />

            <TextField
              label="شاخصه کلی متناظر"
              value={editingProgram?.canonical_macro || ''}
              onChange={e => setEditingProgram(prev => ({ ...prev, canonical_macro: e.target.value }))}
              placeholder="شاخصه‌ای که در پیام‌ها و فرم‌ها نمایش داده می‌شود"
              helperText="در صورتی که خالی باشد، عنوان برنامه به عنوان شاخصه کلی در نظر گرفته می‌شود"
              fullWidth
            />

            <TextField
              label="نام برگه اکسل در کارنامه فرهنگی (اختیاری)"
              value={editingProgram?.workbook_sheet || ''}
              onChange={e => setEditingProgram(prev => ({ ...prev, workbook_sheet: e.target.value }))}
              placeholder="مثال: نماز، مراسمات، مسابقات..."
              fullWidth
            />

            <Stack direction="row" spacing={2}>
              <TextField
                label="شروع اعتبار از سال"
                type="number"
                value={editingProgram?.valid_from_year || 1404}
                onChange={e => setEditingProgram(prev => ({ ...prev, valid_from_year: parseInt(e.target.value, 10) || 1404 }))}
                sx={{ flex: 1 }}
              />
              <TextField
                label="پایان اعتبار تا سال (اختیاری)"
                type="number"
                value={editingProgram?.valid_to_year || ''}
                onChange={e => setEditingProgram(prev => ({ ...prev, valid_to_year: e.target.value ? parseInt(e.target.value, 10) : undefined }))}
                placeholder="خالی = تا اطلاع ثانوی"
                sx={{ flex: 1 }}
              />
            </Stack>

            <FormControlLabel
              control={
                <Switch
                  checked={editingProgram?.is_active !== false}
                  onChange={e => setEditingProgram(prev => ({ ...prev, is_active: e.target.checked }))}
                  color="success"
                />
              }
              label={editingProgram?.is_active !== false ? 'برنامه فعال است و در فرم‌های ثبت گزارش نمایش داده می‌شود' : 'برنامه غیرفعال / بایگانی شده است (فقط برای سوابق تاریخی حفظ می‌شود)'}
            />

            <TextField
              label="توضیحات و مصادیق اجرایی"
              value={editingProgram?.description || ''}
              onChange={e => setEditingProgram(prev => ({ ...prev, description: e.target.value }))}
              multiline
              rows={2}
              fullWidth
              placeholder="توضیحات اختیاری درباره دامنه فعالیت‌های مشمول این برنامه"
            />
          </Stack>
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setProgramModalOpen(false)}>انصراف</Button>
          <Button onClick={handleSaveProgram} variant="contained" color="primary" disabled={savingProgram}>
            {savingProgram ? <CircularProgress size={20} color="inherit" /> : 'ذخیره برنامه'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Baseline Capacity Edit Dialog */}
      <Dialog open={baselineModalOpen} onClose={() => setBaselineModalOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: 800 }}>ویرایش ظرفیت و اطلاعات پایه: {editingBaseline?.unit_id}</DialogTitle>
        <DialogContent sx={{ pt: 2 }}>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <Stack direction="row" spacing={2}>
              <TextField
                label="تعداد کل پرسنل و کارکنان حوزه"
                type="number"
                value={editingBaseline?.staff_count || ''}
                onChange={e => setEditingBaseline(prev => ({ ...prev, staff_count: Number(e.target.value) || 0 }))}
                fullWidth
              />
              <TextField
                label="ضریب عائله و خانواده"
                type="number"
                inputProps={{ step: '0.1' }}
                value={editingBaseline?.family_multiplier || 2.5}
                onChange={e => setEditingBaseline(prev => ({ ...prev, family_multiplier: Number(e.target.value) || 2.5 }))}
                fullWidth
              />
            </Stack>
            <Stack direction="row" spacing={2}>
              <TextField
                label="تعداد ائمه جماعات فعال"
                type="number"
                value={editingBaseline?.imams_count || ''}
                onChange={e => setEditingBaseline(prev => ({ ...prev, imams_count: Number(e.target.value) || 0 }))}
                fullWidth
              />
              <TextField
                label="تعداد نمازخانه‌ها و اماکن مذهبی"
                type="number"
                value={editingBaseline?.prayer_rooms_count || ''}
                onChange={e => setEditingBaseline(prev => ({ ...prev, prayer_rooms_count: Number(e.target.value) || 0 }))}
                fullWidth
              />
            </Stack>
            <TextField
              label="تعداد افراد تقدیرشده سال جاری"
              type="number"
              value={editingBaseline?.honored_count || ''}
              onChange={e => setEditingBaseline(prev => ({ ...prev, honored_count: Number(e.target.value) || 0 }))}
              fullWidth
            />
            <TextField
              label="یادداشت‌های ارزیابی و ظرفیت‌سنجی"
              multiline
              rows={2}
              value={editingBaseline?.notes || ''}
              onChange={e => setEditingBaseline(prev => ({ ...prev, notes: e.target.value }))}
              fullWidth
            />
          </Stack>
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setBaselineModalOpen(false)}>انصراف</Button>
          <Button onClick={handleSaveBaseline} variant="contained" disabled={savingBaseline}>
            {savingBaseline ? <CircularProgress size={20} color="inherit" /> : 'ذخیره ظرفیت'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Imam Add/Edit Dialog */}
      <Dialog open={imamModalOpen} onClose={() => setImamModalOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: 800 }}>ثبت امام جماعت</DialogTitle>
        <DialogContent sx={{ pt: 2 }}>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="نام و نام خانوادگی امام جماعت"
              value={editingImam?.full_name || ''}
              onChange={e => setEditingImam(prev => ({ ...prev, full_name: e.target.value }))}
              fullWidth
              required
            />
            <FormControl fullWidth size="small">
              <InputLabel>حوزه قضایی</InputLabel>
              <Select
                value={editingImam?.unit_id || ''}
                label="حوزه قضایی"
                onChange={e => setEditingImam(prev => ({ ...prev, unit_id: e.target.value }))}
              >
                {units.map(u => (
                  <MenuItem key={u.unit_id} value={u.unit_id}>{u.display_name}</MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              label="سمت / وعده اقامه نماز"
              value={editingImam?.position || ''}
              onChange={e => setEditingImam(prev => ({ ...prev, position: e.target.value }))}
              fullWidth
            />
            <Stack direction="row" spacing={2}>
              <FormControl fullWidth size="small">
                <InputLabel>نوع منشأ</InputLabel>
                <Select
                  value={editingImam?.source_kind || 'staff_cleric'}
                  label="نوع منشأ"
                  onChange={e => setEditingImam(prev => ({ ...prev, source_kind: e.target.value }))}
                >
                  <MenuItem value="staff_cleric">روحانی پرسنل</MenuItem>
                  <MenuItem value="invited_external">مدعو بیرونی</MenuItem>
                  <MenuItem value="none">سایر / نامشخص</MenuItem>
                </Select>
              </FormControl>
              <FormControl fullWidth size="small">
                <InputLabel>وضعیت اشتغال</InputLabel>
                <Select
                  value={editingImam?.status || 'employed'}
                  label="وضعیت اشتغال"
                  onChange={e => setEditingImam(prev => ({ ...prev, status: e.target.value }))}
                >
                  <MenuItem value="employed">شاغل</MenuItem>
                  <MenuItem value="idle">آزاد / غیرشاغل</MenuItem>
                </Select>
              </FormControl>
            </Stack>
            <TextField
              label="شماره پرسنلی (اختیاری)"
              value={editingImam?.personnel_no || ''}
              onChange={e => setEditingImam(prev => ({ ...prev, personnel_no: e.target.value }))}
              fullWidth
            />
            <TextField
              label="توضیحات تکمیلی"
              multiline
              rows={2}
              value={editingImam?.notes || ''}
              onChange={e => setEditingImam(prev => ({ ...prev, notes: e.target.value }))}
              fullWidth
            />
          </Stack>
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setImamModalOpen(false)}>انصراف</Button>
          <Button onClick={handleSaveImam} variant="contained" disabled={savingImam}>
            {savingImam ? <CircularProgress size={20} color="inherit" /> : 'ذخیره امام جماعت'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Venue Add/Edit Dialog */}
      <Dialog open={venueModalOpen} onClose={() => setVenueModalOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: 800 }}>ثبت نمازخانه یا مکان مذهبی</DialogTitle>
        <DialogContent sx={{ pt: 2 }}>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="نام نمازخانه / مکان"
              value={editingVenue?.name || ''}
              onChange={e => setEditingVenue(prev => ({ ...prev, name: e.target.value }))}
              fullWidth
              required
            />
            <FormControl fullWidth size="small">
              <InputLabel>حوزه قضایی میزبان</InputLabel>
              <Select
                value={editingVenue?.unit_id || ''}
                label="حوزه قضایی میزبان"
                onChange={e => setEditingVenue(prev => ({ ...prev, unit_id: e.target.value }))}
              >
                {units.map(u => (
                  <MenuItem key={u.unit_id} value={u.unit_id}>{u.display_name}</MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              label="توضیحات و مشخصات ظرفیت و مساحت"
              multiline
              rows={3}
              value={editingVenue?.notes || ''}
              onChange={e => setEditingVenue(prev => ({ ...prev, notes: e.target.value }))}
              fullWidth
            />
          </Stack>
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setVenueModalOpen(false)}>انصراف</Button>
          <Button onClick={handleSaveVenue} variant="contained" disabled={savingVenue}>
            {savingVenue ? <CircularProgress size={20} color="inherit" /> : 'ذخیره نمازخانه'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* Person Add/Edit Dialog */}
      <Dialog open={personModalOpen} onClose={() => setPersonModalOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontWeight: 800 }}>ثبت شخص در بانک پرسنلی</DialogTitle>
        <DialogContent sx={{ pt: 2 }}>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="نام و نام خانوادگی"
              value={editingPerson?.full_name || ''}
              onChange={e => setEditingPerson(prev => ({ ...prev, full_name: e.target.value }))}
              fullWidth
              required
            />
            <Stack direction="row" spacing={2}>
              <FormControl fullWidth size="small">
                <InputLabel>نوع عضویت</InputLabel>
                <Select
                  value={editingPerson?.kind || 'employee'}
                  label="نوع عضویت"
                  onChange={e => setEditingPerson(prev => ({ ...prev, kind: e.target.value }))}
                >
                  <MenuItem value="employee">همکار شاغل</MenuItem>
                  <MenuItem value="family">عضو خانواده</MenuItem>
                </Select>
              </FormControl>
              <FormControl fullWidth size="small">
                <InputLabel>نسبت</InputLabel>
                <Select
                  value={editingPerson?.relation || ''}
                  label="نسبت"
                  onChange={e => setEditingPerson(prev => ({ ...prev, relation: e.target.value }))}
                >
                  <MenuItem value="">خود همکار</MenuItem>
                  <MenuItem value="spouse">همسر</MenuItem>
                  <MenuItem value="child">فرزند</MenuItem>
                  <MenuItem value="parent">والدین</MenuItem>
                  <MenuItem value="sibling">خواهر / برادر</MenuItem>
                </Select>
              </FormControl>
            </Stack>
            {editingPerson?.kind === 'family' && (
              <TextField
                label="شماره پرسنلی همکار مربوطه"
                value={editingPerson?.related_personnel_no || ''}
                onChange={e => setEditingPerson(prev => ({ ...prev, related_personnel_no: e.target.value }))}
                fullWidth
                required
              />
            )}
            <Stack direction="row" spacing={2}>
              <TextField
                label="شماره پرسنلی"
                value={editingPerson?.personnel_no || ''}
                onChange={e => setEditingPerson(prev => ({ ...prev, personnel_no: e.target.value }))}
                fullWidth
              />
              <TextField
                label="کد ملی"
                value={editingPerson?.national_id || ''}
                onChange={e => setEditingPerson(prev => ({ ...prev, national_id: e.target.value }))}
                fullWidth
              />
            </Stack>
            <Stack direction="row" spacing={2}>
              <TextField
                label="تلفن همراه"
                value={editingPerson?.phone || ''}
                onChange={e => setEditingPerson(prev => ({ ...prev, phone: e.target.value }))}
                fullWidth
              />
              <FormControl fullWidth size="small">
                <InputLabel>حوزه قضایی</InputLabel>
                <Select
                  value={editingPerson?.unit_id || ''}
                  label="حوزه قضایی"
                  onChange={e => setEditingPerson(prev => ({ ...prev, unit_id: e.target.value }))}
                >
                  {units.map(u => (
                    <MenuItem key={u.unit_id} value={u.unit_id}>{u.display_name}</MenuItem>
                  ))}
                </Select>
              </FormControl>
            </Stack>
            <TextField
              label="یادداشت‌ها و سوابق تشویق / تقدیر"
              multiline
              rows={2}
              value={editingPerson?.notes || ''}
              onChange={e => setEditingPerson(prev => ({ ...prev, notes: e.target.value }))}
              fullWidth
            />
          </Stack>
        </DialogContent>
        <DialogActions sx={{ p: 2 }}>
          <Button onClick={() => setPersonModalOpen(false)}>انصراف</Button>
          <Button onClick={handleSavePerson} variant="contained" disabled={savingPerson}>
            {savingPerson ? <CircularProgress size={20} color="inherit" /> : 'ذخیره شخص'}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  )
}

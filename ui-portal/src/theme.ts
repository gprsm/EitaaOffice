import { createTheme } from '@mui/material/styles'
import { faNum } from './periods'

// تم متریال RTL پرتال فرهنگی (F-097) — فونت ایران‌سنس از دارایی‌های پرتال
const IRANSans = "'IRANSansWeb', 'IRANSans', 'Vazirmatn', 'Segoe UI', sans-serif"

export const portalTheme = createTheme({
  direction: 'rtl',
  palette: {
    mode: 'light',
    primary: { main: '#0f3d7c' },
    secondary: { main: '#059669' },
    background: { default: '#f1f5f9', paper: '#ffffff' },
    success: { main: '#059669' },
    warning: { main: '#d97706' },
    error: { main: '#b91c1c' },
  },
  typography: {
    fontFamily: IRANSans,
    fontSize: 13.5,
    h6: { fontWeight: 700 },
    subtitle2: { fontWeight: 700 },
    button: { textTransform: 'none', fontWeight: 700 },
  },
  shape: { borderRadius: 10 },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        body: { fontFamily: IRANSans },
        '@font-face': [
          {
            fontFamily: 'IRANSansWeb',
            src: "url('/cultural-portal/assets/fonts/IRANSansWeb-Regular.woff2') format('woff2'), url('/cultural-portal/app/fonts/IRANSansWeb-Regular.woff2') format('woff2'), url('./fonts/IRANSansWeb-Regular.woff2') format('woff2')",
            fontWeight: 400,
            fontDisplay: 'swap',
          },
          {
            fontFamily: 'IRANSansWeb',
            src: "url('/cultural-portal/assets/fonts/IRANSansWeb-Bold.woff2') format('woff2'), url('/cultural-portal/app/fonts/IRANSansWeb-Bold.woff2') format('woff2'), url('./fonts/IRANSansWeb-Bold.woff2') format('woff2')",
            fontWeight: 700,
            fontDisplay: 'swap',
          },
          {
            fontFamily: 'IRANSans',
            src: "url('/cultural-portal/assets/fonts/IRANSansWeb-Regular.woff2') format('woff2'), url('/cultural-portal/app/fonts/IRANSansWeb-Regular.woff2') format('woff2'), url('./fonts/IRANSansWeb-Regular.woff2') format('woff2')",
            fontWeight: 400,
            fontDisplay: 'swap',
          },
          {
            fontFamily: 'IRANSans',
            src: "url('/cultural-portal/assets/fonts/IRANSansWeb-Bold.woff2') format('woff2'), url('/cultural-portal/app/fonts/IRANSansWeb-Bold.woff2') format('woff2'), url('./fonts/IRANSansWeb-Bold.woff2') format('woff2')",
            fontWeight: 700,
            fontDisplay: 'swap',
          },
        ],
      },
    },
    MuiPaper: { defaultProps: { elevation: 0 }, styleOverrides: { root: { backgroundImage: 'none' } } },
    MuiCard: { styleOverrides: { root: { border: '1px solid #e2e8f0' } } },
    MuiTableCell: { styleOverrides: { head: { fontWeight: 700, background: '#f8fafc' } } },
    MuiChip: { styleOverrides: { root: { fontWeight: 700 } } },
  },
})

export const programCodeLabel = (code: string): string => faNum(code)

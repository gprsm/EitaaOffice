import { createContext, useContext } from 'react'
import { createTheme } from '@mui/material/styles'
import type { Components, Theme } from '@mui/material/styles'

export type DisplayMode = 'dark'
export const ColorModeContext = createContext<{
  mode: DisplayMode
  resolvedMode: DisplayMode
  setMode: (mode: DisplayMode) => void
}>({
  mode: 'dark',
  resolvedMode: 'dark',
  setMode: () => undefined,
})
export const useColorMode = () => useContext(ColorModeContext)

const darkColors = {
  canvas: '#0b1016',
  surface: '#141b24',
  surfaceRaised: '#19222d',
  surfaceInput: '#101720',
  border: '#2d3845',
  text: '#f3f6fa',
  textMuted: '#a7b3c2',
  textDisabled: '#66717e',
  primary: '#64b5f6',
  primarySoft: 'rgba(100, 181, 246, .14)',
  secondary: '#4dd0b8',
}

/*
 * Keep Emotion overrides deliberately flat. The RTL Stylis plugin processes
 * these rules, while state-rich legacy selectors live in styles.css.
 */
const components: Components<Theme> = {
  MuiCssBaseline: {
    styleOverrides: {
      'html, body, #root': {
        minWidth: 320,
        color: darkColors.text,
        backgroundColor: darkColors.canvas,
        colorScheme: 'dark',
      },
      body: { margin: 0 },
      '*': { boxSizing: 'border-box' },
      'button, input, textarea, select': { fontFamily: 'inherit' },
    },
  },
  MuiPaper: {
    styleOverrides: {
      root: {
        color: darkColors.text,
        backgroundColor: darkColors.surface,
        backgroundImage: 'none',
        borderColor: darkColors.border,
      },
    },
  },
  MuiCard: {
    styleOverrides: {
      root: {
        color: darkColors.text,
        backgroundColor: darkColors.surface,
        backgroundImage: 'none',
        borderColor: darkColors.border,
      },
    },
  },
  MuiDialog: {
    defaultProps: { fullWidth: true },
    styleOverrides: {
      paper: ({ theme }) => ({
        color: darkColors.text,
        backgroundColor: darkColors.surface,
        backgroundImage: 'none',
        border: `1px solid ${darkColors.border}`,
        borderRadius: 18,
        boxShadow: '0 24px 80px rgba(0,0,0,.68)',
        [theme.breakpoints.down('sm')]: {
          margin: 6,
          width: 'calc(100% - 12px)',
          maxHeight: 'calc(100% - 12px)',
          borderRadius: 12,
        },
      }),
    },
  },
  MuiDialogTitle: {
    styleOverrides: { root: { color: darkColors.text, borderColor: darkColors.border } },
  },
  MuiDialogContent: {
    styleOverrides: {
      root: ({ theme }) => ({
        color: darkColors.text,
        borderColor: darkColors.border,
        padding: theme.spacing(2.25),
        [theme.breakpoints.down('sm')]: { padding: theme.spacing(1.25) },
      }),
    },
  },
  MuiDialogActions: {
    styleOverrides: { root: { borderColor: darkColors.border } },
  },
  MuiDrawer: {
    styleOverrides: {
      paper: {
        color: darkColors.text,
        backgroundColor: darkColors.surface,
        backgroundImage: 'none',
        borderColor: darkColors.border,
      },
    },
  },
  MuiPopover: {
    styleOverrides: {
      paper: {
        color: darkColors.text,
        backgroundColor: darkColors.surfaceRaised,
        backgroundImage: 'none',
        border: `1px solid ${darkColors.border}`,
      },
    },
  },
  MuiMenu: {
    styleOverrides: {
      paper: {
        color: darkColors.text,
        backgroundColor: darkColors.surfaceRaised,
        backgroundImage: 'none',
        border: `1px solid ${darkColors.border}`,
      },
    },
  },
  MuiTextField: {
    defaultProps: { size: 'small', fullWidth: true, variant: 'outlined' },
  },
  MuiFormControl: {
    defaultProps: { size: 'small', fullWidth: true },
  },
  MuiOutlinedInput: {
    styleOverrides: {
      root: { color: darkColors.text, backgroundColor: darkColors.surfaceInput },
      notchedOutline: { borderColor: '#3a4654' },
      input: { color: darkColors.text },
    },
  },
  MuiInputLabel: {
    styleOverrides: { root: { color: darkColors.textMuted } },
  },
  MuiFormHelperText: {
    styleOverrides: { root: { color: darkColors.textMuted } },
  },
  MuiSelect: {
    styleOverrides: {
      icon: { color: darkColors.textMuted },
      select: { color: darkColors.text },
    },
  },
  MuiCheckbox: { defaultProps: { color: 'primary' } },
  MuiRadio: { defaultProps: { color: 'primary' } },
  MuiSwitch: { defaultProps: { color: 'primary' } },
  MuiFormControlLabel: {
    styleOverrides: { label: { color: darkColors.text } },
  },
  MuiButton: {
    defaultProps: { disableElevation: true },
    styleOverrides: {
      root: {
        minHeight: 38,
        borderRadius: 10,
        fontWeight: 700,
        textTransform: 'none',
      },
      containedPrimary: { color: '#07131f' },
    },
  },
  MuiIconButton: {
    styleOverrides: { root: { color: darkColors.textMuted } },
  },
  MuiChip: {
    styleOverrides: {
      root: {
        color: darkColors.text,
        backgroundColor: '#222d39',
        borderColor: '#3b4857',
        borderRadius: 9,
        fontWeight: 600,
      },
    },
  },
  MuiTabs: {
    styleOverrides: {
      root: { minHeight: 44, borderColor: darkColors.border },
      indicator: { height: 3, borderRadius: 3 },
    },
  },
  MuiTab: {
    styleOverrides: {
      root: {
        minHeight: 44,
        color: darkColors.textMuted,
        fontWeight: 800,
        textTransform: 'none',
      },
    },
  },
  MuiTableCell: {
    styleOverrides: {
      root: { color: darkColors.text, borderColor: darkColors.border },
      head: { color: darkColors.text, backgroundColor: darkColors.surfaceRaised, fontWeight: 800 },
    },
  },
  MuiTooltip: {
    styleOverrides: {
      tooltip: {
        color: darkColors.text,
        backgroundColor: '#273341',
        border: '1px solid #445263',
      },
      arrow: { color: '#273341' },
    },
  },
  MuiSkeleton: {
    styleOverrides: { root: { backgroundColor: 'rgba(145, 167, 190, .16)' } },
  },
  MuiLinearProgress: {
    styleOverrides: { root: { backgroundColor: '#25303c' } },
  },
}

export function createAppTheme() {
  return createTheme({
    direction: 'rtl',
    palette: {
      mode: 'dark',
      primary: {
        main: darkColors.primary,
        dark: '#42a5f5',
        light: '#90caf9',
        contrastText: '#07131f',
      },
      secondary: { main: darkColors.secondary, contrastText: '#061714' },
      background: { default: darkColors.canvas, paper: darkColors.surface },
      text: {
        primary: darkColors.text,
        secondary: darkColors.textMuted,
        disabled: darkColors.textDisabled,
      },
      divider: darkColors.border,
      action: {
        active: '#b9c6d4',
        hover: 'rgba(255,255,255,.055)',
        selected: darkColors.primarySoft,
        disabled: darkColors.textDisabled,
        disabledBackground: 'rgba(255,255,255,.035)',
        focus: 'rgba(100,181,246,.22)',
      },
      success: { main: '#66bb6a', dark: '#388e3c', light: '#9bd89e' },
      warning: { main: '#ffb74d', dark: '#f57c00', light: '#ffd180' },
      error: { main: '#ef5350', dark: '#d32f2f', light: '#ff8a80' },
      info: { main: '#64b5f6', dark: '#1976d2', light: '#90caf9' },
    },
    typography: {
      fontFamily: 'IRANSans, "Segoe UI", Tahoma, Arial, sans-serif',
      button: { fontWeight: 700 },
      h5: { fontWeight: 900 },
      h6: { fontWeight: 900 },
    },
    shape: { borderRadius: 12 },
    breakpoints: { values: { xs: 0, sm: 600, md: 900, lg: 1200, xl: 1536 } },
    components,
  })
}

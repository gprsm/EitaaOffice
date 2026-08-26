import { Box, Typography } from '@mui/material'

export function AuthBrandPill({ label }: { label: string }) {
  return <Box
    sx={{
      alignSelf: 'flex-start',
      display: 'inline-flex',
      alignItems: 'center',
      gap: 1,
      px: 1.25,
      py: 0.75,
      color: 'primary.main',
      bgcolor: 'rgba(100, 181, 246, 0.1)',
      border: 1,
      borderColor: 'rgba(100, 181, 246, 0.28)',
      borderRadius: 999,
    }}
  >
    <Box
      aria-hidden
      sx={{
        inlineSize: 24,
        blockSize: 24,
        display: 'grid',
        placeItems: 'center',
        borderRadius: 1,
        color: 'primary.contrastText',
        bgcolor: 'primary.main',
        fontSize: '0.62rem',
        fontWeight: 900,
        direction: 'ltr',
      }}
    >EB</Box>
    <Typography component="span" variant="caption" fontWeight={800}>{label}</Typography>
  </Box>
}

export function AuthBrandMark() {
  return <Box
    aria-hidden
    sx={{
      inlineSize: 54,
      blockSize: 54,
      display: 'grid',
      placeItems: 'center',
      borderRadius: 2.25,
      color: '#07131f',
      background: 'linear-gradient(145deg, #9bd7ff, #55b7f2 58%, #5ad6c6)',
      boxShadow: '0 14px 34px rgba(18, 121, 188, .28)',
      fontWeight: 950,
      direction: 'ltr',
    }}
  >EB</Box>
}

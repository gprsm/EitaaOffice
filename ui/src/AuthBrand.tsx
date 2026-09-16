import { Box, Typography } from '@mui/material'

export function ProviderBrandBadge({
  provider,
  size = 18,
}: {
  provider: string
  size?: number
}) {
  const isBale = provider.toLowerCase() === 'bale'
  const isEitaa = provider.toLowerCase() === 'eitaa'
  const bgcolor = isBale ? '#00a693' : isEitaa ? '#f26522' : 'primary.main'
  const label = isBale ? 'ب' : isEitaa ? 'e' : (provider[0]?.toUpperCase() || '?')
  return (
    <Box
      aria-hidden
      sx={{
        display: 'grid',
        placeItems: 'center',
        width: size,
        height: size,
        borderRadius: '50%',
        bgcolor,
        color: 'white',
        fontSize: Math.max(9, Math.round(size * 0.55)),
        fontWeight: 900,
        lineHeight: 1,
        flexShrink: 0,
      }}
    >
      {label}
    </Box>
  )
}

export function AuthBrandPill({ label, provider }: { label: string; provider?: string }) {
  const isBale = provider?.toLowerCase() === 'bale'
  const color = isBale ? '#00a693' : 'primary.main'
  const bgcolor = isBale ? 'rgba(0, 166, 147, 0.1)' : 'rgba(100, 181, 246, 0.1)'
  const borderColor = isBale ? 'rgba(0, 166, 147, 0.35)' : 'rgba(100, 181, 246, 0.28)'

  return <Box
    sx={{
      alignSelf: 'flex-start',
      display: 'inline-flex',
      alignItems: 'center',
      gap: 1,
      px: 1.25,
      py: 0.75,
      color,
      bgcolor,
      border: 1,
      borderColor,
      borderRadius: 999,
    }}
  >
    {provider ? (
      <ProviderBrandBadge provider={provider} size={22} />
    ) : (
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
    )}
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

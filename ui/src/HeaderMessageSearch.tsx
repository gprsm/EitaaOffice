import { useEffect, useRef, useState } from 'react'
import { Box, IconButton, InputAdornment, Paper, TextField, Tooltip } from '@mui/material'
import CloseRounded from '@mui/icons-material/CloseRounded'
import SearchRounded from '@mui/icons-material/SearchRounded'

export function HeaderMessageSearch({
  value,
  onChange,
}: {
  value: string
  onChange: (value: string) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    if (!expanded) return

    const handlePointerDown = (event: PointerEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setExpanded(false)
      }
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setExpanded(false)
      }
    }

    document.addEventListener('pointerdown', handlePointerDown)
    
    document.addEventListener('keydown', handleKeyDown)

    // Auto-focus when expanded
    // Small timeout ensures it happens after rendering the TextField
    const timeoutId = setTimeout(() => {
      if (inputRef.current) {
        inputRef.current.focus()
      }
    }, 50)

    return () => {
      document.removeEventListener('pointerdown', handlePointerDown)
      
      document.removeEventListener('keydown', handleKeyDown)
      clearTimeout(timeoutId)
    }
  }, [expanded])

  return (
    <Box ref={containerRef} sx={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
      <Tooltip title="جست‌وجوی پیام">
        <IconButton
          onClick={() => setExpanded(prev => !prev)}
          aria-label="جست‌وجوی پیام"
          aria-expanded={expanded}
        >
          <SearchRounded />
        </IconButton>
      </Tooltip>
      {expanded && (
        <Paper
          elevation={4}
          sx={{
            position: 'absolute',
            top: '50%',
            insetInlineEnd: 0,
            transform: 'translateY(-50%)',
            zIndex: theme => theme.zIndex.appBar + 2,
            minWidth: { xs: 'calc(100vw - 32px)', sm: '320px', md: '400px' },
            p: 0.5,
            display: 'flex',
            borderRadius: 2,
          }}
        >
          <TextField
            inputRef={inputRef}
            fullWidth
            size="small"
            value={value}
            onChange={e => onChange(e.target.value)}
            placeholder="جست‌وجوی پیام..."
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchRounded fontSize="small" />
                </InputAdornment>
              ),
              endAdornment: value ? (
                <InputAdornment position="end">
                  <IconButton
                    size="small"
                    onClick={() => {
                      onChange('')
                      inputRef.current?.focus()
                    }}
                    aria-label="پاک کردن متن جست‌وجو"
                  >
                    <CloseRounded fontSize="small" />
                  </IconButton>
                </InputAdornment>
              ) : null,
            }}
          />
        </Paper>
      )}
    </Box>
  )
}

const fs = require('fs');

let cardCode = fs.readFileSync('ui/src/MessageContentCard.tsx', 'utf8');

// Add timelineGroup prop
cardCode = cardCode.replace(
  'type MessageContentCardProps = {',
  `type MessageContentCardProps = {
  timelineGroup?: 'start' | 'middle' | 'end' | 'none'`
);

cardCode = cardCode.replace(
  '  openUsage,\n}: MessageContentCardProps) {',
  `  openUsage,
  timelineGroup = 'none',
}: MessageContentCardProps) {`
);

// Remove time from CardHeader
cardCode = cardCode.replace(
  `      subheader={<Stack direction="row" spacing={0.75} alignItems="center" flexWrap="wrap">
        {message.sender_username && writer !== \`@\${message.sender_username.replace(/^@/, '')}\` && <Typography variant="caption" color="text.secondary" dir="ltr">@\${message.sender_username.replace(/^@/, '')}</Typography>}
        <Typography component="time" variant="caption" color="text.secondary">{formatDate(album?.last.date || message.date)}</Typography>
      </Stack>}`,
  `      subheader={<Stack direction="row" spacing={0.75} alignItems="center" flexWrap="wrap">
        {message.sender_username && writer !== \`@\${message.sender_username.replace(/^@/, '')}\` && <Typography variant="caption" color="text.secondary" dir="ltr">@\${message.sender_username.replace(/^@/, '')}</Typography>}
      </Stack>}`
);

// Hide CardHeader if middle or end
cardCode = cardCode.replace(
  /    <CardHeader\s+avatar=\{<Avatar[\s\S]*?sx=\{\{ px: \{ xs: 1\.25, sm: 1\.75 \}, py: 1\.1 \}\}\s+\/>/,
  `    {(timelineGroup === 'none' || timelineGroup === 'start') && <CardHeader
      avatar={<Avatar sx={{ width: 38, height: 38, bgcolor: 'primary.main', color: 'primary.contrastText', fontWeight: 800 }}>{authorInitials(writer)}</Avatar>}
      action={message.sender_is_eitaa_contact && <Chip size="small" color="primary" variant="outlined" label="مخاطب" />}
      title={<Typography variant="subtitle2" component="h3" fontWeight={850}>{writer}</Typography>}
      subheader={<Stack direction="row" spacing={0.75} alignItems="center" flexWrap="wrap">
        {message.sender_username && writer !== \`@\${message.sender_username.replace(/^@/, '')}\` && <Typography variant="caption" color="text.secondary" dir="ltr">@\${message.sender_username.replace(/^@/, '')}</Typography>}
      </Stack>}
      sx={{ px: { xs: 1.25, sm: 1.75 }, py: 1.1 }}
    />}`
);

// Add time to CardActions
cardCode = cardCode.replace(
  `<Typography variant="caption" color="text.secondary" sx={{ direction: 'ltr' }}>{album ? \`#\${firstId}-#\${lastId}\` : \`#\${message.id}\`}</Typography>`,
  `<Typography variant="caption" color="text.secondary" sx={{ direction: 'ltr' }}>{album ? \`#\${firstId}-#\${lastId}\` : \`#\${message.id}\`}</Typography>
        <Typography component="time" variant="caption" color="text.secondary" sx={{ ml: 1 }}>{formatDate(album?.last.date || message.date)}</Typography>`
);

// Adjust border radius based on timelineGroup
// Original: borderRadius: message.outgoing ? '16px 16px 16px 5px' : '16px 16px 5px 16px',
// If outgoing:
// - start: '16px 16px 5px 5px'
// - middle: '5px 16px 5px 5px'
// - end: '5px 16px 16px 5px'
// - none: '16px 16px 16px 5px'
// (Eitaa/Telegram style)

cardCode = cardCode.replace(
  `borderRadius: message.outgoing ? '16px 16px 16px 5px' : '16px 16px 5px 16px',`,
  `borderRadius: message.outgoing
        ? timelineGroup === 'start' ? '16px 16px 5px 5px' : timelineGroup === 'middle' ? '5px 16px 5px 5px' : timelineGroup === 'end' ? '5px 16px 16px 5px' : '16px 16px 16px 5px'
        : timelineGroup === 'start' ? '16px 16px 5px 5px' : timelineGroup === 'middle' ? '16px 5px 5px 5px' : timelineGroup === 'end' ? '16px 5px 5px 16px' : '16px 16px 5px 16px',`
);

fs.writeFileSync('ui/src/MessageContentCard.tsx', cardCode);

let appCode = fs.readFileSync('ui/src/App.tsx', 'utf8');

const vListRenderRegex = /\{virtualizer\.getVirtualItems\(\)\.map\(row => \{[\s\S]*?const isAlbumFollower = Boolean\(album && album\.leader\.id !== message\.id\)[\s\S]*?return <Box key=\{key\}.*?transform: \`translateY\(\$\{row\.start\}px\)\`.*?>/;

const newVListRender = `{virtualizer.getVirtualItems().map(row => {
        const message = props.messages[row.index]
        const key = messageKey(props.dialog, message)
        const album = albumLookup.get(message.id)
        const isAlbumFollower = Boolean(album && album.leader.id !== message.id)

        // Calculate timelineGroup
        const prevMessage = row.index > 0 ? props.messages[row.index - 1] : null
        const nextMessage = row.index < props.messages.length - 1 ? props.messages[row.index + 1] : null

        const isSameSenderAsPrev = prevMessage && prevMessage.sender_key === message.sender_key && prevMessage.outgoing === message.outgoing
        const isSameSenderAsNext = nextMessage && nextMessage.sender_key === message.sender_key && nextMessage.outgoing === message.outgoing

        const timeDiffPrev = prevMessage ? new Date(message.date).getTime() - new Date(prevMessage.date).getTime() : Infinity
        const timeDiffNext = nextMessage ? new Date(nextMessage.date).getTime() - new Date(message.date).getTime() : Infinity

        const groupWithPrev = isSameSenderAsPrev && timeDiffPrev < 300000 && !albumLookup.has(prevMessage.id) // simplistic
        const groupWithNext = isSameSenderAsNext && timeDiffNext < 300000 && !albumLookup.has(message.id)

        let timelineGroup: 'none' | 'start' | 'middle' | 'end' = 'none'
        if (groupWithPrev && groupWithNext) timelineGroup = 'middle'
        else if (groupWithPrev) timelineGroup = 'end'
        else if (groupWithNext) timelineGroup = 'start'

        // Wait, for albums, the whole album is one card, so we should consider album's leader.
        // To be safe, just don't group albums for now, or just let it be.

        return <Box key={key} data-index={row.index} data-message-key={key} ref={virtualizer.measureElement} sx={{ position: 'absolute', top: 0, right: 0, width: '100%', py: isAlbumFollower ? 0 : (timelineGroup === 'middle' || timelineGroup === 'end' ? 0.2 : 0.75), height: isAlbumFollower ? 0 : undefined, overflow: 'hidden', overflowAnchor: 'none', contain: isAlbumFollower ? 'strict' : 'layout style', pointerEvents: isAlbumFollower ? 'none' : undefined, transform: \`translateY(\$\{row.start\}px)\`, '& > article': message.id === props.focusMessageId ? { outline: '3px solid', outlineColor: 'primary.main', boxShadow: theme => \`0 0 0 7px \$\{theme.palette.action.selected\}\` } : undefined } }>`;

appCode = appCode.replace(vListRenderRegex, newVListRender);

// add timelineGroup prop to MessageContentCard call
appCode = appCode.replace(
  /<MessageContentCard dialog=\{props\.dialog\} message=\{message\} album=\{album\}/,
  `<MessageContentCard timelineGroup={timelineGroup} dialog={props.dialog} message={message} album={album}`
);

fs.writeFileSync('ui/src/App.tsx', appCode);

console.log('done');

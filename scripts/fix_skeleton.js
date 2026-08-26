const fs = require('fs');

// 1. MessageContentCard.tsx
let cardCode = fs.readFileSync('ui/src/MessageContentCard.tsx', 'utf8');

const regexCard = /\? <Stack spacing=\{1\} alignItems="center" sx=\{\{ width: '100%', p: 2 \}\}><Skeleton variant="rectangular" animation="wave" width="100%" height=\{album \? '100%' : 180\} \/><Typography variant="caption">.*?<\/Typography><\/Stack>/;

const newCard = `? <Skeleton variant="rounded" animation="wave" width="100%" height={album ? '100%' : 240} sx={{ borderRadius: 0 }} />`;

cardCode = cardCode.replace(regexCard, newCard);
fs.writeFileSync('ui/src/MessageContentCard.tsx', cardCode);

// 2. App.tsx
let appCode = fs.readFileSync('ui/src/App.tsx', 'utf8');

const regexApp = /\? <Stack spacing=\{1\.5\} alignItems="center"><Skeleton variant="rectangular" animation="wave" width="min\(76vw, 920px\)" height="min\(68vh, 620px\)" \/><Typography color="text\.secondary">.*?<\/Typography><\/Stack>/;

const newApp = `? <Skeleton variant="rounded" animation="wave" width="min(76vw, 920px)" height="min(68vh, 620px)" />`;

appCode = appCode.replace(regexApp, newApp);
fs.writeFileSync('ui/src/App.tsx', appCode);

console.log('done');

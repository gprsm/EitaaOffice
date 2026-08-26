const fs = require('fs');

let file = fs.readFileSync('ui/src/MessengerAccountGate.tsx', 'utf8');
file = file.replace(
  '<Typography variant="body2" dir="ltr">{account.phone_hint}</Typography>',
  '<Stack direction="row" gap={0.75} alignItems="center"><Box sx={{ display: \'grid\', placeItems: \'center\', width: 16, height: 16, borderRadius: \'50%\', bgcolor: \'#f26522\', color: \'white\', fontSize: 10, fontWeight: \'bold\' }}>e</Box><Typography variant="body2" dir="ltr">{account.phone_hint}</Typography></Stack>'
);
fs.writeFileSync('ui/src/MessengerAccountGate.tsx', file);
console.log('done');

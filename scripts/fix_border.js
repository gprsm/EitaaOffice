const fs = require('fs');

let cardCode = fs.readFileSync('ui/src/MessageContentCard.tsx', 'utf8');

const regex = /borderRadius: message\.outgoing[\s\S]*?'16px 16px 5px 16px',/;

const newBorderRadius = `borderRadius: message.outgoing
        ? timelineGroup === 'start' ? '16px 16px 16px 5px' : timelineGroup === 'middle' ? '5px 16px 16px 5px' : timelineGroup === 'end' ? '5px 16px 16px 16px' : '16px 16px 16px 5px'
        : timelineGroup === 'start' ? '16px 16px 5px 16px' : timelineGroup === 'middle' ? '16px 5px 5px 16px' : timelineGroup === 'end' ? '16px 5px 16px 16px' : '16px 16px 5px 16px',`;

cardCode = cardCode.replace(regex, newBorderRadius);

fs.writeFileSync('ui/src/MessageContentCard.tsx', cardCode);
console.log('done');

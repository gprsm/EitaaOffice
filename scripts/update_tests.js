const fs = require('fs');
const file = 'ui/scripts/run-phase9-workspace-tests.mjs';
let content = fs.readFileSync(file, 'utf8');

content = content.replace(/process\.stdout\.write.*passed.*\\n\`\)/, '');

content += `
check('microphase 3.1: header search is an overlay that captures focus', () => {
  const search = source('src/HeaderMessageSearch.tsx')
  const header = source('src/ChatHeader.tsx')
  assert.match(search, /position: 'absolute'/)
  assert.match(search, /insetInlineEnd: 0/)
  assert.match(search, /minWidth: \\{ xs: 'calc\\(100vw - 32px\\)'/)
  assert.match(search, /inputRef\\.current\\?\\.focus\\(\\)/)
  assert.doesNotMatch(header, /<TextField.*label="جست‌وجوی پیام"/)
  assert.match(header, /<HeaderMessageSearch/)
})

check('microphase 3.2: selection usage history uses independent Dialog and does not open composer', () => {
  const app = source('src/App.tsx')
  const dialog = source('src/UsageInfoDialog.tsx')
  assert.doesNotMatch(app, /setSelectionMode\\(true\\); setComposerOpen\\(true\\)/)
  assert.match(app, /setActiveUsage\\(\\{ message: usedMessage/)
  assert.match(dialog, /<Dialog open=\\{true\\}/)
  assert.doesNotMatch(app, /props\\.activeUsage && !editRecord && <Paper/)
})

check('microphase 3.3: wordpress icon replaces public icon globally', () => {
  const wp = source('src/WordPressIcon.tsx')
  const nav = source('src/WorkspaceNavigation.tsx')
  const header = source('src/ChatHeader.tsx')
  assert.match(wp, /<path d="M12 2C6\\.48 2 2 6\\.48 2 12s4\\.48 10 10 10 10-4\\.48 10-10S17\\.52 2 12 2zm/)
  assert.match(nav, /<WordPressIcon \\/>/)
  assert.doesNotMatch(nav, /<PublicRounded \\/>وردپرس/)
  assert.match(header, /<WordPressIcon \\/><\\/IconButton>/)
  assert.doesNotMatch(header, /<PublicRounded \\/><\\/IconButton>/)
})

process.stdout.write(\`# \${passed}/\${passed} Phase 9 workspace assertions passed\\n\`)
`;

fs.writeFileSync(file, content);

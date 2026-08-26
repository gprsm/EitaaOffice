const fs = require('fs');
let code = fs.readFileSync('ui/src/App.tsx', 'utf8');

const target = /filtersActive=\{contentFiltersOpen \|\| \!showWordPressUsed \|\| selectedIndexLabel \!\=\= null \|\| selectedSenderKey \!\=\= null\}\n\s*filterEnabled=\{Boolean\(dialog\)\}[\s\S]*?onToggleFilters=\{.*?setContentFiltersOpen.*?\}/;

code = code.replace(target, 
`filtersActive={contentFiltersOpen || !showWordPressUsed || selectedIndexLabel !== null || selectedSenderKey !== null}
          filterEnabled={Boolean(dialog && dialog.display_kind !== 'personal')}
          indexActive={indexDialogOpen}
          indexEnabled={Boolean(dialog && dialog.favorite)}
          onToggleFilters={() => setContentFiltersOpen(v => !v)}
          onToggleIndex={() => setIndexDialogOpen(v => !v)}`);

fs.writeFileSync('ui/src/App.tsx', code);

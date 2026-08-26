const fs = require('fs');
let code = fs.readFileSync('ui/src/App.tsx', 'utf8');

// Fix state
code = code.replace(
  "const [indexWorkbenchTab, setIndexWorkbenchTab] = useState<IndexWorkbenchTab>('index')",
  "const [indexDialogOpen, setIndexDialogOpen] = useState(false)"
);
code = code.replace(/type IndexWorkbenchTab = 'index' \| 'display'\r?\n/, '');
code = code.replace(/\|\| indexWorkbenchTab \!\=\= 'display'/g, '');
code = code.replace(/&& indexWorkbenchTab === 'display' /g, '');
code = code.replace(/indexWorkbenchTab,/g, '');

// Fix ChatHeader props
const chatHeaderOld = `filtersActive={contentFiltersOpen || !showWordPressUsed || selectedIndexLabel !== null || selectedSenderKey !== null}
          filterEnabled={Boolean(dialog)}
          datePicker={<JalaliDatePicker`;

const chatHeaderNew = `filtersActive={contentFiltersOpen || !showWordPressUsed || selectedIndexLabel !== null || selectedSenderKey !== null}
          filterEnabled={Boolean(dialog && dialog.display_kind !== 'personal')}
          indexActive={indexDialogOpen}
          indexEnabled={Boolean(dialog && dialog.favorite)}
          onToggleIndex={() => setIndexDialogOpen(v => !v)}
          datePicker={<JalaliDatePicker`;

code = code.replace(chatHeaderOld, chatHeaderNew);

fs.writeFileSync('ui/src/App.tsx', code);

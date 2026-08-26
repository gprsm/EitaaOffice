const fs = require('fs');
let app = fs.readFileSync('ui/src/App.tsx', 'utf8');

// Imports
app = app.replace("const MaterialIndexWorkbench = lazy(() => import('./MaterialIndexWorkbench').then(module => ({ default: module.MaterialIndexWorkbench })))", 
  "const MessageFilterDialog = lazy(() => import('./MessageFilterDialog').then(module => ({ default: module.MessageFilterDialog })))\nconst ContentIndexDialog = lazy(() => import('./ContentIndexDialog').then(module => ({ default: module.ContentIndexDialog })))");

// State
app = app.replace("const [indexWorkbenchTab, setIndexWorkbenchTab] = useState<'index' | 'display'>('display')", "const [indexDialogOpen, setIndexDialogOpen] = useState(false)");

// ChatHeader props
app = app.replace(/filtersActive=\{contentFiltersOpen\}[\s\S]*?onToggleFilters=\{.*?setIndexWorkbenchTab.*?\}/,
`filtersActive={contentFiltersOpen}
        filterEnabled={dialog != null && dialog.display_kind !== 'personal'}
        indexActive={indexDialogOpen}
        indexEnabled={dialog != null && dialog.favorite === true}
        onToggleFilters={() => setContentFiltersOpen(v => !v)}
        onToggleIndex={() => setIndexDialogOpen(v => !v)}`);

// Dialog components
app = app.replace(/\{contentFiltersOpen && <Suspense fallback=\{<CircularProgress sx=\{\{ position: 'fixed', inset: 0, m: 'auto', zIndex: theme => theme\.zIndex\.modal \+ 1 \}\} \/>\}><MaterialIndexWorkbench[\s\S]*?<\/Suspense>\}/,
`{contentFiltersOpen && <Suspense fallback={<CircularProgress sx={{ position: 'fixed', inset: 0, m: 'auto', zIndex: theme => theme.zIndex.modal + 1 }} />}><MessageFilterDialog
      open={contentFiltersOpen}
      close={() => setContentFiltersOpen(false)}
      showWordPressUsed={showWordPressUsed}
      setShowWordPressUsed={setShowWordPressUsed}
      selectedIndexLabel={selectedIndexLabel}
      setSelectedIndexLabel={setSelectedIndexLabel}
      selectedSenderKey={selectedSenderKey}
      setSelectedSenderKey={setSelectedSenderKey}
      indexFilterLabels={indexDefinitions.map(def => ({ id: def.id, name: def.name }))}
      senderFilterOptions={senderFilterOptions}
      senderResolutionState={senderResolutionState}
      unresolvedSenderCount={unresolvedSenderCount}
      filteredMessageCount={filteredDialogMessages.length}
    /></Suspense>}
    {indexDialogOpen && <Suspense fallback={<CircularProgress sx={{ position: 'fixed', inset: 0, m: 'auto', zIndex: theme => theme.zIndex.modal + 1 }} />}><ContentIndexDialog
      open={indexDialogOpen}
      close={() => setIndexDialogOpen(false)}
      contentIndexActive={contentIndexActive}
      contentIndexState={contentIndexState}
      contentIndexProcessed={contentIndexProcessed}
      contentIndexTarget={contentIndexTarget}
      contentIndexPercent={contentIndexPercent}
      coldStart={coldStart}
      resultCount={contentIndexResults.length}
      canStart={dialog != null && indexDefinitions.length > 0}
      start={() => dialog && startIndex(dialog)}
      cancel={cancelIndex}
      definitions={indexDefinitions}
      categories={categories.map(c => ({ id: c.id, name: c.name }))}
      customIndexName={customIndexName}
      setCustomIndexName={setCustomIndexName}
      customIndexKeywords={customIndexKeywords}
      setCustomIndexKeywords={setCustomIndexKeywords}
      customIndexCategoryId={customIndexCategoryId}
      setCustomIndexCategoryId={setCustomIndexCategoryId}
      addCustomIndex={addCustomIndex}
      selectedDefinitionId={indexEditor.id}
      selectDefinition={id => setIndexEditor(current => ({ ...current, id }))}
      indexNameDraft={indexEditor.name}
      setIndexNameDraft={name => setIndexEditor(current => ({ ...current, name }))}
      indexKeywordDraft={indexEditor.keywords}
      setIndexKeywordDraft={keywords => setIndexEditor(current => ({ ...current, keywords }))}
      saveDefinition={saveDefinition}
      deleteDefinition={deleteDefinition}
    /></Suspense>}`);

fs.writeFileSync('ui/src/App.tsx', app);

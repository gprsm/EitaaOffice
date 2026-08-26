const fs = require('fs');
let app = fs.readFileSync('ui/src/App.tsx', 'utf8');

app = app.replace(
  'filteredMessageCount={filteredDialogMessages.length}',
  'filteredMessageCount={filteredMessages.length}'
);

app = app.replace(
  'contentIndexState={contentIndexState}',
  'contentIndexState={contentIndexJob?.state}'
);

app = app.replace(
  'contentIndexProcessed={contentIndexProcessed}',
  'contentIndexProcessed={contentIndexProgress.processed_messages || 0}'
);

app = app.replace(
  'contentIndexTarget={contentIndexTarget}',
  'contentIndexTarget={contentIndexProgress.target_messages || 0}'
);

app = app.replace(
  'resultCount={contentIndexResults.length}',
  'resultCount={Object.keys(contentIndexResults).length}'
);

app = app.replace(
  'coldStart={coldStart}',
  'coldStart={Object.keys(contentIndexResults).length < 5}'
);

app = app.replace(
  'start={() => dialog && startIndex(dialog)}',
  'start={startContentIndex}'
);

app = app.replace(
  'cancel={cancelIndex}',
  'cancel={cancelContentIndex}'
);

// fix indexEditor
app = app.replace(
  'selectedDefinitionId={indexEditor.id}',
  'selectedDefinitionId={indexEditor?.id ?? null}'
);

app = app.replace(
  'selectDefinition={id => setIndexEditor(current => ({ ...current, id }))}',
  'selectDefinition={id => { /* only for actual index editor */ }}'
);

app = app.replace(
  'indexNameDraft={indexEditor.name}',
  "indexNameDraft={''}"
);

app = app.replace(
  'setIndexNameDraft={name => setIndexEditor(current => ({ ...current, name }))}',
  'setIndexNameDraft={() => {}}'
);

app = app.replace(
  'indexKeywordDraft={indexEditor.keywords}',
  "indexKeywordDraft={''}"
);

app = app.replace(
  'setIndexKeywordDraft={keywords => setIndexEditor(current => ({ ...current, keywords }))}',
  'setIndexKeywordDraft={() => {}}'
);

app = app.replace(
  'saveDefinition={saveDefinition}',
  'saveDefinition={() => {}}'
);

app = app.replace(
  'deleteDefinition={deleteDefinition}',
  'deleteDefinition={() => {}}'
);

fs.writeFileSync('ui/src/App.tsx', app);

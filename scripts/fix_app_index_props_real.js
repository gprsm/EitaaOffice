const fs = require('fs');
let code = fs.readFileSync('ui/src/App.tsx', 'utf8');

const regex = /<ContentIndexDialog[\s\S]*?\/>/g;

const newComponent = `<ContentIndexDialog
      open={indexDialogOpen}
      close={() => setIndexDialogOpen(false)}
      contentIndexActive={contentIndexActive}
      contentIndexState={contentIndexJob?.state}
      contentIndexProcessed={contentIndexProgress.processed_messages || 0}
      contentIndexTarget={contentIndexProgress.target_messages || 0}
      contentIndexPercent={contentIndexPercent}
      coldStart={Object.keys(contentIndexResults).length < 5}
      resultCount={Object.keys(contentIndexResults).length}
      canStart={dialog != null && indexDefinitions.length > 0}
      start={startContentIndex}
      cancel={cancelContentIndex}
      definitions={indexDefinitions}
      categories={categories.map(c => ({ id: c.id, name: c.name }))}
      customIndexName={customIndexName}
      setCustomIndexName={setCustomIndexName}
      customIndexKeywords={customIndexKeywords}
      setCustomIndexKeywords={setCustomIndexKeywords}
      customIndexCategoryId={customIndexCategoryId}
      setCustomIndexCategoryId={setCustomIndexCategoryId}
      addCustomIndex={addCustomIndex}
      selectedDefinitionId={indexKeywordCategoryId}
      selectDefinition={setIndexKeywordCategoryId}
      indexNameDraft={indexNameDraft}
      setIndexNameDraft={setIndexNameDraft}
      indexKeywordDraft={indexKeywordDraft}
      setIndexKeywordDraft={setIndexKeywordDraft}
      saveDefinition={saveIndexKeywords}
      deleteDefinition={deleteCustomIndex}
    />`;

code = code.replace(regex, newComponent);

code = code.replace('filteredMessageCount={filteredDialogMessages.length}', 'filteredMessageCount={filteredMessages.length}');

fs.writeFileSync('ui/src/App.tsx', code);

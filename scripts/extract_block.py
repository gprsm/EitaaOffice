with open('ui/src/App.tsx.backup', 'r', encoding='utf-8') as f:
    content = f.read()
    
start_str = "const TEMPORAL_YEAR_OFFSET = 3_000_000_000"
end_str = "function initials(title: string) {"
start_idx = content.find(start_str)
end_idx = content.find(end_str, start_idx)

# Let's extract everything between them and save it to helpers.ts (excluding the jalali stuff which we already have in jalali.tsx)
block = content[start_idx:end_idx]

# We will just write block to a temp file so we can look at it
with open('scripts/extracted_block.ts', 'w', encoding='utf-8') as f:
    f.write(block)

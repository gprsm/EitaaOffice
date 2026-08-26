const fs = require('fs');
const lines = fs.readFileSync('C:/Users/Mohsen/.gemini/antigravity/brain/0c501744-1e2b-47d7-955c-2cf25de84710/.system_generated/logs/transcript.jsonl', 'utf8').split('\n');
const userInputs = lines.filter(l => l.includes('"type":"USER_INPUT"'));
const firstBigInput = userInputs.find(l => l.length > 2000);
if (firstBigInput) {
  const data = JSON.parse(firstBigInput);
  console.log(data.content);
}

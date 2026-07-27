import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import { createRequire } from 'node:module'
import { execFileSync } from 'node:child_process'
const require = createRequire(import.meta.url)
let ts
try {
  ts = require('typescript')
} catch {
  const globalRoot = execFileSync('npm', ['root', '-g'], { encoding: 'utf8' }).trim()
  ts = require(path.join(globalRoot, 'typescript'))
}

const entry = path.resolve('src/lib/groupedMedia.ts')
const source = await readFile(entry, 'utf8')
const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText
const encoded = Buffer.from(compiled).toString('base64')
const { albumCaption, buildAlbumLookup } = await import(`data:text/javascript;base64,${encoded}`)

function message(id, groupedId, text = '', options = {}) {
  return {
    id,
    grouped_id: groupedId,
    text,
    date: options.date || new Date(Date.UTC(2026, 0, 1, 10, 0, id)).toISOString(),
    sender_key: options.senderKey || null,
    reply_to_message_id: options.replyTo ?? null,
    media: options.image ? { is_image: true, type: 'photo' } : null,
  }
}

const messages = [
  message(13, 9001, 'گزارش تکمیلی'),
  message(11, 9001, 'گزارش اصلی'),
  message(12, 9001, 'گزارش اصلی'),
  message(20, null, 'پیام مستقل'),
  message(21, 9002, ''),
]
const lookup = buildAlbumLookup(messages)

assert.equal(lookup.has(20), false, 'ungrouped messages must stay independent')
assert.deepEqual(lookup.get(11).messages.map(item => item.id), [11, 12, 13])
assert.equal(lookup.get(12), lookup.get(13), 'every member must resolve to one album object')
assert.equal(lookup.get(11).leader.id, 11)
assert.equal(lookup.get(11).last.id, 13)
assert.equal(lookup.get(21).messages.length, 1, 'a partial local album remains explicit')
assert.equal(lookup.get(11).kind, 'server')
assert.equal(
  albumCaption(lookup.get(11).messages),
  'گزارش اصلی\n\nگزارش تکمیلی',
  'captions must be ordered, non-empty and deduplicated',
)

const inferredMessages = [
  message(30, null, '', { image: true, senderKey: 'user:7', date: '2026-01-01T10:00:00Z' }),
  message(31, null, '', { image: true, senderKey: 'user:7', date: '2026-01-01T10:01:59Z' }),
  message(40, null, '', { image: true, senderKey: 'user:7', date: '2026-01-01T11:00:00Z' }),
  message(41, null, '', { image: true, senderKey: 'user:8', date: '2026-01-01T11:00:10Z' }),
  message(50, null, '', { image: true, senderKey: 'user:9', date: '2026-01-01T12:00:00Z' }),
  message(51, null, '', { image: true, senderKey: 'user:9', date: '2026-01-01T12:02:01Z' }),
  message(60, null, '', { image: true, senderKey: 'user:10', date: '2026-01-01T13:00:00Z' }),
  message(62, null, '', { image: true, senderKey: 'user:10', date: '2026-01-01T13:00:10Z' }),
  message(70, null, '', { image: true, senderKey: 'user:11', replyTo: 5, date: '2026-01-01T14:00:00Z' }),
  message(71, null, '', { image: true, senderKey: 'user:11', replyTo: 6, date: '2026-01-01T14:00:10Z' }),
]
const inferredLookup = buildAlbumLookup(inferredMessages)

assert.equal(inferredLookup.get(30), inferredLookup.get(31), 'same sender consecutive photos within 120 seconds form one inferred gallery')
assert.equal(inferredLookup.get(30).kind, 'inferred')
assert.equal(inferredLookup.get(30).groupedId, null)
assert.equal(inferredLookup.has(40), false, 'different senders must not be inferred as one gallery')
assert.equal(inferredLookup.has(41), false, 'different senders must remain independent')
assert.equal(inferredLookup.has(50), false, 'more than 120 seconds must break an inferred gallery')
assert.equal(inferredLookup.has(60), false, 'non-adjacent message ids must break an inferred gallery')
assert.equal(inferredLookup.has(70), false, 'different reply contexts must break an inferred gallery')

console.log('# 16/16 grouped-media UI model assertions passed')

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
const { albumCaption, buildAlbumLookup, buildMessageGroupLookup, messageGroupText } = await import(`data:text/javascript;base64,${encoded}`)

function message(id, groupedId, text = '', options = {}) {
  return {
    id,
    grouped_id: groupedId,
    text,
    date: options.date || new Date(Date.UTC(2026, 0, 1, 10, 0, id)).toISOString(),
    sender_key: options.senderKey || null,
    sender_username: options.senderUsername || null,
    outgoing: options.outgoing || false,
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

const timelineMessages = [
  message(80, null, 'متن پیش از عکس', { senderKey: 'user:20', date: '2026-01-01T15:00:00Z' }),
  message(81, null, '', { image: true, senderKey: 'user:20', date: '2026-01-01T15:01:00Z' }),
  message(82, null, '', { image: true, senderKey: 'user:20', date: '2026-01-01T15:02:00Z' }),
  message(83, null, 'متن پس از عکس', { senderKey: 'user:20', date: '2026-01-01T15:03:00Z' }),
  message(90, 9100, '', { image: true, senderKey: 'user:30', date: '2026-01-01T16:00:00Z' }),
  message(91, 9100, '', { image: true, senderKey: 'user:30', date: '2026-01-01T16:00:05Z' }),
  message(92, 9200, '', { image: true, senderKey: 'user:30', date: '2026-01-01T16:00:10Z' }),
  message(93, 9200, '', { image: true, senderKey: 'user:30', date: '2026-01-01T16:00:15Z' }),
  message(100, null, 'الف', { senderKey: 'user:40', date: '2026-01-01T17:00:00Z' }),
  message(101, null, 'ب', { senderKey: 'user:41', date: '2026-01-01T17:00:10Z' }),
  message(102, null, 'ج', { senderKey: 'user:40', date: '2026-01-01T17:00:20Z' }),
  message(110, null, 'قدیمی', { senderKey: 'user:50', date: '2026-01-01T18:00:00Z' }),
  message(111, null, 'جدید', { senderKey: 'user:50', date: '2026-01-01T18:05:01Z' }),
  message(120, null, 'خروجی یک', { outgoing: true, date: '2026-01-01T19:00:00Z' }),
  message(121, null, 'خروجی دو', { outgoing: true, date: '2026-01-01T19:00:10Z' }),
  message(130, null, 'پیش از نیمه‌شب', { senderKey: 'user:60', date: '2026-01-01T23:59:55+03:30' }),
  message(131, null, 'پس از نیمه‌شب', { senderKey: 'user:60', date: '2026-01-02T00:00:05+03:30' }),
]
const timelineLookup = buildMessageGroupLookup(timelineMessages)

assert.deepEqual(timelineLookup.get(80).messages.map(item => item.id), [80, 81, 82, 83], 'text-photo-photo-text must render as one sender block')
assert.equal(timelineLookup.get(80), timelineLookup.get(83), 'every mixed-content member resolves to one group')
assert.equal(messageGroupText(timelineLookup.get(80).messages), 'متن پیش از عکس\n\nمتن پس از عکس', 'group text keeps chronological content')
assert.deepEqual(timelineLookup.get(90).messages.map(item => item.id), [90, 91, 92, 93], 'back-to-back server albums from one sender must merge')
assert.equal(timelineLookup.get(90).kind, 'timeline', 'merged albums become one timeline group')
assert.equal(timelineLookup.has(100), false, 'an intervening sender keeps the first message independent')
assert.equal(timelineLookup.has(102), false, 'messages are not merged across an intervening sender')
assert.equal(timelineLookup.has(110), false, 'more than five minutes breaks the group')
assert.equal(timelineLookup.has(111), false, 'the later message after the gap remains independent')
assert.equal(timelineLookup.get(120), timelineLookup.get(121), 'outgoing messages group without sender metadata')
assert.equal(timelineLookup.has(130), false, 'a local display-day boundary breaks the group')
assert.equal(timelineLookup.has(131), false, 'the new display day begins a separate block')

const fallbackLookup = buildMessageGroupLookup([
  message(140, null, 'یک', { date: '2026-01-01T20:00:00Z' }),
  message(141, null, 'دو', { date: '2026-01-01T20:00:10Z' }),
], { fallbackIncomingSenderKey: 'dialog:personal:1' })
assert.equal(fallbackLookup.get(140), fallbackLookup.get(141), 'personal/channel fallback identity can group missing sender metadata')

console.log('# 29/29 grouped-media UI model assertions passed')

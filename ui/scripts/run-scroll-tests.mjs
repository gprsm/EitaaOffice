import assert from 'node:assert/strict'
import { mkdtemp, rm } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { readFile, writeFile } from 'node:fs/promises'
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

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const temp = await mkdtemp(path.join(os.tmpdir(), 'eitaa-scroll-tests-'))
const outfile = path.join(temp, 'scrollMath.mjs')

try {
  const source = await readFile(path.join(root, 'src', 'lib', 'scrollMath.ts'), 'utf8')
  const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText
  await writeFile(outfile, compiled, 'utf8')
  const scroll = await import(`${pathToFileURL(outfile).href}?v=${Date.now()}`)
  let passed = 0
  const test = (name, fn) => {
    fn()
    passed += 1
    console.log(`ok ${passed} - ${name}`)
  }

  const usage = { used: false, usage_state: 'unused', stale: false, compositions: [] }
  const makeMessage = id => ({
    id,
    date: new Date(1_700_000_000_000 + id * 60_000).toISOString(),
    text: id % 11 === 0 ? 'متن بلند چندخطی\n'.repeat(8) : id % 3 === 0 ? 'پیام کوتاه' : 'پیام متوسط '.repeat(6),
    text_length: id % 11 === 0 ? 144 : id % 3 === 0 ? 10 : 66,
    media: id % 7 === 0 ? { type: 'photo', is_image: true } : id % 13 === 0 ? { type: 'document', is_image: false } : null,
    outgoing: id % 17 === 0,
    usage,
  })
  const messages = Array.from({ length: 5000 }, (_, index) => makeMessage(index + 1))

  test('stable message keys do not change when older messages are prepended', () => {
    const before = messages.slice(200, 260).map(message => scroll.stableMessageKey('channel:42', message.id))
    const prepended = [...Array.from({ length: 200 }, (_, index) => makeMessage(index - 199)), ...messages]
    const after = prepended.slice(400, 460).map(message => scroll.stableMessageKey('channel:42', message.id))
    assert.deepEqual(after, before)
  })

  test('5000 mixed rows receive deterministic positive estimates', () => {
    const first = messages.map((message, index) => scroll.estimateMessageRowSize(message, index % 50 === 0, index === 4800))
    const second = messages.map((message, index) => scroll.estimateMessageRowSize(message, index % 50 === 0, index === 4800))
    assert.deepEqual(second, first)
    assert.equal(first.length, 5000)
    assert.ok(first.every(value => Number.isFinite(value) && value >= 72))
    assert.ok(first.reduce((sum, value) => sum + value, 0) > 5000 * 72)
  })

  test('image estimates reserve substantially more space than short text', () => {
    const image = makeMessage(7)
    const text = makeMessage(3)
    assert.ok(scroll.estimateMessageRowSize(image, false, false) > scroll.estimateMessageRowSize(text, false, false) + 250)
  })

  test('merge keeps all 5000 messages, updates duplicates, and sorts by id', () => {
    const incoming = [{ ...makeMessage(2500), text: 'updated', text_length: 7 }, makeMessage(5001), makeMessage(0)]
    const merged = scroll.mergeMessagesById(messages, incoming)
    assert.equal(merged.length, 5002)
    assert.equal(merged[0].id, 0)
    assert.equal(merged.at(-1).id, 5001)
    assert.equal(merged.find(message => message.id === 2500).text, 'updated')
  })

  test('prepend anchor restores the same pixel offset', () => {
    assert.equal(scroll.anchorScrollTop(12_480, -37), 12_517)
    assert.equal(scroll.anchorScrollTop(40, 75), 0)
  })

  test('top pagination fires once until the user leaves and re-enters the threshold', () => {
    let gate = { armed: true, inFlight: false }
    let update = scroll.updateTopPaginationGate(80, 140, gate)
    assert.equal(update.shouldRequest, true)
    gate = update.gate
    update = scroll.updateTopPaginationGate(60, 80, gate)
    assert.equal(update.shouldRequest, false)
    gate = update.gate
    update = scroll.updateTopPaginationGate(320, 60, gate)
    assert.equal(update.shouldRequest, false)
    gate = update.gate
    update = scroll.updateTopPaginationGate(70, 320, gate)
    assert.equal(update.shouldRequest, true)
  })

  test('an active pagination request cannot be duplicated', () => {
    const update = scroll.updateTopPaginationGate(50, 120, { armed: true, inFlight: true })
    assert.equal(update.shouldRequest, false)
  })

  test('auto-follow occurs only near the bottom or for an outgoing appended message', () => {
    assert.equal(scroll.shouldAutoFollow(false, [makeMessage(18)]), false)
    assert.equal(scroll.shouldAutoFollow(true, [makeMessage(18)]), true)
    assert.equal(scroll.shouldAutoFollow(false, [{ ...makeMessage(18), outgoing: true }]), true)
  })

  test('appended detection ignores prepend and returns only messages after the previous tail', () => {
    const small = messages.slice(0, 10)
    assert.deepEqual(scroll.appendedMessagesAfterTail([makeMessage(0), ...small], 10), [])
    assert.deepEqual(scroll.appendedMessagesAfterTail([...small, makeMessage(11), makeMessage(12)], 10).map(message => message.id), [11, 12])
  })

  test('near-bottom calculation is stable at the threshold boundary', () => {
    assert.equal(scroll.isNearBottom(2000, 1320, 500, 180), true)
    assert.equal(scroll.isNearBottom(2000, 1319, 500, 180), false)
  })

  console.log(`# ${passed}/${passed} scroll model tests passed`)
} finally {
  await rm(temp, { recursive: true, force: true })
}

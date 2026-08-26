import { createHash } from 'node:crypto'
import { mkdir, readFile, readdir, unlink, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const uiRoot = fileURLToPath(new URL('../', import.meta.url))
const sourcePatch = path.join(uiRoot, 'src', 'ui33-runtime-patch.js')
const assetsDir = path.join(uiRoot, 'dist', 'assets')
const indexFile = path.join(uiRoot, 'dist', 'index.html')
const materialMarker = path.join(uiRoot, 'dist', '.material-ui-v1')

await mkdir(assetsDir, { recursive: true })
const patchSource = await readFile(sourcePatch)
const patchHash = createHash('sha256').update(patchSource).digest('hex').slice(0, 16)
const patchFile = `ui33-runtime-patch-${patchHash}.js`
const distPatch = path.join(assetsDir, patchFile)
const patchTag = `    <script src="./assets/${patchFile}"></script>\n`

for (const asset of await readdir(assetsDir)) {
  if (/^ui33-runtime-patch(?:-[0-9a-f]{16})?\.js$/.test(asset)) {
    await unlink(path.join(assetsDir, asset))
  }
}
await writeFile(distPatch, patchSource)

let index = await readFile(indexFile, 'utf8')
index = index.replace(
  /^\s*<script src="\.\/assets\/ui33-runtime-patch(?:-[0-9a-f]{16})?\.js"><\/script>\s*$/gm,
  '',
)
index = index.replace('    <script type="module"', `${patchTag}    <script type="module"`)
await writeFile(indexFile, index, 'utf8')

await writeFile(materialMarker, 'Material UI production build\n', 'utf8')

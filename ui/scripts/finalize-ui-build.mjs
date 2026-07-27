import { copyFile, mkdir, readFile, writeFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const uiRoot = fileURLToPath(new URL('../', import.meta.url))
const sourcePatch = path.join(uiRoot, 'src', 'ui33-runtime-patch.js')
const assetsDir = path.join(uiRoot, 'dist', 'assets')
const distPatch = path.join(assetsDir, 'ui33-runtime-patch.js')
const indexFile = path.join(uiRoot, 'dist', 'index.html')
const patchTag = '    <script src="./assets/ui33-runtime-patch.js"></script>\n'
const materialMarker = path.join(uiRoot, 'dist', '.material-ui-v1')

await mkdir(assetsDir, { recursive: true })
await copyFile(sourcePatch, distPatch)

let index = await readFile(indexFile, 'utf8')
if (!index.includes('ui33-runtime-patch.js')) {
  index = index.replace('    <script type="module"', `${patchTag}    <script type="module"`)
  await writeFile(indexFile, index, 'utf8')
}

await writeFile(materialMarker, 'Material UI production build\n', 'utf8')

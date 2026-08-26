# GMI 4.1.1 TypeScript Build Repair

Corrected the three Windows build failures reported with Node.js 24.18.0 and npm 11.16.0:

1. MUI Select values are represented as strings at the UI boundary and converted to numeric IDs only after selection.
2. A local declaration is provided for the `stylis` `prefixer` export.
3. `electron` and `esbuild` install scripts are explicitly reviewed in `package.json` through `allowScripts`.
4. `setup_ui.bat` now distinguishes registry/install failures from TypeScript and Vite build failures.

The standalone `npm i @mui/material` command run outside the project directory is not required by this package. The project installs its pinned dependencies from `ui/package.json`.

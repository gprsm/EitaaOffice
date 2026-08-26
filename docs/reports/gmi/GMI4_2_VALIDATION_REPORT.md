# GMI 4.2 Validation Report

- Python tests: 260/260 passed with bundled Core wheel on `PYTHONPATH`.
- GMI deterministic smoke: 31/31 passed.
- Scroll model: 10/10 passed with 5,000 mixed synthetic rows.
- Grouped-media model: 16/16 passed.
- TypeScript/TSX parse/transpile syntax: 13/13 source files passed.
- Electron main/preload syntax: passed.
- Python compileall: passed.
- Installed wheel smoke: `eitaa-bridge 0.7.0.dev31` + `eitaa-core 0.6.0.dev19` passed.
- Contact/send focused tests: actual Eitaa contact list/add/sync contract, strict target category filtering, staged upload send and cache behavior passed.

## Build limitation

The review container could not complete npm package installation. Full `tsc -b` and Vite production build must run on the Windows acceptance machine, where npm Registry access has already been proven. The source no longer contains the three TypeScript failures previously reported by the user.

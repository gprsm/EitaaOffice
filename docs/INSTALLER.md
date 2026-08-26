# ساخت Windows Installer

بسته شامل تعریف کامل Inno Setup است، اما فایل EXE نهایی باید روی Windows ساخته و امضا شود.

## بستهٔ تمیز قابل‌ممیزی

`package_clean.py` خروجی را از allowlist صریح runtime/source/UI/installer/wheel/doc می‌سازد؛ پیمایش blacklist مبنای انتشار نیست. هر ZIP یک `_release/CONTENT_MANIFEST.json` داخلی با نام، اندازه و SHA-256 و یک receipt بیرونی با SHA-256 کل archive دارد. `--dry-run` هیچ فایل خروجی نمی‌نویسد.

نام traversal/absolute/backslash، duplicate/case collision، hash/manifest mismatch، محدودیت اندازه و الگوی high-confidence secret رد می‌شود. `data/`، `runtime/`، `diagnostics/`، `backups/`، config/session واقعی، scratch/fix/probe، تست‌ها، حافظهٔ داخلی پروژه و client قرنطینه‌شدهٔ Bale وارد release نمی‌شوند؛ fail-closed provider slot باقی است.

wheel Bridge باید پیش از archive با تمام source مجاز byte-parity داشته باشد. builder آفلاین canonical این پروژه `scripts/build_wheel_stdlib.py` است و metadata/entrypoint را از `pyproject.toml` می‌خواند. `build_wheel.bat` همین builder را اجرا می‌کند و cache یا egg-info را پاک نمی‌کند.

پذیرش آفلاین شامل دو build/archive بایت‌یکسان، extract تازه، self-dry-run، compile، نصب wheelها در venv خالی، runtime checker و `pip check` است. این rehearsal جای code-sign، Windows 10/11 acceptance یا نصب واقعی کاربر را نمی‌گیرد.

پیش‌نیاز ایستگاه Build:

- Windows x64
- Python 3.13 x64
- Node.js 24 LTS x64
- Inno Setup 6
- دسترسی به Electron release assets و npm registry

سپس اجرا کنید:

```bat
build_windows_installer.bat
```

خروجی مورد انتظار:

```text
release\installer\EitaaBridge-0.8.0-rc1-Setup-x64.exe
```

فرایند ابتدا UI را Build و Package می‌کند، سپس Runtime Backend و Wheelهای آفلاین را کنار آن می‌گذارد و در پایان Installer کاربرمحور بدون نیاز به Administrator می‌سازد. پیش از انتشار عمومی، فایل Installer باید Code-sign، روی Windows 10/11 پاک آزمایش و با Session واقعی Acceptance شود.


## MVP 6.1.1 Runtime repair policy

- `install_app.bat` is idempotent for an exact healthy environment and does not force-reinstall it.
- A mismatched environment is upgraded from bundled offline wheels.
- Same-version corruption is not silently overwritten; run `repair_app.bat`.
- `repair_app.bat` first stops only the owned runtime, then performs explicit force-reinstallation.
- Office payload installation calls the ownership controller before copying files so active owned Python modules are not left locked.
- No installer or stop command kills a process by port.

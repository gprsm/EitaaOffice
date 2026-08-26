from __future__ import annotations

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Write an ASCII IExpress SED file.")
    parser.add_argument("--output", required=True)
    parser.add_argument("--source-dir", required=True)
    parser.add_argument("--target-exe", required=True)
    args = parser.parse_args()

    output = Path(args.output)
    source_dir = Path(args.source_dir).resolve()
    target_exe = Path(args.target_exe).resolve()

    # IExpress is old and can reject UTF-8 SED files. Keep this directive file
    # strictly ASCII and place all build paths in the ASCII-only TEMP tree.
    source_text = str(source_dir)
    if not source_text.endswith("\\"):
        source_text += "\\"

    values = [str(output), source_text, str(target_exe)]
    try:
        for value in values:
            value.encode("ascii")
    except UnicodeEncodeError as exc:
        raise SystemExit(
            "IExpress build paths must be ASCII. The builder should use the Windows TEMP folder."
        ) from exc

    sed = f"""[Version]\r\nClass=IEXPRESS\r\nSEDVersion=3\r\n\r\n[Options]\r\nPackagePurpose=InstallApp\r\nShowInstallProgramWindow=1\r\nHideExtractAnimation=0\r\nUseLongFileName=1\r\nInsideCompressed=0\r\nCAB_FixedSize=0\r\nCAB_ResvCodeSigning=0\r\nRebootMode=N\r\nInstallPrompt=%InstallPrompt%\r\nDisplayLicense=%DisplayLicense%\r\nFinishMessage=%FinishMessage%\r\nTargetName=%TargetName%\r\nFriendlyName=%FriendlyName%\r\nAppLaunched=%AppLaunched%\r\nPostInstallCmd=%PostInstallCmd%\r\nAdminQuietInstCmd=%AdminQuietInstCmd%\r\nUserQuietInstCmd=%UserQuietInstCmd%\r\nSourceFiles=SourceFiles\r\n\r\n[SourceFiles]\r\nSourceFiles0={source_text}\r\n\r\n[SourceFiles0]\r\n%FILE0%=\r\n%FILE1%=\r\n\r\n[Strings]\r\nInstallPrompt=\r\nDisplayLicense=\r\nFinishMessage=\r\nTargetName={target_exe}\r\nFriendlyName=Eitaa Bridge Office Setup\r\nAppLaunched=install_office_payload.cmd\r\nPostInstallCmd=<None>\r\nAdminQuietInstCmd=\r\nUserQuietInstCmd=\r\nFILE0=office_payload.zip\r\nFILE1=install_office_payload.cmd\r\n"""

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(sed.encode("ascii"))
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

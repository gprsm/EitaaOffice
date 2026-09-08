Option Explicit

Dim service, systems, system, versionParts, majorVersion, architecture

On Error Resume Next
Set service = GetObject("winmgmts:\\.\root\cimv2")
Set systems = service.ExecQuery("Select Version, OSArchitecture from Win32_OperatingSystem")
If Err.Number <> 0 Then
  MsgBox "Windows compatibility could not be verified. Setup was stopped without changing the computer.", 16, "Eitaa Bridge Setup"
  WScript.Quit 11
End If
On Error GoTo 0

For Each system In systems
  versionParts = Split(CStr(system.Version), ".")
  If UBound(versionParts) < 1 Then
    MsgBox "Windows compatibility could not be verified. Setup was stopped without changing the computer.", 16, "Eitaa Bridge Setup"
    WScript.Quit 11
  End If
  majorVersion = CInt(versionParts(0))
  architecture = LCase(CStr(system.OSArchitecture))
  If majorVersion < 10 Then
    MsgBox "This build requires Windows 10 or newer. Windows 7 cannot safely run the bundled Python and browser runtime.", 16, "Eitaa Bridge Setup"
    WScript.Quit 10
  End If
  If InStr(architecture, "64") = 0 Then
    MsgBox "This build requires 64-bit Windows.", 16, "Eitaa Bridge Setup"
    WScript.Quit 12
  End If
  WScript.Quit 0
Next

MsgBox "Windows compatibility could not be verified. Setup was stopped without changing the computer.", 16, "Eitaa Bridge Setup"
WScript.Quit 11

Option Explicit
Dim fso, root, pythonExe, command, wmi, startup, processId, result
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)

If fso.FileExists(root & "\.venv\Scripts\python.exe") Then
  pythonExe = root & "\.venv\Scripts\python.exe"
ElseIf fso.FileExists(root & "\python\python.exe") Then
  pythonExe = root & "\python\python.exe"
Else
  WScript.Quit 1
End If

command = """" & pythonExe & """ """ & root & "\scripts\background_server.py"" run"

Set wmi = GetObject("winmgmts:\\.\root\cimv2")
Set startup = wmi.Get("Win32_ProcessStartup").SpawnInstance_
startup.ShowWindow = 0

result = wmi.Get("Win32_Process").Create(command, root, startup, processId)
WScript.Quit result

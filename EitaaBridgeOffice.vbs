Option Explicit
Dim fso, shell, root, pythonExe, command, pythonPackages
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
root = fso.GetParentFolderName(WScript.ScriptFullName)

Function Quote(value)
  Quote = Chr(34) & value & Chr(34)
End Function

If fso.FileExists(root & "\python\pythonw.exe") Then
  pythonExe = root & "\python\pythonw.exe"
  pythonPackages = root & "\python-packages"
  shell.Environment("PROCESS")("PYTHONPATH") = pythonPackages
ElseIf fso.FileExists(root & "\python\python.exe") Then
  pythonExe = root & "\python\python.exe"
  pythonPackages = root & "\python-packages"
  shell.Environment("PROCESS")("PYTHONPATH") = pythonPackages
ElseIf fso.FileExists(root & "\.venv\Scripts\pythonw.exe") Then
  pythonExe = root & "\.venv\Scripts\pythonw.exe"
ElseIf fso.FileExists(root & "\.venv\Scripts\python.exe") Then
  pythonExe = root & "\.venv\Scripts\python.exe"
Else
  MsgBox "Eitaa Bridge runtime was not found. Run install_app.bat first.", 16, "Eitaa Bridge"
  WScript.Quit 1
End If

If Not fso.FileExists(root & "\scripts\office_runtime.py") Then
  MsgBox "The owned Office runtime controller is missing. Re-extract the complete package.", 16, "Eitaa Bridge"
  WScript.Quit 1
End If

shell.CurrentDirectory = root
command = Quote(pythonExe) & " " & Quote(root & "\scripts\office_runtime.py") & " launch --root " & Quote(root)
shell.Run command, 0, False

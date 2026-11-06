Unicode True
!include "MUI2.nsh"
!include "x64.nsh"
!include "WinVer.nsh"
!include "nsDialogs.nsh"
Var DeleteData
Var RemovePython
Var RemoveGit
Var RemoveNode
Var RemoveCode
Var RemoveTailscale
Var DataBox
Var PythonBox
Var GitBox
Var NodeBox
Var CodeBox
Var TailscaleBox
Var OptionsDialog
!ifndef PRODUCT_VERSION
  !define PRODUCT_VERSION "2.0.5"
!endif
!ifndef PRODUCT_VERSION_QUAD
  !define PRODUCT_VERSION_QUAD "2.0.5.1"
!endif
Name "Hermes"
Caption "Install Hermes ${PRODUCT_VERSION}"
BrandingText "Hermes · Anshul & Miheer"
OutFile "Hermes-setup-Windows-x64.exe"
InstallDir "$LOCALAPPDATA\Programs\Hermes"
RequestExecutionLevel user
SetCompressor /SOLID lzma
Icon "source/branding/hermes.ico"
UninstallIcon "source/branding/hermes.ico"
VIProductVersion "${PRODUCT_VERSION_QUAD}"
VIAddVersionKey "ProductName" "Hermes"
VIAddVersionKey "FileDescription" "Hermes Windows Installer"
VIAddVersionKey "CompanyName" "Anshul & Miheer"
VIAddVersionKey "LegalCopyright" "All rights reserved."
VIAddVersionKey "FileVersion" "${PRODUCT_VERSION}"
VIAddVersionKey "ProductVersion" "${PRODUCT_VERSION}"
!define MUI_ABORTWARNING
!define MUI_ICON "source/branding/hermes.ico"
!define MUI_UNICON "source/branding/hermes.ico"
!define MUI_WELCOMEPAGE_TITLE "Welcome to Hermes"
!define MUI_WELCOMEPAGE_TEXT "Install Hermes ${PRODUCT_VERSION}, the Highly Efficient Real-time Machine for Everyday Support.$\r$\n$\r$\nHermes uses cloud AI and authenticated local tools. Your provider keys and personal data are not included in this installer."
!define MUI_FINISHPAGE_RUN "Hermes"
!define MUI_FINISHPAGE_RUN_FUNCTION LaunchHermes
!define MUI_FINISHPAGE_RUN_TEXT "Open Hermes"
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "LICENSE"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
UninstPage custom un.CleanupOptions un.CleanupOptionsLeave
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Function LaunchHermes
  Exec '"$SYSDIR\wscript.exe" "$INSTDIR\launch.vbs"'
FunctionEnd

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "Hermes requires 64-bit Windows."
    Abort
  ${EndIf}
  ${IfNot} ${AtLeastWin10}
    MessageBox MB_ICONSTOP "Hermes requires Windows 10 or Windows 11."
    Abort
  ${EndIf}
FunctionEnd

Function un.onInit
  StrCpy $DeleteData 0
  StrCpy $RemovePython 0
  StrCpy $RemoveGit 0
  StrCpy $RemoveNode 0
  StrCpy $RemoveCode 0
  StrCpy $RemoveTailscale 0
FunctionEnd

Function un.CleanupOptions
  !insertmacro MUI_HEADER_TEXT "Choose what to remove" "Keep your data, or select additional cleanup."
  nsDialogs::Create 1018
  Pop $OptionsDialog
  ${If} $OptionsDialog == error
    Abort
  ${EndIf}
  ${NSD_CreateLabel} 0 0 100% 25u "Hermes and its private runtime will be removed. Personal data and shared software are kept unless selected below."
  Pop $0
  ${NSD_CreateCheckbox} 0 28u 100% 22u "Permanently delete Hermes chats, API keys, settings, caches and backups"
  Pop $DataBox
  ${NSD_CreateLabel} 0 55u 100% 27u "Optional: remove software installed by Hermes. Other apps may depend on it. Removing Tailscale disconnects remote access."
  Pop $0
  ${NSD_CreateCheckbox} 0 86u 48% 14u "Python 3.12"
  Pop $PythonBox
  IfFileExists "$INSTDIR\install-state\python.json" +2 0
    EnableWindow $PythonBox 0
  ${NSD_CreateCheckbox} 51% 86u 48% 14u "Git"
  Pop $GitBox
  IfFileExists "$INSTDIR\install-state\Git.Git.json" +2 0
    EnableWindow $GitBox 0
  ${NSD_CreateCheckbox} 0 105u 48% 14u "Node.js"
  Pop $NodeBox
  IfFileExists "$INSTDIR\install-state\OpenJS.NodeJS.LTS.json" +2 0
    EnableWindow $NodeBox 0
  ${NSD_CreateCheckbox} 51% 105u 48% 14u "Visual Studio Code"
  Pop $CodeBox
  IfFileExists "$INSTDIR\install-state\Microsoft.VisualStudioCode.json" +2 0
    EnableWindow $CodeBox 0
  ${NSD_CreateCheckbox} 0 124u 48% 14u "Tailscale"
  Pop $TailscaleBox
  IfFileExists "$INSTDIR\install-state\Tailscale.Tailscale.json" +2 0
    EnableWindow $TailscaleBox 0
  ${NSD_CreateLabel} 0 146u 100% 35u "Unavailable choices have no verified Hermes installation record. Updated dependencies are kept. Documents you created outside Hermes data are always kept."
  Pop $0
  nsDialogs::Show
FunctionEnd

Function un.CleanupOptionsLeave
  ${NSD_GetState} $DataBox $DeleteData
  ${NSD_GetState} $PythonBox $RemovePython
  ${NSD_GetState} $GitBox $RemoveGit
  ${NSD_GetState} $NodeBox $RemoveNode
  ${NSD_GetState} $CodeBox $RemoveCode
  ${NSD_GetState} $TailscaleBox $RemoveTailscale
  ${If} $DeleteData == 1
    MessageBox MB_YESNO|MB_ICONEXCLAMATION|MB_DEFBUTTON2 "Permanently delete your Hermes conversations, API keys, settings and backups? This cannot be undone." IDYES +2
      Abort
  ${EndIf}
FunctionEnd

Section "Hermes"
  SetOutPath "$INSTDIR"
  File "client\Hermes-user-Windows-x64.exe"
  ExecWait '"$INSTDIR\Hermes-user-Windows-x64.exe" /S' $0
  ${If} $0 != 0
    Abort "Hermes User installation failed. Close Hermes and retry."
  ${EndIf}
  File "bootstrap.ps1"
  File "launch.vbs"
  File "uninstall.ps1"
  File "README-WINDOWS.md"
  File "LICENSE"
  SetOutPath "$INSTDIR\source"
  File /r /x __pycache__ "source\*"
  SetOutPath "$INSTDIR\bootstrap"
  File "build-tools\python-3.12.10-amd64.exe"
  File "build-tools\pillow-13.0.0-cp312-cp312-win_amd64.whl"
  SetOutPath "$INSTDIR"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateShortcut "$SMPROGRAMS\Hermes Setup.lnk" "$SYSDIR\wscript.exe" '"$INSTDIR\launch.vbs"' "$INSTDIR\source\branding\hermes.ico"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Hermes" "DisplayName" "Hermes"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Hermes" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Hermes" "Publisher" "Anshul & Miheer"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Hermes" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Hermes" "QuietUninstallString" '"$INSTDIR\Uninstall.exe" /S'
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Hermes" "DisplayIcon" "$INSTDIR\source\branding\hermes.ico"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Hermes" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Hermes" "URLInfoAbout" "https://github.com/design-development-environment/hermes"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Hermes" "HelpLink" "mailto:anshul.pandhare@mitwpu.edu.in"
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Hermes" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Hermes" "NoRepair" 1
  DetailPrint "Hermes is installed. The graphical setup will open when this installer finishes."
SectionEnd

Section "Uninstall"
  nsExec::Exec '"$SYSDIR\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "$INSTDIR\uninstall.ps1" -DeleteData $DeleteData -RemovePython $RemovePython -RemoveGit $RemoveGit -RemoveNode $RemoveNode -RemoveCode $RemoveCode -RemoveTailscale $RemoveTailscale'
  Pop $0
  ${If} $0 != 0
    MessageBox MB_ICONEXCLAMATION "Uninstall did not finish. Nothing was reported as fully removed. See %LOCALAPPDATA%\Hermes-uninstall.log, then retry. You may need to uncheck a dependency or repair Hermes first."
    SetErrorLevel 1
    Abort
  ${EndIf}
  Delete "$SMSTARTUP\Hermes Background.lnk"
  Delete "$SMPROGRAMS\Hermes Setup.lnk"
  Delete "$INSTDIR\launch.vbs"
  Delete "$INSTDIR\bootstrap.ps1"
  Delete "$INSTDIR\uninstall.ps1"
  Delete "$INSTDIR\bootstrap.log"
  Delete "$INSTDIR\README-WINDOWS.md"
  Delete "$INSTDIR\LICENSE"
  Delete "$INSTDIR\Hermes-user-Windows-x64.exe"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\Hermes"
  MessageBox MB_OK "Hermes was removed using your cleanup choices. Dependencies without unchanged ownership records were kept. Details: %LOCALAPPDATA%\Hermes-uninstall.log"
SectionEnd

Unicode True
!include "MUI2.nsh"
!include "x64.nsh"
!include "WinVer.nsh"
!ifndef PRODUCT_VERSION
  !define PRODUCT_VERSION "2.0.6"
!endif
!ifndef PRODUCT_VERSION_QUAD
  !define PRODUCT_VERSION_QUAD "2.0.6.1"
!endif
Name "Hermes User"
Caption "Install Hermes User ${PRODUCT_VERSION}"
BrandingText "Hermes · Anshul & Miheer"
OutFile "Hermes-user-Windows-x64.exe"
InstallDir "$LOCALAPPDATA\Programs\Hermes User"
RequestExecutionLevel user
SetCompressor /SOLID lzma
Icon "..\source\branding\hermes.ico"
UninstallIcon "..\source\branding\hermes.ico"
VIProductVersion "${PRODUCT_VERSION_QUAD}"
VIAddVersionKey "ProductName" "Hermes User"
VIAddVersionKey "FileDescription" "Hermes User Installer"
VIAddVersionKey "CompanyName" "Anshul & Miheer"
VIAddVersionKey "LegalCopyright" "All rights reserved."
VIAddVersionKey "FileVersion" "${PRODUCT_VERSION}"
VIAddVersionKey "ProductVersion" "${PRODUCT_VERSION}"
!define MUI_ICON "..\source\branding\hermes.ico"
!define MUI_UNICON "..\source\branding\hermes.ico"
!define MUI_WELCOMEPAGE_TITLE "Welcome to Hermes User"
!define MUI_WELCOMEPAGE_TEXT "Connect securely to a Hermes Host on this computer or over Tailscale."
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "Hermes"
!define MUI_FINISHPAGE_RUN_FUNCTION LaunchHermes
!define MUI_FINISHPAGE_RUN_TEXT "Open Hermes"
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Function LaunchHermes
  Exec '"$INSTDIR\runtime\electron.exe" "$INSTDIR\app"'
FunctionEnd

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "Hermes User requires 64-bit Windows."
    Abort
  ${EndIf}
  ${IfNot} ${AtLeastWin10}
    MessageBox MB_ICONSTOP "Hermes User requires Windows 10 or Windows 11."
    Abort
  ${EndIf}
FunctionEnd

Section "Hermes User"
  SetOutPath "$INSTDIR\runtime"
  File /r "node_modules\electron\dist\*"
  SetOutPath "$INSTDIR\app"
  File /r "desktop\*"
  File "desktop-package.json"
  File /oname=hermes.ico "..\source\branding\hermes.ico"
  Rename "$INSTDIR\app\desktop-package.json" "$INSTDIR\app\package.json"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  CreateShortcut "$SMPROGRAMS\Hermes.lnk" "$INSTDIR\runtime\electron.exe" '"$INSTDIR\app"' "$INSTDIR\app\hermes.ico"
  CreateShortcut "$DESKTOP\Hermes.lnk" "$INSTDIR\runtime\electron.exe" '"$INSTDIR\app"' "$INSTDIR\app\hermes.ico"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\HermesUser" "DisplayName" "Hermes User"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\HermesUser" "DisplayVersion" "${PRODUCT_VERSION}"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\HermesUser" "Publisher" "Anshul & Miheer"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\HermesUser" "UninstallString" '"$INSTDIR\Uninstall.exe"'
SectionEnd

Section "Uninstall"
  Delete "$SMPROGRAMS\Hermes.lnk"
  Delete "$DESKTOP\Hermes.lnk"
  RMDir /r "$INSTDIR"
  IfFileExists "$INSTDIR\\runtime\\electron.exe" 0 +3
    SetErrorLevel 1
    Abort "Close Hermes User and retry uninstall."
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\HermesUser"
SectionEnd

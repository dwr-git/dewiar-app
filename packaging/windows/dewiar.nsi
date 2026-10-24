; Установщик Dewiar для Windows 10/11 (64-бит).
; Собирается tools/build_win.sh:  makensis -DVERSION=0.12.0 -DSTAGE=… -DOUT=… dewiar.nsi
;
; • Ставится в профиль пользователя (%LOCALAPPDATA%\Programs\Dewiar) — права администратора не нужны.
; • Полный (по умолчанию): внутри Python и все библиотеки, при установке ничего не скачивается.
; • Компактный (-DONLINE=1, меньше 30 МБ): внутри Python и программа, библиотеки скачиваются с PyPI при установке
;   по закреплённому списку requirements-win.lock; при переустановке уже скачанные сохраняются.
; • Настройки — %APPDATA%\Dewiar, модели и голоса — %LOCALAPPDATA%\Dewiar, заметки — «Документы\Dewiar».
; • Обновление из виджета: Dewiar-Setup-X.Y.Z.exe /S /UPDATE — тихо, с прежним выбором автозапуска и ярлыка,
;   в конце запускает новую версию сам.

Target amd64-unicode      ; 64-битный установщик (Dewiar и так только для 64-битной Windows)
ManifestDPIAware true
SetCompressor /SOLID lzma
SetCompressorDictSize 64
RequestExecutionLevel user

!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "FileFunc.nsh"
!include "Sections.nsh"

!ifndef VERSION
  !error "нужен -DVERSION=X.Y.Z"
!endif

Name "Dewiar"
OutFile "${OUT}"
InstallDir "$LOCALAPPDATA\Programs\Dewiar"
BrandingText "Dewiar ${VERSION}"
!ifdef ONLINE
ShowInstDetails show
!else
ShowInstDetails nevershow
!endif
ShowUninstDetails nevershow

VIProductVersion "${VERSION}.0"
VIAddVersionKey /LANG=1049 "ProductName" "Dewiar"
VIAddVersionKey /LANG=1049 "FileDescription" "Установщик Dewiar — голосового ассистента"
VIAddVersionKey /LANG=1049 "ProductVersion" "${VERSION}"
VIAddVersionKey /LANG=1049 "FileVersion" "${VERSION}"
VIAddVersionKey /LANG=1049 "CompanyName" "Dewiar"
VIAddVersionKey /LANG=1049 "LegalCopyright" "Dewiar"

!define PYW   "$INSTDIR\python\pythonw.exe"
!define APPPY "$INSTDIR\app\ui\app.py"
!define RUNKEY "Software\Microsoft\Windows\CurrentVersion\Run"
!define UNKEY  "Software\Microsoft\Windows\CurrentVersion\Uninstall\Dewiar"
; переустановка вручную — в ту же папку, что выбрали в прошлый раз (обновление из программы и так передаёт /D=)
InstallDirRegKey HKCU "${UNKEY}" "InstallLocation"
!define WV2    "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"

!define MUI_ICON "${STAGE}\dewiar.ico"
!define MUI_WELCOMEFINISHPAGE_BITMAP "${STAGE}\welcome.bmp"
!define MUI_HEADERIMAGE
!define MUI_HEADERIMAGE_RIGHT
!define MUI_HEADERIMAGE_BITMAP "${STAGE}\header.bmp"
!define MUI_UNICON "${STAGE}\dewiar.ico"
!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "Установка Dewiar ${VERSION}"
!ifdef ONLINE
!define MUI_WELCOMEPAGE_TEXT "Dewiar — голосовой ассистент с персонажами. Он слушает имя, отвечает голосом, открывает программы и сайты, ведёт заметки и помнит главное о вас.$\r$\n$\r$\nЭто компактный установщик: во время установки он скачает библиотеки (около 100 МБ) — нужен интернет, займёт 2–5 минут. Права администратора не нужны.$\r$\n$\r$\nПосле запуска подключите «мозг» — модель на вашем сервере или в интернете: мастер в студии проведёт по шагам."
!else
!define MUI_WELCOMEPAGE_TEXT "Dewiar — голосовой ассистент с персонажами. Он слушает имя, отвечает голосом, открывает программы и сайты, ведёт заметки и помнит главное о вас.$\r$\n$\r$\nУстановка займёт минуту и не требует прав администратора. После запуска подключите «мозг» — модель на вашем сервере или в интернете: мастер в студии проведёт по шагам."
!endif
!define MUI_COMPONENTSPAGE_NODESC
!define MUI_FINISHPAGE_RUN
!define MUI_FINISHPAGE_RUN_TEXT "Запустить Dewiar"
!define MUI_FINISHPAGE_RUN_FUNCTION LaunchApp

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_COMPONENTS
; выбор папки (24.10, совет пользователя: «чтоб был выбор диска куда ставить»); путь с русскими буквами — предупреждаем
!define MUI_DIRECTORYPAGE_TEXT_TOP "Куда установить Dewiar. Лучше папка, в пути к которой только латинские буквы и цифры — например, C:\Dewiar или D:\Dewiar: часть библиотек речи не открывает файлы по пути с русскими буквами."
!define MUI_PAGE_CUSTOMFUNCTION_LEAVE DirLeave
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Russian"

Var IsUpdate

; ---------- остановить запущенный Dewiar (только его pythonw/python, другие программы на Python не трогаем) ----------
!macro KILL_PIDFILE FILE
  ClearErrors
  FileOpen $1 "${FILE}" r
  ${IfNot} ${Errors}
    FileRead $1 $2
    FileClose $1
    ${If} $2 != ""
      ; номер мог остаться от прошлого сеанса и достаться другой программе (даже самому установщику) —
      ; поэтому завершаем, только если под этим номером сейчас python/pythonw. Без /T (дерева процессов): установщик
      ; запущен из окна Dewiar, он его потомок — /T убивал и сам установщик («нажимаю „Далее“ — и всё исчезает»,
      ; отчёты №126, №131 и комментарии 19–20.10). Остальные python Dewiar гасит stop_dewiar.py по папке.
      nsExec::Exec 'taskkill /F /IM pythonw.exe /FI "PID eq $2"'
      Pop $0
      nsExec::Exec 'taskkill /F /IM python.exe /FI "PID eq $2"'
      Pop $0
    ${EndIf}
  ${EndIf}
!macroend

!macro STOP_DEWIAR
  ; сначала по номерам процессов, которые записал сам Dewiar, затем — все его python по пути: своим же Python
  ; (ui/stop_dewiar.py). Раньше — PowerShell с -ExecutionPolicy Bypass: антивирусы (Kaspersky) видели в этом вирус
  !insertmacro KILL_PIDFILE "$LOCALAPPDATA\Dewiar\ui.pid"
  !insertmacro KILL_PIDFILE "$LOCALAPPDATA\Dewiar\core.pid"
  ${If} ${FileExists} "$INSTDIR\python\python.exe"
    InitPluginsDir                                ; сценарий — из самого установщика: у прежней версии его ещё нет
    File "/oname=$PLUGINSDIR\stop_dewiar.py" "${STAGE}\app\ui\stop_dewiar.py"
    nsExec::Exec '"$INSTDIR\python\python.exe" -X utf8 "$PLUGINSDIR\stop_dewiar.py" "$INSTDIR"'
    Pop $0
  ${EndIf}
  Sleep 700
!macroend


Function LaunchApp
  Exec '"${PYW}" -X utf8 "${APPPY}"'
FunctionEnd

!ifdef ONLINE
Function InstallLibs
  DetailPrint "Скачиваю библиотеки — около 100 МБ, 2–5 минут. Окно можно не трогать."
  retry:
  nsExec::ExecToLog '"$INSTDIR\python\python.exe" -X utf8 -m pip install --disable-pip-version-check --no-warn-script-location --no-cache-dir --progress-bar off --only-binary=:all: --find-links "$INSTDIR\app\wheels" -r "$INSTDIR\app\requirements-win.lock"'
  Pop $0
  ${If} $0 == "error"
    ; python.exe не запустился вовсе (19.10: «код error» — интернет тут ни при чём): обычно его убрал антивирус
    MessageBox MB_RETRYCANCEL|MB_ICONEXCLAMATION "Не запустился Python в папке Dewiar — скорее всего, антивирус убрал или блокирует его файлы (это ложная тревога).$\r$\n$\r$\nДобавьте папку в исключения антивируса и нажмите «Повторить»:$\r$\n$INSTDIR$\r$\n$\r$\nИли возьмите полный установщик — он ничего не скачивает: github.com/dwr-git/dewiar-app/releases/latest → Dewiar-Setup.exe" /SD IDCANCEL IDRETRY retry
    Abort "Python не запустился — установка не завершена."
  ${ElseIf} $0 != "0"
    MessageBox MB_RETRYCANCEL|MB_ICONEXCLAMATION "Не удалось скачать библиотеки Dewiar (код $0).$\r$\n$\r$\nПроверьте интернет и нажмите «Повторить». Не выходит (прокси, блокировки) — полный установщик ничего не скачивает: github.com/dwr-git/dewiar-app/releases/latest → Dewiar-Setup.exe" /SD IDCANCEL IDRETRY retry
    Abort "Библиотеки не скачались — установка не завершена."
  ${EndIf}
  DetailPrint "Библиотеки готовы."
FunctionEnd
!endif

; ---------- проверка после установки: файлы на месте и библиотеки грузятся (антивирус ничего не убрал) ----------
Function SelfCheck
  ${If} $IsUpdate == "1"
    Return                                        ; тихое обновление — проверит сторож при запуске
  ${EndIf}
  DetailPrint "Проверяю, что всё на месте…"
  StrCpy $0 "error"
  ${If} ${FileExists} "$INSTDIR\python\python.exe"
    StrCpy $R9 ""
    IfSilent 0 +2
      StrCpy $R9 " --quiet"                     ; тихая установка — без окон
    nsExec::ExecToLog '"$INSTDIR\python\python.exe" -X utf8 "$INSTDIR\app\ui\selfcheck.py"$R9'
    Pop $0
  ${EndIf}
  ${If} $0 == "0"
    DetailPrint "Проверка пройдена."
    Return
  ${EndIf}
  ${If} $0 == "2"
    Return                                        ; что делать, уже объяснила сама проверка (окном)
  ${EndIf}
  ; Python не запускается вовсе — скорее всего, его файлы убрал антивирус
  MessageBox MB_YESNO|MB_ICONEXCLAMATION "Похоже, антивирус не даёт запуститься файлам Dewiar (это ложная тревога).$\r$\n$\r$\nЕсли у вас Kaspersky, ESET, Dr.Web, Avast или другой антивирус — откройте его, найдите «Исключения» и добавьте туда папку:$\r$\n$INSTDIR$\r$\nЗатем запустите этот установщик ещё раз.$\r$\n$\r$\nЕсли антивирус — только Защитник Windows, нажмите «Да»: откроются его настройки, там «Исключения» → «Добавить исключение» → «Папка»." /SD IDNO IDNO selfcheck_done
  ; сами исключения не добавляем: скрытый PowerShell, добавляющий исключения Защитника — поведение вирусов (за это Kaspersky и убирал Dewiar)
  ExecShell "open" "windowsdefender://threatsettings"
  MessageBox MB_OK|MB_ICONINFORMATION "В открывшемся окне: «Исключения» → «Добавление или удаление исключений» → «Добавить исключение» → «Папка» → выберите:$\r$\n$INSTDIR$\r$\n$\r$\nПотом запустите установщик Dewiar ещё раз: он вернёт убранные файлы." /SD IDOK
  selfcheck_done:
FunctionEnd

Section "Dewiar" SecMain
  SectionIn RO
!ifdef ONLINE
  AddSize 420000                                  ; библиотеки, которые скачаются при установке (~420 МБ на диске)
!endif
  !insertmacro STOP_DEWIAR
  ; старые файлы программы убираем целиком (настройки, модели и заметки лежат в других папках)
!ifdef ONLINE
  RMDir /r "$INSTDIR\app"                         ; компактный: скачанные прошлой установкой библиотеки оставляем
!else
  RMDir /r "$INSTDIR\python"
  RMDir /r "$INSTDIR\app"
!endif
  SetOutPath "$INSTDIR"
  File /r "${STAGE}\python"
  File /r "${STAGE}\app"
  File "${STAGE}\dewiar.ico"
!ifdef ONLINE
  Call InstallLibs
!endif
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  Call SelfCheck

  ; меню «Пуск»
  CreateShortcut "$SMPROGRAMS\Dewiar.lnk" "${PYW}" '-X utf8 "${APPPY}"' "$INSTDIR\dewiar.ico" 0 SW_SHOWNORMAL "" "Голосовой ассистент"
  CreateShortcut "$SMPROGRAMS\Dewiar — студия.lnk" "${PYW}" '-X utf8 "${APPPY}" --settings' "$INSTDIR\dewiar.ico" 0 SW_SHOWNORMAL "" "Настройки Dewiar"
  CreateShortcut "$SMPROGRAMS\Dewiar — диагностика.lnk" "${PYW}" '-X utf8 "$INSTDIR\app\ui\doctor.py"' "$INSTDIR\dewiar.ico" 0 SW_SHOWNORMAL "" "Если Dewiar не запускается: отчёт на рабочий стол"

  ; ссылки dewiar:// и файлы .dewiar открываются в Dewiar
  WriteRegStr HKCU "Software\Classes\dewiar" "" "URL:Dewiar"
  WriteRegStr HKCU "Software\Classes\dewiar" "URL Protocol" ""
  WriteRegStr HKCU "Software\Classes\dewiar\DefaultIcon" "" "$INSTDIR\dewiar.ico"
  WriteRegStr HKCU "Software\Classes\dewiar\shell\open\command" "" '"${PYW}" -X utf8 "${APPPY}" "%1"'
  WriteRegStr HKCU "Software\Classes\.dewiar" "" "Dewiar.Settings"
  WriteRegStr HKCU "Software\Classes\Dewiar.Settings" "" "Настройки Dewiar"
  WriteRegStr HKCU "Software\Classes\Dewiar.Settings\DefaultIcon" "" "$INSTDIR\dewiar.ico"
  WriteRegStr HKCU "Software\Classes\Dewiar.Settings\shell\open\command" "" '"${PYW}" -X utf8 "${APPPY}" "%1"'

  ; «Приложения и возможности»
  WriteRegStr HKCU "${UNKEY}" "DisplayName" "Dewiar"
  WriteRegStr HKCU "${UNKEY}" "DisplayVersion" "${VERSION}"
  WriteRegStr HKCU "${UNKEY}" "Publisher" "Dewiar"
  WriteRegStr HKCU "${UNKEY}" "URLInfoAbout" "https://dewiar.pro"
  WriteRegStr HKCU "${UNKEY}" "DisplayIcon" "$INSTDIR\dewiar.ico"
  WriteRegStr HKCU "${UNKEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNKEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKCU "${UNKEY}" "QuietUninstallString" '"$INSTDIR\Uninstall.exe" /S'
  WriteRegDWORD HKCU "${UNKEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNKEY}" "NoRepair" 1
  ${GetSize} "$INSTDIR" "/S=0K" $0 $1 $2
  IntFmt $0 "0x%08X" $0
  WriteRegDWORD HKCU "${UNKEY}" "EstimatedSize" "$0"

  System::Call 'shell32::SHChangeNotify(i 0x08000000, i 0, p 0, p 0)'
SectionEnd

Section "Запускать вместе с Windows" SecAuto
  WriteRegStr HKCU "${RUNKEY}" "Dewiar" '"${PYW}" -X utf8 "${APPPY}" --autostart'
SectionEnd

Section "Ярлык на рабочем столе" SecDesk
  CreateShortcut "$DESKTOP\Dewiar.lnk" "${PYW}" '-X utf8 "${APPPY}"' "$INSTDIR\dewiar.ico" 0 SW_SHOWNORMAL "" "Голосовой ассистент"
SectionEnd

Section "-Завершение"
  ${IfNot} ${SectionIsSelected} ${SecAuto}
    DeleteRegValue HKCU "${RUNKEY}" "Dewiar"
  ${EndIf}
  ${IfNot} ${SectionIsSelected} ${SecDesk}
    Delete "$DESKTOP\Dewiar.lnk"
  ${EndIf}
  Delete "$LOCALAPPDATA\Dewiar\update.run"       ; метка «идёт установка» для сторожа обновления (ui/app.py relaunch_script)
  ${If} $IsUpdate == "1"
    Call LaunchApp                              ; обновили из виджета — запускаемся новой версией
  ${EndIf}
SectionEnd

; (после секций: здесь уже известны их номера)
; есть ли в пути буквы не из ASCII (кириллица в имени пользователя): преобразование в US-ASCII заменило символ -> $R9 = 1
!macro NONASCII PATH
  StrCpy $R9 0
  System::Call 'kernel32::WideCharToMultiByte(i 20127, i 0, w "${PATH}", i -1, p 0, i 0, p 0, *i 0 R9) i .R8'
!macroend

Function DirLeave
  !insertmacro NONASCII "$INSTDIR"
  ${If} $R9 <> 0
    MessageBox MB_YESNO|MB_ICONEXCLAMATION "В пути к папке есть русские буквы:$\r$\n$INSTDIR$\r$\n$\r$\nЧасть библиотек речи такие пути не открывает — голоса и слух могут не заработать. Лучше выбрать папку латиницей, например C:\Dewiar.$\r$\n$\r$\nВсё равно ставить сюда?" /SD IDYES IDYES +2
    Abort
  ${EndIf}
FunctionEnd

Function .onInit
  System::Call 'kernel32::CreateMutexW(p 0, i 0, w "DewiarSetup") p .r1 ?e'
  Pop $0
  ${If} $0 == 183
    MessageBox MB_OK|MB_ICONINFORMATION "Установщик Dewiar уже запущен." /SD IDOK
    Abort
  ${EndIf}
  ${GetParameters} $R0
  ClearErrors
  ${GetOptions} $R0 "/UPDATE" $R1
  ${If} ${Errors}
    StrCpy $IsUpdate "0"
  ${Else}
    StrCpy $IsUpdate "1"
  ${EndIf}
  ; новая установка, а папка по умолчанию — с русскими буквами (C:\Users\Иван\…): та же папка коротким именем 8.3
  ; (C:\Users\B03C~1\…), а если коротких имён на диске нет — C:\Dewiar. Обновление ставится туда, где стоит (/D=)
  ${If} $IsUpdate == "0"
  ${AndIfNot} ${FileExists} "$INSTDIR\app\ui\app.py"
    !insertmacro NONASCII "$INSTDIR"
    ${If} $R9 <> 0
      GetFullPathName /SHORT $R7 "$LOCALAPPDATA"
      !insertmacro NONASCII "$R7"
      ${If} $R7 != ""
      ${AndIf} $R9 == 0
        StrCpy $INSTDIR "$R7\Programs\Dewiar"
      ${Else}
        StrCpy $INSTDIR "C:\Dewiar"
      ${EndIf}
    ${EndIf}
  ${EndIf}
  ; обновление или переустановка — сохраняем прежний выбор автозапуска и ярлыка на рабочем столе
  ${If} ${FileExists} "$INSTDIR\app\ui\app.py"
    ReadRegStr $R2 HKCU "${RUNKEY}" "Dewiar"
    ${If} $R2 == ""
      !insertmacro UnselectSection ${SecAuto}
    ${EndIf}
    ${IfNot} ${FileExists} "$DESKTOP\Dewiar.lnk"
      !insertmacro UnselectSection ${SecDesk}
    ${EndIf}
  ${EndIf}
FunctionEnd

; установка не удалась — метку сторожа убираем: пусть он вернёт прежнюю версию, а не ждёт 10 минут
Function .onInstFailed
  Delete "$LOCALAPPDATA\Dewiar\update.run"
FunctionEnd

; ---------- WebView2 (окно виджета и студии). В Windows 11 есть всегда, в Windows 10 — почти всегда ----------
Function .onInstSuccess
  ${If} $IsUpdate == "1"
    Return
  ${EndIf}
  SetRegView 32                                 ; WebView2 записан в 32-битной ветке (WOW6432Node)
  ReadRegStr $0 HKLM "SOFTWARE\Microsoft\EdgeUpdate\Clients\${WV2}" "pv"
  ${If} $0 == ""
  ${OrIf} $0 == "0.0.0.0"
    ReadRegStr $0 HKCU "Software\Microsoft\EdgeUpdate\Clients\${WV2}" "pv"
  ${EndIf}
  SetRegView 64
  ${If} $0 == ""
  ${OrIf} $0 == "0.0.0.0"
    MessageBox MB_YESNO|MB_ICONINFORMATION "Для окна виджета нужен компонент Microsoft Edge WebView2 — на этом компьютере его нет.$\r$\n$\r$\nАссистент будет работать и без него (настройки откроются в браузере), но лучше установить. Открыть страницу загрузки Microsoft?" /SD IDNO IDNO +2
      ExecShell "open" "https://go.microsoft.com/fwlink/p/?LinkId=2124703"
  ${EndIf}
FunctionEnd

; ---------- удаление ----------
Section "Uninstall"
  !insertmacro STOP_DEWIAR
  Delete "$SMPROGRAMS\Dewiar.lnk"
  Delete "$SMPROGRAMS\Dewiar — студия.lnk"
  Delete "$SMPROGRAMS\Dewiar — диагностика.lnk"
  Delete "$DESKTOP\Dewiar.lnk"
  DeleteRegValue HKCU "${RUNKEY}" "Dewiar"
  DeleteRegKey HKCU "Software\Classes\dewiar"
  DeleteRegKey HKCU "Software\Classes\.dewiar"
  DeleteRegKey HKCU "Software\Classes\Dewiar.Settings"
  DeleteRegKey HKCU "${UNKEY}"
  RMDir /r "$INSTDIR\python"
  RMDir /r "$INSTDIR\app"
  Delete "$INSTDIR\dewiar.ico"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  MessageBox MB_YESNO|MB_ICONQUESTION "Удалить также настройки, вход в аккаунт и скачанные модели и голоса (около 0,5 ГБ)?$\r$\n$\r$\nПапка «Документы\Dewiar» с заметками и памятью ассистента останется в любом случае." /SD IDNO IDNO +3
    RMDir /r "$APPDATA\Dewiar"
    RMDir /r "$LOCALAPPDATA\Dewiar"
  System::Call 'shell32::SHChangeNotify(i 0x08000000, i 0, p 0, p 0)'
SectionEnd

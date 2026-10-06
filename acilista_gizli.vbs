' acilista_calistir.bat dosyasini pencere acmadan calistirir (Gorev Zamanlayicisi ve Baslangic klasoru icin).
' Ciktilar yine veri\gunluk.log dosyasina yazilir.
Dim klasor
klasor = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
CreateObject("WScript.Shell").Run """" & klasor & "\acilista_calistir.bat"""", 0, True

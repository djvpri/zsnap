@echo off
echo ========================================
echo  ZOMET AI - Build EXE
echo ========================================
echo.

:: Install dependensi yang dibutuhkan
echo Memastikan dependensi terinstall...
py -m pip install pyinstaller pyqt6 requests mss pillow --quiet

:: Generate icon
echo Membuat icon...
py create_icon.py

:: Bersihkan folder build lama
if exist "dist\ZOMET.exe" (
    echo Menghapus build lama...
    del /f "dist\ZOMET.exe"
)
if exist "build" rmdir /s /q "build"

:: Build EXE
echo.
echo Membangun ZOMET.exe...
echo.
py -m PyInstaller zomet.spec --clean

echo.
if exist "dist\ZOMET.exe" (
    echo ========================================
    echo  BERHASIL! File ada di: dist\ZOMET.exe
    echo ========================================
    explorer dist
) else (
    echo ========================================
    echo  GAGAL. Cek error di atas.
    echo ========================================
)

pause

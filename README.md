py -m PyInstaller --noconfirm --clean --windowed --name "WaferMapViewer" --icon "app_icon.ico" --collect-all PySide6 --hidden-import openpyxl --hidden-import lxml mapping_tool.py

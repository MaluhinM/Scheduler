## Сборка EXE с помощью Nuitka

```bash
pip install nuitka
nuitka --standalone --windows-console-mode=disable --enable-plugin=tk-inter --windows-icon-from-ico=.\Scheduler.ico .\Scheduler.py
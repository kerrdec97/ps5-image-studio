# Windows Test & Build Package

Everything here runs from the repo root (`PS5ImageStudio\`).

## Scripts

| File | What it does |
|---|---|
| `run_demo.bat` | Launches **demo mode** (no real files). Window stays open on exit/crash. |
| `run_real.bat` | Launches the real app. Window stays open on exit/crash. |
| `build_exe.bat` | Installs build deps + runs PyInstaller → `dist\PS5ImageStudio\PS5ImageStudio.exe`. |
| `requirements-build.txt` | Build deps (customtkinter, pyinstaller, cryptography). |
| `PS5ImageStudio.spec` | PyInstaller spec (onedir, console, CTk assets + hidden imports). |

All `.bat` files end with `pause`, so the console **never disappears** on error.

## Run from source (fastest iteration)

```bat
python -m pip install -r requirements-studio.txt
run_demo.bat
```

## Build the .exe

```bat
build_exe.bat
```
Then:
```bat
dist\PS5ImageStudio\PS5ImageStudio.exe --demo
dist\PS5ImageStudio\PS5ImageStudio.exe
```

> I could not compile the `.exe` in my authoring environment (no Windows /
> PyInstaller there). `build_exe.bat` + the spec produce it on your machine.
> The frozen-mode pitfalls are already handled: `multiprocessing.freeze_support()`
> is called at startup, and the build subprocess re-execs the exe via
> `--job-runner` instead of `python -m`.

## Logs (always written)

- `logs\studio.log` — INFO + any swallowed exceptions (page build/refresh).
- `logs\crash.log` — full traceback if the app dies.

## About the sidebar / Settings issue you saw

I have **not** changed the UI yet (as requested). I added logging around page
build and refresh, so the next run will record the real cause. Please:

1. `run_demo.bat`
2. Click the sidebar items + open Settings
3. Send me `logs\studio.log` (and `logs\crash.log` if present)

That will tell me exactly which control/layout call is failing so I can fix it
precisely rather than guessing.

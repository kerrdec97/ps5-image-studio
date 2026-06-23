# 🚀 PS5 Image Studio

> A modern workstation for building, compressing, managing and reviewing PS5 game images.

Built on top of **Nazky's LazyMkPFS backend**, PS5 Image Studio provides a modern GUI for creating **exFAT** and **FFPFSC** images, managing build queues, monitoring progress, reviewing build history and much more.

---

## 📦 Platform Support

| Platform   | Status                             |
| ---------- | ---------------------------------- |
| 🪟 Windows | ✅ Fully Supported                  |
| 🐧 Linux   | ⚠️ Experimental / Community Tested |
| 🍎 macOS   | ❌ Not Currently Supported          |

---

## ✨ Features

### 🏗️ Build Wizard

* Build PS5 dump folders into:
  * 📁 `.exfat`
  * 📦 `.ffpfsc`
* Multi-build queue support
* Smart naming presets
* Space preflight checks
* Review & Start workflow

### 📊 Active Build Monitor

* Live build progress
* Build phases
* Speed & ETA
* Compression gain
* Scan activity detection
* Automatic queue processing

### 📚 History

* Full build history
* Rebuild previous jobs
* Saved build logs
* Space saved statistics
* Success / failure tracking

### 📋 Queue Management

* Queue multiple builds
* Reorder jobs
* Pause / resume processing
* Queue statistics
* Post-queue actions

### 🖼️ Image Tools

* Read-only exFAT image browsing
* Metadata inspection
* Future editing support

### ⚙️ Workstation UI

* Overview dashboard
* Build health monitoring
* Storage usage indicators
* Recommended settings
* Debug information export

---

## 📥 Download

Grab the latest release from GitHub Releases.

### 🪟 Windows

Download:

```text
PS5ImageStudio-Windows.zip
```

Extract and run:

```text
PS5ImageStudio.exe
```

Administrator rights are required during image creation.

---

### 🐧 Linux (Experimental)

Install dependencies:

```bash
sudo apt install python3-tk exfatprogs
```

Extract:

```bash
tar -xzf PS5ImageStudio-Linux-Experimental.tar.gz
cd PS5ImageStudio
./PS5ImageStudio
```

⚠️ Linux support is experimental.
Please report:

* Distribution
* Version
* Kernel
* Python version
* Build log

---

## ⚠️ Requirements & First Launch

### 🪟 Windows

Nothing extra needs to be installed.
The application includes:

* Python runtime
* CustomTkinter
* Required Python libraries
* OSFMount integration

**First launch**

PS5 Image Studio requires administrator rights when creating exFAT images.

Windows may show a SmartScreen warning because the application is not code-signed.
If you see:

> Windows protected your PC

Click:

> More info → Run anyway

This is expected for community-developed tools.

### 🐧 Linux (Experimental)

Install required packages:

```bash
sudo apt install python3-tk exfatprogs
```

PS5 Image Studio uses:

* `mkfs.exfat`
* `losetup`
* `mount`
* `umount`

These require elevated privileges.
The application will prompt for `sudo` when required.

**Recommended**

Run the application from a terminal so any Linux system messages are visible.
Example:

```bash
./PS5ImageStudio
```

**Current Linux limitations**

* Edit Image mode is currently Windows-only
* Linux support is experimental and community-tested

Please include:

* Distribution
* Version
* Kernel
* Python version
* Build log

when reporting Linux issues.

---

## 📸 Screenshots

### 🏠 Home

*(add screenshot)*

### 🏗️ Build Wizard

*(add screenshot)*

### 📊 Active Build

*(add screenshot)*

### 📚 History

*(add screenshot)*

### ⚙️ Settings

*(add screenshot)*

---

## 🙏 Credits

### ❤️ LazyMkPFS Backend

Huge thank you to **Nazky** for the incredible LazyMkPFS backend which powers the core build, packing and verification engine behind PS5 Image Studio.

Support Nazky:
🔗 https://github.com/Nazky

---

### ❤️ PS5 Image Studio

Created and maintained by:
🔗 https://github.com/kerrdec97

If you'd like to support development:
☕ https://ko-fi.com/deckerr9746220

Any support is massively appreciated and helps keep development moving forward.

---

## 🐞 Reporting Issues

Before reporting:

1. Open **Settings → Copy Debug Info**
2. Save the build log
3. Include:
   * Platform
   * Version
   * Steps to reproduce
   * Build log
   * Debug info

---

## ⚠️ Disclaimer

This project is intended for PS5 homebrew and educational purposes.
Use at your own risk.

---

## 📄 License

MIT License
© 2026 kerrdec97 & Nazky

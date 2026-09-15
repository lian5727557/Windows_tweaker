# System Tweaker v5.0 🐾

[![中文](https://img.shields.io/badge/中文-简体-red)](#中文) | [![English](https://img.shields.io/badge/English-read-blue)](#english)

**面向师生的一站式 Windows 11 系统调教工具**
*An all-in-one Windows 11 tweaking tool for teachers & students*

---

<a name="中文"></a>

## 🇨🇳 中文

### 简介

System Tweaker v5.0 是一款基于 Python + Tkinter 的 Windows 11 系统调教工具。它将底层的注册表操作、服务管理、驱动控制封装为一键开关，同时提供了完整的双语 GUI 界面。项目的另一个身份是 **Python 教学练习包**——`exercise/` 目录中包含 8 个任务的 TODO 学生版和完整参考答案，涵盖了 `ctypes`、`subprocess`、`reg.exe`、`sc.exe`、`netsh`、`tkinter`、`threading` 等核心模块的使用。

### 七大模块

| 模块 | 禁用 (DISABLE) | 启用 (ENABLE) |
|------|---------------|--------------|
| **Windows 更新** | 一键恢复更新（还原原始值 + 复位服务/任务） | 暂停 10 年（完整暂停状态 + 每 30 天自动续期） |
| **安全中心** | 四层防线彻底禁用 Defender | 一键完整恢复 |
| **Win11 右键菜单** | 切回 Win10 经典完整菜单 | 恢复 Win11 简洁菜单 |
| **防火墙** | 关闭三配置文件 | 打开三配置文件（netsh 即时生效） |
| **KafuuBoost 性能方案** | 切回平衡并删除我们的方案（零残留） | 复刻官方卓越性能 + 9 项增强（性能↑ 功耗/温度↑） |
| **程序主题** | 暗色（Catppuccin Mocha） | 亮色（Catppuccin Latte） |
| **二次元友好模式** | 隐藏壁纸 | 显示全窗口壁纸（暗色/亮色自动换图） |

### Windows 更新模块：2026 新版机制（v5.0 重写）

旧版只写一条 `FlightSettingsMaxPauseDays`。那条值**只是把设置页里的"最大暂停天数"调大，
本身不产生任何暂停状态** —— 注册表看着改了，Windows 该更还是更。

2026 年微软改了两件事：

- **2026-04**：设置页的"暂停更新"从 1~5 周下拉菜单改成日历选择器（Pick a date）。
- **2026-07**：`KB5101650 / KB5101649` 推送后，单次暂停上限仍是 **35 天**，但可以无限次续期；
  同时官方文档把 `DeferFeatureUpdates` 一类延迟策略标注为
  *"legacy policy, isn't applicable for Windows 11"*。

所以新版引擎 `win_update_pause.py` 改成**三层写入 + 自动续期**：

| 层 | 注册表位置 | 作用 |
|----|-----------|------|
| A | `...\WindowsUpdate\UX\Settings` | 6 个暂停时间戳（真正生效的地方） |
| B | `...\WindowsUpdate\UpdatePolicy\Settings` | 暂停状态 `PausedFeatureStatus` / `PausedQualityStatus` |
| C | `...\Policies\Microsoft\Windows\WindowsUpdate` | 版本钉住 `TargetReleaseVersion` + 排除驱动更新 |

再挂一个 **每 30 天自动续期** 的计划任务（SYSTEM 权限）重写时间戳 ——
因为设置页 UI 和 `WaaSMedicSvc` 都可能把结束日期改回 35 天，硬关服务不如定期续期稳。

```powershell
python win_update_pause.py status                 # 体检：现在到底停没停
python win_update_pause.py apply --days 3650      # 暂停 10 年（含自动续期）
python win_update_pause.py apply --mode feature_only --days 365   # 只挡大版本，安全补丁照常
python win_update_pause.py apply --deep           # 追加：停服务 + 禁更新任务
python win_update_pause.py revert                 # 一键恢复
python win_update_pause.py hide KB5101650         # 单独隐藏某个补丁（wushowhide 同款做法）
```

### 安全中心：四层防线详解

Win11 24H2 中微软大幅强化了 Defender 的自保护机制，传统的 `DisableAntiSpyware` 注册表键已被废除。本工具参考了 TairikuOokami/defender-remover 等开源方案，采用四层策略：

1. **注册表策略层** — `DisableAntiVirus` + `DisableRealtimeMonitoring` + 云防护/通知关闭
2. **服务层** — 停止所有 Defender 相关服务并设 `Start=4`（禁止启动）
3. **驱动层** — `WdBoot` / `WdFilter` / `WdNisDrv` 驱动级禁用
4. **计划任务层** — 禁用缓存维护/清理/扫描/验证四个定时任务

恢复时完整清理策略键、恢复服务为自动启动、恢复驱动默认值、启用计划任务并刷新组策略。

### 功能亮点

- 🔄 **中英双语切换** — 底部两个按钮，所有 UI 文字即时切换
- 🎨 **Catppuccin 主题** — 暗色 Mocha + 亮色 Latte，卡片式布局
- 🖼️ **二次元壁纸** — 全窗口 cover 铺满，窗口拉伸时自适缩放
- 📦 **PyInstaller 打包** — 单文件 exe，壁纸和图标全部内嵌，双击即用
- 📚 **教学练习包** — `exercise/` 含 8 个 TODO 任务 + 参考答案

### 快速开始

```powershell
# 方式一：源码运行
pip install Pillow
python tweaker.py          # 以管理员身份

# 方式二：打包运行
# 下载 dist_release/tweaker.zip → 解压 → 双击 tweaker.exe
```

### 打包命令

```powershell
python -m PyInstaller --onefile --noconsole --clean --name tweaker ^
  --icon "photo\chino.ico" ^
  --add-data "photo\huajia.jpg;photo" ^
  --add-data "photo\heihua.png;photo" ^
  --add-data "photo\chino.ico;photo" ^
  --add-data "photo\chino.png;photo" ^
  tweaker.py
# 输出：dist\tweaker.exe（约 22 MB，图片已内嵌，分发只需这一个文件）
```

也可以直接双击 `build.bat`。想要目录版把 `--onefile` 换成 `--onedir` 即可 ——
资源查找两种模式都兼容（同目录 → 同目录/photo → 打包内部 _MEIPASS/photo）。

### 项目结构

```
├── tweaker.py              # 主程序
├── win_update_pause.py     # 更新暂停引擎（25H2/26H1 新版机制）
├── win_power_plan.py       # 卓越性能电源方案引擎（复制官方方案·零残留）
├── exercise/               # 教学练习包
│   ├── tweaker_student.py  # 学生版 — 8 个 TODO 留空
│   ├── tweaker_answer.py   # 参考答案 — 完整可运行
│   └── README.md           # 练习说明
├── huajia.jpg              # 亮色壁纸
├── heihua.png              # 暗色壁纸
├── chino.ico               # 窗口图标
├── README.md               # 本文件
└── 打包命令.txt
```

### 注意事项

- ⚠️ 需要**管理员权限**运行
- ⚠️ 部分修改需重启后完全生效
- ⚠️ 禁用安全中心后系统将不再受 Defender 保护，建议仅在对操作后果有充分了解时使用

### 许可证与素材

- **代码**：MIT 许可，见 [LICENSE](LICENSE)
- **美术素材不在 MIT 覆盖范围内** —— `photo/` 下的角色图与图标、课件 docx 里的插图，
  版权归各自作者所有，**仅作个人演示使用**；二次分发前请先替换或删除（详见 LICENSE 的例外条款）

### 发布与校验

本工具会修改系统设置（更新策略 / 安全中心 / 电源方案等），**请只在自己的机器上使用**。

- ⚠️ PyInstaller 单文件 exe 常被杀软误报，这是打包方式的通病，不是病毒特征
- ✅ 校验你拿到的 exe 与源码构建是否一致：

```powershell
Get-FileHash .\tweaker.exe -Algorithm SHA256
# 本仓库的示例构建（重新打包后哈希会变）：
# 47344A27DBEAFDE17D87657411578228CF51BD3C140E294530407E71ABCA3748
```

- 🛠 自己构建：双击 `build.bat`（需 Python 3.12+ 与 `pip install pyinstaller pillow`）

---

<a name="english"></a>

## 🇬🇧 English

### Overview

System Tweaker v5.0 is a Windows 11 system tweaking tool built with Python + Tkinter. It wraps low-level operations — registry manipulation, service management, driver control — into simple one-click toggles with a fully bilingual GUI. It also doubles as a **Python teaching exercise pack**; the `exercise/` directory contains 8 scaffolded TODO tasks for students plus a complete answer key.

### Seven Modules

| Module | DISABLE | ENABLE |
|--------|---------|--------|
| **Windows Update** | Restore updates (original values + services/tasks reset) | Pause for 10 years (full pause state + 30-day auto-renew) |
| **Security Center** | 4-layer defense disables Defender entirely | One-click full restore |
| **Win11 Context Menu** | Switch to classic Win10 full menu | Restore Win11 compact menu |
| **Firewall** | Turn off all 3 profiles | Turn on all 3 profiles (netsh instant) |
| **KafuuBoost Power Plan** | Back to Balanced and delete our copy (zero residue) | Official Ultimate Performance + 9 tweaks (performance ↑, power/heat ↑) |
| **App Theme** | Dark (Catppuccin Mocha) | Light (Catppuccin Latte) |
| **Anime Mode** | Hide wallpaper | Show full-window wallpaper |

### Windows Update module: what changed in 2026 (rewritten in v5.0)

The old build wrote a single `FlightSettingsMaxPauseDays` value. That only raises the maximum
shown in Settings — **it creates no pause state at all**, so Windows kept updating anyway.

- **2026-04**: the pause dropdown became a calendar picker ("Pick a date").
- **2026-07**: after `KB5101650 / KB5101649`, a single pause is still capped at **35 days**
  but can be renewed indefinitely; Microsoft's docs now mark the `DeferFeatureUpdates`
  policies as *"legacy policy, isn't applicable for Windows 11"*.

`win_update_pause.py` therefore writes three layers (pause timestamps → pause status →
version pin / driver exclusion) and installs a **30-day auto-renew task**, because both the
Settings UI and `WaaSMedicSvc` can reset a long pause back to 35 days.

```powershell
python win_update_pause.py status
python win_update_pause.py apply --days 3650
python win_update_pause.py apply --mode feature_only
python win_update_pause.py revert
```

### Security Center: 4-Layer Detail

Microsoft significantly hardened Defender's self-protection in Win11 24H2 — the traditional `DisableAntiSpyware` registry key is now defunct. This tool draws on community solutions (TairikuOokami/defender-remover) to apply a 4-layer strategy:

1. **Registry Policy** — `DisableAntiVirus` + `DisableRealtimeMonitoring` + cloud protection & notification blocks
2. **Service Layer** — Stop all Defender services and set `Start=4` (prevent startup)
3. **Driver Layer** — Disable `WdBoot` / `WdFilter` / `WdNisDrv` at the kernel level
4. **Scheduled Tasks** — Disable cache maintenance, cleanup, scan, and verification tasks

Restoration fully cleans policy trees, resets services to auto, restores driver defaults, re-enables tasks, and refreshes group policy.

### Highlights

- 🔄 **Bilingual UI** — Chinese ↔ English toggle with instant text switching
- 🎨 **Catppuccin Themes** — Dark Mocha + Light Latte with card-based layout
- 🖼️ **Anime Wallpaper** — Full-window cover-fit with live resize adaption
- 📦 **PyInstaller Ready** — single exe with wallpapers + icon embedded, double-click to run
- 📚 **Exercise Pack** — 8 TODO tasks + answer key in `exercise/`

### Quick Start

```powershell
# Option 1: Run from source
pip install Pillow
python tweaker.py          # Run as Administrator

# Option 2: Run pre-built
# Download dist_release/tweaker.zip → extract → double-click tweaker.exe
```

### Build

```powershell
python -m PyInstaller --onefile --noconsole --clean --name tweaker ^
  --icon "photo\chino.ico" ^
  --add-data "photo\huajia.jpg;photo" ^
  --add-data "photo\heihua.png;photo" ^
  --add-data "photo\chino.ico;photo" ^
  --add-data "photo\chino.png;photo" ^
  tweaker.py
# Output: dist\tweaker.exe (~22 MB, assets embedded — ship this single file)
```

Or just double-click `build.bat`. Swap `--onefile` for `--onedir` if you prefer a folder
build — the resource lookup handles both.

### Project Structure

```
├── tweaker.py              # Main program
├── win_update_pause.py     # Update-pause engine (25H2/26H1 mechanism)
├── win_power_plan.py       # Ultimate Performance plan engine (copy official, zero residue)
├── exercise/               # Student exercise pack
│   ├── tweaker_student.py  # Student version — 8 TODO tasks
│   ├── tweaker_answer.py   # Answer key — full runnable
│   └── README.md           # Exercise guide
├── huajia.jpg              # Light wallpaper
├── heihua.png              # Dark wallpaper
├── chino.ico               # App icon
├── README.md               # This file
└── 打包命令.txt             # Build notes (Chinese)
```

### Notes

- ⚠️ **Administrator privileges** required
- ⚠️ Some changes take effect after a system restart
- ⚠️ Disabling the Security Center removes Defender protection — use with understanding

### License & Assets

- **Code**: MIT — see [LICENSE](LICENSE)
- **Artwork is NOT covered by MIT** — the character images and icon under `photo/`, plus the
  illustrations inside the course `.docx`, belong to their respective authors and are included
  for **personal demonstration only**. Replace or remove them before redistributing.

### Release & Verify

This tool changes system settings (update policy, security center, power plan…).
**Use it on your own machine only.**

- ⚠️ PyInstaller one-file executables are frequently flagged by antivirus engines — that's a
  packaging artifact, not a virus signature.
- ✅ Verify the exe you downloaded was built from this source:

```powershell
Get-FileHash .\tweaker.exe -Algorithm SHA256
# example build from this repo (changes when you rebuild):
# 47344A27DBEAFDE17D87657411578228CF51BD3C140E294530407E71ABCA3748
```

- 🛠 Build it yourself: double-click `build.bat` (needs Python 3.12+ and
  `pip install pyinstaller pillow`)

---

### Star History 💫

If you find this useful, consider giving it a ⭐ on GitHub!

---

[⬆ 回到顶部 / Back to top](#system-tweaker-v42-)

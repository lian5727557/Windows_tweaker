# System Tweaker v5.0 · KafuuBoost ⚡

> **更新机制重写 · 自研电源方案 · 界面重做 · 单文件分发**
>
> v4.2 的更新模块在新版 Windows 上已经失效（只写了一条"上限"，根本不产生暂停状态）；
> v5.0 把它整个重写，并顺手做出了属于自己的性能方案。

---

## 🆚 v4.2 → v5.0 对比

| | v4.2 | v5.0 |
|---|---|---|
| **模块数** | 6 | **7**（新增 KafuuBoost 电源方案）|
| **Windows 更新** | 只写 `FlightSettingsMaxPauseDays` 一条<br>实测：**看着改了，其实一条都没暂停** | 三层写入：暂停时间戳 + 暂停状态 + 策略层<br>再挂每 30 天自动续期任务兜底 |
| **电源方案** | 无 | **KafuuBoost**：复刻官方卓越性能 + 9 项增强<br>固定 GUID、用完即删、零残留 |
| **界面** | 深色底板横跨整个窗口，壁纸被挡掉一半 | 底板只包文字、按钮浮在壁纸上，壁纸看得见了 |
| **隐藏 bug** | 3 个（见下）| 全部修复 |
| **打包** | 文档里的命令引用根目录图片，**实际跑不通** | `build.bat` 一键出单文件 exe（22.9 MB，素材与图标全部内嵌）|
| **许可** | 无 | MIT（代码）+ 素材例外声明 + `.gitignore` |

---

## 🔥 Windows 更新模块：整个重写

**为什么旧的写法会失效？**

- **2026-04**：微软把"暂停更新"从 1~5 周下拉菜单改成了**日历选择器**
- **2026-07**：`KB5101650 / KB5101649` 推送后，单次暂停上限仍是 35 天，但改成**可以无限次续期**；
  同时官方文档把 `DeferFeatureUpdatesPeriodInDays` 一类延迟策略标注为
  *"legacy policy, isn't applicable for Windows 11"*
- 关键点：**暂停状态存在两处注册表**（`UX\Settings` 的时间戳 + `UpdatePolicy\Settings` 的状态值），
  只写"上限"等于什么都没做 —— 实测：`PauseUpdatesExpiryTime` 为空、`PausedFeatureStatus = 0`

**v5.0 的做法**

```
A 层  UX\Settings              6 个暂停时间戳（真正生效的地方）
B 层  UpdatePolicy\Settings    暂停状态 + 暂停日期
C 层  Policies\WindowsUpdate   版本钉住 TargetReleaseVersion + 排除驱动更新
D 层  计划任务                 每 30 天自动重写一次，防止被设置页/Medic 改回 35 天
```

- 支持 **只挡大版本**（`feature_only`，安全补丁照常装）
- 支持把指定补丁**藏起来**（`hide KB...`，wushowhide 同款做法）
- 写入前自动**快照**，`revert` 精确还原到操作前状态
- 命令行：`status` / `apply` / `revert` / `renew`

---

## ⚡ 新增：KafuuBoost 电源方案

**实测发现（这条挺有意思）**：新版 Windows 里那个"官方卓越性能"，在本机**只定义了一项** ——
`硬盘永不关闭`。社区传说的"最低处理器状态 100%、不关核、散热主动"**并不在方案里**，
它实际只是"高性能 + 硬盘不关"，几乎没有性能收益。

**KafuuBoost 就是来补这一刀的**：复刻官方方案后，再写入 9 项增强 ——

| 项目 | 值 | 效果 |
|---|---|---|
| 最低处理器状态 | 100%（交流电）| **不降频** |
| 核心停放最小核心 | 100% | 不关核心 |
| 系统散热策略 | 主动 | 先加风扇再降频 |
| 性能提升模式 | 激进 | Boost 更积极 |
| 硬盘关闭超时 | 0 | 永不关闭 |
| 睡眠 / 显示器 | 0 / 0 | 从不 |
| PCIe 链接状态电源管理 | 关闭 | 不省电 |
| USB 选择性暂停 | 禁用 | 不挂起 |

- **零残留**：方案用固定 GUID 创建，`DISABLE` = 切回平衡 + 删掉自己那份，系统自带方案一根汗毛都不碰
- **电池友好**：默认只写交流电侧，笔记本不会被榨干（要拉满可加 `--tune-dc`）
- **代价已写在方案描述里**：性能 ↑ 功耗与温度 ↑（桌面机大约多 10–25W 待机功耗）

---

## 🎨 界面重做 + 3 个隐藏 bug 修复

**外观**

- 深色底板收窄成"只包住标题和说明"，不再横跨整窗 —— 壁纸露出面积大幅提升
- 按钮改成浮动在壁纸之上，身后不再有打底色块
- 窗口缩放 / 切换语言时按钮自动重排

**修复的 bug（都是"平时能用、关键时刻失灵"的类型）**

1. 主题与壁纸按钮走后台线程 + 全局锁 → 点完主题立刻点壁纸会**被静默丢弃**
2. 后台线程里调 `root.after()` 更新状态栏 → 依赖 Tk 忙等机制，主线程不在主循环时直接抛异常
3. `unbind("<Configure>")` 会**连带删掉其它组件的同事件绑定** → 改为只绑一次、统一分发

---

## 📦 打包与分发

- **单文件 exe**（22.9 MB）：壁纸、图标全部内嵌，拷走一个文件就能用
- `build.bat` 一键重打包；文档里的命令已修正为实际可跑的版本
- **免打包换壁纸**：把 `heihua.png` 放到 exe **同目录**即可覆盖内嵌资源
- 修复冻结态提权重启的路径问题（onefile 的临时解包目录不再被当成参数和工作目录）

---

## ⚠️ 升级提示

- **v4.2 用过更新模块的**：升级后建议点一次卡片 1 的 `ENABLE` 把注册表复位
  （旧版只留了个巨大上限值、没写暂停状态；新版 `ENABLE` 会先精确还原再重新应用）
- **暗色壁纸换新了**（哥特版），旧壁纸保留在 `photo/heihua-original.png`
- 本工具会修改系统设置（更新策略 / 安全中心 / 电源方案），**请只在自己的机器上使用**

---

## 🔐 校验

```powershell
Get-FileHash .\tweaker.exe -Algorithm SHA256
# 47344A27DBEAFDE17D87657411578228CF51BD3C140E294530407E71ABCA3748
```

> PyInstaller 单文件 exe 常被杀软误报，这是打包方式的通病，不是病毒特征。
> 谨慎起见请用上面的哈希校验，或者直接自己构建。

**许可**：代码 MIT；`photo/` 下的角色图与图标、课件中的插图**不在 MIT 覆盖范围内**，
版权归各自作者，仅供个人演示使用，二次分发请先替换或删除。

---
---

# System Tweaker v5.0 · KafuuBoost ⚡ — English

> **Rewritten update engine · custom power plan · redesigned UI · single-file build**
>
> The v4.2 update module no longer works on current Windows: it only wrote a "max pause days"
> value, which creates **no pause state at all**. v5.0 rewrites it from scratch — and ships its
> own performance plan.

## 🆚 v4.2 → v5.0

| | v4.2 | v5.0 |
|---|---|---|
| **Modules** | 6 | **7** (+ KafuuBoost power plan) |
| **Windows Update** | A single `FlightSettingsMaxPauseDays` write.<br>Measured: **nothing was actually paused.** | Three-layer write: pause timestamps + pause status + policy,<br>plus a 30-day auto-renew task |
| **Power plan** | — | **KafuuBoost**: official Ultimate Performance + 9 tweaks,<br>fixed GUID, deleted cleanly on revert |
| **UI** | Full-width dark cards covering the wallpaper | Plates hug the text, buttons float on the wallpaper |
| **Hidden bugs** | 3 (see below) | fixed |
| **Packaging** | Documented command pointed at images that don't exist | `build.bat` → one 22.9 MB exe, assets embedded |
| **Licensing** | none | MIT (code) + asset exception + `.gitignore` |

## 🔥 Windows Update: full rewrite

- **2026-04**: Microsoft replaced the pause dropdown with a **calendar picker**
- **2026-07**: after `KB5101650 / KB5101649`, a single pause is still capped at **35 days** but can
  be renewed indefinitely; official docs now mark the `DeferFeatureUpdates*` policies as
  *"legacy policy, isn't applicable for Windows 11"*
- Pause state lives in **two places** (`UX\Settings` timestamps + `UpdatePolicy\Settings` status) —
  writing only the "max days" value does nothing

v5.0 writes three layers, adds a **30-day auto-renew task**, supports **feature-update-only mode**,
**hiding specific KBs**, and a **snapshot-based exact revert**.

## ⚡ New: KafuuBoost power plan

Measured on a real Windows 11 25H2 machine: the official *Ultimate Performance* plan defines
**exactly one setting** (disk never turns off). The famous "100% minimum processor state" simply
isn't in it — it is just "High performance + disk never sleeps".

KafuuBoost adds the missing nine: **100% min processor state (AC)**, core parking off, active
cooling, aggressive boost, disk/sleep/display never off, PCIe ASPM off, USB selective suspend
disabled — then deletes itself cleanly on `DISABLE`. The battery (DC) side is left untouched by
default.

## 🎨 UI + 3 hidden bug fixes

Full-width dark cards → compact text plates with buttons floating over the wallpaper; and three
"works until it doesn't" bugs fixed: UI toggles silently dropped by the global run-lock, Tk touched
from a worker thread, and an `unbind()` that removed other widgets' event bindings.

## 📦 Packaging

Single 22.9 MB exe with wallpapers and icon embedded; `build.bat` for one-click rebuilds; drop a
`heihua.png` next to the exe to override the wallpaper without repacking.

## 🔐 Verify

```powershell
Get-FileHash .\tweaker.exe -Algorithm SHA256
# 47344A27DBEAFDE17D87657411578228CF51BD3C140E294530407E71ABCA3748
```

**License**: the code is MIT; the character artwork under `photo/` and the illustrations inside the
course `.docx` are **not** covered — they belong to their respective authors and are for personal
demonstration only. Replace or remove them before redistributing.

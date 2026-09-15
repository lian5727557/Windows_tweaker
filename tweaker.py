"""
System Tweaker v5.0
 Windows Update: 新版暂停引擎 — 时间戳+状态双写 & 每30天自动续期
 Defender     : 四层防线 — 注册表 + 服务 + 计划任务 + 防篡改
 Win11 Menu  : 经典完整右键菜单开关
 Firewall    : 三个配置文件防火墙开关
 Theme       : 程序内暗色 / 亮色主题一键切换（Catppuccin 风格）
 Anime Mode  : 二次元友好模式 — chino 装饰图开关
 Requires: Admin | Python 3.12+
"""
import os, sys, subprocess, ctypes, threading, time

# ── Auto-elevate ──────────────────────────────────────────
def is_admin():
    try: return ctypes.windll.shell32.IsUserAnAdmin()
    except: return False

if not is_admin():
    # 打包成 exe 后 __file__ 指向临时解包目录（进程退出即失效），
    # 所以冻结状态下只重启自己，不传脚本参数。
    if getattr(sys, 'frozen', False):
        _params = ""
        _cwd = os.path.dirname(sys.executable)
    else:
        _params = f'"{os.path.abspath(__file__)}"'
        _cwd = os.path.dirname(os.path.abspath(__file__))
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, _params, _cwd, 1)
    sys.exit()

import tkinter as tk
from tkinter import ttk, messagebox

# ── 新版更新暂停引擎（2026 机制：时间戳 + 状态 + 自动续期）──
try:
    import win_update_pause as wup
except Exception:                       # 模块缺失时退回 v4.2 旧写法
    wup = None

# ── 卓越性能电源方案引擎（复制官方方案 → 用完删掉，零残留）──
try:
    import win_power_plan as wpp
except Exception:
    wpp = None

RUNNING = False
_RUNNING_LOCK = threading.Lock()

# ── Shell helpers ─────────────────────────────────────────
def res_path(name):
    """
    查找资源文件（壁纸、图标）。优先级：
      1. exe/脚本 同目录           ← 方便用户直接替换自己的图
      2. exe/脚本 同目录 的 photo/
      3. 打包内部 _MEIPASS 及其 photo/   ← PyInstaller --add-data 解包位置
    找不到返回 None（调用方自行跳过，不报错）。
    """
    if getattr(sys, 'frozen', False):
        here = os.path.dirname(sys.executable)
    else:
        here = os.path.dirname(os.path.abspath(__file__))
    roots = [here, os.path.join(here, 'photo')]
    if getattr(sys, 'frozen', False):
        base = getattr(sys, '_MEIPASS', '')
        if base:
            roots += [base, os.path.join(base, 'photo')]
    for root in roots:
        candidate = os.path.join(root, name)
        if os.path.exists(candidate):
            return candidate
    return None


def _run(cmd, silent=True):
    return subprocess.run(cmd, shell=True,
        stdout=subprocess.DEVNULL if silent else None,
        stderr=subprocess.DEVNULL if silent else None)

def reg_set(path, name, value, reg_type="dword"):
    t = f"REG_{reg_type.upper()}"
    if name:
        _run(f'reg add "{path}" /v {name} /t {t} /d {value} /f')
    else:
        _run(f'reg add "{path}" /ve /f')

def svc_set(name, action):
    """action = auto | demand | disabled（映射 SC 命令 start= 参数）"""
    _run(f'sc config {name} start= {action}')

def svc_stop(name): _run(f'sc stop {name}')
def svc_start(name): _run(f'sc start {name}')

def task_set(name, action):
    """action = disable | enable"""
    _run(f'schtasks /change /tn "{name}" /{action}')

def restart_explorer():
    _run('taskkill /f /im explorer.exe')
    time.sleep(1)
    subprocess.Popen('explorer.exe', shell=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

# ═══════════════════════════════════════════════════════════
#  MODULE 1: Windows Update
#  实际逻辑在 win_update_pause.py：
#  老写法只改 FlightSettingsMaxPauseDays（只放大上限，不产生暂停状态），
#  新写法必须同时写暂停时间戳 + 暂停状态，再挂自动续期任务兜底。
# ═══════════════════════════════════════════════════════════

UPDATE_REG_BASE = r"HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate"
UPDATE_PAUSE_PATH = r"HKLM\SOFTWARE\Microsoft\WindowsUpdate\UX\Settings"
UPDATE_SERVICES = ["wuauserv", "UsoSvc", "WaaSMedicSvc", "BITS"]
UPDATE_TASKS = [
    r"Microsoft\Windows\WindowsUpdate\Scheduled Start",
    r"Microsoft\Windows\WindowsUpdate\sih",
    r"Microsoft\Windows\WindowsUpdate\sihboot",
    r"Microsoft\Windows\WindowsUpdate\Automatic App Update",
    r"Microsoft\Windows\UpdateOrchestrator\Schedule Scan",
    r"Microsoft\Windows\UpdateOrchestrator\Schedule Scan Static Task",
    r"Microsoft\Windows\UpdateOrchestrator\Refresh Settings",
    r"Microsoft\Windows\UpdateOrchestrator\USO_UxBroker",
]

# 最近一次更新模块操作的结果，GUI 用它显示暂停到期日
LAST_WU_RESULT = {}

def disable_update():
    """
    延长暂停（2026 新版机制）。

    旧写法只写 FlightSettingsMaxPauseDays —— 那条值只是"把设置页里的
    最大暂停天数调大"，本身不产生暂停状态，所以注册表看着改了、
    Windows 该更还是更。新版必须同时写：
      1. UX\\Settings 的 6 个暂停时间戳（真正生效的地方）
      2. UpdatePolicy\\Settings 的暂停状态值
      3. 版本钉住 + 排除驱动更新（策略层，专业版以上）
    再挂一个每 30 天自动续期的计划任务兜底 —— 因为设置页 UI 和
    WaaSMedicSvc 都可能把结束日期改回 35 天。
    """
    global LAST_WU_RESULT
    if wup is None:                       # 兜底：模块丢失时保持旧行为
        reg_set(UPDATE_PAUSE_PATH, "FlightSettingsMaxPauseDays", 25000)
        return True
    LAST_WU_RESULT = wup.apply(days=3650, mode="extend")
    return bool(LAST_WU_RESULT.get("ok"))

def enable_update():
    """一键恢复更新：还原写入前的注册表值，复位服务与计划任务"""
    global LAST_WU_RESULT
    if wup is None:
        reg_set(UPDATE_PAUSE_PATH, "FlightSettingsMaxPauseDays", 35)
        return True
    LAST_WU_RESULT = wup.revert()
    return bool(LAST_WU_RESULT.get("ok"))

# ═══════════════════════════════════════════════════════════
#  MODULE 2: Windows Defender & Security Center
#  基于社区开源方案 (TairikuOokami/defender-remover) 优化
#  关键：24H2 需要驱动级禁用 WdBoot/WdFilter + 安全中心关闭
# ═══════════════════════════════════════════════════════════

DEF_BASE = r"HKLM\SOFTWARE\Policies\Microsoft\Windows Defender"
DEF_SERVICES = [
    "WinDefend", "WdNisSvc", "SecurityHealthService",
    "wscsvc", "WdFilter", "SgrmBroker", "MpKslDrv",
    "MDCoreSvc",  # 24H2 新增核心服务
]
DEF_DRIVERS = ["WdBoot", "WdFilter", "WdNisDrv"]  # 驱动级，需设 Start=4
DEF_TASKS = [
    r"Microsoft\Windows\Windows Defender\Windows Defender Cache Maintenance",
    r"Microsoft\Windows\Windows Defender\Windows Defender Cleanup",
    r"Microsoft\Windows\Windows Defender\Windows Defender Scheduled Scan",
    r"Microsoft\Windows\Windows Defender\Windows Defender Verification",
]

def disable_defender():
    """彻底禁用 Defender — 四层：注册表策略 + 服务 + 驱动 + 计划任务"""
    # ── 第零层：关闭 Tamper Protection ──
    reg_set(r"HKLM\SOFTWARE\Microsoft\Windows Defender\Features", "TamperProtection", 0)
    reg_set(r"HKLM\SOFTWARE\Microsoft\Windows Defender\Features", "MpTamperProtectionSource", 0)

    # ── 第一层：注册表策略（24H2 兼容）──
    reg_set(DEF_BASE, "DisableAntiSpyware", 1)
    reg_set(DEF_BASE, "DisableAntiVirus", 1)
    reg_set(DEF_BASE, "DisableRoutinelyTakingAction", 1)
    reg_set(DEF_BASE, "AllowFastServiceStartup", 0)
    reg_set(DEF_BASE, "DisableLocalAdminMerge", 1)
    # 实时防护子键
    rtp = f"{DEF_BASE}\\Real-Time Protection"
    reg_set(rtp, "DisableRealtimeMonitoring", 1)
    reg_set(rtp, "DisableBehaviorMonitoring", 1)
    reg_set(rtp, "DisableOnAccessProtection", 1)
    reg_set(rtp, "DisableScanOnRealtimeEnable", 1)
    reg_set(rtp, "DisableIOAVProtection", 1)
    # 云防护/样本提交
    reg_set(f"{DEF_BASE}\\Spynet", "DisableBlockAtFirstSeen", 1)
    reg_set(f"{DEF_BASE}\\Spynet", "SpynetReporting", 0)
    reg_set(f"{DEF_BASE}\\Spynet", "SubmitSamplesConsent", 2)
    # 通知
    scn = r"HKLM\SOFTWARE\Policies\Microsoft\Windows Defender Security Center\Notifications"
    reg_set(scn, "DisableNotifications", 1)
    reg_set(scn, "DisableEnhancedNotifications", 1)

    # ── 第二层：服务停止 + 设为禁用 ──
    for svc in DEF_SERVICES:
        svc_stop(svc)
        svc_set(svc, "disabled")
        # 直写注册表 Start=4 防反弹（24H2 关键）
        reg_set(f"HKLM\\SYSTEM\\CurrentControlSet\\Services\\{svc}", "Start", 4)

    # ── 第三层：驱动级禁用 ──
    for drv in DEF_DRIVERS:
        reg_set(f"HKLM\\SYSTEM\\CurrentControlSet\\Services\\{drv}", "Start", 4)

    # ── 第四层：计划任务 ──
    for task in DEF_TASKS:
        task_set(task, "disable")

    # ── 额外：隐藏安全中心托盘图标 ──
    reg_set(r"HKLM\SOFTWARE\Microsoft\Windows Defender Security Center", "DisableTrayIcon", 1)

    # ── 移除自启托盘进程（SecurityHealthSystray.exe）──
    SYSTRAY_KEY = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run"
    _run(f'reg add "{SYSTRAY_KEY}" /v SecurityHealth.DisableBg /t REG_SZ /d "SecurityHealth" /f')
    _run(f'reg delete "{SYSTRAY_KEY}" /v SecurityHealth /f')

    return True


def enable_defender():
    """完整恢复 Defender 到默认状态"""
    # 删除所有策略键
    _run(f'reg delete "{DEF_BASE}" /f')
    _run(r'reg delete "HKLM\SOFTWARE\Policies\Microsoft\Windows Defender Security Center" /f')
    _run(r'reg delete "HKLM\SOFTWARE\Microsoft\Windows Defender Security Center" /v DisableTrayIcon /f')

    # 恢复 Tamper Protection
    reg_set(r"HKLM\SOFTWARE\Microsoft\Windows Defender\Features", "TamperProtection", 5)
    _run(r'reg delete "HKLM\SOFTWARE\Microsoft\Windows Defender\Features" /v MpTamperProtectionSource /f')

    # 恢复所有服务为自动启动
    for svc in DEF_SERVICES:
        _run(f'reg delete "HKLM\\SYSTEM\\CurrentControlSet\\Services\\{svc}" /v Start /f')
        svc_set(svc, "auto")

    # 恢复驱动为默认
    for drv in DEF_DRIVERS:
        _run(f'reg delete "HKLM\\SYSTEM\\CurrentControlSet\\Services\\{drv}" /v Start /f')

    # 恢复计划任务
    for task in DEF_TASKS:
        task_set(task, "enable")

    # 恢复自启托盘进程
    SYSTRAY_KEY = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run"
    _run(f'reg add "{SYSTRAY_KEY}" /v SecurityHealth /t REG_SZ /d "C:\\Windows\\System32\\SecurityHealthSystray.exe" /f')
    _run(f'reg delete "{SYSTRAY_KEY}" /v SecurityHealth.DisableBg /f')

    # 刷新组策略
    _run('gpupdate /force')
    return True

# ═══════════════════════════════════════════════════════════
#  MODULE 3: Win11 Right-Click Menu (Classic)
# ═══════════════════════════════════════════════════════════

CTX_KEY = r"HKCU\Software\Classes\CLSID\{86ca1aa0-34aa-4e8b-a509-50c905bae2a2}"
CTX_SUB = f"{CTX_KEY}\\InprocServer32"

def disable_win11_context():
    _run(f'reg add "{CTX_SUB}" /ve /f')
    threading.Thread(target=restart_explorer, daemon=True).start()
    return True

def enable_win11_context():
    _run(f'reg delete "{CTX_KEY}" /f')
    threading.Thread(target=restart_explorer, daemon=True).start()
    return True

# ═══════════════════════════════════════════════════════════
#  MODULE 4: Windows Firewall
# ═══════════════════════════════════════════════════════════

FW_BASE = r"HKLM\SOFTWARE\Policies\Microsoft\WindowsFirewall"
FW_PROFILES = ["DomainProfile", "PrivateProfile", "PublicProfile"]

def disable_firewall():
    """关闭三配置文件防火墙 — 策略注册表 + netsh 即时生效"""
    for profile in FW_PROFILES:
        reg_set(f"{FW_BASE}\\{profile}", "EnableFirewall", 0)
        _run(f'netsh advfirewall set {profile.lower().replace("profile","")}profile state off')
    return True

def enable_firewall():
    """开启防火墙 — 删策略键值 + 设默认值 1 + netsh"""
    for profile in FW_PROFILES:
        _run(f'reg delete "{FW_BASE}\\{profile}" /v EnableFirewall /f')
        # 删完策略键后，设回默认开启
        reg_set(f"{FW_BASE}\\{profile}", "EnableFirewall", 1)
        short = profile.lower().replace("profile", "")
        _run(f'netsh advfirewall set {short}profile state on')
    return True

# ═══════════════════════════════════════════════════════════
#  GUI — Theme & Widget System
# ═══════════════════════════════════════════════════════════

# Catppuccin Mocha Dark  /  Catppuccin Latte Light
THEMES = {
    "dark": {
        "bg": "#1e1e2e", "surf_bg": "#313244", "ovl_bg": "#45475a",
        "text_fg": "#cdd6f4", "dim": "#a6adc8", "accent": "#cba6f7",
        "subtle": "#a6adc8",
    },
    "light": {
        "bg": "#eff1f5", "surf_bg": "#ccd0da", "ovl_bg": "#bcc0cc",
        "text_fg": "#4c4f69", "dim": "#5c5f77", "accent": "#8839ef",
        "subtle": "#6c6f85",
    },
}

# ═══════════════════════════════════════════════════════════
#  中英双语字典
# ═══════════════════════════════════════════════════════════
L = {
    "zh": {
        "title": "系统调教工具  v5.0",
        "subtitle": "每个模块独立开关 · 点ENABLE即可恢复 · 需管理员权限",
        "card1_title": "Windows 更新",
        "card1_desc": "暂停功能+安全更新10年 · 写入完整暂停状态\n挂自动续期任务防被改回 · ENABLE即恢复",
        "card2_title": "Windows 安全中心",
        "card2_desc": "四层防线：策略+服务+驱动+计划任务\n保留防火墙  |  ENABLE一键恢复",
        "card3_title": "Win11 右键菜单",
        "card3_desc": "DISABLE = 恢复 Win10 经典完整菜单\nENABLE  = 回到 Win11 简洁菜单",
        "card4_title": "Windows 防火墙",
        "card4_desc": "关闭域/专用/公用三配置文件防火墙\nDISABLE=关  ENABLE=开",
        "card5_title": "KafuuBoost 性能方案",
        "card5_desc": "复刻官方卓越性能 + 9 项增强（最低 100% 频率）\n性能 ↑ 功耗/温度 ↑ · DISABLE 零残留还原",
        "card6_title": "程序主题 — 暗色 / 亮色",
        "card6_desc": "DISABLE = 暗色（Catppuccin Mocha）\nENABLE  = 亮色（Catppuccin Latte）",
        "card7_title": "二次元友好模式",
        "card7_desc": "ENABLE  = 显示 huajia 装饰图  ✨\nDISABLE = 隐藏装饰",
        "status_ready": "就绪",
        "status_running": "操作进行中，请稍候...",
        "bottom_hint": "操作完成后建议重启系统以完全生效",
        "btn_disable": "DISABLE",
        "btn_enable": "ENABLE",
        "running_suffix": "禁用中...",
        "done_suffix": "已完成",
        "fail_suffix": "失败",
        "wu_paused": "更新已暂停至",
        "wu_resumed": "更新已恢复",
        "pp_on": "已切换到",
        "pp_off": "已恢复平衡，方案已删除",
        "pp_failed": "电源操作失败",
        "pp_tuned": "9 项增强已生效",
    },
    "en": {
        "title": "System Tweaker  v5.0",
        "subtitle": "Independent module toggles · Admin required",
        "card1_title": "Windows Update",
        "card1_desc": "Pause feature + security updates for 10 years\nAuto-renew task keeps it paused · ENABLE to restore",
        "card2_title": "Windows Security Center",
        "card2_desc": "4-layer defense: Policy + Service + Driver + Tasks\nKeeps Firewall  |  ENABLE to restore",
        "card3_title": "Win11 Right-Click Menu",
        "card3_desc": "DISABLE = Restore Win10 classic full menu\nENABLE  = Use Win11 compact menu",
        "card4_title": "Windows Firewall",
        "card4_desc": "Turn off Domain/Private/Public firewall profiles\nDISABLE=Off  ENABLE=On",
        "card5_title": "KafuuBoost Power Plan",
        "card5_desc": "Official Ultimate Performance + 9 tweaks (100% min state)\nPerformance ↑  power/heat ↑ · DISABLE restores cleanly",
        "card6_title": "App Theme — Dark / Light",
        "card6_desc": "DISABLE = Dark (Catppuccin Mocha)\nENABLE  = Light (Catppuccin Latte)",
        "card7_title": "Anime-Friendly Mode",
        "card7_desc": "ENABLE  = Show huajia wallpaper  ✨\nDISABLE = Hide wallpaper",
        "status_ready": "Ready",
        "status_running": "Operation in progress, please wait...",
        "bottom_hint": "A system restart is recommended for full effect",
        "btn_disable": "DISABLE",
        "btn_enable": "ENABLE",
        "running_suffix": "disabling...",
        "done_suffix": "Done",
        "fail_suffix": "Failed",
        "wu_paused": "Updates paused until",
        "wu_resumed": "Updates resumed",
        "pp_on": "Switched to",
        "pp_off": "Back to Balanced, our plan removed",
        "pp_failed": "Power plan failed",
        "pp_tuned": "9 tweaks applied",
    },
}

class TweakerApp:
    def __init__(self, root):
        self.root = root
        self.theme_name = "dark"
        self.c = THEMES["dark"].copy()
        self.anime_on = False
        self.lang = "zh"  # 当前语言: zh / en
        self._text_widgets = []  # (widget, key) 用于语言切换
        self._pending_status = None  # 后台线程写这里，主线程轮询后显示
        self._tw = []          # (widget, attr, dark_val, light_val)
        self.anime_label = None  # 全窗口背景 label
        self._chino_photo = None
        self.card_frames = []  # card outer frames for surf_bg swap
        self.card_rows = []    # [(文字底板, [按钮, ...])] 按钮用 place 浮在背景上
        self.EDGE = 24         # 按钮距窗口右边距
        self.BTN_GAP = 6       # 两颗按钮之间的间距

        # ── 预加载原图（不缩放，运行时按窗口动态计算）──
        self._chino_raw = None   # 亮色壁纸 (huajia.jpg)
        self._heihua_raw = None  # 暗色壁纸 (heihua.png)
        try:
            from PIL import Image, ImageTk
            self.Image = Image
            self.ImageTk = ImageTk
            # 兼容 PyInstaller 打包和直接运行（图片在 photo/ 子目录里）
            src_light = res_path('huajia.jpg')
            src_dark = res_path('heihua.png')
            if src_light:
                self._chino_raw = Image.open(src_light)
            else:
                print("[tweaker] huajia.jpg not found")
            if src_dark:
                self._heihua_raw = Image.open(src_dark)
            else:
                print("[tweaker] heihua.png not found")
        except Exception as e:
            print(f"[tweaker] preload image: {e}")

        root.title(self.T("title"))
        root.geometry("660x900")
        root.resizable(True, True)
        root.minsize(660, 850)   # 七张卡片：最小高度也要放得下，否则会压到底部按钮
        root.configure(bg=self.c["bg"])
        self._add_tw(root, "bg", THEMES["dark"]["bg"], THEMES["light"]["bg"])

        # Header
        hdr = tk.Frame(root, bg=self.c["bg"])
        hdr.pack(pady=(14, 4))
        self._add_tw(hdr, "bg", THEMES["dark"]["bg"], THEMES["light"]["bg"])

        self.head_lbl = tk.Label(hdr, text=self.T("title"),
                                  font=("Microsoft YaHei UI", 14, "bold"))
        self.t(self.head_lbl, "fg", "accent")
        self.t(self.head_lbl, "bg", "bg")
        self._bind_text(self.head_lbl, "title")
        self.head_lbl.pack()

        self.sub_lbl = tk.Label(hdr, text=self.T("subtitle"),
                                 font=("Microsoft YaHei UI", 8))
        self.t(self.sub_lbl, "fg", "ovl_bg")
        self.t(self.sub_lbl, "bg", "bg")
        self._bind_text(self.sub_lbl, "subtitle")
        self.sub_lbl.pack()

        # Section 1-4: system tweaks
        self.make_card("card1_title", "card1_desc",
                       self._disable_update, self._enable_update)
        self.make_card("card2_title", "card2_desc",
                       disable_defender, enable_defender)
        self.make_card("card3_title", "card3_desc",
                       disable_win11_context, enable_win11_context)
        self.make_card("card4_title", "card4_desc",
                       disable_firewall, enable_firewall)

        # Section 5: Ultimate Performance power plan
        self.make_card("card5_title", "card5_desc",
                       self._disable_power, self._enable_power)

        # Section 6: App Theme Toggle
        self.make_card("card6_title", "card6_desc",
                       self._disable_theme, self._enable_theme, local=True)

        # Section 7: Anime-Friendly Mode
        self.make_card("card7_title", "card7_desc",
                       self._disable_anime, self._enable_anime, local=True)

        # ── 窗口尺寸变化：重排按钮 + 重铺背景图（只绑一次；unbind 会误删别的绑定）──
        self.root.bind("<Configure>", self._on_resize)

        # ── 全窗口背景图（place 在 root 底层）──
        self.bg_label = tk.Label(root, bg=self.c["bg"], bd=0)
        # 默认隐藏，由 _set_anime 控制

        # Status bar
        self.status_label = tk.Label(root, text=self.T("status_ready"),
                                      font=("Microsoft YaHei UI", 9))
        self.t(self.status_label, "fg", "ovl_bg")
        self.t(self.status_label, "bg", "bg")
        self._bind_text(self.status_label, "status_ready")
        self.status_label.pack(side="bottom", pady=(6, 2))

        self.bottom_lbl = tk.Label(root, text=self.T("bottom_hint"),
                                    font=("Microsoft YaHei UI", 8))
        self.t(self.bottom_lbl, "fg", "subtle")
        self.t(self.bottom_lbl, "bg", "bg")
        self._bind_text(self.bottom_lbl, "bottom_hint")
        self.bottom_lbl.pack(side="bottom", pady=(0, 14))

        # ── 语言切换按钮 ──
        lang_frame = tk.Frame(root, bg=self.c["bg"])
        self._add_tw(lang_frame, "bg", THEMES["dark"]["bg"], THEMES["light"]["bg"])
        lang_frame.pack(side="bottom", pady=(0, 8))

        self.btn_zh = tk.Button(lang_frame, text="中文", font=("Microsoft YaHei UI", 9, "bold"),
                                bg="#a6e3a1", fg="#1e1e2e", relief="flat",
                                padx=10, pady=3, cursor="hand2",
                                command=self._switch_zh)
        self.btn_zh.pack(side="left", padx=(0, 4))

        self.btn_en = tk.Button(lang_frame, text="English", font=("Segoe UI", 9, "bold"),
                                bg="#89b4fa", fg="#1e1e2e", relief="flat",
                                padx=10, pady=3, cursor="hand2",
                                command=self._switch_en)
        self.btn_en.pack(side="left")

        # 强制刷新主题：解决 Tkinter 在 Windows 上初始渲染时的白色闪烁
        root.update_idletasks()
        self._apply_theme("light")  # 默认亮色主题
        self._set_lang("zh")  # 初始语言高亮
        self.root.after(80, self._layout_buttons)  # 首帧后把按钮摆到右侧
        self.root.after(120, self._pump_status)    # 主线程轮询后台状态
        # ── 默认开启二次元友好模式 ──
        self.root.after(200, lambda: self._set_anime(True))

    # ── Theme helpers ────────────────────────────────────
    def _disable_update(self):
        """走新版引擎：暂停 10 年 + 自动续期，返回带到期日的提示"""
        if not disable_update():
            return False
        expiry = str(LAST_WU_RESULT.get("expiry") or "")[:10]
        return f'{self.T("wu_paused")} {expiry}'.strip()

    def _enable_update(self):
        if not enable_update():
            return False
        return self.T("wu_resumed")

    # ── 卓越性能电源方案 ─────────────────────────────────
    def _enable_power(self):
        """
        复刻官方卓越性能方案 + 叠加 9 项性能增强 → 激活。

        为什么要加 tune：实测（2026-09-16）官方方案在本机只定义了一项
        （硬盘永不关闭），其余落到家族基线，实际效果 ≈ 高性能 + 硬盘不关，
        几乎没有性能收益。真正的"卓越性能"效果来自这 9 项：
        最低处理器 100%、不关核、散热主动、提升激进、硬盘/睡眠/显示器永不、
        PCIe ASPM 关闭、USB 选择性暂停禁用。
        """
        if wpp is None:
            return False
        res = wpp.apply(tune=True)
        if not res.get("ok"):
            return f'{self.T("pp_failed")}: {str(res.get("error") or "")[:40]}'
        name = (res.get("active") or {}).get("name") or "Ultimate Performance"
        return f'{self.T("pp_on")} {name} + {self.T("pp_tuned")}'.strip()

    def _disable_power(self):
        """切回平衡并删掉我们复制的那份方案"""
        if wpp is None:
            return False
        res = wpp.revert(delete_scheme=True)
        if not res.get("ok"):
            return f'{self.T("pp_failed")}: {str(res.get("error") or "")[:40]}'
        return self.T("pp_off")

    def t(self, widget, attr, color_key):
        self._tw.append((widget, attr, THEMES["dark"][color_key], THEMES["light"][color_key]))

    def _add_tw(self, widget, attr, dark_val, light_val):
        self._tw.append((widget, attr, dark_val, light_val))

    def T(self, key):
        """获取当前语言的文字"""
        return L[self.lang].get(key, key)

    def _bind_text(self, widget, key):
        """注册一个需要语言切换的 Label/控件"""
        self._text_widgets.append((widget, key))

    # ── Theme switch ─────────────────────────────────────
    def _disable_theme(self):
        """Switch to dark theme"""
        self._apply_theme("dark")
        return True

    def _enable_theme(self):
        """Switch to light theme"""
        self._apply_theme("light")
        return True

    def _apply_theme(self, name):
        self.theme_name = name
        self.c = THEMES[name].copy()
        for widget, attr, dark_val, light_val in self._tw:
            try:
                widget.configure(**{attr: light_val if name == "light" else dark_val})
            except Exception:
                pass
        # Also update card frames' surf_bg
        surf_d, surf_l = THEMES["dark"]["surf_bg"], THEMES["light"]["surf_bg"]
        for f in self.card_frames:
            try:
                f.configure(bg=surf_l if name == "light" else surf_d)
            except Exception:
                pass
        # ── 二次元模式下切换壁纸 ──
        if self.anime_on:
            self._refresh_bg_image()

    # ── Anime mode ───────────────────────────────────────
    def _disable_anime(self):
        """DISABLE = 隐藏壁纸"""
        return self._set_anime(False)

    def _enable_anime(self):
        """ENABLE = 显示壁纸"""
        return self._set_anime(True)

    def _set_anime(self, show):
        self.root.after(0, self._set_anime_main, show)
        return True

    def _set_anime_main(self, show):
        if show:
            if self._chino_raw is None:
                return
            self.anime_on = True
            self._refresh_bg_image()
        else:
            self.anime_on = False
            self.bg_label.place_forget()

    def _on_resize(self, event):
        """窗口尺寸变化：重排按钮 + 重新缩放背景图（防抖 80ms）"""
        if event.widget is not self.root:
            return
        if getattr(self, '_resize_after_id', None):
            try:
                self.root.after_cancel(self._resize_after_id)
            except Exception:
                pass
        self._resize_after_id = self.root.after(80, self._after_resize)

    def _after_resize(self):
        self._resize_after_id = None
        self._layout_buttons()
        if self.anime_on:
            self._refresh_bg_image()

    def _refresh_bg_image(self):
        """按窗口当前尺寸缩放并铺满背景"""
        if not self.anime_on:
            return
        # 亮色主题 → huajia.jpg，暗色主题 → heihua.png
        raw = self._chino_raw if self.theme_name == "light" else self._heihua_raw
        if raw is None:
            return
        self.root.update_idletasks()
        win_w = self.root.winfo_width()
        win_h = self.root.winfo_height()
        if win_w < 50 or win_h < 50:
            self.root.after(50, self._refresh_bg_image)
            return

        # 按比例缩放填满窗口（cover 模式，会裁切多余部分）
        scale = max(win_w / raw.width, win_h / raw.height)  # 用 max 保证 cover
        new_w = max(1, int(raw.width * scale))
        new_h = max(1, int(raw.height * scale))
        img = raw.resize((new_w, new_h), self.Image.LANCZOS)

        # 居中裁剪到窗口尺寸
        left = (new_w - win_w) // 2
        top = (new_h - win_h) // 2
        img = img.crop((left, top, left + win_w, top + win_h))

        self._chino_photo = self.ImageTk.PhotoImage(img)
        self.bg_label.configure(image=self._chino_photo)
        # place 铺满整个窗口，放在最底层
        self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)
        # 确保背景在最底层
        self.bg_label.lower()
        # 同时把卡片帧提升到背景之上
        for f in self.card_frames:
            f.lift()

    # ── Card builder ─────────────────────────────────────
    def make_card(self, title_key, desc_key, disable_fn, enable_fn, local=False):
        """
        local=False（默认）: 系统类操作 → 丢到后台线程，避开界面卡死
        local=True        : 纯界面开关（主题 / 壁纸）→ 主线程直接执行，
                            既不碰 RUNNING 锁，也不在线程里操作 Tk（会偶发失灵）
        """
        # 文字底板：只包住标题+说明（左右各留一小段距离），不再横跨整个窗口，
        # 这样壁纸不会被一大块深色挡住。
        frame = tk.Frame(self.root, bg=self.c["surf_bg"], bd=0, highlightthickness=0)
        frame.pack(anchor="w", padx=24, pady=5)
        self.card_frames.append(frame)

        inner = tk.Frame(frame, bg=self.c["surf_bg"])
        inner.pack(padx=14, pady=9)
        self._add_tw(inner, "bg", THEMES["dark"]["surf_bg"], THEMES["light"]["surf_bg"])

        title_lbl = tk.Label(inner, text=self.T(title_key),
                             font=("Microsoft YaHei UI", 11, "bold"))
        self.t(title_lbl, "fg", "text_fg")
        self.t(title_lbl, "bg", "surf_bg")
        self._bind_text(title_lbl, title_key)
        title_lbl.pack(anchor="w")

        desc_lbl = tk.Label(inner, text=self.T(desc_key),
                            font=("Microsoft YaHei UI", 8), justify="left")
        self.t(desc_lbl, "fg", "dim")
        self.t(desc_lbl, "bg", "surf_bg")
        self._bind_text(desc_lbl, desc_key)
        desc_lbl.pack(anchor="w", pady=(4, 0))

        # 按钮：直接挂在 root 上，由 _layout_buttons 用 place 浮到右侧。
        # 按钮之外不再有底板，壁纸可从按钮周围透出来。
        runner = self.run_local if local else self.run_op
        btn_disable = tk.Button(self.root, text=self.T("btn_disable"),
                                font=("Segoe UI", 10, "bold"),
                                bg="#f38ba8", fg="#1e1e2e", activebackground="#e06c7f",
                                relief="flat", padx=16, pady=5, cursor="hand2",
                                command=lambda: runner(disable_fn, self.T(title_key), "disable"))
        btn_enable = tk.Button(self.root, text=self.T("btn_enable"),
                               font=("Segoe UI", 10, "bold"),
                               bg="#a6e3a1", fg="#1e1e2e", activebackground="#7ec97c",
                               relief="flat", padx=16, pady=5, cursor="hand2",
                               command=lambda: runner(enable_fn, self.T(title_key), "enable"))
        self.card_rows.append((frame, [btn_disable, btn_enable]))

    def _layout_buttons(self):
        """把每张卡的两颗按钮贴到窗口右侧，并与文字底板垂直居中对齐。"""
        self.root.update_idletasks()
        win_w = self.root.winfo_width()
        for plate, btns in self.card_rows:
            if not btns or not plate.winfo_ismapped():
                continue
            total = sum(b.winfo_reqwidth() for b in btns) + self.BTN_GAP * (len(btns) - 1)
            # 正常情况下靠右对齐；窗口太窄时退到文字底板右侧，避免压字
            x = max(win_w - self.EDGE - total, plate.winfo_x() + plate.winfo_width() + 12)
            y = plate.winfo_y() + max(0, (plate.winfo_height() - btns[0].winfo_reqheight()) // 2)
            for btn in btns:
                btn.place(x=x, y=y)
                btn.lift()
                x += btn.winfo_reqwidth() + self.BTN_GAP

    # ── Operation runner ─────────────────────────────────
    def run_local(self, fn, title, action):
        """纯界面操作（主题 / 壁纸）：主线程直接跑，不占 RUNNING 锁、不跨线程碰 Tk"""
        self.set_status(f"{title}: {self.T(action + '_suffix')}", "#f9e2af")
        try:
            res = fn()
        except Exception as e:
            self.set_status(str(e)[:80], "#f38ba8")
            return
        if isinstance(res, str) and res:
            self.set_status(res, "#a6e3a1")
        else:
            self.set_status(f"{title}  {self.T('done_suffix') if res else self.T('fail_suffix')}",
                            "#a6e3a1" if res else "#f38ba8")

    def run_op(self, fn, title, action):
        global RUNNING
        with _RUNNING_LOCK:
            if RUNNING:
                self.set_status(self.T("status_running"), "#f9e2af")
                return
            RUNNING = True
        label = f"{title}: {self.T(action + '_suffix')}"
        self.set_status(label, "#f9e2af")
        threading.Thread(target=self._run, args=(fn, title, action), daemon=True).start()

    def _run(self, fn, title, action):
        global RUNNING
        try:
            res = fn()
            if isinstance(res, str) and res:     # 带详情的成功提示（如暂停到期日）
                self.set_status(res, "#a6e3a1")
            else:
                self.set_status(f"{title}  {self.T('done_suffix')}" if res
                                else f"{title}  {self.T('fail_suffix')}",
                                "#a6e3a1" if res else "#f38ba8")
        except Exception as e:
            self.set_status(str(e)[:80], "#f38ba8")
        finally:
            with _RUNNING_LOCK:
                RUNNING = False

    def set_status(self, text, color=None):
        """
        状态栏更新。后台线程**不能**碰 Tk —— 从工作线程直接调 root.after()
        是"平时能用但不稳"的写法（依赖 Tk 的忙等机制，主线程不在 mainloop
        时会抛 main thread is not in main loop）。所以工作线程只写变量，
        由主线程的 _pump_status 轮询显示。
        """
        if threading.current_thread() is threading.main_thread():
            self.status_label.config(text=text, fg=color or self.c["ovl_bg"])
        else:
            self._pending_status = (text, color)

    def _pump_status(self):
        """主线程定时器：把后台线程留下的状态显示出来"""
        item = self._pending_status
        if item:
            self._pending_status = None
            text, color = item
            self.status_label.config(text=text, fg=color or self.c["ovl_bg"])
        self.root.after(120, self._pump_status)

    # ── Language switch ──────────────────────────────────
    def _switch_zh(self):
        self._set_lang("zh")

    def _switch_en(self):
        self._set_lang("en")

    def _set_lang(self, lang):
        self.lang = lang
        self.root.title(self.T("title"))
        # 更新所有注册的文本控件
        for widget, key in self._text_widgets:
            try:
                widget.config(text=self.T(key))
            except Exception:
                pass
        # 高亮当前语言按钮
        self.btn_zh.configure(bg="#a6e3a1" if lang == "zh" else "#d9d9d9")
        self.btn_en.configure(bg="#89b4fa" if lang == "en" else "#d9d9d9")
        # 文字长度变了 → 底板尺寸变了 → 重新摆按钮
        self.root.after(30, self._layout_buttons)

# ── Main ──────────────────────────────────────────────────
if __name__ == "__main__":
    # 计划任务调用：只做续期，不开 GUI
    if "--renew" in sys.argv:
        sys.exit(0 if (wup and wup.renew(days=wup.DEFAULT_DAYS).get("ok")) else 1)

    root = tk.Tk()
    app = TweakerApp(root)
    # 窗口图标（exe 同目录 / photo / 打包内部 三处自动找）
    ico = res_path('chino.ico')
    if ico:
        root.iconbitmap(ico)
    root.mainloop()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
动态照片转换 —— MotionPhoto2 的 macOS 中文图形界面

把 iPhone 实况照片（HEIC/JPG 照片 + MOV 视频）批量合成为
谷歌相册 / 三星相册可识别的动态照片（Motion Photo）。

转换核心仍是原项目的 motionphoto2.py / Muxer.py，本文件只负责界面：
- 原生 Tk 界面，自动跟随 macOS 深色 / 浅色模式
- 不再弹出终端窗口
- 可把文件夹拖到 Dock 图标上
- 优先使用系统里的 exiftool，找不到时使用 App 内置的 exiftool
"""

import json
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
from pathlib import Path

APP_NAME = "动态照片转换"
APP_VERSION = "1.0.0"
SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "MotionPhoto2-zh"
SETTINGS_FILE = SUPPORT_DIR / "settings.json"

DEFAULT_SETTINGS = {
    "input_directory": "",
    "output_directory": "",
    "exif_match": True,
    "copy_unmuxed": True,
    "recursive": True,
    "incremental_mode": False,
    "verbose": False,
}


# --------------------------------------------------------------------------
# 运行环境
# --------------------------------------------------------------------------

def resource_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


def setup_exiftool() -> bool:
    """从访达启动的 App 没有 Homebrew 的 PATH，这里补上；
    系统里没有 exiftool 时，使用 App 内置的版本。"""
    extra = ["/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"]
    parts = [p for p in os.environ.get("PATH", "").split(os.pathsep) if p]
    os.environ["PATH"] = os.pathsep.join(extra + [p for p in parts if p not in extra])

    if shutil.which("exiftool"):
        return True

    bundled = resource_dir() / "exiftool_bundle" / "exiftool"
    perl = shutil.which("perl")
    if bundled.exists() and perl:
        try:
            bin_dir = SUPPORT_DIR / "bin"
            bin_dir.mkdir(parents=True, exist_ok=True)
            wrapper = bin_dir / "exiftool"
            wrapper.write_text(
                f'#!/bin/sh\nexec "{perl}" "{bundled}" "$@"\n', encoding="utf-8"
            )
            wrapper.chmod(0o755)
            os.environ["PATH"] = str(bin_dir) + os.pathsep + os.environ["PATH"]
        except OSError:
            return False
    return shutil.which("exiftool") is not None


def run_cli(argv):
    """命令行模式：界面在后台用这个模式调用原项目的转换核心。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", line_buffering=True)
        except Exception:
            pass
    setup_exiftool()
    sys.argv = ["motionphoto2"] + list(argv)
    import motionphoto2  # noqa: E402  (原项目的转换核心)
    motionphoto2.main()


def load_settings() -> dict:
    settings = dict(DEFAULT_SETTINGS)
    try:
        settings.update(json.loads(SETTINGS_FILE.read_text(encoding="utf-8")))
    except Exception:
        pass
    return settings


def save_settings(settings: dict):
    try:
        SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(
            json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception:
        pass


# --------------------------------------------------------------------------
# 把原项目的英文输出翻译成简洁的中文
# --------------------------------------------------------------------------

RE_PROGRESS = re.compile(r"^=+\[(\d+)/(\d+)\]$")
RE_LOG = re.compile(r"^\[[^\]]*\] \[(\w+)\] \[[^\]]*\] - (.*)$")


def translate(line: str, copy_unmuxed: bool):
    """返回 (类型, 中文文本)。类型用于统计；文本为 None 表示默认不显示。"""
    s = line.strip()
    if not s:
        return "skip", None

    m = RE_PROGRESS.match(s)
    if m:
        return "progress", (int(m.group(1)), int(m.group(2)))
    if set(s) == {"="}:
        return "skip", None

    m = RE_LOG.match(s)
    if m:
        level, msg = m.group(1), m.group(2)
        w = re.match(r"Writing output file: (.*)$", msg)
        if w:
            return "converted", f"✅ 已合成动态照片：{Path(w.group(1)).name}"
        if level == "ERROR":
            return "error", f"❌ 出错：{msg}"
        if level == "WARNING":
            if msg.startswith("XMP of original file is empty"):
                return "detail", None  # 常见且无害，不打扰用户
            fx = re.match(r"File extension (\S+) doesn't match with metadata\. Treating as (\S+)", msg)
            if fx:
                return "warning", f"⚠️ 文件扩展名 {fx.group(1)} 和实际格式不一致，已按 {fx.group(2)} 处理"
            return "warning", f"⚠️ 提示：{msg}"
        return "detail", None

    if s.startswith("Converting files in "):
        return "info", f"📂 开始处理：{s[len('Converting files in '):]}"
    if s == "Running in EXIF matching mode.":
        return "info", "🔎 按照片内部信息配对照片和视频"
    if s.startswith("Getting metadata for images"):
        return "info", "⏳ 正在读取照片信息，照片多时需要一会儿…"
    if s.startswith("Getting metadata for videos"):
        return "info", "⏳ 正在读取视频信息…"
    if s.startswith("No images found"):
        return "info", "没有找到照片。"
    if s.startswith("No videos found"):
        return "info", "没有找到视频，没有可合成的实况照片。"

    m = re.match(r"^Input (.+) is already a motion photo", s)
    if m:
        return "skipped", f"⏭ 本来就是动态照片：{m.group(1)}"
    m = re.match(r"^Destination (.+?) (?:as it )?is already a motion photo", s)
    if m:
        return "skipped", f"⏭ 之前已经转换过：{m.group(1)}"
    m = re.match(r"^No matching video found for (.+)$", s)
    if m:
        if copy_unmuxed:
            return "plain", None
        return "plain", f"📷 普通照片（没有配对视频），未复制：{m.group(1)}"
    if s == "Copying unmuxed files...":
        return "info", "📄 正在复制普通照片和视频…"
    if s.startswith("Copying "):
        return "copied", None
    if s.startswith("[ERROR]"):
        return "error", f"❌ 出错：{s[len('[ERROR]'):].strip()}"
    if s.startswith("Traceback") or "Error" in s.split(":")[0]:
        return "error", f"❌ {s}"
    return "detail", None


# --------------------------------------------------------------------------
# 图形界面
# --------------------------------------------------------------------------

def run_gui(selftest: bool = False):
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    class App:
        def __init__(self, root):
            self.root = root
            self.settings = load_settings()
            self.proc = None
            self.queue = queue.Queue()
            self.stats = {}
            self.exiftool_ok = setup_exiftool()

            root.title(APP_NAME)
            root.geometry("780x680")
            root.minsize(680, 560)

            self.var_in = tk.StringVar(value=self.settings["input_directory"])
            self.var_out = tk.StringVar(value=self.settings["output_directory"])
            self.var_exif = tk.BooleanVar(value=self.settings["exif_match"])
            self.var_copy = tk.BooleanVar(value=self.settings["copy_unmuxed"])
            self.var_rec = tk.BooleanVar(value=self.settings["recursive"])
            self.var_inc = tk.BooleanVar(value=self.settings["incremental_mode"])
            self.var_verbose = tk.BooleanVar(value=self.settings["verbose"])
            self.var_status = tk.StringVar(value="准备就绪")

            self.build()

            # 把文件夹拖到 Dock 图标上
            try:
                root.createcommand("::tk::mac::OpenDocument", self.on_open_documents)
            except Exception:
                pass
            root.protocol("WM_DELETE_WINDOW", self.on_close)

            if not self.exiftool_ok:
                self.btn_run.state(["disabled"])
                self.log("❌ 没有找到 ExifTool，无法转换。")
                self.log("   请在终端运行：brew install exiftool，然后重新打开本程序。")

        # ---------- 布局 ----------
        def build(self):
            root = self.root
            outer = ttk.Frame(root, padding=(22, 18, 22, 18))
            outer.pack(fill="both", expand=True)

            ttk.Label(outer, text=APP_NAME, font=("PingFang SC", 22, "bold")).pack(anchor="w")
            ttk.Label(
                outer,
                text="把 iPhone 实况照片（照片 + 视频）合成谷歌相册能识别的动态照片。原文件不会被修改。",
                wraplength=720,
            ).pack(anchor="w", pady=(4, 14))

            # 1. 文件夹
            box1 = ttk.LabelFrame(outer, text=" 1. 选择文件夹 ", padding=(14, 10))
            box1.pack(fill="x")
            box1.columnconfigure(1, weight=1)
            ttk.Label(box1, text="照片所在文件夹").grid(row=0, column=0, sticky="w", pady=4)
            ttk.Entry(box1, textvariable=self.var_in).grid(row=0, column=1, sticky="ew", padx=8)
            ttk.Button(box1, text="选择…", command=self.choose_input).grid(row=0, column=2)
            ttk.Label(box1, text="转换后保存到").grid(row=1, column=0, sticky="w", pady=4)
            ttk.Entry(box1, textvariable=self.var_out).grid(row=1, column=1, sticky="ew", padx=8)
            ttk.Button(box1, text="选择…", command=self.choose_output).grid(row=1, column=2)
            ttk.Label(
                box1,
                text="小技巧：可以直接把照片文件夹拖到 Dock 里的本程序图标上。不选保存位置时，会自动新建「原文件夹名_动态照片」。",
                wraplength=700,
                foreground="gray",
            ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))

            # 2. 选项
            box2 = ttk.LabelFrame(outer, text=" 2. 选项 ", padding=(14, 10))
            box2.pack(fill="x", pady=(12, 0))
            opts = [
                (self.var_exif, "按照片内部信息配对（推荐）", "文件名对不上时也能找到对应的视频"),
                (self.var_copy, "同时复制普通照片和视频（推荐）", "保存的文件夹就是完整一批，直接整个拖给手机"),
                (self.var_rec, "包含子文件夹", "照片分在多个子文件夹时打开"),
                (self.var_inc, "跳过之前已经转换过的", "往同一个保存文件夹里追加新照片时打开"),
                (self.var_verbose, "显示详细日志", "出问题、需要排查时再打开"),
            ]
            for i, (var, title, desc) in enumerate(opts):
                ttk.Checkbutton(box2, text=title, variable=var).grid(row=i, column=0, sticky="w", pady=2)
                ttk.Label(box2, text=desc, foreground="gray").grid(row=i, column=1, sticky="w", padx=(12, 0))

            # 3. 开始
            box3 = ttk.Frame(outer)
            box3.pack(fill="x", pady=(14, 6))
            self.btn_run = ttk.Button(box3, text="开始转换", command=self.start)
            self.btn_run.pack(side="left")
            self.btn_stop = ttk.Button(box3, text="停止", command=self.stop)
            self.btn_stop.pack(side="left", padx=(8, 0))
            self.btn_stop.state(["disabled"])
            self.btn_open = ttk.Button(box3, text="在访达中打开结果", command=self.open_output)
            self.btn_open.pack(side="right")
            self.btn_open.state(["disabled"])

            self.progress = ttk.Progressbar(outer, mode="determinate", maximum=100)
            self.progress.pack(fill="x", pady=(6, 2))
            ttk.Label(outer, textvariable=self.var_status).pack(anchor="w")

            # 日志
            log_frame = ttk.Frame(outer)
            log_frame.pack(fill="both", expand=True, pady=(8, 0))
            self.text = tk.Text(
                log_frame, height=12, wrap="word", font=("Menlo", 12),
                relief="flat", borderwidth=0, highlightthickness=1, padx=8, pady=6,
            )
            try:
                # macOS 动态系统颜色：自动适配深色 / 浅色模式
                self.text.configure(
                    background="systemTextBackgroundColor",
                    foreground="systemTextColor",
                    insertbackground="systemTextColor",
                    highlightbackground="systemSeparatorColor",
                    highlightcolor="systemSeparatorColor",
                )
            except tk.TclError:
                pass
            scroll = ttk.Scrollbar(log_frame, command=self.text.yview)
            self.text.configure(yscrollcommand=scroll.set, state="disabled")
            self.text.pack(side="left", fill="both", expand=True)
            scroll.pack(side="right", fill="y")

            ttk.Label(
                outer,
                text=f"v{APP_VERSION} · 转换核心：MotionPhoto2（Petr Vyskocil，MIT 许可）",
                foreground="gray",
            ).pack(anchor="e", pady=(6, 0))

        # ---------- 交互 ----------
        def log(self, msg):
            self.text.configure(state="normal")
            self.text.insert("end", msg + "\n")
            self.text.see("end")
            self.text.configure(state="disabled")

        def choose_input(self):
            d = filedialog.askdirectory(title="选择照片所在文件夹", initialdir=self.var_in.get() or str(Path.home()))
            if d:
                self.set_input(d)

        def choose_output(self):
            d = filedialog.askdirectory(title="选择转换后保存的位置", initialdir=self.var_out.get() or str(Path.home()))
            if d:
                self.var_out.set(d)

        def set_input(self, path):
            p = Path(path)
            if p.is_file():
                p = p.parent
            self.var_in.set(str(p))
            out = self.var_out.get().strip()
            if not out or Path(out).resolve() == p.resolve():
                self.var_out.set(str(p.parent / f"{p.name}_动态照片"))

        def on_open_documents(self, *paths):
            if paths and not self.proc:
                self.set_input(paths[0])

        def open_output(self):
            out = self.var_out.get().strip()
            if out and Path(out).exists():
                subprocess.Popen(["open", out])

        def collect_settings(self):
            return {
                "input_directory": self.var_in.get().strip(),
                "output_directory": self.var_out.get().strip(),
                "exif_match": self.var_exif.get(),
                "copy_unmuxed": self.var_copy.get(),
                "recursive": self.var_rec.get(),
                "incremental_mode": self.var_inc.get(),
                "verbose": self.var_verbose.get(),
            }

        def start(self):
            s = self.collect_settings()
            inp = s["input_directory"]
            if not inp or not Path(inp).is_dir():
                messagebox.showwarning(APP_NAME, "请先选择照片所在的文件夹。")
                return
            if not s["output_directory"]:
                p = Path(inp)
                s["output_directory"] = str(p.parent / f"{p.name}_动态照片")
                self.var_out.set(s["output_directory"])
            out = Path(s["output_directory"])
            if out.exists() and out.resolve() == Path(inp).resolve():
                messagebox.showwarning(APP_NAME, "保存位置不能和照片所在文件夹相同，请换一个文件夹。")
                return
            if out.exists() and out.is_file():
                messagebox.showwarning(APP_NAME, "保存位置是一个文件，请选择文件夹。")
                return
            save_settings(s)
            self.current = s

            args = ["--input-directory", inp, "--output-directory", str(out)]
            if s["exif_match"]:
                args.append("--exif-match")
            if s["copy_unmuxed"]:
                args.append("--copy-unmuxed")
            if s["recursive"]:
                args.append("--recursive")
            if s["incremental_mode"]:
                args.append("--incremental-mode")
            if s["verbose"]:
                args.append("--verbose")

            if getattr(sys, "frozen", False):
                cmd = [sys.executable, "--cli"] + args
            else:
                cmd = [sys.executable, str(Path(__file__).resolve()), "--cli"] + args

            env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
            try:
                self.proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    stdin=subprocess.DEVNULL, env=env, bufsize=1,
                    text=True, encoding="utf-8", errors="replace",
                )
            except OSError as e:
                messagebox.showerror(APP_NAME, f"无法启动转换：{e}")
                self.proc = None
                return

            self.stats = {"converted": 0, "copied": 0, "skipped": 0, "plain": 0, "error": 0, "warning": 0}
            self.text.configure(state="normal")
            self.text.delete("1.0", "end")
            self.text.configure(state="disabled")
            self.progress.configure(value=0)
            self.var_status.set("正在转换…")
            self.btn_run.state(["disabled"])
            self.btn_stop.state(["!disabled"])
            self.btn_open.state(["disabled"])

            threading.Thread(target=self.reader, args=(self.proc,), daemon=True).start()
            self.root.after(100, self.poll)

        def reader(self, proc):
            for line in proc.stdout:
                self.queue.put(("line", line.rstrip("\n")))
            proc.wait()
            self.queue.put(("done", proc.returncode))

        def poll(self):
            done = None
            try:
                while True:
                    kind, payload = self.queue.get_nowait()
                    if kind == "line":
                        self.handle_line(payload)
                    else:
                        done = payload
            except queue.Empty:
                pass
            if done is not None:
                self.finish(done)
            else:
                self.root.after(100, self.poll)

        def handle_line(self, line):
            kind, text = translate(line, self.current["copy_unmuxed"])
            if kind == "progress":
                i, n = text
                self.progress.configure(value=i / max(n, 1) * 100)
                self.var_status.set(f"正在处理第 {i} / {n} 张照片…")
                return
            if kind in self.stats:
                self.stats[kind] += 1
            if text:
                self.log(text)
            elif self.current["verbose"] and kind != "skip":
                self.log(line)

        def finish(self, returncode):
            st = self.stats
            self.proc = None
            self.btn_run.state(["!disabled"] if self.exiftool_ok else ["disabled"])
            self.btn_stop.state(["disabled"])
            if returncode == 0:
                self.progress.configure(value=100)
                summary = f"完成！合成动态照片 {st['converted']} 张"
                if self.current["copy_unmuxed"]:
                    summary += f"，复制普通照片和视频 {st['copied']} 个"
                if st["skipped"]:
                    summary += f"，跳过 {st['skipped']} 个"
                if st["error"]:
                    summary += f"，出错 {st['error']} 处（见上方日志）"
                self.var_status.set(summary)
                self.log("")
                self.log("🎉 " + summary)
                self.btn_open.state(["!disabled"])
            elif returncode in (-15, -9):
                self.var_status.set("已停止")
                self.log("⏹ 已停止。")
                if Path(self.current["output_directory"]).exists():
                    self.btn_open.state(["!disabled"])
            else:
                self.var_status.set("转换失败，请查看日志（可以打开「显示详细日志」再试一次）")
                self.log(f"❌ 转换失败（代码 {returncode}）")

        def stop(self):
            if self.proc and self.proc.poll() is None:
                self.proc.terminate()

        def on_close(self):
            if self.proc and self.proc.poll() is None:
                if not messagebox.askyesno(APP_NAME, "正在转换，确定要退出吗？"):
                    return
                self.proc.terminate()
            save_settings(self.collect_settings())
            self.root.destroy()

    root = tk.Tk()
    App(root)
    if selftest:
        root.after(1500, root.destroy)
    root.mainloop()


if __name__ == "__main__":
    if "--cli" in sys.argv:
        run_cli(sys.argv[sys.argv.index("--cli") + 1:])
    else:
        run_gui(selftest="--selftest" in sys.argv)

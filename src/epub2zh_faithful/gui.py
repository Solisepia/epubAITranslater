from __future__ import annotations

from argparse import Namespace
from dataclasses import asdict
from datetime import datetime
import json
import os
from pathlib import Path
from queue import Empty, Queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable

import yaml

from .config import STYLE_OPTIONS, AppConfig, load_config, normalize_style
from .pipeline import run_translation
from .termbase_generator import GenerateOptions, generate_termbase

APP_HOME = Path(os.environ.get("APPDATA", str(Path.home()))) / "epub2zh-faithful"
UI_STATE_PATH = APP_HOME / "ui_state.json"
DEFAULT_CONFIG_PATH = APP_HOME / "config.yaml"
DEFAULT_TERMBASE_PATH = APP_HOME / "termbase.yaml"

FIELD_HELP: dict[str, str] = {
    "Input EPUB": "选择要翻译的源 EPUB 文件。",
    "Output EPUB": "翻译后输出文件路径。建议使用新文件名避免覆盖原书。",
    "Provider": "全局模式：openai/deepseek/dashscope/mixed/mock。mixed 可分开指定 draft 与 revise。",
    "Draft Provider": "初译阶段使用的服务商。",
    "Revise Provider": "二次处理阶段使用的服务商。设为 none 表示不做二次处理。",
    "Model": "默认模型名。若 Draft/Revise Model 留空则回退到这里。",
    "Draft Model": "初译阶段模型名（可留空）。",
    "Revise Model": "二次处理阶段模型名（可留空）。",
    "Cache SQLite": "缓存数据库路径。用于断点续跑和避免重复 API 调用。",
    "Config": "主配置文件路径（config.yaml/json）。可点击 Edit Config 在界面内编辑。",
    "Termbase": "术语表路径。翻译与术语一致性 QA 会读取该文件。",
    "Max Concurrency": "并发批次数。越大越快但更容易触发限流。",
    "OpenAI Key": "OpenAI API Key。仅当前 GUI 进程生效，不会自动保存到磁盘。",
    "DeepSeek Key": "DeepSeek API Key。仅当前 GUI 进程生效，不会自动保存到磁盘。",
    "DashScope Key": "阿里云百炼 API Key。仅当前 GUI 进程生效，不会自动保存到磁盘。",
    "Resume": "开启后命中缓存的段落不会重翻，适合断点续跑。",
    "Keep Workdir": "保留临时解包目录，便于排错；会占用更多磁盘。",
    "Logs": "显示运行阶段、批次进度、错误和输出路径。",
}

CONFIG_FIELD_HELP: dict[str, str] = {
    "style": "翻译风格枚举。可选：`faithful_literal`、`faithful_fluent`、`literary_cn`、`concise_cn`。会直接影响 LLM 的翻译与润色风格提示词。",
    "translate_toc": "是否翻译目录（TOC）标题。勾选后目录文本会被翻译；取消则保留原文目录。",
    "translate_titles": "是否翻译 HTML `title` 节点。勾选会翻译页面标题；取消可避免标题类误翻或误报。",
    "latin_mode.translate_normally": "拉丁字母文本是否按普通文本翻译。勾选会正常翻译英文段；取消可更多保留原文。",
    "table_mode.preserve_numbers": "表格中是否强制保留数字。勾选可减少数字被改写的风险。",
    "table_mode.preserve_abbreviations": "表格中是否保留缩写。勾选可减少术语缩写被误翻。",
    "segmentation.max_chars_per_segment": "单段最大字符数。值越小分段越细、上下文更少；值越大单次段落更长。",
    "segmentation.max_chars_per_batch": "单批最大字符数。值越大请求更少但每次负载更重，可能更易触发限流。",
    "segmentation.max_segments_per_batch": "单批最多段数。适当调小可提升稳定性，调大可提升吞吐。",
    "segmentation.sentence_split_fallback": "分段超长时是否按句子兜底切分。勾选通常更稳，减少硬切断句。",
    "context.use_prev_segment": "是否给模型传入上一段上下文。勾选有助于衔接一致性。",
    "context.prev_segment_chars": "上下文使用的上一段字符数。越大上下文越多，但提示词也更长。",
    "context.use_term_hints": "是否把命中的术语提示传给模型。建议勾选以提升术语一致性。",
    "llm.temperature": "采样温度（常用 0.0）。越低越稳定可复现，越高越发散。",
    "llm.max_retries": "同一请求最大重试次数。增大可提高成功率，但失败时总耗时更长。",
    "llm.retry_backoff_seconds": "重试等待秒数列表，逗号分隔（如 `1,2,4,8`）。用于控制每次重试间隔。",
    "llm.timeout_seconds": "单次请求超时秒数。网络慢或模型响应慢时可适当调大。",
    "qa.warn_ratio_limit": "QA 警告占比阈值（0~1）。越小越严格，越大越宽松。",
    "qa.warn_min_cap": "QA 警告最小上限（整数）。与比例阈值共同决定是否通过 QA gate。",
}

STYLE_SCENARIO_HINT = (
    "推荐场景: "
    "faithful_literal=技术文档/术语敏感; "
    "faithful_fluent=通用阅读; "
    "literary_cn=小说/散文; "
    "concise_cn=摘要/速读。"
)


class HoverTooltip:
    def __init__(self, widget: tk.Widget, text: str, delay_ms: int = 450) -> None:
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self.tip_window: tk.Toplevel | None = None
        self.after_id: str | None = None

        self.widget.bind("<Enter>", self._on_enter, add="+")
        self.widget.bind("<Leave>", self._on_leave, add="+")
        self.widget.bind("<ButtonPress>", self._on_leave, add="+")

    def _on_enter(self, _event: tk.Event) -> None:
        self._schedule()

    def _on_leave(self, _event: tk.Event) -> None:
        self._unschedule()
        self._hide()

    def _schedule(self) -> None:
        self._unschedule()
        self.after_id = self.widget.after(self.delay_ms, self._show)

    def _unschedule(self) -> None:
        if self.after_id is not None:
            self.widget.after_cancel(self.after_id)
            self.after_id = None

    def _show(self) -> None:
        if self.tip_window is not None:
            return
        x = self.widget.winfo_rootx() + 14
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self.tip_window = tk.Toplevel(self.widget)
        self.tip_window.wm_overrideredirect(True)
        self.tip_window.wm_geometry(f"+{x}+{y}")
        label = tk.Label(
            self.tip_window,
            text=self.text,
            justify=tk.LEFT,
            background="#fffde8",
            relief=tk.SOLID,
            borderwidth=1,
            wraplength=360,
            padx=6,
            pady=4,
        )
        label.pack()

    def _hide(self) -> None:
        if self.tip_window is not None:
            self.tip_window.destroy()
            self.tip_window = None


class ConfigEditorDialog:
    def __init__(self, parent: tk.Tk, config_path: str, on_saved: Callable[[str], None]) -> None:
        self.parent = parent
        self.config_path = Path(config_path)
        self.on_saved = on_saved
        self.config = load_config(str(self.config_path)) if self.config_path.exists() else AppConfig()

        self.win = tk.Toplevel(parent)
        self.win.title("Edit Config")
        self.win.transient(parent)
        self.win.grab_set()

        self.vars: dict[str, tk.Variable] = {}
        self._tooltips: list[HoverTooltip] = []
        self._build()
        self._fit_window_to_content()

    def _build(self) -> None:
        outer = ttk.Frame(self.win, padding=10)
        outer.pack(fill=tk.BOTH, expand=True)

        self._add_enum(outer, 0, "style", self.config.style, list(STYLE_OPTIONS))
        self._add_hint(outer, 1, STYLE_SCENARIO_HINT)

        self._add_bool(outer, 2, "translate_toc", self.config.translate_toc)
        self._add_bool(outer, 3, "translate_titles", self.config.translate_titles)

        self._add_int(outer, 4, "segmentation.max_chars_per_segment", self.config.segmentation.max_chars_per_segment)
        self._add_int(outer, 5, "segmentation.max_chars_per_batch", self.config.segmentation.max_chars_per_batch)
        self._add_int(outer, 6, "segmentation.max_segments_per_batch", self.config.segmentation.max_segments_per_batch)

        self._add_int(outer, 7, "context.prev_segment_chars", self.config.context.prev_segment_chars)

        self._add_float(outer, 8, "llm.temperature", self.config.llm.temperature)
        self._add_int(outer, 9, "llm.max_retries", self.config.llm.max_retries)
        self._add_str(outer, 10, "llm.retry_backoff_seconds", ",".join(str(x) for x in self.config.llm.retry_backoff_seconds))
        self._add_int(outer, 11, "llm.timeout_seconds", self.config.llm.timeout_seconds)

        self._add_float(outer, 12, "qa.warn_ratio_limit", self.config.qa.warn_ratio_limit)
        self._add_int(outer, 13, "qa.warn_min_cap", self.config.qa.warn_min_cap)

        for i in range(14):
            outer.rowconfigure(i, weight=0)
        outer.columnconfigure(1, weight=1)

        actions = ttk.Frame(outer)
        actions.grid(row=14, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttk.Button(actions, text="Save", command=self._save).pack(side=tk.LEFT)
        ttk.Button(actions, text="Cancel", command=self.win.destroy).pack(side=tk.LEFT, padx=(8, 0))

    def _fit_window_to_content(self) -> None:
        self.win.update_idletasks()
        req_w = self.win.winfo_reqwidth()
        req_h = self.win.winfo_reqheight()
        screen_w = self.win.winfo_screenwidth()
        screen_h = self.win.winfo_screenheight()
        width = min(req_w + 20, screen_w - 80)
        height = min(req_h + 20, screen_h - 100)
        self.win.geometry(f"{width}x{height}")

    def _add_str(self, parent: ttk.Frame, row: int, key: str, value: str) -> None:
        var = tk.StringVar(value=str(value))
        self.vars[key] = var
        label = ttk.Label(parent, text=key)
        label.grid(row=row, column=0, sticky="w", pady=2)
        entry = ttk.Entry(parent, textvariable=var)
        entry.grid(row=row, column=1, sticky="ew", pady=2)
        self._attach_config_help(key, label, entry)

    def _add_enum(self, parent: ttk.Frame, row: int, key: str, value: str, options: list[str]) -> None:
        normalized_value = normalize_style(str(value)) if key == "style" else str(value)
        var = tk.StringVar(value=normalized_value)
        self.vars[key] = var
        label = ttk.Label(parent, text=key)
        label.grid(row=row, column=0, sticky="w", pady=2)
        combo = ttk.Combobox(parent, textvariable=var, values=options, state="readonly")
        combo.grid(row=row, column=1, sticky="ew", pady=2)
        self._attach_config_help(key, label, combo)

    def _add_hint(self, parent: ttk.Frame, row: int, text: str) -> None:
        ttk.Label(parent, text=text, foreground="#555555", wraplength=560, justify=tk.LEFT).grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(2, 6),
        )

    def _add_int(self, parent: ttk.Frame, row: int, key: str, value: int) -> None:
        self._add_str(parent, row, key, str(int(value)))

    def _add_float(self, parent: ttk.Frame, row: int, key: str, value: float) -> None:
        self._add_str(parent, row, key, str(float(value)))

    def _add_bool(self, parent: ttk.Frame, row: int, key: str, value: bool) -> None:
        var = tk.BooleanVar(value=bool(value))
        self.vars[key] = var
        label = ttk.Label(parent, text=key)
        label.grid(row=row, column=0, sticky="w", pady=2)
        check = ttk.Checkbutton(parent, variable=var)
        check.grid(row=row, column=1, sticky="w", pady=2)
        self._attach_config_help(key, label, check)

    def _attach_config_help(self, key: str, *widgets: tk.Widget) -> None:
        tip = CONFIG_FIELD_HELP.get(key)
        if not tip:
            return
        for widget in widgets:
            self._tooltips.append(HoverTooltip(widget, tip))

    def _save(self) -> None:
        try:
            cfg = AppConfig()
            cfg.style = normalize_style(self._get_str("style"))
            cfg.translate_toc = self._get_bool("translate_toc")
            cfg.translate_titles = self._get_bool("translate_titles")

            cfg.segmentation.max_chars_per_segment = self._get_int("segmentation.max_chars_per_segment")
            cfg.segmentation.max_chars_per_batch = self._get_int("segmentation.max_chars_per_batch")
            cfg.segmentation.max_segments_per_batch = self._get_int("segmentation.max_segments_per_batch")
            cfg.context.prev_segment_chars = self._get_int("context.prev_segment_chars")

            cfg.llm.temperature = self._get_float("llm.temperature")
            cfg.llm.max_retries = self._get_int("llm.max_retries")
            cfg.llm.retry_backoff_seconds = self._get_int_list("llm.retry_backoff_seconds")
            cfg.llm.timeout_seconds = self._get_int("llm.timeout_seconds")

            cfg.qa.warn_ratio_limit = self._get_float("qa.warn_ratio_limit")
            cfg.qa.warn_min_cap = self._get_int("qa.warn_min_cap")

            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            self.config_path.write_text(yaml.safe_dump(asdict(cfg), sort_keys=False, allow_unicode=True), encoding="utf-8")
            self.on_saved(str(self.config_path))
            self.win.destroy()
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Config Error", f"Failed to save config:\n{exc}")

    def _get_str(self, key: str) -> str:
        return str(self.vars[key].get()).strip()

    def _get_bool(self, key: str) -> bool:
        return bool(self.vars[key].get())

    def _get_int(self, key: str) -> int:
        return int(str(self.vars[key].get()).strip())

    def _get_float(self, key: str) -> float:
        return float(str(self.vars[key].get()).strip())

    def _get_int_list(self, key: str) -> list[int]:
        raw = self._get_str(key)
        if not raw:
            return []
        values = [part.strip() for part in raw.split(",") if part.strip()]
        return [int(v) for v in values]


class TranslatorUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("epub2zh faithful translator")
        self.root.geometry("980x700")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.is_running = False
        self.log_queue: Queue[str] = Queue()
        self._save_job: str | None = None
        self._tooltips: list[HoverTooltip] = []

        self._ensure_default_files()

        self.input_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.provider = tk.StringVar(value="dashscope")
        self.draft_provider = tk.StringVar(value="dashscope")
        self.revise_provider = tk.StringVar(value="none")
        self.model = tk.StringVar(value="qwen-plus")
        self.draft_model = tk.StringVar()
        self.revise_model = tk.StringVar()
        self.cache_path = tk.StringVar(value=str(APP_HOME / "cache.sqlite"))
        self.config_path = tk.StringVar(value=str(DEFAULT_CONFIG_PATH))
        self.termbase_path = tk.StringVar(value=str(DEFAULT_TERMBASE_PATH))
        self.max_concurrency = tk.StringVar(value="4")
        self.openai_key = tk.StringVar()
        self.deepseek_key = tk.StringVar()
        self.dashscope_key = tk.StringVar()
        self.resume = tk.BooleanVar(value=False)
        self.keep_workdir = tk.BooleanVar(value=False)
        self.status_text = tk.StringVar(value="idle")

        self._build()
        self._load_ui_state()
        self.provider.trace_add("write", self._on_provider_changed)
        self._bind_persistence()
        self._pump_logs()

    def _ensure_default_files(self) -> None:
        APP_HOME.mkdir(parents=True, exist_ok=True)
        if not DEFAULT_CONFIG_PATH.exists():
            DEFAULT_CONFIG_PATH.write_text(yaml.safe_dump(asdict(AppConfig()), sort_keys=False, allow_unicode=True), encoding="utf-8")
        if not DEFAULT_TERMBASE_PATH.exists():
            DEFAULT_TERMBASE_PATH.write_text(
                yaml.safe_dump({"version": 1, "terms": []}, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )

    def _build(self) -> None:
        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        row = 0
        row = self._path_row(frame, row, "Input EPUB", self.input_path, is_save=False, kind="epub")
        row = self._path_row(frame, row, "Output EPUB", self.output_path, is_save=True, kind="epub")
        row = self._simple_row(frame, row, "Model", self.model)
        row = self._simple_row(frame, row, "Draft Model", self.draft_model)
        row = self._simple_row(frame, row, "Revise Model", self.revise_model)
        row = self._path_row(frame, row, "Cache SQLite", self.cache_path, is_save=True, kind="sqlite")
        row = self._path_row(frame, row, "Config", self.config_path, is_save=True, kind="yaml")
        row = self._path_row(frame, row, "Termbase", self.termbase_path, is_save=True, kind="yaml")
        row = self._simple_row(frame, row, "Max Concurrency", self.max_concurrency)

        row = self._entry_row(frame, row, "Provider", self.provider, values=["openai", "deepseek", "dashscope", "mixed", "mock"])
        row = self._entry_row(frame, row, "Draft Provider", self.draft_provider, values=["openai", "deepseek", "dashscope", "mock"])
        row = self._entry_row(frame, row, "Revise Provider", self.revise_provider, values=["openai", "deepseek", "dashscope", "none", "mock"])

        row = self._secret_row(frame, row, "OpenAI Key", self.openai_key)
        row = self._secret_row(frame, row, "DeepSeek Key", self.deepseek_key)
        row = self._secret_row(frame, row, "DashScope Key", self.dashscope_key)

        options = ttk.Frame(frame)
        options.grid(row=row, column=0, columnspan=3, sticky="w", pady=(8, 0))
        resume_btn = ttk.Checkbutton(options, text="Resume", variable=self.resume)
        resume_btn.pack(side=tk.LEFT, padx=(0, 14))
        keep_btn = ttk.Checkbutton(options, text="Keep Workdir", variable=self.keep_workdir)
        keep_btn.pack(side=tk.LEFT, padx=(0, 14))
        self._attach_tooltip(resume_btn, "Resume")
        self._attach_tooltip(keep_btn, "Keep Workdir")
        row += 1

        actions = ttk.Frame(frame)
        actions.grid(row=row, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        self.run_btn = ttk.Button(actions, text="Start Translation", command=self._start)
        self.run_btn.pack(side=tk.LEFT)

        self.generate_btn = ttk.Button(actions, text="Generate Termbase", command=self._start_generate_termbase)
        self.generate_btn.pack(side=tk.LEFT, padx=(8, 0))

        self.edit_config_btn = ttk.Button(actions, text="Edit Config", command=self._open_config_editor)
        self.edit_config_btn.pack(side=tk.LEFT, padx=(8, 0))

        ttk.Button(actions, text="Open Output Folder", command=self._open_output_folder).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(actions, textvariable=self.status_text).pack(side=tk.RIGHT)
        row += 1

        logs_label = ttk.Label(frame, text="Logs")
        logs_label.grid(row=row, column=0, sticky="w", pady=(8, 2))
        self._attach_tooltip(logs_label, "Logs")
        row += 1

        self.log = tk.Text(frame, height=14, wrap=tk.WORD)
        self.log.grid(row=row, column=0, columnspan=3, sticky="nsew")
        row += 1

        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.log.yview)
        scrollbar.grid(row=row - 1, column=3, sticky="ns")
        self.log.configure(yscrollcommand=scrollbar.set)

        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(row - 1, weight=1)

    def _path_row(self, parent: ttk.Frame, row: int, label: str, var: tk.StringVar, is_save: bool, kind: str) -> int:
        self._make_field_label(parent, row, label)
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky="ew", pady=2)
        ttk.Button(parent, text="Browse", command=lambda: self._choose_file(var, is_save, kind)).grid(row=row, column=2, padx=(8, 0), pady=2)
        return row + 1

    def _simple_row(self, parent: ttk.Frame, row: int, label: str, var: tk.StringVar) -> int:
        self._make_field_label(parent, row, label)
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, columnspan=2, sticky="ew", pady=2)
        return row + 1

    def _entry_row(self, parent: ttk.Frame, row: int, label: str, var: tk.StringVar, values: list[str]) -> int:
        self._make_field_label(parent, row, label)
        box = ttk.Combobox(parent, textvariable=var, values=values, state="readonly")
        box.grid(row=row, column=1, columnspan=2, sticky="ew", pady=2)
        return row + 1

    def _secret_row(self, parent: ttk.Frame, row: int, label: str, var: tk.StringVar) -> int:
        self._make_field_label(parent, row, label)
        ttk.Entry(parent, textvariable=var, show="*").grid(row=row, column=1, columnspan=2, sticky="ew", pady=2)
        return row + 1

    def _make_field_label(self, parent: ttk.Frame, row: int, label: str) -> ttk.Label:
        widget = ttk.Label(parent, text=label)
        widget.grid(row=row, column=0, sticky="w", pady=2)
        self._attach_tooltip(widget, label)
        return widget

    def _attach_tooltip(self, widget: tk.Widget, field_name: str) -> None:
        tip = FIELD_HELP.get(field_name)
        if not tip:
            return
        self._tooltips.append(HoverTooltip(widget, tip))

    def _choose_file(self, var: tk.StringVar, is_save: bool, kind: str) -> None:
        default_ext, filetypes = self._file_dialog_spec(kind)
        if is_save:
            path = filedialog.asksaveasfilename(defaultextension=default_ext, filetypes=filetypes)
        else:
            path = filedialog.askopenfilename(filetypes=filetypes)
        if path:
            var.set(path)

    def _file_dialog_spec(self, kind: str) -> tuple[str, list[tuple[str, str]]]:
        if kind == "yaml":
            return ".yaml", [("YAML", "*.yaml *.yml"), ("All", "*.*")]
        if kind == "sqlite":
            return ".sqlite", [("SQLite", "*.sqlite *.db"), ("All", "*.*")]
        return ".epub", [("EPUB", "*.epub"), ("All", "*.*")]

    def _on_provider_changed(self, *_: object) -> None:
        current = self.provider.get()
        if current == "openai":
            self.draft_provider.set("openai")
            self.revise_provider.set("none")
        elif current == "deepseek":
            self.draft_provider.set("deepseek")
            self.revise_provider.set("none")
        elif current == "dashscope":
            self.draft_provider.set("dashscope")
            self.revise_provider.set("none")
        elif current == "mixed":
            if self.draft_provider.get() not in {"openai", "deepseek", "dashscope", "mock"}:
                self.draft_provider.set("dashscope")
            if self.revise_provider.get() not in {"openai", "deepseek", "dashscope", "none", "mock"}:
                self.revise_provider.set("none")

    def _open_config_editor(self) -> None:
        path = self.config_path.get().strip() or str(DEFAULT_CONFIG_PATH)

        def on_saved(saved_path: str) -> None:
            self.config_path.set(saved_path)
            self._log(f"Config saved: {saved_path}")

        ConfigEditorDialog(self.root, path, on_saved)

    def _open_output_folder(self) -> None:
        out = self.output_path.get().strip()
        if not out:
            messagebox.showinfo("Info", "Set Output EPUB first")
            return
        folder = Path(out).resolve().parent
        if os.name == "nt":
            os.startfile(str(folder))  # type: ignore[attr-defined]
        else:
            messagebox.showinfo("Info", f"Output folder: {folder}")

    def _start(self) -> None:
        if self.is_running:
            return

        args = self._build_args()
        if args is None:
            return

        self.is_running = True
        self.run_btn.configure(state="disabled")
        self.generate_btn.configure(state="disabled")
        self.edit_config_btn.configure(state="disabled")
        self.status_text.set("running")
        self._save_ui_state()
        self._log("Starting translation...")

        worker = threading.Thread(target=self._run_worker, args=(args,), daemon=True)
        worker.start()

    def _start_generate_termbase(self) -> None:
        if self.is_running:
            return

        input_epub = self.input_path.get().strip()
        output_termbase = self.termbase_path.get().strip()
        if not input_epub or not Path(input_epub).exists():
            messagebox.showerror("Error", "Input EPUB is missing")
            return
        if not output_termbase:
            messagebox.showerror("Error", "Termbase path is missing")
            return

        if self.openai_key.get().strip():
            os.environ["OPENAI_API_KEY"] = self.openai_key.get().strip()
        if self.deepseek_key.get().strip():
            os.environ["DEEPSEEK_API_KEY"] = self.deepseek_key.get().strip()
        if self.dashscope_key.get().strip():
            os.environ["DASHSCOPE_API_KEY"] = self.dashscope_key.get().strip()

        fill_provider = self.provider.get().strip()
        if fill_provider == "mixed":
            fill_provider = self.draft_provider.get().strip() or "dashscope"
        if fill_provider not in {"openai", "deepseek", "dashscope", "mock"}:
            fill_provider = "dashscope"
        fill_model = self.model.get().strip() or "qwen-plus"
        config_path = self.config_path.get().strip() or None

        self.is_running = True
        self.run_btn.configure(state="disabled")
        self.generate_btn.configure(state="disabled")
        self.edit_config_btn.configure(state="disabled")
        self.status_text.set("generating termbase")
        self._save_ui_state()
        self._log("Starting termbase generation...")

        worker = threading.Thread(
            target=self._run_generate_worker,
            args=(input_epub, output_termbase, fill_provider, fill_model, config_path),
            daemon=True,
        )
        worker.start()

    def _build_args(self) -> Namespace | None:
        input_epub = self.input_path.get().strip()
        output_epub = self.output_path.get().strip()
        if not input_epub or not Path(input_epub).exists():
            messagebox.showerror("Error", "Input EPUB is missing")
            return None
        if not output_epub:
            messagebox.showerror("Error", "Output EPUB is missing")
            return None

        try:
            max_concurrency = int(self.max_concurrency.get().strip())
            if max_concurrency <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Error", "Max Concurrency must be a positive integer")
            return None

        if self.openai_key.get().strip():
            os.environ["OPENAI_API_KEY"] = self.openai_key.get().strip()
        if self.deepseek_key.get().strip():
            os.environ["DEEPSEEK_API_KEY"] = self.deepseek_key.get().strip()
        if self.dashscope_key.get().strip():
            os.environ["DASHSCOPE_API_KEY"] = self.dashscope_key.get().strip()

        provider = self.provider.get().strip()
        draft_provider = self.draft_provider.get().strip() or None
        revise_provider = self.revise_provider.get().strip() or None

        return Namespace(
            input=input_epub,
            output=output_epub,
            provider=provider,
            draft_provider=draft_provider,
            revise_provider=revise_provider,
            model=self.model.get().strip() or "gpt-5-mini",
            draft_model=self.draft_model.get().strip() or None,
            revise_model=self.revise_model.get().strip() or None,
            resume=bool(self.resume.get()),
            cache=self.cache_path.get().strip() or str(APP_HOME / "cache.sqlite"),
            termbase=self.termbase_path.get().strip() or None,
            config=self.config_path.get().strip() or None,
            max_concurrency=max_concurrency,
            keep_workdir=bool(self.keep_workdir.get()),
        )

    def _run_worker(self, args: Namespace) -> None:
        code = run_translation(args, progress_cb=self._enqueue_progress)
        self.root.after(0, lambda: self._finish_translation(code))

    def _run_generate_worker(
        self,
        input_epub: str,
        output_termbase: str,
        fill_provider: str,
        fill_model: str,
        config_path: str | None,
    ) -> None:
        try:
            cfg = load_config(config_path)
            stats = generate_termbase(
                input_epub=input_epub,
                output_path=output_termbase,
                options=GenerateOptions(
                    min_freq=2,
                    max_terms=300,
                    include_single_word=False,
                    merge_existing=True,
                    fill_empty_targets=True,
                    fill_provider=fill_provider,
                    fill_model=fill_model,
                    fill_batch_size=40,
                ),
                progress_cb=self._enqueue_progress,
                llm_config=cfg,
            )
            self.root.after(0, lambda: self._finish_generate(stats, output_termbase))
        except Exception as exc:  # noqa: BLE001
            self.root.after(0, lambda: self._finish_generate_error(str(exc)))

    def _finish_translation(self, code: int) -> None:
        self.is_running = False
        self.run_btn.configure(state="normal")
        self.generate_btn.configure(state="normal")
        self.edit_config_btn.configure(state="normal")
        self.status_text.set(f"finished (exit={code})")

        out = Path(self.output_path.get().strip())
        artifacts = out.parent / f"{out.stem}_artifacts"
        self._log(f"Finished with exit code: {code}")
        self._log(f"Output: {out}")
        self._log(f"QA report: {artifacts / 'qa_report.json'}")
        self._log(f"QA summary: {artifacts / 'qa_summary.md'}")

        if code == 0:
            messagebox.showinfo("Done", "Translation finished: QA passed")
        elif code == 2:
            messagebox.showwarning("Finished", "Translation finished but QA has errors (exit=2)")
        else:
            messagebox.showerror("Failed", "Translation failed (exit=1)")

    def _finish_generate(self, stats: dict[str, int], output_termbase: str) -> None:
        self.is_running = False
        self.run_btn.configure(state="normal")
        self.generate_btn.configure(state="normal")
        self.edit_config_btn.configure(state="normal")
        self.status_text.set("termbase generated")
        self._log(
            "Termbase generated: "
            f"scanned={stats['scanned_text_nodes']} candidates={stats['candidate_terms']} "
            f"added={stats['generated_terms']} filled={stats.get('filled_targets', 0)} "
            f"rejected_no_cjk={stats.get('rejected_non_cjk_targets', 0)} "
            f"cleared_no_cjk={stats.get('cleared_non_cjk_targets', 0)} "
            f"total={stats['total_terms_in_file']}"
        )
        self._log(f"Termbase path: {Path(output_termbase).resolve()}")
        messagebox.showinfo("Done", f"Termbase generated:\n{output_termbase}")

    def _finish_generate_error(self, message: str) -> None:
        self.is_running = False
        self.run_btn.configure(state="normal")
        self.generate_btn.configure(state="normal")
        self.edit_config_btn.configure(state="normal")
        self.status_text.set("generation failed")
        self._log(f"Termbase generation failed: {message}")
        messagebox.showerror("Failed", f"Termbase generation failed:\n{message}")

    def _log(self, text: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self.log.insert(tk.END, f"[{ts}] {text}\n")
        self.log.see(tk.END)

    def _enqueue_progress(self, text: str) -> None:
        self.log_queue.put(text)

    def _pump_logs(self) -> None:
        while True:
            try:
                item = self.log_queue.get_nowait()
            except Empty:
                break
            self._log(item)
        self.root.after(150, self._pump_logs)

    def _bind_persistence(self) -> None:
        for var in self._persistable_vars().values():
            var.trace_add("write", lambda *_: self._schedule_state_save())

    def _schedule_state_save(self) -> None:
        if self._save_job is not None:
            self.root.after_cancel(self._save_job)
        self._save_job = self.root.after(400, self._save_ui_state)

    def _load_ui_state(self) -> None:
        if not UI_STATE_PATH.exists():
            return
        try:
            data = json.loads(UI_STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return

        vars_map = self._persistable_vars()
        for key, value in data.items():
            var = vars_map.get(key)
            if var is None:
                continue
            if isinstance(var, tk.BooleanVar):
                var.set(bool(value))
            else:
                var.set(str(value))

    def _save_ui_state(self) -> None:
        self._save_job = None
        data: dict[str, object] = {}
        for key, var in self._persistable_vars().items():
            data[key] = var.get()
        try:
            UI_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
            UI_STATE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            return

    def _persistable_vars(self) -> dict[str, tk.Variable]:
        # API keys are intentionally excluded from auto-save.
        return {
            "input_path": self.input_path,
            "output_path": self.output_path,
            "provider": self.provider,
            "draft_provider": self.draft_provider,
            "revise_provider": self.revise_provider,
            "model": self.model,
            "draft_model": self.draft_model,
            "revise_model": self.revise_model,
            "cache_path": self.cache_path,
            "config_path": self.config_path,
            "termbase_path": self.termbase_path,
            "max_concurrency": self.max_concurrency,
            "resume": self.resume,
            "keep_workdir": self.keep_workdir,
        }

    def _on_close(self) -> None:
        self._save_ui_state()
        self.root.destroy()


def main() -> int:
    root = tk.Tk()
    TranslatorUI(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

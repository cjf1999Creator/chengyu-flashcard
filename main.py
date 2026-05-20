"""
成语积累与复习 - 闪卡应用主程序
macOS 风格 UI，使用 tkinter 构建
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import random
import re
import os
import sys
import calendar
from datetime import datetime, date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from parser import parse_idiom_text, parse_multiple_idioms, format_flashcard_back, idiom_to_editable_text, get_last_parse_errors
from storage import (
    load_idioms, add_idiom, add_idioms_batch, update_review_stats,
    set_mastery_level, delete_idiom, get_idiom_names, search_idioms, get_review_stats_summary
)


# ==================== 颜色插值辅助函数 ====================

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def rgb_to_hex(r, g, b):
    return f'#{int(r):02x}{int(g):02x}{int(b):02x}'

def lerp_color(color1, color2, t):
    r1, g1, b1 = hex_to_rgb(color1)
    r2, g2, b2 = hex_to_rgb(color2)
    return rgb_to_hex(r1 + (r2 - r1) * t, g1 + (g2 - g1) * t, b1 + (b2 - b1) * t)


# ==================== macOS 风格颜色常量 ====================

class C:
    """macOS 系统配色"""
    BG = "#F5F5F7"
    SIDEBAR = "#E8E8ED"
    SURFACE = "#FFFFFF"
    BORDER = "#D2D2D7"
    BORDER_LIGHT = "#E5E5EA"

    TEXT_PRIMARY = "#1D1D1F"
    TEXT_SECONDARY = "#86868B"
    TEXT_TERTIARY = "#AEAEB2"
    TEXT_PLACEHOLDER = "#C7C7CC"

    ACCENT = "#007AFF"
    ACCENT_HOVER = "#0062CC"
    GREEN = "#34C759"
    GREEN_BG = "#E8F8ED"
    ORANGE = "#FF9500"
    ORANGE_BG = "#FFF4E5"
    RED = "#FF3B30"
    RED_BG = "#FFEDED"
    PURPLE = "#AF52DE"
    TEAL = "#5AC8FA"
    YELLOW_BG = "#FFF9E6"

    CARD_FRONT = "#FFFFFF"
    CARD_BACK = "#FFFBEB"

    LIST_BG = "#FFFFFF"
    LIST_SELECT = "#007AFF"
    LIST_SELECT_TEXT = "#FFFFFF"
    LIST_HOVER = "#F2F2F7"

    TOOLBAR = "#F8F8FA"
    TOOLBAR_BORDER = "#D1D1D6"

    PROGRESS_BG = "#E5E5EA"
    PROGRESS_FILL = "#007AFF"


class IdoimApp:
    """成语闪卡应用 - macOS 风格"""

    def __init__(self, root):
        self.root = root
        self.root.title("成语积累")
        self.root.geometry("960x700")
        self.root.minsize(800, 600)
        self.root.configure(bg=C.BG)

        # macOS 字体
        if sys.platform == "darwin":
            self._cn_font = "PingFang SC"
            self._ui_font = "Helvetica Neue"
            self._mono_font = "Menlo"
        else:
            self._cn_font = "Microsoft YaHei"
            self._ui_font = "Segoe UI"
            self._mono_font = "Consolas"

        self.font_title = (self._ui_font, 15, "bold")
        self.font_normal = (self._ui_font, 12)
        self.font_button = (self._ui_font, 11)
        self.font_small = (self._ui_font, 10)
        self.font_button_big = (self._ui_font, 12, "bold")
        self.font_section = (self._cn_font, 13, "bold")

        # 闪卡字体
        self._card_front_size = 36
        self._card_back_size = 13
        self.font_card_front = (self._cn_font, self._card_front_size, "bold")
        self.font_card_back = (self._cn_font, self._card_back_size)

        # 复习状态
        self.current_review_list = []
        self.current_index = 0
        self.is_showing_back = False
        self._animating = False

        # 编辑状态
        self.is_editing = False
        self.editing_idiom_name = None

        self._build_ui()
        self._bind_shortcuts()
        self._refresh_stats()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        self.root.destroy()

    # ==================== macOS 风格组件工厂 ====================

    def _mac_button(self, parent, text, command, color=C.ACCENT, fg="white", font=None, padx=16, pady=6, **kw):
        """创建 macOS 风格按钮"""
        font = font or self.font_button
        btn = tk.Button(
            parent, text=text, command=command,
            font=font, bg=color, fg=fg,
            activebackground=self._darken(color, 0.1), activeforeground=fg,
            relief=tk.FLAT, bd=0, padx=padx, pady=pady,
            cursor="hand2", highlightthickness=0,
            **kw
        )
        return btn

    @staticmethod
    def _darken(hex_color, amount):
        r, g, b = hex_to_rgb(hex_color)
        return rgb_to_hex(max(0, r - int(255 * amount)), max(0, g - int(255 * amount)), max(0, b - int(255 * amount)))

    # ==================== 快捷键 ====================

    def _bind_shortcuts(self):
        self.root.bind("<space>", lambda e: self._flip_card())
        self.root.bind("<j>", lambda e: self._prev_card())
        self.root.bind("<J>", lambda e: self._prev_card())
        self.root.bind("<k>", lambda e: self._next_card())
        self.root.bind("<K>", lambda e: self._next_card())
        self.root.bind("<Left>", lambda e: self._prev_card())
        self.root.bind("<Right>", lambda e: self._next_card())
        self.root.bind("<a>", lambda e: self._mark_card(True))
        self.root.bind("<A>", lambda e: self._mark_card(True))
        self.root.bind("<d>", lambda e: self._mark_card(False))
        self.root.bind("<D>", lambda e: self._mark_card(False))
        self.root.bind("<s>", lambda e: self._mark_mastered())
        self.root.bind("<S>", lambda e: self._mark_mastered())

    # ==================== 界面构建 ====================

    def _build_ui(self):
        # 顶部工具栏
        toolbar = tk.Frame(self.root, bg=C.TOOLBAR, height=52)
        toolbar.pack(fill=tk.X)
        toolbar.pack_propagate(False)

        tk.Label(
            toolbar, text="成语积累",
            font=(self._ui_font, 16, "bold"), bg=C.TOOLBAR, fg=C.TEXT_PRIMARY
        ).pack(side=tk.LEFT, padx=20, pady=10)

        self.stats_header = tk.Label(
            toolbar, text="",
            font=self.font_small, bg=C.TOOLBAR, fg=C.TEXT_SECONDARY
        )
        self.stats_header.pack(side=tk.RIGHT, padx=20, pady=10)

        # 工具栏底部细线
        tk.Frame(self.root, bg=C.TOOLBAR_BORDER, height=1).pack(fill=tk.X)

        # 标签页
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        self.import_frame = tk.Frame(notebook, bg=C.BG)
        notebook.add(self.import_frame, text="  导入  ")
        self._build_import_tab()

        self.library_frame = tk.Frame(notebook, bg=C.BG)
        notebook.add(self.library_frame, text="  成语库  ")
        self._build_library_tab()

        self.review_frame = tk.Frame(notebook, bg=C.BG)
        notebook.add(self.review_frame, text="  闪卡复习  ")
        self._build_review_tab()

        self.stats_frame = tk.Frame(notebook, bg=C.BG)
        notebook.add(self.stats_frame, text="  统计  ")
        self._build_stats_tab()

    # ==================== 导入成语 ====================

    def _build_import_tab(self):
        # 按钮区
        btn_frame = tk.Frame(self.import_frame, bg=C.BG)
        btn_frame.pack(fill=tk.X, padx=20, pady=(15, 10))

        self._mac_button(btn_frame, "从文件导入", self._import_from_file, color=C.PURPLE, padx=20, pady=8).pack(side=tk.LEFT, padx=(0, 8))
        self._mac_button(btn_frame, "预览解析结果", self._preview_import, color=C.ACCENT, padx=20, pady=8).pack(side=tk.LEFT, padx=(0, 8))
        self._mac_button(btn_frame, "清空", lambda: self.import_text.delete("1.0", tk.END), color=C.TEXT_TERTIARY, padx=14, pady=8).pack(side=tk.LEFT, padx=(0, 8))
        self._mac_button(btn_frame, "确认导入", self._do_import, color=C.GREEN, font=self.font_button_big, padx=24, pady=8).pack(side=tk.RIGHT)

        # PanedWindow
        import_paned = ttk.PanedWindow(self.import_frame, orient=tk.VERTICAL)
        import_paned.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 15))

        # 输入区
        top_frame = tk.Frame(import_paned, bg=C.SURFACE, highlightbackground=C.BORDER, highlightthickness=1)
        import_paned.add(top_frame, weight=1)

        tk.Label(top_frame, text="粘贴成语文本", font=(self.font_small[0], 11, "bold"), bg=C.SURFACE, fg=C.TEXT_SECONDARY, anchor=tk.W).pack(fill=tk.X, padx=12, pady=(10, 2))

        self.import_text = scrolledtext.ScrolledText(
            top_frame, font=(self._mono_font, 12), wrap=tk.WORD,
            bg=C.SURFACE, fg=C.TEXT_PRIMARY, insertbackground=C.ACCENT,
            selectbackground=C.ACCENT, selectforeground="white",
            relief=tk.FLAT, bd=0, padx=8, pady=6,
            highlightthickness=0
        )
        self.import_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        # 预览区
        bottom_frame = tk.Frame(import_paned, bg=C.SURFACE, highlightbackground=C.BORDER, highlightthickness=1)
        import_paned.add(bottom_frame, weight=1)

        tk.Label(bottom_frame, text="解析预览", font=(self.font_small[0], 11, "bold"), bg=C.SURFACE, fg=C.TEXT_SECONDARY, anchor=tk.W).pack(fill=tk.X, padx=12, pady=(10, 2))

        self.preview_text = scrolledtext.ScrolledText(
            bottom_frame, font=self.font_normal, wrap=tk.WORD,
            bg=C.SURFACE, fg=C.TEXT_PRIMARY,
            selectbackground=C.ACCENT, selectforeground="white",
            relief=tk.FLAT, bd=0, padx=8, pady=6,
            highlightthickness=0
        )
        self.preview_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

    def _preview_import(self):
        text = self.import_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("提示", "请先输入成语文本！")
            return

        idioms = parse_multiple_idioms(text)
        errors = get_last_parse_errors()
        self.preview_text.delete("1.0", tk.END)

        if not idioms and not errors:
            messagebox.showerror("错误", "未能解析出任何成语，请检查格式！")
            return

        for idiom in idioms:
            self.preview_text.insert(tk.END, f"{'─' * 40}\n")
            self.preview_text.insert(tk.END, format_flashcard_back(idiom))
            self.preview_text.insert(tk.END, "\n")

        if errors:
            self.preview_text.insert(tk.END, f"\n解析警告：\n")
            for err in errors:
                self.preview_text.insert(tk.END, f"  - {err}\n")

        if idioms:
            msg = f"成功解析 {len(idioms)} 个成语"
            if errors:
                msg += f"\n有 {len(errors)} 个警告"
            messagebox.showinfo("预览结果", msg)
        else:
            messagebox.showerror("解析失败", "未能解析出任何成语。\n\n" + "\n".join(errors[:5]))

    def _do_import(self):
        text = self.import_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("提示", "请先输入成语文本！")
            return

        idioms = parse_multiple_idioms(text)
        errors = get_last_parse_errors()

        if not idioms:
            err_msg = "\n".join(errors[:5]) if errors else "请检查格式是否正确。"
            messagebox.showerror("导入失败", f"未能解析出任何成语！\n\n{err_msg}")
            return

        count = add_idioms_batch(idioms)
        msg = f"成功导入 {count} 个成语！"
        if errors:
            msg += f"\n\n有 {len(errors)} 个卡片解析失败"
        messagebox.showinfo("导入完成", msg)

        self.import_text.delete("1.0", tk.END)
        self.preview_text.delete("1.0", tk.END)
        self._refresh_stats()
        self._refresh_library()

    def _import_from_file(self):
        filepath = filedialog.askopenfilename(
            title="选择成语文本文件",
            filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")]
        )
        if not filepath:
            return
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            self.import_text.delete("1.0", tk.END)
            self.import_text.insert("1.0", content)
            messagebox.showinfo("成功", "已加载文件内容，请预览后确认导入。")
        except Exception as e:
            messagebox.showerror("错误", f"读取文件失败: {e}")

    # ==================== Markdown 渲染 ====================

    def _render_markdown(self, widget, text, base_size=13):
        """将文本以 Markdown 风格渲染到 tkinter Text 控件"""
        sz = base_size
        widget.tag_configure("md_h1", font=(self._cn_font, sz + 4, "bold"), foreground=C.ACCENT, spacing1=12, spacing3=6)
        widget.tag_configure("md_h2", font=(self._cn_font, sz + 2, "bold"), foreground=C.ACCENT, spacing1=10, spacing3=4)
        widget.tag_configure("md_h3", font=(self._cn_font, sz + 1, "bold"), foreground=C.TEXT_PRIMARY, spacing1=6, spacing3=2)
        widget.tag_configure("md_bold", font=(self._cn_font, sz, "bold"), foreground=C.TEXT_PRIMARY)
        widget.tag_configure("md_italic", font=(self._cn_font, sz, "italic"), foreground=C.TEXT_SECONDARY)
        widget.tag_configure("md_code", font=(self._mono_font, sz - 1), foreground=C.RED, background="#E8E8ED")
        widget.tag_configure("md_code_block", font=(self._mono_font, sz - 1), foreground=C.TEXT_PRIMARY, background="#F5F5F7", lmargin1=16, lmargin2=16)
        widget.tag_configure("md_quote", font=(self._cn_font, sz), foreground=C.TEXT_SECONDARY, lmargin1=20, lmargin2=20)
        widget.tag_configure("md_bullet", font=(self._cn_font, sz), foreground=C.TEXT_PRIMARY, lmargin1=8, lmargin2=20)
        widget.tag_configure("md_sub_bullet", font=(self._cn_font, sz), foreground=C.TEXT_PRIMARY, lmargin1=28, lmargin2=40)
        widget.tag_configure("md_numlist", font=(self._cn_font, sz), foreground=C.TEXT_PRIMARY, lmargin1=8, lmargin2=20)
        widget.tag_configure("md_hr", font=(self._ui_font, 6), foreground=C.BORDER)
        widget.tag_configure("md_link", font=(self._cn_font, sz, "underline"), foreground=C.ACCENT)
        widget.tag_configure("md_highlight", font=(self._cn_font, sz, "bold"), foreground=C.ORANGE)
        widget.tag_configure("md_normal", font=(self._cn_font, sz), foreground=C.TEXT_PRIMARY, spacing1=1, spacing3=1)
        widget.tag_configure("md_label", font=(self._cn_font, sz, "bold"), foreground=C.ACCENT)

        lines = text.split('\n')
        in_code_block = False
        code_lines = []

        for line in lines:
            if line.strip().startswith('```'):
                if in_code_block:
                    widget.insert(tk.END, '\n'.join(code_lines) + '\n', "md_code_block")
                    code_lines = []
                    in_code_block = False
                else:
                    in_code_block = True
                continue
            if in_code_block:
                code_lines.append(line)
                continue

            stripped = line.strip()
            indent = len(line) - len(line.lstrip())

            if not stripped:
                widget.insert(tk.END, '\n', "md_normal")
                continue

            # 水平线
            if re.match(r'^(\*{3,}|-{3,}|_{3,})$', stripped):
                widget.insert(tk.END, '─' * 50 + '\n', "md_hr")
                continue

            # # ## ### 标题
            heading_match = re.match(r'^(#{1,3})\s+(.+)', stripped)
            if heading_match:
                level = len(heading_match.group(1))
                tag = f"md_h{level}"
                self._render_inline(widget, heading_match.group(2), tag, sz)
                widget.insert(tk.END, '\n', tag)
                continue

            # 引用 >
            if stripped.startswith('>'):
                content = stripped.lstrip('> ').strip()
                widget.insert(tk.END, '│ ', "md_quote")
                self._render_inline(widget, content, "md_quote", sz)
                widget.insert(tk.END, '\n', "md_quote")
                continue

            # 缩进子列表项（2+空格 + - 或 *）
            if indent >= 2:
                sub_bullet_match = re.match(r'^[-*]\s+(.+)', stripped)
                if sub_bullet_match:
                    widget.insert(tk.END, '  ‣  ', "md_sub_bullet")
                    self._render_inline(widget, sub_bullet_match.group(1), "md_sub_bullet", sz)
                    widget.insert(tk.END, '\n', "md_sub_bullet")
                    continue

            # 无序列表
            bullet_match = re.match(r'^[-*]\s+(.+)', stripped)
            if bullet_match:
                widget.insert(tk.END, '  •  ', "md_bullet")
                self._render_inline(widget, bullet_match.group(1), "md_bullet", sz)
                widget.insert(tk.END, '\n', "md_bullet")
                continue

            # 有序列表
            num_match = re.match(r'^(\d+)[.、)]\s*(.+)', stripped)
            if num_match:
                num = num_match.group(1)
                widget.insert(tk.END, f'  {num}.  ', "md_numlist")
                self._render_inline(widget, num_match.group(2), "md_numlist", sz)
                widget.insert(tk.END, '\n', "md_numlist")
                continue

            # 中文数字标题（一、二、三、）
            cn_header_match = re.match(r'^([一二三四五六七八九十]+、)\s*(.+)', stripped)
            if cn_header_match:
                prefix = cn_header_match.group(1)
                content = cn_header_match.group(2)
                widget.insert(tk.END, f'{prefix} ', "md_h2")
                self._render_inline(widget, content, "md_h2", sz)
                widget.insert(tk.END, '\n', "md_h2")
                continue

            # 缩进的普通文本（续行）
            if indent >= 2:
                widget.insert(tk.END, '      ', "md_normal")
                self._render_inline(widget, stripped, "md_normal", sz)
                widget.insert(tk.END, '\n', "md_normal")
                continue

            # 普通行
            self._render_inline(widget, stripped, "md_normal", sz)
            widget.insert(tk.END, '\n', "md_normal")

    def _render_inline(self, widget, text, default_tag, base_size):
        """渲染行内 Markdown 格式"""
        pattern = r'(\*\*(.+?)\*\*|\*(.+?)\*|`([^`]+)`|==(.+?)==|~~(.+?)~~|\[([^\]]+)\]\(([^)]+)\))'

        last_end = 0
        for match in re.finditer(pattern, text):
            start, end = match.span()
            if start > last_end:
                self._render_label_colon(widget, text[last_end:start], default_tag)

            full = match.group(0)
            if full.startswith('**'):
                widget.insert(tk.END, match.group(2), "md_bold")
            elif full.startswith('`'):
                widget.insert(tk.END, match.group(4), "md_code")
            elif full.startswith('*') and not full.startswith('**'):
                widget.insert(tk.END, match.group(3), "md_italic")
            elif full.startswith('=='):
                widget.insert(tk.END, match.group(5), "md_highlight")
            elif full.startswith('~~'):
                widget.insert(tk.END, match.group(6), "md_italic")
            elif full.startswith('['):
                widget.insert(tk.END, match.group(7), "md_link")
            last_end = end

        if last_end < len(text):
            self._render_label_colon(widget, text[last_end:], default_tag)

    def _render_label_colon(self, widget, text, default_tag):
        """渲染带冒号的标签（如"语义侧重：内容"）"""
        label_match = re.match(r'^([^:：\n]{1,15})([：:])\s*(.*)', text, re.DOTALL)
        if label_match:
            widget.insert(tk.END, label_match.group(1) + label_match.group(2), "md_label")
            rest = label_match.group(3)
            if rest:
                widget.insert(tk.END, rest, default_tag)
        else:
            widget.insert(tk.END, text, default_tag)

    # ==================== 成语库 ====================

    def _build_library_tab(self):
        # 搜索栏
        search_frame = tk.Frame(self.library_frame, bg=C.BG)
        search_frame.pack(fill=tk.X, padx=20, pady=(15, 8))

        search_inner = tk.Frame(search_frame, bg=C.SURFACE, highlightbackground=C.BORDER, highlightthickness=1)
        search_inner.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Label(search_inner, text="", font=self.font_normal, bg=C.SURFACE).pack(side=tk.LEFT, padx=(8, 0))

        self.search_entry = tk.Entry(
            search_inner, font=self.font_normal, width=25,
            bg=C.SURFACE, fg=C.TEXT_PRIMARY, insertbackground=C.ACCENT,
            relief=tk.FLAT, bd=0, highlightthickness=0
        )
        self.search_entry.pack(side=tk.LEFT, padx=6, pady=6)
        self.search_entry.bind("<Return>", lambda e: self._search_idioms())

        self._mac_button(search_frame, "搜索", self._search_idioms, color=C.ACCENT, padx=14).pack(side=tk.LEFT, padx=(8, 0))
        self._mac_button(search_frame, "显示全部", self._refresh_library, color=C.TEXT_TERTIARY, padx=14).pack(side=tk.LEFT, padx=(6, 0))

        # 底部按钮
        bottom_frame = tk.Frame(self.library_frame, bg=C.BG)
        bottom_frame.pack(fill=tk.X, padx=20, pady=(0, 10))

        self._mac_button(bottom_frame, "删除选中", self._delete_selected_idiom, color=C.RED, padx=14).pack(side=tk.LEFT)
        self._mac_button(bottom_frame, "导出", self._show_export_menu, color=C.PURPLE, padx=14).pack(side=tk.LEFT, padx=(8, 0))

        self.library_count_label = tk.Label(
            bottom_frame, text="", font=self.font_small, bg=C.BG, fg=C.TEXT_SECONDARY
        )
        self.library_count_label.pack(side=tk.RIGHT)

        # 详情操作按钮栏
        detail_btn_frame = tk.Frame(bottom_frame, bg=C.BG)
        detail_btn_frame.pack(side=tk.RIGHT, padx=(0, 10))

        self.edit_status_label = tk.Label(detail_btn_frame, text="", font=self.font_small, fg=C.ACCENT, bg=C.BG)
        self.edit_status_label.pack(side=tk.RIGHT, padx=(8, 0))

        self.btn_cancel_edit = self._mac_button(detail_btn_frame, "取消", self._cancel_edit, color=C.TEXT_TERTIARY, padx=10)
        self.btn_cancel_edit.pack(side=tk.RIGHT, padx=(4, 0))

        self.btn_save = self._mac_button(detail_btn_frame, "保存", self._save_edit, color=C.GREEN, padx=10)
        self.btn_save.pack(side=tk.RIGHT, padx=(4, 0))

        self.btn_edit = self._mac_button(detail_btn_frame, "编辑", self._enter_edit_mode, color=C.ORANGE, padx=10)
        self.btn_edit.pack(side=tk.RIGHT, padx=(4, 0))

        # PanedWindow
        paned = ttk.PanedWindow(self.library_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 5))

        # 左侧列表
        left_frame = tk.Frame(paned, bg=C.LIST_BG, highlightbackground=C.BORDER, highlightthickness=1)
        paned.add(left_frame, weight=1)

        self.idiom_listbox = tk.Listbox(
            left_frame, font=self.font_normal,
            selectmode=tk.EXTENDED, relief=tk.FLAT, bd=0,
            bg=C.LIST_BG, fg=C.TEXT_PRIMARY,
            selectbackground=C.LIST_SELECT, selectforeground=C.LIST_SELECT_TEXT,
            highlightthickness=0, activestyle="none",
            selectborderwidth=0
        )
        self.idiom_listbox.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)
        self.idiom_listbox.bind("<<ListboxSelect>>", self._on_idiom_select)

        # 右侧详情
        right_frame = tk.Frame(paned, bg=C.SURFACE, highlightbackground=C.BORDER, highlightthickness=1)
        paned.add(right_frame, weight=2)

        self.detail_text = scrolledtext.ScrolledText(
            right_frame, font=self.font_card_back, wrap=tk.WORD,
            bg=C.SURFACE, fg=C.TEXT_PRIMARY, insertbackground=C.ACCENT,
            selectbackground=C.ACCENT, selectforeground="white",
            relief=tk.FLAT, bd=0, padx=16, pady=12,
            highlightthickness=0
        )
        self.detail_text.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        # 详情文本标签样式
        self.detail_text.tag_configure("title", foreground=C.ACCENT, font=(self._cn_font, 16, "bold"))
        self.detail_text.tag_configure("section", foreground=C.ACCENT, font=(self._cn_font, 12, "bold"))
        self.detail_text.tag_configure("label", foreground=C.TEXT_SECONDARY, font=(self._cn_font, 11, "bold"))
        self.detail_text.tag_configure("content", foreground=C.TEXT_PRIMARY, font=(self._cn_font, 11))
        self.detail_text.tag_configure("dim", foreground=C.TEXT_TERTIARY, font=(self._cn_font, 10))

        self._enter_view_mode()
        self._refresh_library()

    def _refresh_library(self):
        idioms = load_idioms()
        self.idiom_listbox.delete(0, tk.END)
        self.all_idioms = idioms
        for idiom in idioms:
            mastery = idiom.get("review_stats", {}).get("mastery_level", 0)
            stars = "★" * mastery + "☆" * (5 - mastery)
            self.idiom_listbox.insert(tk.END, f"  {idiom['name']}  {stars}")
        self.library_count_label.config(text=f"共 {len(idioms)} 个成语")

    def _search_idioms(self):
        keyword = self.search_entry.get().strip()
        if not keyword:
            self._refresh_library()
            return
        results = search_idioms(keyword)
        self.idiom_listbox.delete(0, tk.END)
        self.all_idioms = results
        for idiom in results:
            mastery = idiom.get("review_stats", {}).get("mastery_level", 0)
            stars = "★" * mastery + "☆" * (5 - mastery)
            self.idiom_listbox.insert(tk.END, f"  {idiom['name']}  {stars}")
        self.library_count_label.config(text=f"找到 {len(results)} 个成语")

    def _on_idiom_select(self, event):
        if self.is_editing:
            return
        selection = self.idiom_listbox.curselection()
        if not selection:
            return
        # 多选模式下显示最后一个选中项的详情
        index = selection[-1]
        if index < len(self.all_idioms):
            self._show_idiom_detail(self.all_idioms[index])
            self.detail_text.config(state=tk.DISABLED)
        # 更新选中计数
        count = len(selection)
        if count > 1:
            self.library_count_label.config(text=f"已选 {count} 个成语")

    def _show_idiom_detail(self, idiom):
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert(tk.END, f"【{idiom['name']}】\n\n", "title")

        added = idiom.get("added_at")
        if added:
            self.detail_text.insert(tk.END, f"导入时间：{added}\n\n", "dim")

        raw_text = idiom.get("raw_text")
        if raw_text:
            self._render_markdown(self.detail_text, raw_text, base_size=12)
        else:
            for kp in idiom["knowledge_points"]:
                label = kp["label"]
                content = kp["content"]
                self.detail_text.insert(tk.END, f"## {label}\n", "md_h2")
                self._render_markdown(self.detail_text, content, base_size=11)

    def _delete_selected_idiom(self):
        selection = self.idiom_listbox.curselection()
        if not selection:
            messagebox.showwarning("提示", "请先选择成语！")
            return
        names = [self.all_idioms[i]["name"] for i in selection if i < len(self.all_idioms)]
        if not names:
            return
        msg = f"确定要删除「{names[0]}」吗？" if len(names) == 1 else f"确定要删除选中的 {len(names)} 个成语吗？"
        if messagebox.askyesno("确认删除", msg):
            for name in names:
                delete_idiom(name)
            self._refresh_library()
            self.detail_text.delete("1.0", tk.END)
            self._refresh_stats()

    # ==================== 编辑功能 ====================

    def _enter_view_mode(self):
        self.is_editing = False
        self.editing_idiom_name = None
        self.detail_text.config(state=tk.DISABLED)
        self.btn_save.config(state=tk.DISABLED)
        self.btn_cancel_edit.config(state=tk.DISABLED)
        self.edit_status_label.config(text="", fg=C.TEXT_SECONDARY)

    def _enter_edit_mode(self):
        selection = self.idiom_listbox.curselection()
        if not selection:
            messagebox.showwarning("提示", "请先从列表中选择一个成语！")
            return
        index = selection[0]
        if index >= len(self.all_idioms):
            return
        idiom = self.all_idioms[index]
        self.is_editing = True
        self.editing_idiom_name = idiom["name"]

        editable_text = idiom_to_editable_text(idiom)
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert("1.0", editable_text)

        self.btn_save.config(state=tk.NORMAL)
        self.btn_cancel_edit.config(state=tk.NORMAL)
        self.edit_status_label.config(text="编辑模式", fg=C.ORANGE)

    def _save_edit(self):
        if not self.is_editing or not self.editing_idiom_name:
            return
        edited_text = self.detail_text.get("1.0", tk.END).strip()
        if not edited_text:
            messagebox.showwarning("提示", "内容不能为空！")
            return

        parsed = parse_idiom_text(edited_text)
        if not parsed or not parsed["name"]:
            messagebox.showerror("解析失败", "无法解析编辑后的文本！")
            return

        if not parsed.get("raw_text") and not parsed.get("knowledge_points"):
            messagebox.showwarning("警告", f"解析到「{parsed['name']}」但没有内容。")
            return

        if parsed["name"] != self.editing_idiom_name:
            delete_idiom(self.editing_idiom_name)

        add_idiom(parsed)
        self.edit_status_label.config(text="保存成功", fg=C.GREEN)
        self.is_editing = False
        self.editing_idiom_name = None
        self._refresh_library()
        self._refresh_stats()

        self._enter_view_mode()
        self.detail_text.config(state=tk.NORMAL)
        updated = None
        for idiom in load_idioms():
            if idiom["name"] == parsed["name"]:
                updated = idiom
                break
        if updated:
            self._show_idiom_detail(updated)
            for i, idiom in enumerate(self.all_idioms):
                if idiom["name"] == parsed["name"]:
                    self.idiom_listbox.selection_clear(0, tk.END)
                    self.idiom_listbox.selection_set(i)
                    self.idiom_listbox.see(i)
                    break

    def _cancel_edit(self):
        self.is_editing = False
        self.editing_idiom_name = None
        self._enter_view_mode()
        selection = self.idiom_listbox.curselection()
        if selection:
            index = selection[0]
            if index < len(self.all_idioms):
                self.detail_text.config(state=tk.NORMAL)
                self._show_idiom_detail(self.all_idioms[index])

    # ==================== 导出功能 ====================

    def _show_export_menu(self):
        selection = self.idiom_listbox.curselection()
        if not selection:
            messagebox.showwarning("提示", "请先选择要导出的成语！\n按住 Cmd/Ctrl 可多选。")
            return
        # 获取选中的成语完整数据
        selected_idioms = []
        for i in selection:
            if i < len(self.all_idioms):
                idioms_all = load_idioms()
                for idiom in idioms_all:
                    if idiom["name"] == self.all_idioms[i]["name"]:
                        selected_idioms.append(idiom)
                        break
        self._export_idioms = selected_idioms
        count = len(selected_idioms)

        menu = tk.Menu(self.root, tearoff=0, font=self.font_normal)
        menu.add_command(label=f"导出 {count} 个成语为 Markdown (.md)", command=lambda: self._do_export("md"))
        menu.add_command(label=f"导出 {count} 个成语为纯文本 (.txt)", command=lambda: self._do_export("txt"))
        menu.add_separator()
        menu.add_command(label=f"导出 {count} 个成语为 PDF (.pdf)", command=lambda: self._do_export("pdf"))
        menu.tk_popup(*self.root.winfo_pointerxy())

    def _do_export(self, fmt):
        ext_map = {"md": ".md", "txt": ".txt", "pdf": ".pdf"}
        type_map = {"md": [("Markdown", "*.md")], "txt": [("文本文件", "*.txt")], "pdf": [("PDF", "*.pdf")]}
        name_map = {"md": "成语积累", "txt": "成语积累", "pdf": "成语积累"}

        filepath = filedialog.asksaveasfilename(
            title="导出成语库",
            defaultextension=ext_map[fmt],
            filetypes=type_map[fmt],
            initialfile=name_map[fmt] + ext_map[fmt],
        )
        if not filepath:
            return

        try:
            if fmt == "md":
                self._export_as_markdown(filepath)
            elif fmt == "txt":
                self._export_as_txt(filepath)
            elif fmt == "pdf":
                self._export_as_pdf(filepath)
            messagebox.showinfo("导出成功", f"已导出到：\n{filepath}")
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    def _get_mastery_stars(self, level):
        return "★" * level + "☆" * (5 - level)

    def _idiom_core_meaning(self, idiom):
        """提取成语的核心释义（第一个知识点）"""
        if idiom.get("raw_text"):
            lines = idiom["raw_text"].strip().split('\n')
            for line in lines:
                stripped = line.strip()
                if stripped and ('核心释义' in stripped or stripped.startswith('核心')):
                    match = re.match(r'[^：:]*[：:]\s*(.*)', stripped)
                    if match and match.group(1).strip():
                        return self._clean_meaning(match.group(1).strip())
            for line in lines:
                stripped = line.strip()
                if stripped:
                    match = re.match(r'[^：:]*[：:]\s*(.*)', stripped)
                    if match and match.group(1).strip():
                        return self._clean_meaning(match.group(1).strip())
            return self._clean_meaning(idiom["raw_text"].strip())
        kps = idiom.get("knowledge_points", [])
        if kps:
            return self._clean_meaning(kps[0].get("content", ""))
        return ""

    @staticmethod
    def _clean_meaning(text):
        """清理释义文本中的序号残留和空白"""
        text = text.strip()
        # 去掉末尾的孤立序号如 "2." "3." 等
        text = re.sub(r'\n+\d+\.\s*$', '', text)
        text = re.sub(r'\s*\d+\.\s*$', '', text)
        return text.strip()

    def _export_as_markdown(self, filepath):
        idioms = self._export_idioms
        lines = ["# 成语积累\n"]
        lines.append(f"> 导出 {len(idioms)} 个成语，导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}\n")

        for idiom in idioms:
            lines.append(f"- **{idiom['name']}**：")
            meaning = self._idiom_core_meaning(idiom)
            if meaning:
                # 多行内容缩进
                meaning_lines = meaning.split('\n')
                lines.append(meaning_lines[0])
                for ml in meaning_lines[1:]:
                    if ml.strip():
                        lines.append("  " + ml.strip())
            lines.append("")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    def _export_as_txt(self, filepath):
        idioms = self._export_idioms
        parts = []
        for idiom in idioms:
            meaning = self._idiom_core_meaning(idiom)
            parts.append(f"【{idiom['name']}】{meaning}")

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(parts))

    def _export_as_pdf(self, filepath):
        from fpdf import FPDF

        font_candidates = [
            "/System/Library/Fonts/STHeiti Medium.ttc",
            "/System/Library/Fonts/Supplemental/Songti.ttc",
        ]
        font_path = None
        for fp in font_candidates:
            if os.path.exists(fp):
                font_path = fp
                break
        if not font_path:
            raise RuntimeError("未找到中文字体，无法导出 PDF")

        class IdiomPDF(FPDF):
            def footer(self):
                self.set_y(-15)
                self.set_font("chinese", "", 8)
                self.set_text_color(166, 166, 178)
                self.cell(0, 10, f"成语积累  —  第 {self.page_no()} 页", align="C")

        pdf = IdiomPDF()
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.add_font("chinese", "", font_path)
        pdf.add_font("chinese", "B", font_path)

        idioms = self._export_idioms

        # 封面
        pdf.add_page()
        pdf.set_font("chinese", "B", 24)
        pdf.set_text_color(29, 29, 31)
        pdf.ln(60)
        pdf.cell(0, 15, "成语积累", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("chinese", "", 12)
        pdf.set_text_color(134, 134, 139)
        pdf.cell(0, 10, f"导出 {len(idioms)} 个成语", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(0, 10, f"导出时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}", align="C", new_x="LMARGIN", new_y="NEXT")

        # 成语内容 - 仅核心释义
        for idiom in idioms:
            pdf.add_page()
            pdf.set_font("chinese", "B", 14)
            pdf.set_text_color(0, 122, 255)
            pdf.cell(0, 10, idiom["name"], new_x="LMARGIN", new_y="NEXT")

            pdf.set_draw_color(210, 210, 215)
            pdf.line(10, pdf.get_y() + 1, 200, pdf.get_y() + 1)
            pdf.ln(4)

            meaning = self._idiom_core_meaning(idiom)
            if meaning:
                pdf.set_font("chinese", "", 10)
                pdf.set_text_color(29, 29, 31)
                pdf.multi_cell(0, 6, meaning)

        pdf.output(filepath)

    # ==================== 闪卡复习 ====================

    def _build_review_tab(self):
        # 顶部控制栏
        control_frame = tk.Frame(self.review_frame, bg=C.BG)
        control_frame.pack(fill=tk.X, padx=20, pady=(15, 5))

        tk.Label(control_frame, text="复习模式：", font=self.font_normal, bg=C.BG, fg=C.TEXT_SECONDARY).pack(side=tk.LEFT)

        self.review_mode = tk.StringVar(value="all")
        modes = [("全部", "all"), ("随机20", "random20"), ("未掌握", "unmastered"), ("已掌握", "mastered"), ("按日期", "bydate")]
        for text, value in modes:
            tk.Radiobutton(
                control_frame, text=text, variable=self.review_mode,
                value=value, font=self.font_small,
                bg=C.BG, fg=C.TEXT_PRIMARY, selectcolor=C.SURFACE,
                activebackground=C.BG, activeforeground=C.TEXT_PRIMARY,
                highlightthickness=0,
                command=self._on_review_mode_change
            ).pack(side=tk.LEFT, padx=4)

        self._mac_button(control_frame, "开始复习", self._start_review, color=C.ACCENT, font=self.font_button_big, padx=20, pady=6).pack(side=tk.RIGHT)

        # 字号调节
        font_frame = tk.Frame(control_frame, bg=C.BG)
        font_frame.pack(side=tk.RIGHT, padx=15)

        tk.Label(font_frame, text="字号", font=self.font_small, bg=C.BG, fg=C.TEXT_SECONDARY).pack(side=tk.LEFT)

        self._mac_button(font_frame, "A-", self._font_size_down, color=C.TEXT_TERTIARY, padx=8, pady=2).pack(side=tk.LEFT, padx=2)

        self.font_size_var = tk.IntVar(value=self._card_back_size)
        self.font_size_scale = tk.Scale(
            font_frame, from_=8, to=24, orient=tk.HORIZONTAL,
            variable=self.font_size_var, length=80,
            showvalue=False, bg=C.BG, fg=C.TEXT_PRIMARY,
            troughcolor=C.PROGRESS_BG, highlightthickness=0,
            sliderrelief=tk.FLAT, command=self._on_font_size_change
        )
        self.font_size_scale.pack(side=tk.LEFT, padx=2)

        self._mac_button(font_frame, "A+", self._font_size_up, color=C.TEXT_TERTIARY, padx=8, pady=2).pack(side=tk.LEFT, padx=2)

        # 主内容区：左侧日历 + 右侧闪卡
        main_paned = ttk.PanedWindow(self.review_frame, orient=tk.HORIZONTAL)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=20, pady=(5, 0))

        # 左侧：日历侧栏
        self.calendar_frame = tk.Frame(main_paned, bg=C.SURFACE, width=260,
                                       highlightbackground=C.BORDER, highlightthickness=1)
        self.calendar_frame.pack_propagate(False)
        main_paned.add(self.calendar_frame, weight=0)

        # 日历标题
        cal_header = tk.Frame(self.calendar_frame, bg=C.SURFACE)
        cal_header.pack(fill=tk.X, padx=12, pady=(12, 4))

        self._mac_button(cal_header, "<", self._cal_prev_month, color=C.SURFACE, fg=C.TEXT_PRIMARY, font=(self._ui_font, 14, "bold"), padx=6, pady=0).pack(side=tk.LEFT)
        self._mac_button(cal_header, ">", self._cal_next_month, color=C.SURFACE, fg=C.TEXT_PRIMARY, font=(self._ui_font, 14, "bold"), padx=6, pady=0).pack(side=tk.RIGHT)

        self.cal_month_label = tk.Label(cal_header, text="", font=(self._ui_font, 13, "bold"), bg=C.SURFACE, fg=C.TEXT_PRIMARY)
        self.cal_month_label.pack(side=tk.LEFT, expand=True)

        # 选中日期信息
        self.cal_info_label = tk.Label(self.calendar_frame, text="", font=self.font_small, bg=C.SURFACE, fg=C.TEXT_SECONDARY)
        self.cal_info_label.pack(fill=tk.X, padx=12, pady=(0, 4))

        # 日历网格
        self.cal_grid_frame = tk.Frame(self.calendar_frame, bg=C.SURFACE)
        self.cal_grid_frame.pack(fill=tk.X, padx=12)

        # 星期标题
        weekdays = ["一", "二", "三", "四", "五", "六", "日"]
        for wd in weekdays:
            tk.Label(self.cal_grid_frame, text=wd, font=(self._ui_font, 9),
                     bg=C.SURFACE, fg=C.TEXT_TERTIARY, width=3).grid(row=0, column=weekdays.index(wd), padx=1, pady=(0, 2))

        # 日历日期按钮容器
        self.cal_buttons_frame = tk.Frame(self.cal_grid_frame, bg=C.SURFACE)
        self.cal_buttons_frame.grid(row=1, column=0, columnspan=7, sticky="ew")

        # 日历状态
        self._cal_year = date.today().year
        self._cal_month = date.today().month
        self._cal_selected = None  # 选中的日期字符串 "YYYY-MM-DD"
        self._cal_date_counts = {}  # 缓存每个日期的成语数量

        self._render_calendar()

        # 右侧：闪卡区域
        right_area = tk.Frame(main_paned, bg=C.BG)
        main_paned.add(right_area, weight=1)

        # 进度条
        progress_frame = tk.Frame(right_area, bg=C.BG)
        progress_frame.pack(fill=tk.X, pady=(0, 4))

        self.progress_label = tk.Label(
            progress_frame, text="点击「开始复习」",
            font=self.font_small, fg=C.TEXT_SECONDARY, bg=C.BG
        )
        self.progress_label.pack(side=tk.LEFT)

        self.progress_bar = ttk.Progressbar(
            progress_frame, mode="determinate", length=400
        )
        self.progress_bar.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 0))

        # 快捷键提示
        shortcut_bar = tk.Frame(right_area, bg=C.BG)
        shortcut_bar.pack(fill=tk.X, pady=(0, 2))
        tk.Label(
            shortcut_bar,
            text="Space = 翻转    K/→ = 下一个    J/← = 上一个    A = 认识    D = 不认识    S = 已掌握",
            font=(self._ui_font, 9), fg=C.TEXT_TERTIARY, bg=C.BG
        ).pack(anchor=tk.W)

        # 闪卡区域
        self.card_frame = tk.Frame(
            right_area, bg=C.CARD_FRONT,
            highlightbackground=C.BORDER, highlightthickness=1
        )
        self.card_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 4))

        self.card_text = tk.Text(
            self.card_frame, font=self.font_card_front,
            bg=C.CARD_FRONT, fg=C.TEXT_PRIMARY, wrap=tk.WORD,
            relief=tk.FLAT, bd=0, padx=30, pady=20,
            cursor="arrow", spacing1=2, spacing3=2,
            highlightthickness=0
        )
        self.card_text.pack(fill=tk.BOTH, expand=True)
        self.card_text.config(state=tk.DISABLED)
        self.card_text.bind("<Double-Button-1>", lambda e: self._flip_card())

        self.card_text.tag_configure("center", justify=tk.CENTER)
        self.card_text.tag_configure("name", font=(self._cn_font, self._card_front_size, "bold"), foreground=C.TEXT_PRIMARY, justify=tk.CENTER)
        self.card_text.tag_configure("hint", font=(self._ui_font, 12), foreground=C.TEXT_TERTIARY, justify=tk.CENTER)
        self.card_text.tag_configure("section_title", font=(self._cn_font, max(10, self._card_back_size + 2), "bold"), foreground=C.TEXT_PRIMARY)
        self.card_text.tag_configure("label", font=(self._cn_font, max(9, self._card_back_size - 1), "bold"), foreground=C.TEXT_SECONDARY)
        self.card_text.tag_configure("body", font=(self._cn_font, self._card_back_size), foreground=C.TEXT_PRIMARY)
        self.card_text.tag_configure("divider", font=(self._ui_font, 8), foreground=C.BORDER_LIGHT)
        self.card_text.tag_configure("mastery", font=(self._ui_font, 14), foreground=C.ORANGE, justify=tk.CENTER)
        self.card_text.tag_configure("mastery_back", font=(self._cn_font, max(9, self._card_back_size)), foreground=C.ORANGE)

        self._show_card_placeholder()

        # 底部操作按钮
        action_frame = tk.Frame(right_area, bg=C.BG)
        action_frame.pack(fill=tk.X, pady=(0, 10))

        self._mac_button(action_frame, "← 上一个 (J)", self._prev_card, color=C.TEXT_TERTIARY, fg="white", padx=16, pady=7).pack(side=tk.LEFT)
        self._mac_button(action_frame, "翻转 (Space)", self._flip_card, color=C.ACCENT, padx=16, pady=7).pack(side=tk.LEFT, padx=6)
        self._mac_button(action_frame, "下一个 (K) →", self._next_card, color=C.TEXT_TERTIARY, fg="white", padx=16, pady=7).pack(side=tk.LEFT)

        master_frame = tk.Frame(action_frame, bg=C.BG)
        master_frame.pack(side=tk.RIGHT)

        self._mac_button(master_frame, "不认识 (D)", lambda: self._mark_card(False), color=C.RED, padx=12, pady=7).pack(side=tk.RIGHT)
        self._mac_button(master_frame, "认识 (A)", lambda: self._mark_card(True), color=C.GREEN, padx=12, pady=7).pack(side=tk.RIGHT, padx=6)
        self._mac_button(master_frame, "已掌握 (S)", self._mark_mastered, color=C.ORANGE, padx=12, pady=7).pack(side=tk.RIGHT, padx=6)

    # ==================== 日历组件 ====================

    def _on_review_mode_change(self):
        """切换复习模式时更新日历可见性"""
        if self.review_mode.get() == "bydate":
            self.calendar_frame.pack_propagate(False)
            self.calendar_frame.configure(width=260)
        else:
            pass

    def _cal_prev_month(self):
        if self._cal_month == 1:
            self._cal_month = 12
            self._cal_year -= 1
        else:
            self._cal_month -= 1
        self._render_calendar()

    def _cal_next_month(self):
        if self._cal_month == 12:
            self._cal_month = 1
            self._cal_year += 1
        else:
            self._cal_month += 1
        self._render_calendar()

    def _build_date_counts(self):
        """统计每个日期的成语数量"""
        self._cal_date_counts = {}
        for idiom in load_idioms():
            added = idiom.get("added_at", "")
            if added:
                day_str = added[:10]  # "YYYY-MM-DD"
                self._cal_date_counts[day_str] = self._cal_date_counts.get(day_str, 0) + 1

    def _render_calendar(self):
        """渲染日历网格"""
        self._build_date_counts()
        self.cal_month_label.config(text=f"{self._cal_year}年{self._cal_month}月")

        # 清除旧的日期按钮
        for widget in self.cal_buttons_frame.winfo_children():
            widget.destroy()

        today = date.today()
        month_days = calendar.monthrange(self._cal_year, self._cal_month)[1]
        first_weekday = calendar.monthrange(self._cal_year, self._cal_month)[0]  # 0=Monday

        row, col = 0, first_weekday
        for day in range(1, month_days + 1):
            day_str = f"{self._cal_year}-{self._cal_month:02d}-{day:02d}"
            is_today = (self._cal_year == today.year and self._cal_month == today.month and day == today.day)
            is_selected = (self._cal_selected == day_str)
            count = self._cal_date_counts.get(day_str, 0)

            btn_frame = tk.Frame(self.cal_buttons_frame, bg=C.SURFACE)
            btn_frame.grid(row=row, column=col, padx=1, pady=1, sticky="nsew")

            if is_selected:
                bg = C.ACCENT
                fg = "white"
            elif is_today:
                bg = "#E8F0FE"
                fg = C.ACCENT
            elif count > 0:
                bg = "#F0F4FF"
                fg = C.TEXT_PRIMARY
            else:
                bg = C.SURFACE
                fg = C.TEXT_TERTIARY

            btn = tk.Label(
                btn_frame, text=str(day),
                font=(self._ui_font, 10, "bold" if (is_today or is_selected) else "normal"),
                bg=bg, fg=fg, width=3, height=1,
                cursor="hand2"
            )
            btn.pack(pady=(0, 0))

            # 有成语的日期下方显示小圆点
            if count > 0 and not is_selected:
                dot = tk.Label(btn_frame, text=f"{count}", font=(self._ui_font, 7),
                               bg=bg, fg=C.ACCENT if not is_today else C.ACCENT)
                dot.pack()

            btn.bind("<Button-1>", lambda e, d=day_str: self._on_cal_date_click(d))
            if count > 0 and not is_selected:
                btn_frame.bind("<Button-1>", lambda e, d=day_str: self._on_cal_date_click(d))
                # 也给 dot 绑定点击
                for child in btn_frame.winfo_children():
                    child.bind("<Button-1>", lambda e, d=day_str: self._on_cal_date_click(d))

            col += 1
            if col > 6:
                col = 0
                row += 1

        # 确保列等宽
        for c in range(7):
            self.cal_buttons_frame.columnconfigure(c, weight=1)

        # 更新选中日期信息
        self._update_cal_info()

    def _on_cal_date_click(self, day_str):
        """点击日历日期"""
        self._cal_selected = day_str
        self.review_mode.set("bydate")
        self._render_calendar()

    def _update_cal_info(self):
        """更新日历下方的选中信息"""
        if self._cal_selected:
            count = self._cal_date_counts.get(self._cal_selected, 0)
            self.cal_info_label.config(text=f"已选：{self._cal_selected}（{count} 个成语）")
        else:
            self.cal_info_label.config(text="选择日期以按日期复习")

    def _font_size_up(self):
        self._card_back_size = min(24, self._card_back_size + 1)
        self._card_front_size = min(60, self._card_front_size + 2)
        self.font_size_var.set(self._card_back_size)
        self._apply_font_size()

    def _font_size_down(self):
        self._card_back_size = max(8, self._card_back_size - 1)
        self._card_front_size = max(20, self._card_front_size - 2)
        self.font_size_var.set(self._card_back_size)
        self._apply_font_size()

    def _on_font_size_change(self, val):
        new_size = int(float(val))
        diff = new_size - self._card_back_size
        if diff != 0:
            self._card_back_size = new_size
            self._card_front_size = max(20, min(60, self._card_front_size + diff * 2))
            self._apply_font_size()

    def _apply_font_size(self):
        self.font_card_front = (self._cn_font, self._card_front_size, "bold")
        self.font_card_back = (self._cn_font, self._card_back_size)
        if self.current_review_list and not self._animating:
            if self.is_showing_back:
                self._show_back_content()
            else:
                self._show_front_content()

    def _show_card_placeholder(self):
        self.card_text.config(state=tk.NORMAL)
        self.card_text.delete("1.0", tk.END)
        self.card_text.tag_configure("name", font=(self._cn_font, 24, "bold"), foreground=C.TEXT_TERTIARY, justify=tk.CENTER)
        self.card_text.insert(tk.END, "\n\n\n", "center")
        self.card_text.insert(tk.END, "点击「开始复习」\n", "name")
        self.card_text.insert(tk.END, "进入闪卡模式\n", "hint")
        self.card_text.config(state=tk.DISABLED)

    def _start_review(self):
        mode = self.review_mode.get()
        all_idioms = load_idioms()

        if not all_idioms:
            messagebox.showwarning("提示", "成语库为空，请先导入成语！")
            return

        if mode == "all":
            self.current_review_list = list(all_idioms)
        elif mode == "random20":
            count = min(20, len(all_idioms))
            self.current_review_list = random.sample(all_idioms, count)
        elif mode == "unmastered":
            self.current_review_list = [
                i for i in all_idioms
                if i.get("review_stats", {}).get("mastery_level", 0) < 4
            ]
            if not self.current_review_list:
                messagebox.showinfo("恭喜", "所有成语都已掌握！")
                return
        elif mode == "mastered":
            self.current_review_list = [
                i for i in all_idioms
                if i.get("review_stats", {}).get("mastery_level", 0) >= 4
            ]
            if not self.current_review_list:
                messagebox.showinfo("提示", "还没有已掌握的成语，先复习一些吧！")
                return
        elif mode == "bydate":
            if not self._cal_selected:
                messagebox.showwarning("提示", "请在左侧日历中选择一个日期！")
                return
            self.current_review_list = [
                i for i in all_idioms
                if i.get("added_at", "")[:10] == self._cal_selected
            ]
            if not self.current_review_list:
                messagebox.showinfo("提示", f"{self._cal_selected} 当天没有导入成语。")
                return

        random.shuffle(self.current_review_list)
        self.current_index = 0
        self.is_showing_back = False
        self._show_current_card()

    def _update_card_tags(self):
        self.card_text.tag_configure("name", font=(self._cn_font, self._card_front_size, "bold"), foreground=C.TEXT_PRIMARY, justify=tk.CENTER)
        self.card_text.tag_configure("hint", font=(self._ui_font, max(10, self._card_front_size // 3)), foreground=C.TEXT_TERTIARY, justify=tk.CENTER)
        self.card_text.tag_configure("section_title", font=(self._cn_font, max(10, self._card_back_size + 2), "bold"), foreground=C.TEXT_PRIMARY, justify=tk.LEFT)
        self.card_text.tag_configure("label", font=(self._cn_font, max(9, self._card_back_size), "bold"), foreground=C.TEXT_SECONDARY, justify=tk.LEFT)
        self.card_text.tag_configure("body", font=(self._cn_font, self._card_back_size), foreground=C.TEXT_PRIMARY, justify=tk.LEFT)
        self.card_text.tag_configure("divider", font=(self._ui_font, 8), foreground=C.BORDER_LIGHT, justify=tk.CENTER)

    def _get_mastery_label(self, level):
        labels = ["未复习", "初识", "了解", "熟悉", "掌握", "精通"]
        return labels[level] if level < len(labels) else f"Lv.{level}"

    def _show_current_card(self):
        if not self.current_review_list:
            return
        total = len(self.current_review_list)
        current = self.current_index + 1
        idiom = self.current_review_list[self.current_index]
        mastery = idiom.get("review_stats", {}).get("mastery_level", 0)

        self.progress_label.config(text=f"{current} / {total}    {self._get_mastery_stars(mastery)} {self._get_mastery_label(mastery)}")
        self.progress_bar["value"] = (current / total) * 100

        self.is_showing_back = False
        self._update_card_tags()

        self.card_text.config(state=tk.NORMAL, bg=C.CARD_FRONT, fg=C.TEXT_PRIMARY)
        self.card_text.delete("1.0", tk.END)
        self.card_text.insert(tk.END, "\n\n\n", "name")
        self.card_text.insert(tk.END, f"{idiom['name']}\n", "name")
        self.card_text.insert(tk.END, "\n", "name")
        self.card_text.tag_configure("mastery", font=(self._ui_font, 14), foreground=C.ORANGE, justify=tk.CENTER)
        self.card_text.insert(tk.END, f"{self._get_mastery_stars(mastery)} {self._get_mastery_label(mastery)}\n", "mastery")
        self.card_text.insert(tk.END, "\n", "name")
        self.card_text.insert(tk.END, "按 Space 翻转\n", "hint")
        self.card_text.config(state=tk.DISABLED)
        self.card_frame.config(bg=C.CARD_FRONT)

    def _flip_card(self):
        if not self.current_review_list or self._animating:
            return
        self._animating = True
        if self.is_showing_back:
            self._animate_transition(C.CARD_BACK, C.CARD_FRONT, self._show_front_content)
        else:
            self._animate_transition(C.CARD_FRONT, C.CARD_BACK, self._show_back_content)

    def _animate_transition(self, from_color, to_color, final_action, steps=8, delay=25):
        if steps <= 0:
            final_action()
            self._animating = False
            return
        t = 1.0 - (steps / 8.0)
        bg = lerp_color(from_color, to_color, t)
        self.card_text.config(bg=bg)
        self.card_frame.config(bg=bg)
        self.root.after(delay, lambda: self._animate_transition(from_color, to_color, final_action, steps - 1, delay))

    def _get_current_idiom_fresh(self):
        if not self.current_review_list:
            return None
        idiom = self.current_review_list[self.current_index]
        fresh_idioms = {i["name"]: i for i in load_idioms()}
        return fresh_idioms.get(idiom["name"], idiom)

    def _show_front_content(self):
        if not self.current_review_list:
            return
        self.is_showing_back = False
        idiom = self._get_current_idiom_fresh()
        self.current_review_list[self.current_index] = idiom
        self._update_card_tags()

        mastery = idiom.get("review_stats", {}).get("mastery_level", 0)
        stars = self._get_mastery_stars(mastery)

        self.card_text.config(state=tk.NORMAL, bg=C.CARD_FRONT, fg=C.TEXT_PRIMARY)
        self.card_text.delete("1.0", tk.END)
        self.card_text.insert(tk.END, "\n\n\n", "name")
        self.card_text.insert(tk.END, f"{idiom['name']}\n", "name")
        self.card_text.insert(tk.END, "\n", "name")
        self.card_text.tag_configure("mastery", font=(self._ui_font, 14), foreground=C.ORANGE, justify=tk.CENTER)
        self.card_text.insert(tk.END, f"{stars} {self._get_mastery_label(mastery)}\n", "mastery")
        self.card_text.insert(tk.END, "\n", "name")
        self.card_text.insert(tk.END, "按 Space 翻转\n", "hint")
        self.card_text.config(state=tk.DISABLED)
        self.card_frame.config(bg=C.CARD_FRONT)

    def _show_back_content(self):
        if not self.current_review_list:
            return
        self.is_showing_back = True
        idiom = self._get_current_idiom_fresh()
        self.current_review_list[self.current_index] = idiom
        self._update_card_tags()

        self.card_text.config(state=tk.NORMAL, bg=C.CARD_BACK, fg=C.TEXT_PRIMARY)
        self.card_text.delete("1.0", tk.END)

        mastery = idiom.get("review_stats", {}).get("mastery_level", 0)
        stars = self._get_mastery_stars(mastery)
        self.card_text.insert(tk.END, f"【{idiom['name']}】\n", "name")
        self.card_text.tag_configure("mastery_back", font=(self._cn_font, max(9, self._card_back_size)), foreground=C.ORANGE)
        self.card_text.insert(tk.END, f"掌握度：{stars} {self._get_mastery_label(mastery)}\n", "mastery_back")
        added = idiom.get("added_at")
        if added:
            self.card_text.tag_configure("dim", font=(self._cn_font, max(9, self._card_back_size - 1)), foreground=C.TEXT_TERTIARY)
            self.card_text.insert(tk.END, f"导入时间：{added}\n", "dim")
        self.card_text.insert(tk.END, "─" * 40 + "\n\n", "divider")

        raw_text = idiom.get("raw_text")
        if raw_text:
            self._render_markdown(self.card_text, raw_text, base_size=self._card_back_size)
        else:
            for kp in idiom["knowledge_points"]:
                label = kp["label"]
                content = kp["content"]
                self.card_text.insert(tk.END, f"## {label}\n", "md_h2")
                self._render_markdown(self.card_text, content, base_size=self._card_back_size)
                self.card_text.insert(tk.END, "\n", "body")

        self.card_text.config(state=tk.DISABLED)
        self.card_frame.config(bg=C.CARD_BACK)

    def _next_card(self):
        if not self.current_review_list or self._animating:
            return
        if self.current_index < len(self.current_review_list) - 1:
            self.current_index += 1
            self.is_showing_back = False
            self._slide_animation()
        else:
            self._update_card_tags()
            self.card_text.config(state=tk.NORMAL, bg=C.CARD_FRONT, fg=C.GREEN)
            self.card_text.delete("1.0", tk.END)
            self.card_text.insert(tk.END, "\n\n\n", "center")
            self.card_text.insert(tk.END, "复习完成！\n\n", "name")
            self.card_text.insert(tk.END, "你可以重新选择模式\n再次开始复习\n", "hint")
            self.card_text.config(state=tk.DISABLED)
            self.card_frame.config(bg=C.CARD_FRONT)

    def _prev_card(self):
        if not self.current_review_list or self._animating:
            return
        if self.current_index > 0:
            self.current_index -= 1
            self.is_showing_back = False
            self._slide_animation()

    def _slide_animation(self, steps=6, delay=20):
        if steps <= 0:
            self._show_current_card()
            self._animating = False
            return
        t = 1.0 - (steps / 6.0)
        bg = lerp_color(C.BORDER_LIGHT, C.CARD_FRONT, t)
        self.card_text.config(bg=bg)
        self.card_frame.config(bg=bg)
        self.root.after(delay, lambda: self._slide_animation(steps - 1, delay))

    def _mark_card(self, known: bool):
        if not self.current_review_list or self._animating:
            return
        idiom = self.current_review_list[self.current_index]
        update_review_stats(idiom["name"], known)
        fresh = self._get_current_idiom_fresh()
        if fresh:
            self.current_review_list[self.current_index] = fresh
        self._refresh_stats()
        if known:
            self._next_card()
        else:
            if not self.is_showing_back:
                self._flip_card()

    def _mark_mastered(self):
        if not self.current_review_list or self._animating:
            return
        idiom = self.current_review_list[self.current_index]
        set_mastery_level(idiom["name"], 5)
        fresh = self._get_current_idiom_fresh()
        if fresh:
            self.current_review_list[self.current_index] = fresh
        self._refresh_stats()
        self._next_card()

    # ==================== 统计 ====================

    def _build_stats_tab(self):
        btn_row = tk.Frame(self.stats_frame, bg=C.BG)
        btn_row.pack(fill=tk.X, padx=20, pady=(15, 0))

        self._mac_button(btn_row, "刷新统计", self._refresh_stats, color=C.ACCENT, padx=16, pady=6).pack(side=tk.LEFT)

        self.stats_display = scrolledtext.ScrolledText(
            self.stats_frame, font=self.font_normal, wrap=tk.WORD,
            bg=C.SURFACE, fg=C.TEXT_PRIMARY,
            selectbackground=C.ACCENT, selectforeground="white",
            relief=tk.FLAT, bd=0, padx=16, pady=12,
            highlightthickness=0
        )
        self.stats_display.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        self.stats_display.tag_configure("title", foreground=C.ACCENT, font=(self._cn_font, 16, "bold"))
        self.stats_display.tag_configure("separator", foreground=C.BORDER)
        self.stats_display.tag_configure("section", foreground=C.ACCENT, font=(self._cn_font, 13, "bold"))
        self.stats_display.tag_configure("stat_label", foreground=C.TEXT_SECONDARY, font=(self._cn_font, 12))
        self.stats_display.tag_configure("stat_value", foreground=C.TEXT_PRIMARY, font=(self._cn_font, 12, "bold"))
        self.stats_display.tag_configure("bar_fill", foreground=C.ACCENT)
        self.stats_display.tag_configure("bar_empty", foreground=C.BORDER_LIGHT)
        self.stats_display.tag_configure("dim", foreground=C.TEXT_TERTIARY)

    def _refresh_stats(self):
        summary = get_review_stats_summary()
        idioms = load_idioms()

        self.stats_header.config(
            text=f"{summary['total']} 个成语  |  {summary['mastered']} 已掌握  |  {summary['reviewed']} 已复习"
        )

        self.stats_display.config(state=tk.NORMAL)
        self.stats_display.delete("1.0", tk.END)

        self.stats_display.insert(tk.END, "成语积累统计报告\n", "title")
        self.stats_display.insert(tk.END, "─" * 50 + "\n\n", "separator")

        self.stats_display.insert(tk.END, "总览\n", "section")
        self.stats_display.insert(tk.END, "  总成语数：", "stat_label")
        self.stats_display.insert(tk.END, f"{summary['total']}\n", "stat_value")
        self.stats_display.insert(tk.END, "  已复习数：", "stat_label")
        self.stats_display.insert(tk.END, f"{summary['reviewed']}\n", "stat_value")
        self.stats_display.insert(tk.END, "  已掌握数：", "stat_label")
        self.stats_display.insert(tk.END, f"{summary['mastered']}\n", "stat_value")
        self.stats_display.insert(tk.END, "  平均掌握度：", "stat_label")
        self.stats_display.insert(tk.END, f"{summary['avg_mastery']:.1f} / 5.0\n\n", "stat_value")

        self.stats_display.insert(tk.END, "掌握度分布\n", "section")
        self.stats_display.insert(tk.END, "─" * 50 + "\n", "separator")

        level_names = ["未复习", "初识  ", "了解  ", "熟悉  ", "掌握  ", "精通  "]
        level_counts = [0] * 6

        for idiom in idioms:
            level = idiom.get("review_stats", {}).get("mastery_level", 0)
            level_counts[level] += 1

        max_count = max(level_counts) if level_counts else 1
        bar_width = 25

        for level, count in enumerate(level_counts):
            filled = int((count / max_count) * bar_width) if max_count > 0 else 0
            empty = bar_width - filled
            bar_filled = "█" * filled
            bar_empty = "░" * empty
            name = level_names[level] if level < len(level_names) else f"Lv.{level}"
            self.stats_display.insert(tk.END, f"  Lv.{level} {name}: ", "stat_label")
            self.stats_display.insert(tk.END, bar_filled, "bar_fill")
            self.stats_display.insert(tk.END, bar_empty, "bar_empty")
            self.stats_display.insert(tk.END, f" ({count})\n", "stat_value")

        self.stats_display.insert(tk.END, "\n")

        self.stats_display.insert(tk.END, "最近添加\n", "section")
        self.stats_display.insert(tk.END, "─" * 50 + "\n", "separator")

        sorted_idioms = sorted(idioms, key=lambda x: x.get("added_at", ""), reverse=True)

        for i, idiom in enumerate(sorted_idioms[:10]):
            name = idiom["name"]
            level = idiom.get("review_stats", {}).get("mastery_level", 0)
            stars = "★" * level + "☆" * (5 - level)
            added = idiom.get("added_at", "未知")
            self.stats_display.insert(tk.END, f"  {i+1:2d}. ", "dim")
            self.stats_display.insert(tk.END, f"{name}", "stat_label")
            self.stats_display.insert(tk.END, f" {stars} ", "dim")
            self.stats_display.insert(tk.END, f"({added})\n", "dim")

        self.stats_display.insert(tk.END, "\n")
        self.stats_display.insert(tk.END, "─" * 50 + "\n", "separator")
        self.stats_display.insert(tk.END, "  所有数据已自动保存到本地\n", "dim")


def main():
    root = tk.Tk()

    style = ttk.Style()
    available = style.theme_names()
    if "clam" in available:
        style.theme_use("clam")

    _cn_font = "PingFang SC" if sys.platform == "darwin" else "Microsoft YaHei"

    # macOS 风格 Notebook 样式
    style.configure("TNotebook", background=C.BG, borderwidth=0)
    style.configure(
        "TNotebook.Tab",
        font=(_cn_font, 12),
        padding=[20, 8],
        background=C.TOOLBAR,
        foreground=C.TEXT_SECONDARY,
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", C.BG)],
        foreground=[("selected", C.ACCENT)],
        expand=[("selected", [0, 0, 0, 2])],
    )
    style.configure("TPanedwindow", background=C.BG)
    style.configure("Sash", sashthickness=6)
    style.configure(
        "TProgressbar",
        troughcolor=C.PROGRESS_BG,
        background=C.ACCENT,
        borderwidth=0,
        thickness=6,
    )

    app = IdoimApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

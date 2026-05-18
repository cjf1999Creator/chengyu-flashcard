"""
成语积累与复习 - 闪卡应用主程序
使用 tkinter 构建 GUI 界面
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import random
import re
import os
import sys

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from parser import parse_idiom_text, parse_multiple_idioms, format_flashcard_back, idiom_to_editable_text, get_last_parse_errors
from storage import (
    load_idioms, add_idiom, add_idioms_batch, update_review_stats,
    set_mastery_level, delete_idiom, get_idiom_names, search_idioms, get_review_stats_summary
)


# ==================== 颜色插值辅助函数 ====================

def hex_to_rgb(hex_color):
    """将十六进制颜色转换为 RGB 元组"""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def rgb_to_hex(r, g, b):
    """将 RGB 转换为十六进制颜色"""
    return f'#{int(r):02x}{int(g):02x}{int(b):02x}'


def lerp_color(color1, color2, t):
    """在两个颜色之间线性插值，t 从 0 到 1"""
    r1, g1, b1 = hex_to_rgb(color1)
    r2, g2, b2 = hex_to_rgb(color2)
    r = r1 + (r2 - r1) * t
    g = g1 + (g2 - g1) * t
    b = b1 + (b2 - b1) * t
    return rgb_to_hex(r, g, b)


class IdoimApp:
    """成语闪卡应用主窗口"""

    def __init__(self, root):
        self.root = root
        self.root.title("成语积累 - 闪卡复习系统")
        self.root.geometry("950x750")
        self.root.minsize(800, 600)

        # Apple 风格字体设置
        if sys.platform == "darwin":
            self._cn_font = "PingFang SC"
            self._ui_font = "Helvetica Neue"    # 苹果英文字体
            self._mono_font = "Menlo"            # 苹果等宽字体
        else:
            self._cn_font = "Microsoft YaHei"
            self._ui_font = "Segoe UI"
            self._mono_font = "Consolas"

        self.font_title = (self._cn_font, 18, "bold")
        self.font_normal = (self._ui_font, 12)
        self.font_button = (self._ui_font, 11)
        self.font_small = (self._ui_font, 10)
        self.font_button_big = (self._ui_font, 13, "bold")

        # 闪卡字体（可通过界面调节大小）
        self._card_front_size = 40
        self._card_back_size = 13
        self.font_card_front = (self._cn_font, self._card_front_size, "bold")
        self.font_card_back = (self._cn_font, self._card_back_size)

        # 复习状态
        self.current_review_list = []
        self.current_index = 0
        self.is_showing_back = False
        self._animating = False  # 动画锁

        # 编辑状态
        self.is_editing = False
        self.editing_idiom_name = None

        # 构建界面
        self._build_ui()
        self._bind_shortcuts()
        self._refresh_stats()

        # 关闭时自动保存（数据已在 storage.py 中实时保存到 JSON）
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_close(self):
        """关闭窗口时的处理"""
        self.root.destroy()

    # ==================== 快捷键绑定 ====================

    def _bind_shortcuts(self):
        """绑定全局快捷键"""
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
        """构建主界面"""
        # 顶部标题栏
        header = tk.Frame(self.root, bg="#2C3E50", height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        title_label = tk.Label(
            header, text="📚 成语积累 · 闪卡复习系统",
            font=self.font_title, bg="#2C3E50", fg="white"
        )
        title_label.pack(side=tk.LEFT, padx=20, pady=8)

        stats_label = tk.Label(
            header, text="",
            font=self.font_small, bg="#2C3E50", fg="#BDC3C7",
            name="stats_header"
        )
        stats_label.pack(side=tk.RIGHT, padx=20, pady=8)
        self.stats_header = stats_label

        # 主内容区域 - 使用 Notebook 实现标签页
        notebook = ttk.Notebook(self.root)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 标签页1: 导入成语
        self.import_frame = tk.Frame(notebook)
        notebook.add(self.import_frame, text="  📥 导入成语  ")
        self._build_import_tab()

        # 标签页2: 成语库
        self.library_frame = tk.Frame(notebook)
        notebook.add(self.library_frame, text="  📖 成语库  ")
        self._build_library_tab()

        # 标签页3: 闪卡复习
        self.review_frame = tk.Frame(notebook)
        notebook.add(self.review_frame, text="  🔄 闪卡复习  ")
        self._build_review_tab()

        # 标签页4: 统计
        self.stats_frame = tk.Frame(notebook)
        notebook.add(self.stats_frame, text="  📊 统计  ")
        self._build_stats_tab()

    # ==================== 导入成语标签页 ====================

    def _build_import_tab(self):
        """构建导入标签页"""
        # 说明文字
        info_frame = tk.Frame(self.import_frame, bg="#ECF0F1")
        info_frame.pack(fill=tk.X, padx=15, pady=(10, 5))

        info_text = (
            "请将成语卡片文本粘贴到下方文本框中，支持一次导入多个成语。\n"
            "格式：【成语: 成语名 (拼音)】后，每行一个知识点，格式为「标签：内容」\n"
            "如：核心释义: xxx\n    字面含义: xxx\n    情感色彩: xxx"
        )
        tk.Label(
            info_frame, text=info_text,
            font=self.font_small, fg="#555555", bg="#ECF0F1", justify=tk.LEFT
        ).pack(anchor=tk.W)

        # 文本输入区 - 深色背景白色字体
        # 按钮区 - 独立醒目区域（放在顶部，始终可见）
        btn_frame = tk.LabelFrame(
            self.import_frame, text="  操作  ",
            font=self.font_normal, padx=10, pady=10
        )
        btn_frame.pack(fill=tk.X, padx=15, pady=5)

        # 使用 PanedWindow 让上下两个文本区可自由拖拽调整大小
        import_paned = ttk.PanedWindow(self.import_frame, orient=tk.VERTICAL)
        import_paned.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 10))

        # 上半部分：输入区
        top_frame = tk.Frame(import_paned)
        import_paned.add(top_frame, weight=1)

        input_label = tk.Label(top_frame, text="📝 粘贴成语文本：", font=self.font_normal, anchor=tk.W)
        input_label.pack(fill=tk.X)

        self.import_text = scrolledtext.ScrolledText(
            top_frame, font=("Courier New", 12), wrap=tk.WORD,
            bg="#1E1E1E", fg="#FFFFFF", insertbackground="white",
            selectbackground="#264F78", selectforeground="white",
            relief=tk.SUNKEN, bd=2
        )
        self.import_text.pack(fill=tk.BOTH, expand=True, pady=(2, 0))

        btn_row1 = tk.Frame(btn_frame)
        btn_row1.pack(fill=tk.X, pady=(0, 5))

        tk.Button(
            btn_row1, text="📂 从文件导入", font=self.font_button_big,
            bg="#8E44AD", fg="white", relief=tk.RAISED, bd=2,
            padx=25, pady=10, cursor="hand2",
            command=self._import_from_file
        ).pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(
            btn_row1, text="🔍 预览解析结果", font=self.font_button_big,
            bg="#3498DB", fg="white", relief=tk.RAISED, bd=2,
            padx=25, pady=10, cursor="hand2",
            command=self._preview_import
        ).pack(side=tk.LEFT, padx=(0, 10))

        tk.Button(
            btn_row1, text="🗑 清空文本", font=self.font_button_big,
            bg="#E74C3C", fg="white", relief=tk.RAISED, bd=2,
            padx=25, pady=10, cursor="hand2",
            command=lambda: self.import_text.delete("1.0", tk.END)
        ).pack(side=tk.LEFT)

        tk.Button(
            btn_row1, text="✅ 确认导入到成语库", font=(self._cn_font, 14, "bold"),
            bg="#27AE60", fg="white", relief=tk.RAISED, bd=3,
            padx=35, pady=10, cursor="hand2",
            command=self._do_import
        ).pack(side=tk.RIGHT)

        # 下半部分：预览区
        bottom_frame = tk.Frame(import_paned)
        import_paned.add(bottom_frame, weight=1)

        preview_label = tk.Label(
            bottom_frame, text="📋 解析预览：",
            font=self.font_normal, anchor=tk.W
        )
        preview_label.pack(fill=tk.X)

        self.preview_text = scrolledtext.ScrolledText(
            bottom_frame, font=self.font_small, wrap=tk.WORD,
            bg="#F5F5DC", fg="#333333", relief=tk.GROOVE, bd=2
        )
        self.preview_text.pack(fill=tk.BOTH, expand=True, pady=(2, 0))

    def _preview_import(self):
        """预览解析结果（带错误提示）"""
        text = self.import_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("提示", "请先输入成语文本！")
            return

        idioms = parse_multiple_idioms(text)
        errors = get_last_parse_errors()

        self.preview_text.delete("1.0", tk.END)

        if not idioms and not errors:
            messagebox.showerror("错误", "未能解析出任何成语，请检查格式！\n\n需要以 【词汇卡片：成语名】 开头")
            return

        # 显示成功解析的成语
        for idiom in idioms:
            self.preview_text.insert(tk.END, f"{'='*50}\n")
            self.preview_text.insert(tk.END, format_flashcard_back(idiom))
            self.preview_text.insert(tk.END, "\n")

        # 显示解析警告/错误
        if errors:
            self.preview_text.insert(tk.END, f"\n{'⚠️'*20}\n")
            self.preview_text.insert(tk.END, "⚠️ 解析警告：\n")
            for err in errors:
                self.preview_text.insert(tk.END, f"  • {err}\n")
            self.preview_text.insert(tk.END, f"\n提示：可以导入后在「成语库」中点击「编辑」按钮修正内容\n")

        if idioms:
            msg = f"✅ 成功解析 {len(idioms)} 个成语！"
            if errors:
                msg += f"\n⚠️ 有 {len(errors)} 个警告（见预览区底部）"
            messagebox.showinfo("预览结果", msg)
        else:
            messagebox.showerror("解析失败", f"未能解析出任何成语。\n\n错误信息：\n" + "\n".join(errors[:5]))

    def _do_import(self):
        """执行导入（带错误报告）"""
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

        # 构建结果消息
        msg = f"✅ 成功导入 {count} 个成语！\n数据已自动保存到本地。"
        if errors:
            msg += f"\n\n⚠️ 有 {len(errors)} 个卡片解析失败：\n"
            msg += "\n".join(errors[:3])
            if len(errors) > 3:
                msg += f"\n... 还有 {len(errors)-3} 个"
            msg += "\n\n💡 可以稍后通过「成语库→编辑」手动修正。"
        messagebox.showinfo("导入完成", msg)

        self.import_text.delete("1.0", tk.END)
        self.preview_text.delete("1.0", tk.END)
        self._refresh_stats()
        self._refresh_library()

    def _import_from_file(self):
        """从文件导入"""
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
            messagebox.showinfo("成功", f"已加载文件内容，请预览后确认导入。")
        except Exception as e:
            messagebox.showerror("错误", f"读取文件失败: {e}")

    # ==================== 成语库标签页（可拖拽分隔条） ====================

    def _build_library_tab(self):
        """构建成语库标签页 - 使用 PanedWindow 实现可拖拽调整大小"""
        # 搜索栏
        search_frame = tk.Frame(self.library_frame)
        search_frame.pack(fill=tk.X, padx=15, pady=10)

        tk.Label(search_frame, text="搜索：", font=self.font_normal).pack(side=tk.LEFT)

        self.search_entry = tk.Entry(search_frame, font=self.font_normal, width=25)
        self.search_entry.pack(side=tk.LEFT, padx=5)
        self.search_entry.bind("<Return>", lambda e: self._search_idioms())

        tk.Button(
            search_frame, text="🔍 搜索", font=self.font_button,
            bg="#3498DB", fg="white", relief=tk.FLAT,
            padx=15, cursor="hand2",
            command=self._search_idioms
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            search_frame, text="📋 显示全部", font=self.font_button,
            bg="#95A5A6", fg="white", relief=tk.FLAT,
            padx=15, cursor="hand2",
            command=self._refresh_library
        ).pack(side=tk.LEFT, padx=5)

        # 使用 PanedWindow 实现可拖拽分隔
        paned = ttk.PanedWindow(self.library_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 5))

        # 左侧列表
        left_frame = tk.Frame(paned)
        paned.add(left_frame, weight=1)

        tk.Label(left_frame, text="成语列表", font=self.font_normal, anchor=tk.W).pack(fill=tk.X)

        self.idiom_listbox = tk.Listbox(
            left_frame, font=self.font_normal,
            selectmode=tk.SINGLE, relief=tk.GROOVE, bd=2,
            bg="#1E1E1E", fg="#FFFFFF", selectbackground="#264F78",
            selectforeground="white"
        )
        self.idiom_listbox.pack(fill=tk.BOTH, expand=True, pady=5)
        self.idiom_listbox.bind("<<ListboxSelect>>", self._on_idiom_select)

        # 右侧详情 - 深色背景白色字体
        right_frame = tk.Frame(paned)
        paned.add(right_frame, weight=2)

        tk.Label(right_frame, text="成语详情", font=self.font_normal, anchor=tk.W).pack(fill=tk.X)

        self.detail_text = scrolledtext.ScrolledText(
            right_frame, font=self.font_card_back, wrap=tk.WORD,
            bg="#1E1E1E", fg="#D4D4D4", insertbackground="white",
            selectbackground="#264F78", selectforeground="white",
            relief=tk.GROOVE, bd=2
        )
        self.detail_text.pack(fill=tk.BOTH, expand=True, pady=5)

        # 配置详情文本的标签样式
        self.detail_text.tag_configure("title", foreground="#569CD6", font=(self._cn_font, 14, "bold"))
        self.detail_text.tag_configure("section", foreground="#4EC9B0", font=(self._cn_font, 12, "bold"))
        self.detail_text.tag_configure("label", foreground="#9CDCFE", font=(self._cn_font, 11, "bold"))
        self.detail_text.tag_configure("content", foreground="#D4D4D4", font=(self._cn_font, 11))
        self.detail_text.tag_configure("highlight", foreground="#FFD700", font=(self._cn_font, 11, "bold"))

        # 详情操作按钮栏
        detail_btn_frame = tk.Frame(right_frame)
        detail_btn_frame.pack(fill=tk.X, pady=(2, 0))

        self.btn_view_mode = tk.Button(
            detail_btn_frame, text="📖 查看模式", font=self.font_button,
            bg="#3498DB", fg="white", relief=tk.FLAT,
            padx=12, cursor="hand2",
            command=self._enter_view_mode
        )
        self.btn_view_mode.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_edit = tk.Button(
            detail_btn_frame, text="✏️ 编辑", font=self.font_button,
            bg="#F39C12", fg="white", relief=tk.FLAT,
            padx=12, cursor="hand2",
            command=self._enter_edit_mode
        )
        self.btn_edit.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_save = tk.Button(
            detail_btn_frame, text="💾 保存", font=self.font_button,
            bg="#27AE60", fg="white", relief=tk.FLAT,
            padx=12, cursor="hand2",
            command=self._save_edit
        )
        self.btn_save.pack(side=tk.LEFT, padx=(0, 5))

        self.btn_cancel_edit = tk.Button(
            detail_btn_frame, text="❌ 取消", font=self.font_button,
            bg="#95A5A6", fg="white", relief=tk.FLAT,
            padx=12, cursor="hand2",
            command=self._cancel_edit
        )
        self.btn_cancel_edit.pack(side=tk.LEFT)

        # 编辑状态提示
        self.edit_status_label = tk.Label(
            detail_btn_frame, text="", font=self.font_small, fg="#27AE60"
        )
        self.edit_status_label.pack(side=tk.RIGHT)

        # 底部按钮
        bottom_frame = tk.Frame(self.library_frame)
        bottom_frame.pack(fill=tk.X, padx=15, pady=10)

        tk.Button(
            bottom_frame, text="🗑 删除选中", font=self.font_button,
            bg="#E74C3C", fg="white", relief=tk.FLAT,
            padx=15, cursor="hand2",
            command=self._delete_selected_idiom
        ).pack(side=tk.LEFT)

        self.library_count_label = tk.Label(
            bottom_frame, text="", font=self.font_small, fg="#7F8C8D"
        )
        self.library_count_label.pack(side=tk.RIGHT)

        # 初始状态：查看模式
        self._enter_view_mode()

        # 初始化列表
        self._refresh_library()

    def _refresh_library(self):
        """刷新成语库列表"""
        idioms = load_idioms()
        self.idiom_listbox.delete(0, tk.END)
        self.all_idioms = idioms
        for idiom in idioms:
            mastery = idiom.get("review_stats", {}).get("mastery_level", 0)
            stars = "⭐" * mastery + "☆" * (5 - mastery)
            self.idiom_listbox.insert(tk.END, f"  {idiom['name']}  {stars}")
        self.library_count_label.config(text=f"共 {len(idioms)} 个成语 | 数据已自动保存")

    def _search_idioms(self):
        """搜索成语"""
        keyword = self.search_entry.get().strip()
        if not keyword:
            self._refresh_library()
            return

        results = search_idioms(keyword)
        self.idiom_listbox.delete(0, tk.END)
        self.all_idioms = results
        for idiom in results:
            mastery = idiom.get("review_stats", {}).get("mastery_level", 0)
            stars = "⭐" * mastery + "☆" * (5 - mastery)
            self.idiom_listbox.insert(tk.END, f"  {idiom['name']}  {stars}")
        self.library_count_label.config(text=f"找到 {len(results)} 个成语")

    def _on_idiom_select(self, event):
        """选中成语时显示详情（编辑模式下不覆盖）"""
        if self.is_editing:
            return  # 编辑模式下不自动覆盖

        selection = self.idiom_listbox.curselection()
        if not selection:
            return

        index = selection[0]
        if index < len(self.all_idioms):
            idiom = self.all_idioms[index]
            self._show_idiom_detail(idiom)
            self.detail_text.config(state=tk.DISABLED)

    def _show_idiom_detail(self, idiom):
        """用带颜色标签的方式显示成语详情"""
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)

        # 标题
        self.detail_text.insert(tk.END, f"【{idiom['name']}】\n\n", "title")

        raw_text = idiom.get("raw_text")
        if raw_text:
            # 原文格式显示
            self.detail_text.insert(tk.END, raw_text, "content")
        else:
            # 向后兼容旧数据
            for kp in idiom["knowledge_points"]:
                label = kp["label"]
                content = kp["content"]
                self.detail_text.insert(tk.END, f"📌 {label}\n", "section")
                content_lines = content.split('\n')
                for cl in content_lines:
                    cl = cl.strip()
                    if not cl:
                        continue
                    sub_match = re.match(r'^([^:：]{1,20})[：:]\s*(.*)', cl)
                    if sub_match:
                        self.detail_text.insert(tk.END, f"  • {sub_match.group(1)}：", "label")
                        self.detail_text.insert(tk.END, f"{sub_match.group(2)}\n", "content")
                    else:
                        self.detail_text.insert(tk.END, f"  {cl}\n", "content")
                self.detail_text.insert(tk.END, "\n")

    def _delete_selected_idiom(self):
        """删除选中的成语"""
        selection = self.idiom_listbox.curselection()
        if not selection:
            messagebox.showwarning("提示", "请先选择一个成语！")
            return

        index = selection[0]
        if index < len(self.all_idioms):
            name = self.all_idioms[index]["name"]
            if messagebox.askyesno("确认删除", f"确定要删除「{name}」吗？"):
                delete_idiom(name)
                self._refresh_library()
                self.detail_text.delete("1.0", tk.END)
                self._refresh_stats()

    # ==================== 成语编辑功能 ====================

    def _enter_view_mode(self):
        """进入查看模式：详情只读，编辑按钮可用"""
        self.is_editing = False
        self.editing_idiom_name = None
        self.detail_text.config(state=tk.DISABLED)
        self.btn_view_mode.config(bg="#3498DB")
        self.btn_edit.config(bg="#F39C12")
        self.btn_save.config(state=tk.DISABLED)
        self.btn_cancel_edit.config(state=tk.DISABLED)
        self.edit_status_label.config(text="📖 查看模式", fg="#3498DB")

    def _enter_edit_mode(self):
        """进入编辑模式：加载可编辑的原始文本"""
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

        # 加载可编辑文本
        editable_text = idiom_to_editable_text(idiom)
        self.detail_text.config(state=tk.NORMAL)
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert("1.0", editable_text)

        # 更新按钮状态
        self.btn_view_mode.config(bg="#95A5A6")
        self.btn_edit.config(bg="#E67E22")
        self.btn_save.config(state=tk.NORMAL)
        self.btn_cancel_edit.config(state=tk.NORMAL)
        self.edit_status_label.config(text="✏️ 编辑模式 - 修改后点击「保存」", fg="#F39C12")

    def _save_edit(self):
        """保存编辑内容"""
        if not self.is_editing or not self.editing_idiom_name:
            return

        edited_text = self.detail_text.get("1.0", tk.END).strip()
        if not edited_text:
            messagebox.showwarning("提示", "内容不能为空！")
            return

        # 重新解析编辑后的文本
        parsed = parse_idiom_text(edited_text)
        if not parsed or not parsed["name"]:
            messagebox.showerror(
                "解析失败",
                "无法解析编辑后的文本！\n"
                "请确保格式正确：\n"
                "【词汇卡片：成语名】\n"
                "核心释义: ...\n"
                "辨析要点: ...\n"
                "真题场景: ..."
            )
            return

        if not parsed.get("raw_text") and not parsed.get("knowledge_points"):
            messagebox.showwarning(
                "警告",
                f"解析到「{parsed['name']}」但没有知识点内容。\n"
                "请检查各章节标题（核心释义/辨析要点/真题场景）是否正确。"
            )
            return

        # 如果改了名字，删除旧记录
        if parsed["name"] != self.editing_idiom_name:
            delete_idiom(self.editing_idiom_name)

        # 保存更新
        add_idiom(parsed)

        self.edit_status_label.config(text="✅ 保存成功！", fg="#27AE60")
        self.is_editing = False
        self.editing_idiom_name = None

        # 刷新界面
        self._refresh_library()
        self._refresh_stats()

        # 自动切回查看模式并显示更新后的内容
        self._enter_view_mode()
        self.detail_text.config(state=tk.NORMAL)
        updated = None
        for idiom in load_idioms():
            if idiom["name"] == parsed["name"]:
                updated = idiom
                break
        if updated:
            self._show_idiom_detail(updated)
            # 选中新更新成语在列表中的位置
            for i, idiom in enumerate(self.all_idioms):
                if idiom["name"] == parsed["name"]:
                    self.idiom_listbox.selection_clear(0, tk.END)
                    self.idiom_listbox.selection_set(i)
                    self.idiom_listbox.see(i)
                    break

    def _cancel_edit(self):
        """取消编辑，恢复查看模式"""
        self.is_editing = False
        self.editing_idiom_name = None
        self._enter_view_mode()

        # 重新显示当前选中的成语详情
        selection = self.idiom_listbox.curselection()
        if selection:
            index = selection[0]
            if index < len(self.all_idioms):
                self.detail_text.config(state=tk.NORMAL)
                self._show_idiom_detail(self.all_idioms[index])

    # ==================== 闪卡复习标签页（带动画+快捷键） ====================

    def _build_review_tab(self):
        """构建闪卡复习标签页"""
        # 快捷键提示
        shortcut_bar = tk.Frame(self.review_frame, bg="#ECF0F1")
        shortcut_bar.pack(fill=tk.X, padx=15, pady=(8, 2))

        shortcuts_text = "⌨️ 快捷键：  Space = 翻转  |  K/→ = 下一个  |  J/← = 上一个  |  A = 认识  |  D = 不认识  |  S = 已掌握"
        tk.Label(
            shortcut_bar, text=shortcuts_text,
            font=self.font_small, fg="#666666", bg="#ECF0F1"
        ).pack(anchor=tk.W, padx=5)

        # 顶部控制栏
        control_frame = tk.Frame(self.review_frame)
        control_frame.pack(fill=tk.X, padx=15, pady=5)

        tk.Label(control_frame, text="复习模式：", font=self.font_normal).pack(side=tk.LEFT)

        self.review_mode = tk.StringVar(value="all")
        modes = [
            ("全部成语", "all"),
            ("随机20个", "random20"),
            ("仅未掌握", "unmastered"),
            ("仅已掌握", "mastered"),
        ]
        for text, value in modes:
            tk.Radiobutton(
                control_frame, text=text, variable=self.review_mode,
                value=value, font=self.font_small
            ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            control_frame, text="🔄 开始复习", font=self.font_button,
            bg="#27AE60", fg="white", relief=tk.FLAT,
            padx=20, pady=5, cursor="hand2",
            command=self._start_review
        ).pack(side=tk.RIGHT)

        # 字体大小调节
        font_frame = tk.Frame(control_frame)
        font_frame.pack(side=tk.RIGHT, padx=15)

        tk.Label(font_frame, text="字号：", font=(self._ui_font, 10)).pack(side=tk.LEFT)

        tk.Button(
            font_frame, text="A-", font=(self._ui_font, 10, "bold"),
            bg="#7F8C8D", fg="white", relief=tk.FLAT, width=3,
            cursor="hand2", command=self._font_size_down
        ).pack(side=tk.LEFT, padx=2)

        self.font_size_var = tk.IntVar(value=self._card_back_size)
        self.font_size_scale = tk.Scale(
            font_frame, from_=8, to=24, orient=tk.HORIZONTAL,
            variable=self.font_size_var, length=100,
            showvalue=True, font=(self._ui_font, 8),
            command=self._on_font_size_change
        )
        self.font_size_scale.pack(side=tk.LEFT, padx=2)

        tk.Button(
            font_frame, text="A+", font=(self._ui_font, 10, "bold"),
            bg="#7F8C8D", fg="white", relief=tk.FLAT, width=3,
            cursor="hand2", command=self._font_size_up
        ).pack(side=tk.LEFT, padx=2)

        # 进度条
        progress_frame = tk.Frame(self.review_frame)
        progress_frame.pack(fill=tk.X, padx=15)

        self.progress_label = tk.Label(
            progress_frame, text="点击「开始复习」",
            font=self.font_small, fg="#7F8C8D"
        )
        self.progress_label.pack(side=tk.LEFT)

        self.progress_bar = ttk.Progressbar(
            progress_frame, mode="determinate", length=400
        )
        self.progress_bar.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=(10, 0))

        # 闪卡区域
        self.card_frame = tk.Frame(
            self.review_frame, bg="white",
            relief=tk.RAISED, bd=3
        )
        self.card_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

        # 使用 Text 替代 Label 以支持富文本对齐
        self.card_text = tk.Text(
            self.card_frame, font=self.font_card_front,
            bg="white", fg="#2C3E50", wrap=tk.WORD,
            relief=tk.FLAT, bd=0, padx=30, pady=20,
            cursor="arrow", spacing1=2, spacing3=2
        )
        self.card_text.pack(fill=tk.BOTH, expand=True)
        self.card_text.config(state=tk.DISABLED)

        # 配置卡片文本标签样式
        self.card_text.tag_configure("center", justify=tk.CENTER)
        self.card_text.tag_configure("left", justify=tk.LEFT)
        self.card_text.tag_configure("name", font=(self._cn_font, self._card_front_size, "bold"), justify=tk.CENTER)
        self.card_text.tag_configure("hint", font=(self._ui_font, 12), foreground="#AAAAAA", justify=tk.CENTER)
        self.card_text.tag_configure("section_title", font=(self._cn_font, max(10, self._card_back_size), "bold"), foreground="#2C3E50")
        self.card_text.tag_configure("label", font=(self._cn_font, max(9, self._card_back_size - 1), "bold"), foreground="#34495E")
        self.card_text.tag_configure("body", font=(self._cn_font, self._card_back_size), foreground="#333333")
        self.card_text.tag_configure("divider", font=(self._ui_font, 8), foreground="#CCCCCC")
        self.card_text.tag_configure("mastery", font=(self._ui_font, 14), foreground="#F39C12", justify=tk.CENTER)
        self.card_text.tag_configure("mastery_back", font=(self._cn_font, max(9, self._card_back_size)), foreground="#F39C12")

        # 初始占位
        self._show_card_placeholder()

        # 底部操作按钮
        action_frame = tk.Frame(self.review_frame)
        action_frame.pack(fill=tk.X, padx=15, pady=10)

        tk.Button(
            action_frame, text="👈 上一个 (J)", font=self.font_button,
            bg="#95A5A6", fg="white", relief=tk.FLAT,
            padx=20, pady=8, cursor="hand2",
            command=self._prev_card
        ).pack(side=tk.LEFT)

        tk.Button(
            action_frame, text="🔄 翻转 (Space)", font=self.font_button,
            bg="#3498DB", fg="white", relief=tk.FLAT,
            padx=20, pady=8, cursor="hand2",
            command=self._flip_card
        ).pack(side=tk.LEFT, padx=10)

        tk.Button(
            action_frame, text="👉 下一个 (K)", font=self.font_button,
            bg="#95A5A6", fg="white", relief=tk.FLAT,
            padx=20, pady=8, cursor="hand2",
            command=self._next_card
        ).pack(side=tk.LEFT)

        # 掌握程度按钮
        master_frame = tk.Frame(action_frame)
        master_frame.pack(side=tk.RIGHT)

        tk.Button(
            master_frame, text="❌ 不认识 (D)", font=self.font_button,
            bg="#E74C3C", fg="white", relief=tk.FLAT,
            padx=15, pady=8, cursor="hand2",
            command=lambda: self._mark_card(False)
        ).pack(side=tk.RIGHT)

        tk.Button(
            master_frame, text="✅ 认识 (A)", font=self.font_button,
            bg="#27AE60", fg="white", relief=tk.FLAT,
            padx=15, pady=8, cursor="hand2",
            command=lambda: self._mark_card(True)
        ).pack(side=tk.RIGHT, padx=5)

        tk.Button(
            master_frame, text="👑 已掌握 (S)", font=self.font_button,
            bg="#F39C12", fg="white", relief=tk.FLAT,
            padx=15, pady=8, cursor="hand2",
            command=self._mark_mastered
        ).pack(side=tk.RIGHT, padx=5)

    def _font_size_up(self):
        """增大闪卡字体"""
        self._card_back_size = min(24, self._card_back_size + 1)
        self._card_front_size = min(60, self._card_front_size + 2)
        self.font_size_var.set(self._card_back_size)
        self._apply_font_size()

    def _font_size_down(self):
        """减小闪卡字体"""
        self._card_back_size = max(8, self._card_back_size - 1)
        self._card_front_size = max(20, self._card_front_size - 2)
        self.font_size_var.set(self._card_back_size)
        self._apply_font_size()

    def _on_font_size_change(self, val):
        """滑块改变字体大小"""
        new_size = int(float(val))
        diff = new_size - self._card_back_size
        if diff != 0:
            self._card_back_size = new_size
            self._card_front_size = max(20, min(60, self._card_front_size + diff * 2))
            self._apply_font_size()

    def _apply_font_size(self):
        """应用当前字体大小设置"""
        self.font_card_front = (self._cn_font, self._card_front_size, "bold")
        self.font_card_back = (self._cn_font, self._card_back_size)
        # 如果正在复习，刷新当前卡片
        if self.current_review_list and not self._animating:
            if self.is_showing_back:
                self._show_back_content()
            else:
                self._show_front_content()

    def _show_card_placeholder(self):
        """显示卡片占位内容"""
        self.card_text.config(state=tk.NORMAL)
        self.card_text.delete("1.0", tk.END)
        self.card_text.tag_configure("name", font=(self._cn_font, 28, "bold"), justify=tk.CENTER)
        self.card_text.tag_configure("hint", font=(self._ui_font, 14), foreground="#AAAAAA", justify=tk.CENTER)
        self.card_text.insert(tk.END, "\n\n\n", "center")
        self.card_text.insert(tk.END, "📚\n\n", "center")
        self.card_text.insert(tk.END, "点击「开始复习」\n", "name")
        self.card_text.insert(tk.END, "进入闪卡模式\n", "hint")
        self.card_text.config(state=tk.DISABLED)

    def _start_review(self):
        """开始复习"""
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
                messagebox.showinfo("恭喜", "所有成语都已掌握！🎉")
                return
        elif mode == "mastered":
            self.current_review_list = [
                i for i in all_idioms
                if i.get("review_stats", {}).get("mastery_level", 0) >= 4
            ]
            if not self.current_review_list:
                messagebox.showinfo("提示", "还没有已掌握的成语，先复习一些吧！")
                return

        random.shuffle(self.current_review_list)
        self.current_index = 0
        self.is_showing_back = False
        self._show_current_card()

    def _update_card_tags(self):
        """更新卡片 Text 标签的字体大小"""
        self.card_text.tag_configure("name", font=(self._cn_font, self._card_front_size, "bold"), justify=tk.CENTER)
        self.card_text.tag_configure("hint", font=(self._ui_font, max(10, self._card_front_size // 3)), foreground="#AAAAAA", justify=tk.CENTER)
        self.card_text.tag_configure("section_title", font=(self._cn_font, max(10, self._card_back_size + 2), "bold"), foreground="#2C3E50", justify=tk.LEFT)
        self.card_text.tag_configure("label", font=(self._cn_font, max(9, self._card_back_size), "bold"), foreground="#34495E", justify=tk.LEFT)
        self.card_text.tag_configure("body", font=(self._cn_font, self._card_back_size), foreground="#333333", justify=tk.LEFT)
        self.card_text.tag_configure("divider", font=(self._ui_font, 8), foreground="#DDDDDD", justify=tk.CENTER)

    def _get_mastery_stars(self, level):
        """获取掌握程度的星星字符串"""
        return "⭐" * level + "☆" * (5 - level)

    def _get_mastery_label(self, level):
        """获取掌握程度的文字标签"""
        labels = ["未复习", "初识", "了解", "熟悉", "掌握", "精通"]
        return labels[level] if level < len(labels) else f"Lv.{level}"

    def _show_current_card(self):
        """显示当前卡片（正面）"""
        if not self.current_review_list:
            return

        total = len(self.current_review_list)
        current = self.current_index + 1
        idiom = self.current_review_list[self.current_index]
        mastery = idiom.get("review_stats", {}).get("mastery_level", 0)

        self.progress_label.config(text=f"进度：{current} / {total}  |  当前掌握度：{self._get_mastery_stars(mastery)} {self._get_mastery_label(mastery)}")
        self.progress_bar["value"] = (current / total) * 100

        self.is_showing_back = False
        self._update_card_tags()

        # 清空并写入正面内容（居中对齐）
        self.card_text.config(state=tk.NORMAL, bg="#FFFFFF", fg="#2C3E50")
        self.card_text.delete("1.0", tk.END)

        # 居中显示成语名
        self.card_text.insert(tk.END, "\n\n\n", "name")
        self.card_text.insert(tk.END, f"{idiom['name']}\n", "name")
        self.card_text.insert(tk.END, "\n", "name")
        # 掌握程度指示
        stars = self._get_mastery_stars(mastery)
        self.card_text.tag_configure("mastery", font=(self._ui_font, 14), foreground="#F39C12", justify=tk.CENTER)
        self.card_text.insert(tk.END, f"{stars} {self._get_mastery_label(mastery)}\n", "mastery")
        self.card_text.insert(tk.END, "\n", "name")
        self.card_text.insert(tk.END, "👆 点击「翻转」或按 Space 查看知识点\n", "hint")

        self.card_text.config(state=tk.DISABLED)
        self.card_frame.config(bg="#FFFFFF")

    def _flip_card(self):
        """翻转卡片（带渐变动画）"""
        if not self.current_review_list or self._animating:
            return

        self._animating = True

        if self.is_showing_back:
            self._animate_transition(
                from_color="#FFFDE7", to_color="#FFFFFF",
                final_action=self._show_front_content
            )
        else:
            self._animate_transition(
                from_color="#FFFFFF", to_color="#FFFDE7",
                final_action=self._show_back_content
            )

    def _animate_transition(self, from_color, to_color, final_action, steps=8, delay=25):
        """执行渐变动画"""
        if steps <= 0:
            final_action()
            self._animating = False
            return

        t = 1.0 - (steps / 8.0)
        bg = lerp_color(from_color, to_color, t)

        self.card_text.config(bg=bg)
        self.card_frame.config(bg=bg)

        self.root.after(
            delay,
            lambda: self._animate_transition(from_color, to_color, final_action, steps - 1, delay)
        )

    def _get_current_idiom_fresh(self):
        """从存储中获取当前成语的最新数据（与成语库保持同步）"""
        if not self.current_review_list:
            return None
        idiom = self.current_review_list[self.current_index]
        # 从存储中重新加载最新数据
        fresh_idioms = {i["name"]: i for i in load_idioms()}
        return fresh_idioms.get(idiom["name"], idiom)

    def _show_front_content(self):
        """显示正面内容"""
        if not self.current_review_list:
            return
        self.is_showing_back = False
        idiom = self._get_current_idiom_fresh()
        # 同步更新到复习列表
        self.current_review_list[self.current_index] = idiom
        self._update_card_tags()

        mastery = idiom.get("review_stats", {}).get("mastery_level", 0)
        stars = self._get_mastery_stars(mastery)

        self.card_text.config(state=tk.NORMAL, bg="#FFFFFF", fg="#2C3E50")
        self.card_text.delete("1.0", tk.END)
        self.card_text.insert(tk.END, "\n\n\n", "name")
        self.card_text.insert(tk.END, f"{idiom['name']}\n", "name")
        self.card_text.insert(tk.END, "\n", "name")
        self.card_text.tag_configure("mastery", font=(self._ui_font, 14), foreground="#F39C12", justify=tk.CENTER)
        self.card_text.insert(tk.END, f"{stars} {self._get_mastery_label(mastery)}\n", "mastery")
        self.card_text.insert(tk.END, "\n", "name")
        self.card_text.insert(tk.END, "👆 点击「翻转」或按 Space 查看知识点\n", "hint")
        self.card_text.config(state=tk.DISABLED)
        self.card_frame.config(bg="#FFFFFF")

    def _show_back_content(self):
        """显示背面内容"""
        if not self.current_review_list:
            return
        self.is_showing_back = True
        idiom = self._get_current_idiom_fresh()
        # 同步更新到复习列表
        self.current_review_list[self.current_index] = idiom
        self._update_card_tags()

        self.card_text.config(state=tk.NORMAL, bg="#FFFDE7", fg="#333333")
        self.card_text.delete("1.0", tk.END)

        # 标题行 + 掌握度
        mastery = idiom.get("review_stats", {}).get("mastery_level", 0)
        stars = self._get_mastery_stars(mastery)
        self.card_text.insert(tk.END, f"【{idiom['name']}】\n", "name")
        self.card_text.tag_configure("mastery_back", font=(self._cn_font, max(9, self._card_back_size)), foreground="#F39C12")
        self.card_text.insert(tk.END, f"掌握度：{stars} {self._get_mastery_label(mastery)}\n", "mastery_back")
        self.card_text.insert(tk.END, "─" * 40 + "\n\n", "divider")

        raw_text = idiom.get("raw_text")
        if raw_text:
            # 原文格式显示
            self.card_text.insert(tk.END, raw_text, "body")
        else:
            # 向后兼容旧数据
            for kp in idiom["knowledge_points"]:
                label = kp["label"]
                content = kp["content"]
                self.card_text.insert(tk.END, f"📌 {label}\n", "section_title")
                content_lines = content.split('\n')
                for cl in content_lines:
                    cl = cl.strip()
                    if not cl:
                        continue
                    sub_match = re.match(r'^([^:：]{1,20})[：:]\s*(.*)', cl)
                    if sub_match:
                        self.card_text.insert(tk.END, f"  • {sub_match.group(1)}：", "label")
                        self.card_text.insert(tk.END, f"{sub_match.group(2)}\n", "body")
                    else:
                        self.card_text.insert(tk.END, f"  {cl}\n", "body")
                self.card_text.insert(tk.END, "\n", "body")

        self.card_text.config(state=tk.DISABLED)
        self.card_frame.config(bg="#FFFDE7")

    def _next_card(self):
        """下一个卡片"""
        if not self.current_review_list or self._animating:
            return

        if self.current_index < len(self.current_review_list) - 1:
            self.current_index += 1
            self.is_showing_back = False
            self._slide_animation(direction="left")
        else:
            # 复习完成
            self._update_card_tags()
            self.card_text.config(state=tk.NORMAL, bg="#FFFFFF", fg="#27AE60")
            self.card_text.delete("1.0", tk.END)
            self.card_text.insert(tk.END, "\n\n\n", "center")
            self.card_text.insert(tk.END, "🎉\n\n", "center")
            self.card_text.insert(tk.END, "复习完成！\n\n", "name")
            self.card_text.insert(tk.END, "你可以重新选择模式\n再次开始复习\n", "hint")
            self.card_text.config(state=tk.DISABLED)
            self.card_frame.config(bg="#FFFFFF")

    def _prev_card(self):
        """上一个卡片"""
        if not self.current_review_list or self._animating:
            return

        if self.current_index > 0:
            self.current_index -= 1
            self.is_showing_back = False
            self._slide_animation(direction="right")

    def _slide_animation(self, direction="left", steps=6, delay=20):
        """卡片切换滑动动画"""
        if steps <= 0:
            self._show_current_card()
            self._animating = False
            return

        t = 1.0 - (steps / 6.0)
        bg = lerp_color("#BDC3C7", "#FFFFFF", t)

        self.card_text.config(bg=bg)
        self.card_frame.config(bg=bg)

        self.root.after(
            delay,
            lambda: self._slide_animation(direction, steps - 1, delay)
        )

    def _mark_card(self, known: bool):
        """标记当前卡片是否认识"""
        if not self.current_review_list or self._animating:
            return

        idiom = self.current_review_list[self.current_index]
        update_review_stats(idiom["name"], known)

        # 同步更新复习列表中的掌握度
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
        """将当前卡片标记为已掌握（直接设为最高等级5）"""
        if not self.current_review_list or self._animating:
            return

        idiom = self.current_review_list[self.current_index]
        set_mastery_level(idiom["name"], 5)

        # 同步更新复习列表
        fresh = self._get_current_idiom_fresh()
        if fresh:
            self.current_review_list[self.current_index] = fresh

        self._refresh_stats()
        self._next_card()

    # ==================== 统计标签页（深色主题） ====================

    def _build_stats_tab(self):
        """构建统计标签页 - 深色主题"""
        self.stats_display = scrolledtext.ScrolledText(
            self.stats_frame, font=self.font_normal, wrap=tk.WORD,
            bg="#1E1E1E", fg="#D4D4D4", insertbackground="white",
            relief=tk.GROOVE, bd=2
        )
        self.stats_display.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        # 配置文本标签样式
        self.stats_display.tag_configure("title", foreground="#569CD6", font=(self._cn_font, 16, "bold"))
        self.stats_display.tag_configure("separator", foreground="#3C3C3C")
        self.stats_display.tag_configure("section", foreground="#4EC9B0", font=(self._cn_font, 13, "bold"))
        self.stats_display.tag_configure("stat_label", foreground="#9CDCFE", font=(self._cn_font, 12))
        self.stats_display.tag_configure("stat_value", foreground="#CE9178", font=(self._cn_font, 12, "bold"))
        self.stats_display.tag_configure("bar_fill", foreground="#4EC9B0")
        self.stats_display.tag_configure("bar_empty", foreground="#555555")
        self.stats_display.tag_configure("star", foreground="#FFD700")
        self.stats_display.tag_configure("dim", foreground="#808080")

        tk.Button(
            self.stats_frame, text="🔄 刷新统计", font=self.font_button,
            bg="#3498DB", fg="white", relief=tk.FLAT,
            padx=20, pady=8, cursor="hand2",
            command=self._refresh_stats
        ).pack(pady=10)

    def _refresh_stats(self):
        """刷新统计信息（深色主题）"""
        summary = get_review_stats_summary()
        idioms = load_idioms()

        self.stats_header.config(
            text=f"📚 {summary['total']} 个成语 | "
                 f"✅ {summary['mastered']} 已掌握 | "
                 f"📖 {summary['reviewed']} 已复习"
        )

        self.stats_display.config(state=tk.NORMAL)
        self.stats_display.delete("1.0", tk.END)

        # 标题
        self.stats_display.insert(tk.END, "📊 成语积累统计报告\n", "title")
        self.stats_display.insert(tk.END, "═" * 50 + "\n\n", "separator")

        # 总览统计
        self.stats_display.insert(tk.END, "📈 总览\n", "section")
        self.stats_display.insert(tk.END, "  📚 总成语数：", "stat_label")
        self.stats_display.insert(tk.END, f"{summary['total']}\n", "stat_value")
        self.stats_display.insert(tk.END, "  📖 已复习数：", "stat_label")
        self.stats_display.insert(tk.END, f"{summary['reviewed']}\n", "stat_value")
        self.stats_display.insert(tk.END, "  ✅ 已掌握数：", "stat_label")
        self.stats_display.insert(tk.END, f"{summary['mastered']}\n", "stat_value")
        self.stats_display.insert(tk.END, "  📈 平均掌握度：", "stat_label")
        self.stats_display.insert(tk.END, f"{summary['avg_mastery']:.1f} / 5.0\n\n", "stat_value")

        # 掌握度分布
        self.stats_display.insert(tk.END, "📊 掌握度分布\n", "section")
        self.stats_display.insert(tk.END, "─" * 50 + "\n", "separator")

        level_names = ["未复习", "初识  ", "了解  ", "熟悉  ", "掌握  ", "精通  "]
        level_colors = ["#FF4444", "#FF8800", "#FFCC00", "#88CC00", "#44BB44", "#44FF44"]
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

        # 最近添加的成语
        self.stats_display.insert(tk.END, "🕐 最近添加的成语\n", "section")
        self.stats_display.insert(tk.END, "─" * 50 + "\n", "separator")

        sorted_idioms = sorted(
            idioms,
            key=lambda x: x.get("added_at", ""),
            reverse=True
        )

        for i, idiom in enumerate(sorted_idioms[:10]):
            name = idiom["name"]
            level = idiom.get("review_stats", {}).get("mastery_level", 0)
            stars = "⭐" * level + "☆" * (5 - level)
            added = idiom.get("added_at", "未知")
            self.stats_display.insert(tk.END, f"  {i+1:2d}. ", "dim")
            self.stats_display.insert(tk.END, f"{name}", "stat_label")
            self.stats_display.insert(tk.END, f" {stars} ", "star")
            self.stats_display.insert(tk.END, f"(添加于 {added})\n", "dim")

        self.stats_display.insert(tk.END, "\n")
        self.stats_display.insert(tk.END, "═" * 50 + "\n", "separator")
        self.stats_display.insert(tk.END, "  所有数据已自动保存到本地 JSON 文件\n", "dim")


def main():
    root = tk.Tk()

    # 尝试设置主题
    style = ttk.Style()
    available_themes = style.theme_names()
    if "clam" in available_themes:
        style.theme_use("clam")

    # 自定义样式
    _cn_font = "PingFang SC" if sys.platform == "darwin" else "Microsoft YaHei"
    style.configure("TNotebook", background="#ECF0F1")
    style.configure(
        "TNotebook.Tab",
        font=(_cn_font, 11),
        padding=[15, 8]
    )
    # PanedWindow 样式
    style.configure("TPanedwindow", background="#ECF0F1")
    style.configure("Sash", sashthickness=6)

    app = IdoimApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
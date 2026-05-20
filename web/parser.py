"""
成语解析器 - 将特定格式的成语文本解析为结构化数据
支持两种格式：
1. 简洁格式：每行一个知识点，格式为 "标签：内容"
2. 原始格式：带「核心释义/辨析要点/真题场景」等章节标题
"""

import re
from typing import Dict, List, Optional


def parse_idiom_text(text: str) -> Optional[Dict]:
    """
    解析单个成语的文本，返回结构化字典。
    
    支持格式：
    - 【成语: xxx (pinyin)】 或 【词汇卡片：xxx】 或 【xxx】
    - 其余内容按 "标签：内容" 或 "label: content" 逐行解析
    
    返回:
    {
        "name": "鞭打快牛",
        "knowledge_points": [
            {"label": "字面含义", "content": "..."},
            {"label": "比喻义", "content": "..."},
            ...
        ]
    }
    """
    result = {
        "name": "",
        "raw_text": "",
        "knowledge_points": []
    }

    # 提取成语名称 - 多种格式
    # 【成语: 鞭打快牛 (biān dǎ kuài niú)】
    name_match = re.search(r'【成语\s*[：:]\s*(.+?)】', text)
    if not name_match:
        # 【词汇卡片：xxx】 或 【词汇卡片(xxx)：xxx】
        name_match = re.search(r'【词汇卡片\s*(?:\([^)]*\))?\s*[：:]\s*(.+?)】', text)
    if not name_match:
        # 【xxx】
        name_match = re.search(r'【(.+?)】', text)
    if not name_match:
        return None

    raw_name = name_match.group(1).strip()
    # 去掉拼音部分，如 "鞭打快牛 (biān dǎ kuài niú)" → "鞭打快牛"
    result["name"] = re.sub(r'\s*\(.*?\)\s*$', '', raw_name).strip()

    # 获取头部之后的内容，保留原文
    header_end = name_match.end()
    body = text[header_end:].strip()
    result["raw_text"] = body

    return result


def _is_old_format(text: str) -> bool:
    """检测是否为旧格式（带章节标题的格式）"""
    old_markers = [
        r'核心释义\s*[\(（]',
        r'辨析要点\s*[\(（]',
        r'真题场景\s*[\(（]',
        r'Key Distinctions',
        r'Exam Context',
        r'Core Meaning',
    ]
    for marker in old_markers:
        if re.search(marker, text, re.IGNORECASE):
            return True
    return False


def _parse_simple_format(body: str, result: Dict):
    """
    解析简洁格式：每行一个知识点，格式为 "标签：内容"
    没有冒号的行追加到上一个知识点的末尾
    """
    lines = body.split('\n')
    
    current_label = None
    current_content = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        # 尝试匹配 "标签：内容" 或 "label: content"
        # 要求冒号前有非空内容，且不是以特殊字符开头
        match = re.match(r'^([^：:\n]{1,20})[：:]\s*(.*)', line)
        
        if match:
            # 保存上一个知识点
            if current_label is not None:
                result["knowledge_points"].append({
                    "label": current_label,
                    "content": current_content.strip()
                })
            
            current_label = match.group(1).strip()
            current_content = match.group(2).strip()
        else:
            # 没有冒号的行，追加到当前知识点
            if current_label is not None:
                current_content += "\n" + line
            # 如果还没有任何标签，跳过这行（或作为无标签内容）
    
    # 保存最后一个知识点
    if current_label is not None:
        result["knowledge_points"].append({
            "label": current_label,
            "content": current_content.strip()
        })


def _parse_old_format(body: str, result: Dict):
    """
    解析旧格式：带「核心释义/辨析要点/真题场景」等章节标题的格式
    保持向后兼容
    """
    # 提取核心释义
    core_content = _extract_section(
        body,
        headers=[
            r'核心释义\s*[\(（]\s*Core Meaning\s*[\)）]\s*[：:\n]',
            r'核心释义\s*[：:\n]',
            r'释义\s*[：:\n]',
            r'Core Meaning\s*[：:\n]',
        ],
        end_patterns=[
            r'辨析要点', r'真题场景', r'辨析', r'例句', r'Exam Context',
            r'Key Distinctions', r'搭配', r'用法'
        ]
    )
    if core_content:
        result["knowledge_points"].append({
            "label": "核心释义",
            "content": core_content
        })
    
    # 提取辨析要点
    dist_content = _extract_section(
        body,
        headers=[
            r'辨析要点\s*[\(（]\s*Key Distinctions\s*[\)）]\s*[：:\n]',
            r'辨析要点\s*[：:\n]',
            r'辨析\s*[：:\n]',
            r'Key Distinctions\s*[：:\n]',
        ],
        end_patterns=[
            r'真题场景', r'例句', r'Exam Context', r'真题', r'考试'
        ]
    )
    if dist_content:
        result["knowledge_points"].append({
            "label": "辨析要点",
            "content": dist_content
        })
    
    # 提取真题场景
    exam_content = _extract_section(
        body,
        headers=[
            r'真题场景\s*[\(（]\s*Exam Context\s*[\)）]\s*[：:\n]',
            r'真题场景\s*[：:\n]',
            r'真题\s*[：:\n]',
            r'Exam Context\s*[：:\n]',
            r'典型例句\s*[：:\n]',
            r'例句\s*[：:\n]',
        ],
        end_patterns=[]
    )
    if exam_content:
        result["knowledge_points"].append({
            "label": "真题场景",
            "content": exam_content
        })


def _extract_section(text: str, headers: List[str], end_patterns: List[str]) -> Optional[str]:
    """从文本中提取一个章节的内容（旧格式用）"""
    for header in headers:
        match = re.search(header, text, re.IGNORECASE)
        if match:
            content_start = match.end()
            
            if end_patterns:
                end_regex = '|'.join(end_patterns)
                end_match = re.search(end_regex, text[content_start:], re.IGNORECASE)
                if end_match:
                    content = text[content_start:content_start + end_match.start()].strip()
                else:
                    content = text[content_start:].strip()
            else:
                content = text[content_start:].strip()
            
            content = re.sub(r'^[\s：:\n]+', '', content)
            content = content.strip()
            
            if content:
                return content
    
    return None


def parse_multiple_idioms(text: str) -> List[Dict]:
    """
    解析包含多个成语的文本。
    每个成语以 【xxx】 开头分隔。
    """
    # 按成语卡片标记分割
    parts = re.split(r'(?=【[^】]*[：:][^】]*】)', text)
    
    # 如果上面没分割出结果，尝试简单的【分割
    if len(parts) <= 1:
        parts = re.split(r'(?=【)', text)
    
    results = []
    errors = []
    
    for i, part in enumerate(parts):
        part = part.strip()
        if not part:
            continue
        if '【' not in part:
            continue
        
        try:
            parsed = parse_idiom_text(part)
            if parsed and parsed["name"]:
                if parsed.get("raw_text") or parsed.get("knowledge_points"):
                    results.append(parsed)
                else:
                    errors.append(f"第 {i+1} 个卡片「{parsed['name']}」解析到 0 个知识点")
            else:
                name_match = re.search(r'【(.+?)】', part)
                name = name_match.group(1) if name_match else f"第 {i+1} 个"
                errors.append(f"「{name}」解析失败")
        except Exception as e:
            errors.append(f"第 {i+1} 个卡片解析出错: {e}")
    
    # 保存错误信息供外部查询
    parse_multiple_idioms._last_errors = errors
    
    return results


def get_last_parse_errors() -> List[str]:
    """获取上次解析的错误/警告信息"""
    return getattr(parse_multiple_idioms, '_last_errors', [])


def format_flashcard_back(idiom: Dict) -> str:
    """将成语数据格式化为闪卡背面的文本。"""
    if idiom.get("raw_text"):
        return f"【{idiom['name']}】\n\n{idiom['raw_text']}"

    # 向后兼容旧数据
    lines = []
    lines.append(f"【{idiom['name']}】】")
    lines.append("")

    for kp in idiom["knowledge_points"]:
        label = kp["label"]
        content = kp["content"]
        if '\n' in content:
            content_lines = content.split('\n')
            lines.append(f"{label}：{content_lines[0]}")
            for cl in content_lines[1:]:
                lines.append(f"  {cl.strip()}")
        else:
            lines.append(f"{label}：{content}")

    return "\n".join(lines)


def idiom_to_editable_text(idiom: Dict) -> str:
    """将成语数据转换为可编辑的文本格式。"""
    if idiom.get("raw_text"):
        return f"【成语：{idiom['name']}】\n\n{idiom['raw_text']}"

    # 向后兼容旧数据
    lines = []
    lines.append(f"【成语：{idiom['name']}】")
    lines.append("")

    for kp in idiom["knowledge_points"]:
        label = kp["label"]
        content = kp["content"]
        lines.append(f"{label}：{content}")
        lines.append("")

    return "\n".join(lines)
"""
成语数据存储模块 - 使用JSON文件持久化成语数据
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional


DATA_DIR = os.path.join(os.path.expanduser("~"), "成语积累", "data")
IDIOMS_FILE = os.path.join(DATA_DIR, "idioms.json")

_cache = None


def _ensure_data_dir():
    """确保数据目录存在"""
    os.makedirs(DATA_DIR, exist_ok=True)


def _invalidate_cache():
    global _cache
    _cache = None


def load_idioms() -> List[Dict]:
    """从JSON文件加载所有成语数据（带内存缓存）"""
    global _cache
    if _cache is not None:
        return _cache
    _ensure_data_dir()
    if not os.path.exists(IDIOMS_FILE):
        return []
    try:
        with open(IDIOMS_FILE, "r", encoding="utf-8") as f:
            _cache = json.load(f)
            return _cache
    except (json.JSONDecodeError, IOError):
        return []


def save_idioms(idioms: List[Dict]) -> bool:
    """保存所有成语数据到JSON文件（同时更新缓存）"""
    global _cache
    _ensure_data_dir()
    try:
        with open(IDIOMS_FILE, "w", encoding="utf-8") as f:
            json.dump(idioms, f, ensure_ascii=False, indent=2)
        _cache = idioms
        return True
    except IOError as e:
        print(f"保存失败: {e}")
        return False


def add_idiom(idiom: Dict) -> bool:
    """
    添加单个成语到数据库。
    如果同名成语已存在，则更新。
    """
    idioms = load_idioms()
    
    # 检查是否已存在
    existing_index = None
    for i, existing in enumerate(idioms):
        if existing["name"] == idiom["name"]:
            existing_index = i
            break
    
    # 添加时间戳
    idiom["added_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 添加复习统计
    if existing_index is not None:
        # 保留已有的复习统计
        old_stats = idioms[existing_index].get("review_stats", {})
        idiom["review_stats"] = old_stats
        idiom["review_stats"]["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        idioms[existing_index] = idiom
    else:
        idiom["review_stats"] = {
            "total_reviews": 0,
            "correct_count": 0,
            "last_reviewed": None,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "mastery_level": 0  # 0-5 掌握程度
        }
        idioms.append(idiom)
    
    return save_idioms(idioms)


def add_idioms_batch(idioms_to_add: List[Dict]) -> int:
    """
    批量添加成语，返回成功添加的数量。
    一次加载 + 一次保存，避免 N+1 磁盘写入。
    """
    if not idioms_to_add:
        return 0
    idioms = load_idioms()
    existing_map = {i["name"]: idx for idx, i in enumerate(idioms)}
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    success_count = 0

    for idiom in idioms_to_add:
        name = idiom.get("name")
        if not name:
            continue
        idiom["added_at"] = now
        if name in existing_map:
            idx = existing_map[name]
            idiom["review_stats"] = idioms[idx].get("review_stats", {})
            idiom["review_stats"]["last_updated"] = now
            idioms[idx] = idiom
        else:
            idiom["review_stats"] = {
                "total_reviews": 0,
                "correct_count": 0,
                "last_reviewed": None,
                "last_updated": now,
                "mastery_level": 0,
            }
            idioms.append(idiom)
            existing_map[name] = len(idioms) - 1
        success_count += 1

    save_idioms(idioms)
    return success_count


def delete_idioms_batch(names: List[str]) -> bool:
    """批量删除成语，一次加载 + 一次保存"""
    if not names:
        return True
    idioms = load_idioms()
    name_set = set(names)
    new_idioms = [i for i in idioms if i["name"] not in name_set]
    if len(new_idioms) == len(idioms):
        return False
    return save_idioms(new_idioms)


def update_review_stats(idiom_name: str, correct: bool) -> bool:
    """
    更新成语的复习统计（认识/不认识模式）
    """
    idioms = load_idioms()
    
    for idiom in idioms:
        if idiom["name"] == idiom_name:
            stats = idiom.get("review_stats", {})
            stats["total_reviews"] = stats.get("total_reviews", 0) + 1
            if correct:
                stats["correct_count"] = stats.get("correct_count", 0) + 1
                stats["mastery_level"] = min(5, stats.get("mastery_level", 0) + 1)
            else:
                stats["mastery_level"] = max(0, stats.get("mastery_level", 0) - 1)
            stats["last_reviewed"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            idiom["review_stats"] = stats
            return save_idioms(idioms)
    
    return False


def set_mastery_level(idiom_name: str, level: int) -> bool:
    """
    直接设置成语的掌握等级
    level: 0-5
    """
    level = max(0, min(5, level))
    idioms = load_idioms()
    
    for idiom in idioms:
        if idiom["name"] == idiom_name:
            stats = idiom.get("review_stats", {})
            stats["total_reviews"] = stats.get("total_reviews", 0) + 1
            stats["correct_count"] = stats.get("correct_count", 0) + 1
            stats["mastery_level"] = level
            stats["last_reviewed"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            idiom["review_stats"] = stats
            return save_idioms(idioms)
    
    return False


def delete_idiom(idiom_name: str) -> bool:
    """删除指定成语"""
    idioms = load_idioms()
    new_idioms = [i for i in idioms if i["name"] != idiom_name]
    if len(new_idioms) == len(idioms):
        return False
    return save_idioms(new_idioms)


def get_idiom_names() -> List[str]:
    """获取所有成语名称列表"""
    idioms = load_idioms()
    return [i["name"] for i in idioms]


def search_idioms(keyword: str) -> List[Dict]:
    """搜索成语（按名称或释义）"""
    idioms = load_idioms()
    keyword = keyword.lower()
    results = []
    for idiom in idioms:
        if (keyword in idiom["name"].lower() or
            keyword in idiom.get("core_meaning", "").lower() or
            keyword in idiom.get("distinctions", "").lower() or
            keyword in idiom.get("raw_text", "").lower()):
            results.append(idiom)
    return results


def get_review_stats_summary() -> Dict:
    """获取复习统计摘要"""
    idioms = load_idioms()
    if not idioms:
        return {
            "total": 0,
            "reviewed": 0,
            "mastered": 0,
            "avg_mastery": 0
        }
    
    total = len(idioms)
    reviewed = sum(1 for i in idioms if i.get("review_stats", {}).get("total_reviews", 0) > 0)
    mastered = sum(1 for i in idioms if i.get("review_stats", {}).get("mastery_level", 0) >= 4)
    mastery_levels = [i.get("review_stats", {}).get("mastery_level", 0) for i in idioms]
    avg_mastery = sum(mastery_levels) / len(mastery_levels) if mastery_levels else 0
    
    return {
        "total": total,
        "reviewed": reviewed,
        "mastered": mastered,
        "avg_mastery": round(avg_mastery, 2)
    }
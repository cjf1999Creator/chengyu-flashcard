# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Chinese idiom (成语) flashcard study application for exam preparation (行测). Built with Python + tkinter as a desktop GUI. Parses structured idiom notes into flashcards with spaced repetition tracking.

## Running

```bash
python main.py
```

No external dependencies — uses only Python standard library (tkinter, json, re, os, sys, random).

## Architecture

Three-module design:

- **main.py** — `IdoimApp` class (note the typo in class name). tkinter GUI with four tabs: Import, Library, Review (flashcards), Statistics. Handles all UI state, animations, and keyboard shortcuts (Space=flip, K/J=navigate, A/D=mark known/unknown, S=mastered).
- **parser.py** — Text parsing engine. Converts structured idiom notes into `{name, knowledge_points: [{label, content}]}` dicts. Supports two input formats: simple `标签：内容` lines and legacy section-based format with `核心释义/辨析要点/真题场景` headers.
- **storage.py** — JSON file persistence. All data lives in `data/idioms.json`. Each idiom has `review_stats` with a 0-5 mastery level tracked via correct/incorrect responses.

## Data Model

Idiom record shape:
```
{
  "name": str,
  "knowledge_points": [{"label": str, "content": str}, ...],
  "core_meaning": str,       # legacy field, kept for search
  "distinctions": str,       # legacy field, kept for search
  "exam_context": str,       # legacy field, kept for search
  "added_at": "YYYY-MM-DD HH:MM:SS",
  "review_stats": {
    "total_reviews": int, "correct_count": int,
    "last_reviewed": str|None, "last_updated": str,
    "mastery_level": int  // 0-5
  }
}
```

## Key Details

- The class is named `IdoimApp` (typo: missing 'o' in Idiom) — do not "fix" this as it would require renaming across the entire file.
- `search_idioms()` in storage.py searches legacy `core_meaning` and `distinctions` fields, not the newer `knowledge_points` — be aware of this gap when modifying search.
- Parser uses `re.split(r'(?=【[^】]*[：:][^】]*】)', text)` to split multiple idioms from pasted text; the `【成语：名称】` header format is required.
- Card flip uses a color interpolation animation between `#FFFFFF` (front) and `#FFFDE7` (back).
- `txt.txt` and `sample_idioms.txt` are sample input files, not source code.

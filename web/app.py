"""成语积累 - Flask Web 应用"""

from flask import Flask, jsonify, request, render_template, send_file
from werkzeug.utils import secure_filename
import os
import random
import json
from urllib.parse import unquote

app = Flask(__name__, static_folder='static', template_folder='templates')

from parser import parse_idiom_text, parse_multiple_idioms, format_flashcard_back, idiom_to_editable_text, get_last_parse_errors
from storage import (load_idioms, add_idiom, add_idioms_batch, update_review_stats,
                     set_mastery_level, delete_idiom, search_idioms, get_review_stats_summary)


@app.route('/')
def index():
    return render_template('index.html')


# ==================== 成语库 API ====================

@app.route('/api/idioms', methods=['GET'])
def api_list_idioms():
    keyword = request.args.get('search', '').strip()
    if keyword:
        idioms = search_idioms(keyword)
    else:
        idioms = load_idioms()
    result = []
    for i in idioms:
        result.append({
            'name': i['name'],
            'added_at': i.get('added_at'),
            'mastery_level': i.get('review_stats', {}).get('mastery_level', 0),
            'total_reviews': i.get('review_stats', {}).get('total_reviews', 0),
        })
    return jsonify(result)


@app.route('/api/idioms/<path:name>', methods=['GET'])
def api_get_idiom(name):
    name = unquote(name)
    idioms = load_idioms()
    for i in idioms:
        if i['name'] == name:
            return jsonify(i)
    return jsonify({'error': '未找到该成语'}), 404


@app.route('/api/idioms/<path:name>', methods=['PUT'])
def api_update_idiom(name):
    name = unquote(name)
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({'error': '缺少 text 字段'}), 400

    parsed = parse_idiom_text(data['text'])
    if not parsed or not parsed['name']:
        return jsonify({'error': '解析失败'}), 400

    if not parsed.get('raw_text') and not parsed.get('knowledge_points'):
        return jsonify({'error': '解析到成语但没有内容'}), 400

    old_name = data.get('old_name', name)
    if old_name != parsed['name']:
        delete_idiom(old_name)

    add_idiom(parsed)
    return jsonify({'success': True, 'name': parsed['name']})


@app.route('/api/idioms/<path:name>', methods=['DELETE'])
def api_delete_idiom(name):
    name = unquote(name)
    if delete_idiom(name):
        return jsonify({'success': True})
    return jsonify({'error': '未找到该成语'}), 404


# ==================== 导入 API ====================

@app.route('/api/import/preview', methods=['POST'])
def api_import_preview():
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({'error': '缺少 text 字段'}), 400

    text = data['text'].strip()
    if not text:
        return jsonify({'error': '文本为空'}), 400

    idioms = parse_multiple_idioms(text)
    errors = get_last_parse_errors()

    results = []
    for idiom in idioms:
        results.append({
            'name': idiom['name'],
            'preview': format_flashcard_back(idiom),
        })

    return jsonify({'idioms': results, 'errors': errors, 'count': len(results)})


@app.route('/api/import', methods=['POST'])
def api_import():
    data = request.get_json()
    if not data or 'text' not in data:
        return jsonify({'error': '缺少 text 字段'}), 400

    text = data['text'].strip()
    if not text:
        return jsonify({'error': '文本为空'}), 400

    idioms = parse_multiple_idioms(text)
    errors = get_last_parse_errors()

    if not idioms:
        return jsonify({'error': '未能解析出任何成语', 'details': errors[:5]}), 400

    count = add_idioms_batch(idioms)
    return jsonify({'success': True, 'count': count, 'errors': errors})


@app.route('/api/import/file', methods=['POST'])
def api_import_file():
    if 'file' not in request.files:
        return jsonify({'error': '未上传文件'}), 400

    f = request.files['file']
    if not f.filename:
        return jsonify({'error': '文件名为空'}), 400

    try:
        content = f.read().decode('utf-8')
    except Exception as e:
        return jsonify({'error': f'读取文件失败: {e}'}), 400

    return jsonify({'text': content, 'filename': f.filename})


# ==================== 复习 API ====================

@app.route('/api/review/start', methods=['POST'])
def api_review_start():
    data = request.get_json() or {}
    mode = data.get('mode', 'all')
    date_filter = data.get('date')

    all_idioms = load_idioms()
    if not all_idioms:
        return jsonify({'error': '成语库为空，请先导入成语'}), 400

    deck = []
    if mode == 'all':
        deck = list(all_idioms)
    elif mode == 'random20':
        count = min(20, len(all_idioms))
        deck = random.sample(all_idioms, count)
    elif mode == 'unmastered':
        deck = [i for i in all_idioms if i.get('review_stats', {}).get('mastery_level', 0) < 4]
        if not deck:
            return jsonify({'error': '所有成语都已掌握'}), 400
    elif mode == 'mastered':
        deck = [i for i in all_idioms if i.get('review_stats', {}).get('mastery_level', 0) >= 4]
        if not deck:
            return jsonify({'error': '还没有已掌握的成语'}), 400
    elif mode == 'bydate':
        if not date_filter:
            return jsonify({'error': '请选择日期'}), 400
        deck = [i for i in all_idioms if i.get('added_at', '')[:10] == date_filter]
        if not deck:
            return jsonify({'error': f'{date_filter} 当天没有导入成语'}), 400
    else:
        return jsonify({'error': '无效的复习模式'}), 400

    random.shuffle(deck)

    result = []
    for idiom in deck:
        result.append({
            'name': idiom['name'],
            'raw_text': idiom.get('raw_text', ''),
            'knowledge_points': idiom.get('knowledge_points', []),
            'added_at': idiom.get('added_at'),
            'review_stats': idiom.get('review_stats', {}),
        })

    return jsonify(result)


@app.route('/api/review/mark', methods=['POST'])
def api_review_mark():
    data = request.get_json()
    if not data or 'name' not in data or 'action' not in data:
        return jsonify({'error': '缺少参数'}), 400

    name = data['name']
    action = data['action']

    if action == 'known':
        update_review_stats(name, True)
    elif action == 'unknown':
        update_review_stats(name, False)
    elif action == 'mastered':
        set_mastery_level(name, 5)
    else:
        return jsonify({'error': '无效操作'}), 400

    idioms = load_idioms()
    for i in idioms:
        if i['name'] == name:
            return jsonify({
                'name': i['name'],
                'review_stats': i.get('review_stats', {}),
            })

    return jsonify({'error': '未找到该成语'}), 404


# ==================== 统计 API ====================

@app.route('/api/stats', methods=['GET'])
def api_stats():
    summary = get_review_stats_summary()
    idioms = load_idioms()

    level_counts = [0] * 6
    for idiom in idioms:
        level = idiom.get('review_stats', {}).get('mastery_level', 0)
        level_counts[level] += 1

    sorted_idioms = sorted(idioms, key=lambda x: x.get('added_at', ''), reverse=True)
    recent = []
    for i in sorted_idioms[:10]:
        recent.append({
            'name': i['name'],
            'added_at': i.get('added_at', '未知'),
            'mastery_level': i.get('review_stats', {}).get('mastery_level', 0),
        })

    return jsonify({
        'summary': summary,
        'level_counts': level_counts,
        'recent': recent,
    })


@app.route('/api/stats/dates', methods=['GET'])
def api_stats_dates():
    idioms = load_idioms()
    date_counts = {}
    for idiom in idioms:
        added = idiom.get('added_at', '')
        if added:
            day = added[:10]
            date_counts[day] = date_counts.get(day, 0) + 1
    return jsonify(date_counts)


# ==================== 数据同步 API ====================

@app.route('/api/data/export', methods=['GET'])
def api_data_export():
    from storage import IDIOMS_FILE
    if os.path.exists(IDIOMS_FILE):
        return send_file(IDIOMS_FILE, mimetype='application/json', as_attachment=True, download_name='idioms.json')
    return jsonify({'error': '数据文件不存在'}), 404


@app.route('/api/data/import-sync', methods=['POST'])
def api_data_import_sync():
    if 'file' not in request.files:
        data = request.get_json()
        if data and 'idioms' in data:
            from storage import save_idioms
            save_idioms(data['idioms'])
            return jsonify({'success': True, 'count': len(data['idioms'])})
        return jsonify({'error': '缺少数据'}), 400

    f = request.files['file']
    try:
        content = f.read().decode('utf-8')
        idioms = json.loads(content)
        from storage import save_idioms
        save_idioms(idioms)
        return jsonify({'success': True, 'count': len(idioms)})
    except Exception as e:
        return jsonify({'error': f'导入失败: {e}'}), 400


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)

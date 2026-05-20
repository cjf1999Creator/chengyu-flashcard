/* 成语积累 - Web 前端逻辑 */

const App = {
    // ==================== 状态 ====================
    state: {
        allIdioms: [],
        selectedIdiom: null,
        editing: false,
        editingName: null,
        reviewDeck: [],
        reviewIndex: 0,
        isFlipped: false,
        fontSize: 13,
        calYear: new Date().getFullYear(),
        calMonth: new Date().getMonth(),
        calSelected: null,
        dateCounts: {},
    },

    // ==================== 初始化 ====================
    init() {
        this.bindTabs();
        this.bindShortcuts();
        this.bindResizers();
        this.refreshStats();
        this.renderCalendar();
    },

    // ==================== 标签切换 ====================
    bindTabs() {
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                btn.classList.add('active');
                const tabId = 'tab-' + btn.dataset.tab;
                document.getElementById(tabId).classList.add('active');

                if (btn.dataset.tab === 'library') this.refreshLibrary();
                if (btn.dataset.tab === 'stats') this.refreshStats();
                if (btn.dataset.tab === 'review') this.renderCalendar();
            });
        });
    },

    // ==================== 快捷键 ====================
    bindShortcuts() {
        document.addEventListener('keydown', (e) => {
            const reviewTab = document.getElementById('tab-review');
            if (!reviewTab.classList.contains('active')) return;
            if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') return;

            switch (e.key) {
                case ' ':
                    e.preventDefault();
                    this.flipCard();
                    break;
                case 'k': case 'K': case 'ArrowRight':
                    this.nextCard();
                    break;
                case 'j': case 'J': case 'ArrowLeft':
                    this.prevCard();
                    break;
                case 'a': case 'A':
                    this.markKnown();
                    break;
                case 'd': case 'D':
                    this.markUnknown();
                    break;
                case 's': case 'S':
                    this.markMastered();
                    break;
            }
        });
    },

    // ==================== 面板拖拽 ====================
    bindResizers() {
        document.querySelectorAll('.pane-resizer').forEach(resizer => {
            let startY, startHeight1, startHeight2;
            let isVertical = resizer.dataset.direction === 'vertical';

            resizer.addEventListener('mousedown', (e) => {
                e.preventDefault();
                const parent = resizer.parentElement;
                const panes = Array.from(parent.children).filter(c => c !== resizer && c.classList.contains('import-pane'));

                if (isVertical) {
                    startY = e.clientY;
                    startHeight1 = panes[0].getBoundingClientRect().height;
                    startHeight2 = panes[1].getBoundingClientRect().height;
                }

                const onMouseMove = (e) => {
                    if (isVertical) {
                        const delta = e.clientY - startY;
                        panes[0].style.flex = 'none';
                        panes[0].style.height = Math.max(80, startHeight1 + delta) + 'px';
                    }
                };

                const onMouseUp = () => {
                    document.removeEventListener('mousemove', onMouseMove);
                    document.removeEventListener('mouseup', onMouseUp);
                };

                document.addEventListener('mousemove', onMouseMove);
                document.addEventListener('mouseup', onMouseUp);
            });
        });
    },

    // ==================== Toast 通知 ====================
    toast(msg, type = '') {
        const el = document.getElementById('toast');
        el.textContent = msg;
        el.className = 'toast show ' + type;
        clearTimeout(this._toastTimer);
        this._toastTimer = setTimeout(() => { el.className = 'toast'; }, 2500);
    },

    // ==================== Markdown 渲染 ====================
    renderMarkdown(text) {
        if (!text) return '';
        // 预处理：标签：内容 模式
        let processed = text.replace(/^([^：:\n]{1,15})([：:])\s*/gm, '<span class="md-label">$1$2</span> ');
        // 使用 marked 渲染
        if (typeof marked !== 'undefined') {
            return marked.parse(processed);
        }
        // fallback: 简单换行
        return processed.replace(/\n/g, '<br>');
    },

    getMasteryStars(level) {
        return '★'.repeat(level) + '☆'.repeat(5 - level);
    },

    getMasteryLabel(level) {
        const labels = ['未复习', '初识', '了解', '熟悉', '掌握', '精通'];
        return labels[level] || 'Lv.' + level;
    },

    // ==================== 导入功能 ====================
    importFile() {
        document.getElementById('fileInput').click();
    },

    async handleFile(event) {
        const file = event.target.files[0];
        if (!file) return;
        const text = await file.text();
        document.getElementById('importText').value = text;
        this.toast('已加载文件：' + file.filename, 'success');
        event.target.value = '';
    },

    clearImport() {
        document.getElementById('importText').value = '';
        document.getElementById('previewArea').innerHTML = '';
    },

    async previewImport() {
        const text = document.getElementById('importText').value.trim();
        if (!text) { this.toast('请先输入成语文本！', 'error'); return; }

        try {
            const resp = await fetch('/api/import/preview', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text }),
            });
            const data = await resp.json();
            if (!resp.ok) { this.toast(data.error || '预览失败', 'error'); return; }

            const area = document.getElementById('previewArea');
            let html = '';
            for (const idiom of data.idioms) {
                html += '<div class="md-content" style="border-bottom:1px solid var(--border-light); padding:8px 0">';
                html += this.renderMarkdown(idiom.preview);
                html += '</div>';
            }
            if (data.errors && data.errors.length) {
                html += '<div style="color:var(--orange); margin-top:8px; font-size:12px">解析警告：<br>';
                for (const err of data.errors) {
                    html += '  - ' + err + '<br>';
                }
                html += '</div>';
            }
            area.innerHTML = html;
            this.toast(`成功解析 ${data.count} 个成语`, 'success');
        } catch (e) {
            this.toast('网络错误', 'error');
        }
    },

    async doImport() {
        const text = document.getElementById('importText').value.trim();
        if (!text) { this.toast('请先输入成语文本！', 'error'); return; }

        try {
            const resp = await fetch('/api/import', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text }),
            });
            const data = await resp.json();
            if (!resp.ok) { this.toast(data.error || '导入失败', 'error'); return; }

            let msg = `成功导入 ${data.count} 个成语！`;
            if (data.errors && data.errors.length) msg += ` (${data.errors.length} 个失败)`;
            this.toast(msg, 'success');
            document.getElementById('importText').value = '';
            document.getElementById('previewArea').innerHTML = '';
            this.refreshStats();
        } catch (e) {
            this.toast('网络错误', 'error');
        }
    },

    // ==================== 成语库 ====================
    async refreshLibrary() {
        try {
            const resp = await fetch('/api/idioms');
            const idioms = await resp.json();
            this.state.allIdioms = idioms;
            this.renderIdiomList(idioms);
            document.getElementById('libraryCount').textContent = `共 ${idioms.length} 个成语`;
        } catch (e) {
            this.toast('加载失败', 'error');
        }
    },

    renderIdiomList(idioms) {
        const list = document.getElementById('idiomList');
        list.innerHTML = '';
        for (const idiom of idioms) {
            const item = document.createElement('div');
            item.className = 'idiom-item';
            item.innerHTML = `<span>${idiom.name}</span><span class="mastery-stars">${this.getMasteryStars(idiom.mastery_level)}</span>`;
            item.addEventListener('click', () => this.selectIdiom(idiom, item));
            list.appendChild(item);
        }
    },

    async selectIdiom(idiom, element) {
        if (this.state.editing) return;

        document.querySelectorAll('.idiom-item').forEach(i => i.classList.remove('active'));
        if (element) element.classList.add('active');

        try {
            const resp = await fetch('/api/idioms/' + encodeURIComponent(idiom.name));
            const data = await resp.json();
            if (!resp.ok) { this.toast(data.error, 'error'); return; }
            this.state.selectedIdiom = data;
            this.showIdiomDetail(data);
        } catch (e) {
            this.toast('加载失败', 'error');
        }
    },

    showIdiomDetail(idiom) {
        const view = document.getElementById('detailView');
        document.getElementById('detailView').style.display = '';
        document.getElementById('detailEdit').style.display = 'none';

        let html = `<div class="detail-title">【${idiom.name}】</div>`;
        if (idiom.added_at) html += `<div class="detail-dim">导入时间：${idiom.added_at}</div>`;
        html += '<hr class="detail-divider">';

        const rawText = idiom.raw_text;
        if (rawText) {
            html += '<div class="md-content">' + this.renderMarkdown(rawText) + '</div>';
        } else if (idiom.knowledge_points && idiom.knowledge_points.length) {
            html += '<div class="md-content">';
            for (const kp of idiom.knowledge_points) {
                html += `<h2>${kp.label}</h2>`;
                html += this.renderMarkdown(kp.content);
            }
            html += '</div>';
        }
        view.innerHTML = html;
    },

    async searchIdioms() {
        const keyword = document.getElementById('searchInput').value.trim();
        if (!keyword) { this.refreshLibrary(); return; }
        try {
            const resp = await fetch('/api/idioms?search=' + encodeURIComponent(keyword));
            const idioms = await resp.json();
            this.state.allIdioms = idioms;
            this.renderIdiomList(idioms);
            document.getElementById('libraryCount').textContent = `找到 ${idioms.length} 个成语`;
        } catch (e) {
            this.toast('搜索失败', 'error');
        }
    },

    // ==================== 编辑功能 ====================
    enterEdit() {
        if (!this.state.selectedIdiom) { this.toast('请先选择一个成语', 'error'); return; }
        const idiom = this.state.selectedIdiom;
        this.state.editing = true;
        this.state.editingName = idiom.name;

        let text = '';
        if (idiom.raw_text) {
            text = `【成语：${idiom.name}】\n\n${idiom.raw_text}`;
        } else if (idiom.knowledge_points && idiom.knowledge_points.length) {
            text = `【成语：${idiom.name}】\n\n`;
            for (const kp of idiom.knowledge_points) {
                text += `${kp.label}：${kp.content}\n\n`;
            }
        }

        document.getElementById('detailView').style.display = 'none';
        document.getElementById('detailEdit').style.display = '';
        document.getElementById('editTextarea').value = text;

        document.getElementById('btnSave').disabled = false;
        document.getElementById('btnCancelEdit').disabled = false;
        document.getElementById('editStatus').textContent = '编辑模式';
        document.getElementById('editStatus').style.color = 'var(--orange)';
    },

    async saveEdit() {
        if (!this.state.editing) return;
        const text = document.getElementById('editTextarea').value.trim();
        if (!text) { this.toast('内容不能为空', 'error'); return; }

        try {
            const resp = await fetch('/api/idioms/' + encodeURIComponent(this.state.editingName), {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text, old_name: this.state.editingName }),
            });
            const data = await resp.json();
            if (!resp.ok) { this.toast(data.error, 'error'); return; }

            this.toast('保存成功', 'success');
            this.state.editing = false;
            this.state.editingName = null;
            document.getElementById('btnSave').disabled = true;
            document.getElementById('btnCancelEdit').disabled = true;
            document.getElementById('editStatus').textContent = '';

            await this.refreshLibrary();
            // 重新选中
            const newName = data.name;
            for (let i = 0; i < this.state.allIdioms.length; i++) {
                if (this.state.allIdioms[i].name === newName) {
                    await this.selectIdiom(this.state.allIdioms[i],
                        document.querySelectorAll('.idiom-item')[i]);
                    break;
                }
            }
        } catch (e) {
            this.toast('保存失败', 'error');
        }
    },

    cancelEdit() {
        this.state.editing = false;
        this.state.editingName = null;
        document.getElementById('btnSave').disabled = true;
        document.getElementById('btnCancelEdit').disabled = true;
        document.getElementById('editStatus').textContent = '';
        if (this.state.selectedIdiom) {
            this.showIdiomDetail(this.state.selectedIdiom);
        }
    },

    async deleteIdiom() {
        if (!this.state.selectedIdiom) { this.toast('请先选择一个成语', 'error'); return; }
        const name = this.state.selectedIdiom.name;
        if (!confirm(`确定要删除「${name}」吗？`)) return;

        try {
            const resp = await fetch('/api/idioms/' + encodeURIComponent(name), { method: 'DELETE' });
            if (resp.ok) {
                this.toast('已删除', 'success');
                this.state.selectedIdiom = null;
                document.getElementById('detailView').innerHTML = '';
                this.refreshLibrary();
                this.refreshStats();
            }
        } catch (e) {
            this.toast('删除失败', 'error');
        }
    },

    // ==================== 日历 ====================
    async renderCalendar() {
        // 获取日期数据
        try {
            const resp = await fetch('/api/stats/dates');
            this.state.dateCounts = await resp.json();
        } catch (e) { this.state.dateCounts = {}; }

        const { calYear, calMonth } = this.state;
        document.getElementById('calMonthLabel').textContent = `${calYear}年${calMonth + 1}月`;

        const grid = document.getElementById('calGrid');
        grid.innerHTML = '';

        const firstDay = new Date(calYear, calMonth, 1).getDay(); // 0=Sunday
        const offset = firstDay === 0 ? 6 : firstDay - 1; // 转为周一=0
        const daysInMonth = new Date(calYear, calMonth + 1, 0).getDate();

        const today = new Date();
        const todayStr = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, '0')}-${String(today.getDate()).padStart(2, '0')}`;

        // 空白格
        for (let i = 0; i < offset; i++) {
            const cell = document.createElement('div');
            cell.className = 'cal-day empty';
            grid.appendChild(cell);
        }

        // 日期格
        for (let d = 1; d <= daysInMonth; d++) {
            const dayStr = `${calYear}-${String(calMonth + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`;
            const cell = document.createElement('div');
            cell.className = 'cal-day';

            if (dayStr === todayStr) cell.classList.add('today');
            if (dayStr === this.state.calSelected) cell.classList.add('selected');

            const count = this.state.dateCounts[dayStr] || 0;
            if (count > 0 && dayStr !== this.state.calSelected) cell.classList.add('has-data');

            cell.innerHTML = `<span>${d}</span>` + (count > 0 ? `<span class="cal-count">${count}</span>` : '');
            cell.addEventListener('click', () => this.selectCalDate(dayStr));
            grid.appendChild(cell);
        }

        this.updateCalInfo();
    },

    selectCalDate(dayStr) {
        this.state.calSelected = dayStr;
        document.querySelector('input[name="reviewMode"][value="bydate"]').checked = true;
        this.renderCalendar();
    },

    updateCalInfo() {
        const info = document.getElementById('calInfo');
        if (this.state.calSelected) {
            const count = this.state.dateCounts[this.state.calSelected] || 0;
            info.textContent = `已选：${this.state.calSelected}（${count} 个成语）`;
        } else {
            info.textContent = '选择日期以按日期复习';
        }
    },

    calPrev() {
        if (this.state.calMonth === 0) {
            this.state.calMonth = 11;
            this.state.calYear--;
        } else {
            this.state.calMonth--;
        }
        this.renderCalendar();
    },

    calNext() {
        if (this.state.calMonth === 11) {
            this.state.calMonth = 0;
            this.state.calYear++;
        } else {
            this.state.calMonth++;
        }
        this.renderCalendar();
    },

    // ==================== 字号控制 ====================
    setFontSize(val) {
        this.state.fontSize = parseInt(val);
        if (this.state.reviewDeck.length) {
            if (this.state.isFlipped) this.renderBackContent();
            else this.renderFrontContent();
        }
    },

    fontSizeUp() {
        this.state.fontSize = Math.min(24, this.state.fontSize + 1);
        document.getElementById('fontSlider').value = this.state.fontSize;
        this.setFontSize(this.state.fontSize);
    },

    fontSizeDown() {
        this.state.fontSize = Math.max(8, this.state.fontSize - 1);
        document.getElementById('fontSlider').value = this.state.fontSize;
        this.setFontSize(this.state.fontSize);
    },

    // ==================== 复习功能 ====================
    async startReview() {
        const mode = document.querySelector('input[name="reviewMode"]:checked').value;
        const body = { mode };
        if (mode === 'bydate') {
            if (!this.state.calSelected) { this.toast('请选择日期', 'error'); return; }
            body.date = this.state.calSelected;
        }

        try {
            const resp = await fetch('/api/review/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            const data = await resp.json();
            if (!resp.ok) { this.toast(data.error, 'error'); return; }

            this.state.reviewDeck = data;
            this.state.reviewIndex = 0;
            this.state.isFlipped = false;

            const flashcard = document.getElementById('flashcard');
            flashcard.classList.remove('flipped');

            this.renderFrontContent();
        } catch (e) {
            this.toast('网络错误', 'error');
        }
    },

    renderFrontContent() {
        const deck = this.state.reviewDeck;
        if (!deck.length) return;
        const idx = this.state.reviewIndex;
        const idiom = deck[idx];
        const mastery = idiom.review_stats?.mastery_level || 0;
        const total = deck.length;

        document.getElementById('progressLabel').textContent =
            `${idx + 1} / ${total}    ${this.getMasteryStars(mastery)} ${this.getMasteryLabel(mastery)}`;
        document.getElementById('progressFill').style.width = ((idx + 1) / total * 100) + '%';

        document.getElementById('cardContent').innerHTML = `
            <div class="card-name" style="font-size:${this.state.fontSize * 2.8}px">${idiom.name}</div>
            <div class="card-mastery">${this.getMasteryStars(mastery)} ${this.getMasteryLabel(mastery)}</div>
            <div class="card-hint">按 Space 翻转</div>
        `;
    },

    renderBackContent() {
        const deck = this.state.reviewDeck;
        if (!deck.length) return;
        const idiom = deck[this.state.reviewIndex];
        const mastery = idiom.review_stats?.mastery_level || 0;
        const fs = this.state.fontSize;

        let html = `<div class="card-back-title" style="font-size:${fs + 3}px">【${idiom.name}】</div>`;
        html += `<div class="card-back-meta">掌握度：${this.getMasteryStars(mastery)} ${this.getMasteryLabel(mastery)}</div>`;
        if (idiom.added_at) html += `<div class="card-back-meta">导入时间：${idiom.added_at}</div>`;
        html += '<hr class="card-back-divider">';
        html += '<div class="md-content" style="font-size:' + fs + 'px">';

        if (idiom.raw_text) {
            html += this.renderMarkdown(idiom.raw_text);
        } else if (idiom.knowledge_points && idiom.knowledge_points.length) {
            for (const kp of idiom.knowledge_points) {
                html += `<h2>${kp.label}</h2>`;
                html += this.renderMarkdown(kp.content);
            }
        }
        html += '</div>';

        document.getElementById('cardBackContent').innerHTML = html;
    },

    flipCard() {
        if (!this.state.reviewDeck.length) return;
        this.state.isFlipped = !this.state.isFlipped;
        const flashcard = document.getElementById('flashcard');

        if (this.state.isFlipped) {
            this.renderBackContent();
            flashcard.classList.add('flipped');
        } else {
            flashcard.classList.remove('flipped');
        }
    },

    nextCard() {
        const deck = this.state.reviewDeck;
        if (!deck.length) return;
        if (this.state.reviewIndex < deck.length - 1) {
            this.state.reviewIndex++;
            this.state.isFlipped = false;
            document.getElementById('flashcard').classList.remove('flipped');
            this.renderFrontContent();
        } else {
            // 完成
            document.getElementById('cardContent').innerHTML = `
                <div class="card-finished">
                    <div class="card-finished-title">复习完成！</div>
                    <div class="card-finished-hint">你可以重新选择模式<br>再次开始复习</div>
                </div>
            `;
        }
    },

    prevCard() {
        if (!this.state.reviewDeck.length) return;
        if (this.state.reviewIndex > 0) {
            this.state.reviewIndex--;
            this.state.isFlipped = false;
            document.getElementById('flashcard').classList.remove('flipped');
            this.renderFrontContent();
        }
    },

    async markKnown() {
        if (!this.state.reviewDeck.length) return;
        const idiom = this.state.reviewDeck[this.state.reviewIndex];
        try {
            const resp = await fetch('/api/review/mark', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: idiom.name, action: 'known' }),
            });
            const data = await resp.json();
            if (resp.ok) {
                idiom.review_stats = data.review_stats;
                this.refreshStats();
            }
        } catch (e) {}
        this.nextCard();
    },

    async markUnknown() {
        if (!this.state.reviewDeck.length) return;
        const idiom = this.state.reviewDeck[this.state.reviewIndex];
        try {
            const resp = await fetch('/api/review/mark', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: idiom.name, action: 'unknown' }),
            });
            const data = await resp.json();
            if (resp.ok) {
                idiom.review_stats = data.review_stats;
                this.refreshStats();
            }
        } catch (e) {}
        if (!this.state.isFlipped) this.flipCard();
    },

    async markMastered() {
        if (!this.state.reviewDeck.length) return;
        const idiom = this.state.reviewDeck[this.state.reviewIndex];
        try {
            const resp = await fetch('/api/review/mark', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name: idiom.name, action: 'mastered' }),
            });
            const data = await resp.json();
            if (resp.ok) {
                idiom.review_stats = data.review_stats;
                this.refreshStats();
            }
        } catch (e) {}
        this.nextCard();
    },

    // ==================== 统计 ====================
    async refreshStats() {
        try {
            const resp = await fetch('/api/stats');
            const data = await resp.json();
            const s = data.summary;

            document.getElementById('statsHeader').textContent =
                `${s.total} 个成语  |  ${s.mastered} 已掌握  |  ${s.reviewed} 已复习`;

            // 检查统计标签页是否可见
            const statsTab = document.getElementById('tab-stats');
            if (!statsTab.classList.contains('active')) return;

            const levelNames = ['未复习', '初识', '了解', '熟悉', '掌握', '精通'];
            const maxCount = Math.max(...data.level_counts, 1);

            let html = '<div class="stats-title">成语积累统计报告</div>';
            html += '<hr class="detail-divider">';

            html += '<div class="stats-section">总览</div>';
            html += `<div class="stats-row"><span class="stats-label">总成语数：</span><span class="stats-value">${s.total}</span></div>`;
            html += `<div class="stats-row"><span class="stats-label">已复习数：</span><span class="stats-value">${s.reviewed}</span></div>`;
            html += `<div class="stats-row"><span class="stats-label">已掌握数：</span><span class="stats-value">${s.mastered}</span></div>`;
            html += `<div class="stats-row"><span class="stats-label">平均掌握度：</span><span class="stats-value">${s.avg_mastery.toFixed(1)} / 5.0</span></div>`;

            html += '<div class="stats-section">掌握度分布</div>';
            html += '<hr class="detail-divider">';

            for (let level = 0; level < 6; level++) {
                const count = data.level_counts[level];
                const pct = (count / maxCount * 100).toFixed(0);
                const name = levelNames[level];
                html += `<div class="stats-bar-container">
                    <span class="stats-bar-label">Lv.${level} ${name}:</span>
                    <div class="stats-bar"><div class="stats-bar-fill" style="width:${pct}%"></div></div>
                    <span class="stats-bar-count">${count}</span>
                </div>`;
            }

            html += '<div class="stats-section">最近添加</div>';
            html += '<hr class="detail-divider">';

            for (let i = 0; i < data.recent.length; i++) {
                const r = data.recent[i];
                html += `<div class="stats-recent-item">
                    <span style="color:var(--text-tertiary)">${String(i + 1).padStart(2)}.</span>
                    <span class="stats-recent-name">${r.name}</span>
                    <span class="mastery-stars">${this.getMasteryStars(r.mastery_level)}</span>
                    <span class="stats-recent-date">(${r.added_at})</span>
                </div>`;
            }

            html += '<hr class="detail-divider">';
            html += '<div style="color:var(--text-tertiary); font-size:12px">所有数据已自动保存到服务器</div>';

            document.getElementById('statsContent').innerHTML = html;
        } catch (e) {}
    },
};

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', () => App.init());

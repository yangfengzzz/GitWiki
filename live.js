/* GitWiki local library UI. Repository data comes from the local API. */

const svgPaths = {
  logo: '<path d="M12 2.5 14.4 8l5.6 2.4-5.6 2.4L12 18.3l-2.4-5.5L4 10.4 9.6 8 12 2.5Z" fill="currentColor" stroke="none"/><path d="m18.4 16 .8 1.8 1.8.8-1.8.8-.8 1.8-.8-1.8-1.8-.8 1.8-.8.8-1.8Z" fill="currentColor" stroke="none"/>',
  search: '<circle cx="10.8" cy="10.8" r="6.8"/><path d="m16 16 4.5 4.5"/>',
  sync: '<path d="M20 7v5h-5M4 17v-5h5"/><path d="M5.8 9A7 7 0 0 1 18 6.8L20 12M4 12l2 5.2A7 7 0 0 0 18.2 15"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
  moon: '<path d="M20.5 14.4A8.8 8.8 0 0 1 9.6 3.5 8.8 8.8 0 1 0 20.5 14.4Z"/>',
  grid: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  inbox: '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 14h5l2 3h4l2-3h5"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3.5 2"/>',
  folder: '<path d="M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6Z"/>',
  chevron: '<path d="m9 5 7 7-7 7"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  star: '<path d="m12 2.8 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.4l6.2-.9L12 2.8Z"/>',
  external: '<path d="M13 5h6v6M19 5l-9 9"/><path d="M19 14v4a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h4"/>',
  github: '<path d="M9 19c-4.5 1.3-4.5-2-6-2.2M15 21v-3.4c0-.9.1-1.3-.4-1.8 2.4-.3 4.9-1.2 4.9-5.3 0-1.1-.4-2.1-1.1-2.9.1-.3.5-1.5-.2-3.1 0 0-1-.3-3.2 1.2a11 11 0 0 0-5.8 0C7 3.2 6 3.5 6 3.5c-.7 1.6-.3 2.8-.2 3.1-.7.8-1.1 1.8-1.1 2.9 0 4.1 2.5 5 4.9 5.3-.5.5-.5 1-.5 1.8V21"/><path d="M15 19c4.5 1.3 4.5-2 6-2.2"/>',
  tag: '<path d="M3 4h8l10 10-7 7L4 11V4Z"/><circle cx="8" cy="8" r="1"/>',
  book: '<path d="M4 5.5C4 4.7 4.7 4 5.5 4H20v15H5.5C4.7 19 4 19.7 4 20.5v-15Z"/><path d="M4 20.5c0-.8.7-1.5 1.5-1.5H20"/>',
  check: '<path d="m4 12 5 5L20 6"/>',
  x: '<path d="M5 5 19 19M19 5 5 19"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  spark: '<path d="m12 2 2.1 7.9L22 12l-7.9 2.1L12 22l-2.1-7.9L2 12l7.9-2.1L12 2Z"/>',
  note: '<path d="M5 3h10l4 4v13a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1Z"/><path d="M14 3v5h5M8 12h8M8 16h6"/>',
  dots: '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>',
  arrowLeft: '<path d="m14 5-7 7 7 7M7 12h14"/>'
};

function icon(name, size) {
  return '<svg aria-hidden="true" width="' + (size || 16) + '" height="' + (size || 16) + '" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">' + (svgPaths[name] || '') + '</svg>';
}

function esc(value) {
  return String(value == null ? '' : value).replace(/[&<>"']/g, function (character) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character];
  });
}

const state = {
  repos: [], categories: [], username: '', connected: false, lastSync: '', jobs: null,
  activeScope: 'all', selectedId: '', selectedIds: new Set(), expanded: new Set(),
  detailTab: 'overview', query: '', readmeHits: new Set(), quickFilter: 'all', sort: 'starred',
  showAllCategories: false, showCategoryPicker: false, showTagInput: false,
  visibleLimit: 80, modal: null, theme: localStorage.getItem('gitwiki-theme') || 'light',
  readmes: new Map(), toastTimer: null, lastJobFingerprint: '', noteTimer: null,
  pendingStateRefresh: false, editCategoryId: '', confirmCategoryDelete: false,
};

document.body.dataset.theme = state.theme;
document.getElementById('app').innerHTML =
  '<div class="app-shell" id="app-shell"><header class="topbar" id="topbar"></header>' +
  '<main class="workspace"><aside class="sidebar" id="sidebar"></aside>' +
  '<section class="browser" id="browser"></section><section class="detail" id="detail"></section></main></div>' +
  '<div id="overlay-root"></div><div id="toast-root"></div>';

async function api(path, options = {}) {
  const response = await fetch(path, { cache: 'no-store', ...options });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || '请求失败');
  return data;
}
function post(path, value) {
  return api(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(value) });
}
function category(id) { return state.categories.find(c => c.id === id); }
function repo(id) { return state.repos.find(r => r.id === id); }
function childrenOf(id) { return state.categories.filter(c => c.parent === id); }
function descendantsOf(id) {
  return [id, ...childrenOf(id).flatMap(child => descendantsOf(child.id))];
}
function expandCategoryPath(id) {
  for (let current = category(id); current; current = category(current.parent)) {
    if (current.parent) state.expanded.add(current.parent);
  }
}
function joinedCategories(item) { return item.categories.map(category).filter(Boolean); }
function selectedRepo() { return repo(state.selectedId); }
function dateOnly(value) { return value ? value.slice(0, 10) : ''; }
function formattedDate(value) {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : `${date.getMonth() + 1}月${date.getDate()}日`;
}
function formatNumber(value) {
  const number = Number(value) || 0;
  return number >= 100000 ? `${(number / 1000).toFixed(0)}k` : number >= 10000 ? `${(number / 1000).toFixed(1)}k` : number.toLocaleString('zh-CN');
}
function repoColor(item) {
  const palette = [['#39765f','#e2f0e8'],['#6e6fa7','#eeedfa'],['#9a6c50','#f5eae0'],['#3b6c82','#e5f0f4'],['#a67375','#f6e8ea']];
  let hash = 0; for (const letter of item.id) hash = (hash * 31 + letter.charCodeAt(0)) | 0;
  return palette[Math.abs(hash) % palette.length];
}
function recentRepos() {
  const cutoff = Date.now() - 30 * 24 * 60 * 60 * 1000;
  return state.repos.filter(item => new Date(item.starred).getTime() >= cutoff);
}
function matchingRepos() {
  const query = state.query.trim().toLowerCase();
  const recentCutoff = Date.now() - 30 * 24 * 60 * 60 * 1000;
  let items = state.repos.filter(item => {
    if (state.activeScope === 'uncategorized' && item.categories.length) return false;
    if (state.activeScope === 'recent' && new Date(item.starred).getTime() < recentCutoff) return false;
    if (state.activeScope.startsWith('category:')) {
      const ids = descendantsOf(state.activeScope.slice(9));
      if (!item.categories.some(id => ids.includes(id))) return false;
    }
    if (state.quickFilter === 'noted' && !(item.notes || '').trim()) return false;
    if (state.quickFilter === 'tagged' && !item.tags.length) return false;
    if (query) {
      const haystack = [item.id, item.description, item.language, item.notes, ...item.topics, ...item.tags,
        ...joinedCategories(item).map(cat => cat.name)].join(' ').toLowerCase();
      if (!haystack.includes(query) && !state.readmeHits.has(item.id)) return false;
    }
    return true;
  });
  items.sort((a, b) => state.sort === 'name' ? a.name.localeCompare(b.name) :
    state.sort === 'updated' ? b.updated.localeCompare(a.updated) :
      state.sort === 'stars' ? (Number(b.stars) - Number(a.stars) || b.starred.localeCompare(a.starred)) :
        b.starred.localeCompare(a.starred));
  return items;
}
function ensureSelectedVisible() {
  const items = matchingRepos();
  if (!items.some(item => item.id === state.selectedId)) state.selectedId = items[0]?.id || '';
}
function categoryCount(cat) {
  const ids = descendantsOf(cat.id);
  return state.repos.filter(item => item.categories.some(id => ids.includes(id))).length;
}
function statusText() {
  const jobs = state.jobs || {};
  if (jobs.sync?.running) return jobs.sync.message || '正在同步';
  if (jobs.classification?.running) return jobs.classification.message || '正在整理分类';
  if (jobs.readmes?.running) return jobs.readmes.message || '正在缓存 README';
  if (jobs.classification?.phase === 'error') return '分类已暂停';
  if (['paused', 'error'].includes(jobs.readmes?.phase)) return 'README 缓存已暂停';
  return state.connected ? `${state.username || 'GitHub'} · 已连接` : '等待连接 GitHub';
}
function renderHeader() {
  const syncing = !!state.jobs?.sync?.running;
  document.getElementById('topbar').innerHTML =
    '<div class="brand"><button class="mobile-nav" data-action="mobile-nav" aria-label="打开分类导航">' + icon('menu', 19) + '</button>' +
    '<div class="brand-mark">' + icon('logo', 23) + '</div><div class="brand-text"><span class="brand-name">GitWiki</span><span class="brand-tagline">让收藏重新被找到</span></div></div>' +
    '<label class="search-wrap">' + icon('search', 16) +
    '<input id="global-search" type="search" autocomplete="off" placeholder="搜索项目、README、标签和笔记…" value="' + esc(state.query) + '" aria-label="搜索资料库" />' +
    '<span class="shortcut">⌘ K</span></label>' +
    '<div class="top-actions"><div class="sync-meta"><strong>' + esc(statusText()) + '</strong><span>' +
    (state.lastSync ? '上次同步 · ' + formattedDate(state.lastSync) : '本地资料库') + '</span></div>' +
    '<button class="icon-button outlined" data-action="theme" title="切换明暗主题" aria-label="切换明暗主题">' + icon(state.theme === 'dark' ? 'sun' : 'moon', 17) + '</button>' +
    '<button class="primary-button" data-action="sync" ' + (syncing ? 'disabled' : '') + '><span class="' + (syncing ? 'spin' : '') + '">' + icon('sync', 15) + '</span>' + (syncing ? '同步中' : '立即同步') + '</button></div>';
}
function renderCategoryTree(parent, depth) {
  return childrenOf(parent).map(item => {
    const children = childrenOf(item.id);
    const expanded = state.showAllCategories || state.expanded.has(item.id);
    const active = state.activeScope === 'category:' + item.id;
    return '<div class="category-node"><div class="category-row" data-depth="' + depth + '" data-category-id="' + esc(item.id) + '">' +
      (children.length ? '<button class="category-toggle" data-action="toggle-category" data-id="' + esc(item.id) + '" aria-label="' + (expanded ? '收起' : '展开') + esc(item.name) + '"><span class="' + (expanded ? 'rotated' : '') + '">' + icon('chevron', 12) + '</span></button>' : '<span class="category-toggle"></span>') +
      '<button class="category-item ' + (active ? 'active' : '') + '" data-action="category" data-id="' + esc(item.id) + '" title="' + esc(item.name) + '"><span class="category-dot" style="--cat-color:' + esc(item.color) + '"></span><span class="category-label">' + esc(item.name) + '</span><span class="category-count">' + categoryCount(item) + '</span></button>' +
      '<button class="category-edit" data-action="edit-category" data-id="' + esc(item.id) + '" title="编辑分类" aria-label="编辑' + esc(item.name) + '">' + icon('dots', 13) + '</button></div>' +
      (children.length && expanded ? renderCategoryTree(item.id, depth + 1) : '') + '</div>';
  }).join('');
}
function renderSidebar() {
  const container = document.getElementById('sidebar');
  const scroll = container.querySelector('.sidebar-scroll')?.scrollTop || 0;
  const uncategorized = state.repos.filter(item => !item.categories.length).length;
  const classifyIssue = state.jobs?.classification?.phase === 'error';
  const readmeIssue = ['paused', 'error'].includes(state.jobs?.readmes?.phase);
  const backgroundRunning = state.jobs?.classification?.running || state.jobs?.readmes?.running;
  const footer = classifyIssue ? '<div class="tip-card"><div class="tip-head">' + icon('spark', 13) + ' 分类已暂停</div><p>' + esc(state.jobs.classification.error || '可从剩余项目继续整理。') + '</p><button class="tip-action" data-action="retry-classify">继续分类</button></div>' :
    readmeIssue ? '<div class="tip-card"><div class="tip-head">' + icon('book', 13) + ' README 缓存已暂停</div><p>' + esc(state.jobs.readmes.error || '可稍后从剩余项目继续缓存。') + '</p><button class="tip-action" data-action="retry-readmes">继续缓存</button></div>' :
      backgroundRunning ? '<div class="tip-card" id="job-progress"><div class="tip-head">' + icon('spark', 13) + ' 后台处理中</div><p><span class="job-line" data-job="classification">' + (state.jobs.classification.running ? '分类 ' + state.jobs.classification.current + '/' + state.jobs.classification.total : '分类已完成') + '</span><span class="job-line" data-job="readmes">' + (state.jobs.readmes.running ? 'README ' + state.jobs.readmes.current + '/' + state.jobs.readmes.total : 'README 已完成') + '</span></p></div>' :
      '<div class="tip-card"><div class="tip-head">' + icon('spark', 13) + ' 随手整理</div><p>把项目拖到左侧分类。一个项目可以属于多个分类；新同步的 Star 留在「未分类」。</p></div>';
  container.innerHTML = '<div class="sidebar-scroll"><div class="sidebar-group"><div class="sidebar-title">资料库</div>' +
    '<button class="nav-item ' + (state.activeScope === 'all' ? 'active' : '') + '" data-action="scope" data-id="all">' + icon('grid', 16) + '<span class="nav-label">全部收藏</span><span class="nav-count">' + state.repos.length.toLocaleString('zh-CN') + '</span></button>' +
    '<button class="nav-item unclassified ' + (state.activeScope === 'uncategorized' ? 'active' : '') + '" data-action="scope" data-id="uncategorized"><span class="nav-icon">' + icon('inbox', 16) + '</span><span class="nav-label">未分类</span><span class="nav-count">' + uncategorized + '</span></button>' +
    '<button class="nav-item ' + (state.activeScope === 'recent' ? 'active' : '') + '" data-action="scope" data-id="recent">' + icon('clock', 16) + '<span class="nav-label">最近收藏</span><span class="nav-count">' + recentRepos().length + '</span></button></div>' +
    '<div class="sidebar-group"><div class="section-heading"><span>我的分类 · ' + state.categories.length + '</span><button data-action="new-category" title="新建分类" aria-label="新建分类">' + icon('plus', 15) + '</button></div>' +
    renderCategoryTree(null, 0) +
    (state.categories.length ? '<button class="show-more" data-action="show-categories">' + (state.showAllCategories ? '收起分类' : '展开全部 ' + state.categories.length + ' 个分类') + '</button>' : '') + '</div></div>' +
    '<div class="sidebar-bottom">' + footer + '</div>';
  container.querySelector('.sidebar-scroll').scrollTop = scroll;
}
function currentTitle() {
  if (state.activeScope === 'uncategorized') return { title: '未分类', subtitle: '新同步的项目会先来到这里，等你给它们一个位置。', eyebrow: 'INBOX' };
  if (state.activeScope === 'recent') return { title: '最近收藏', subtitle: '回看最近加入资料库的发现。', eyebrow: 'RECENTLY STARRED' };
  if (state.activeScope.startsWith('category:')) {
    return { title: category(state.activeScope.slice(9))?.name || '分类', subtitle: '一个主题下的项目、想法与可复用的工具。', eyebrow: 'COLLECTION' };
  }
  return { title: '全部收藏', subtitle: '每一个 Star，都值得在需要的时候被重新找到。', eyebrow: 'YOUR LIBRARY' };
}
function renderRepoCard(item) {
  const active = item.id === state.selectedId;
  const checked = state.selectedIds.has(item.id);
  const categories = joinedCategories(item);
  const [color, bg] = repoColor(item);
  return '<div class="repo-card ' + (active ? 'active' : '') + '" draggable="true" data-repo-id="' + esc(item.id) + '" data-action="select-repo"><div class="repo-top">' +
    '<div class="repo-avatar" style="--avatar-color:' + color + ';--avatar-bg:' + bg + '">' + esc(item.name.charAt(0).toUpperCase()) + '</div><div class="repo-content">' +
    '<div class="repo-title-line"><div class="repo-name"><span>' + esc(item.owner) + ' / </span>' + esc(item.name) + '</div><button class="repo-select ' + (checked ? 'checked' : '') + '" data-action="toggle-select" data-id="' + esc(item.id) + '" aria-label="选择项目">' + (checked ? icon('check', 11) : '') + '</button></div>' +
    '<p class="repo-desc">' + esc(item.description || '暂无描述') + '</p><div class="repo-tags">' +
    (categories.length ? categories.map(cat => '<button class="mini-tag category-tag category-link" type="button" data-action="category" data-id="' + esc(cat.id) + '" title="查看分类：' + esc(cat.name) + '">' + esc(cat.name) + '</button>').join('') : '<span class="mini-tag uncategorized">未分类</span>') +
    item.topics.slice(0, 2).map(topic => '<span class="mini-tag">' + esc(topic) + '</span>').join('') + '</div></div></div>' +
    '<div class="repo-bottom"><span>' + icon('star', 12) + formatNumber(item.stars) + '</span><span><i class="language-dot" style="--lang-color:' + color + '"></i>' + esc(item.language) + '</span><span class="push-right">' + formattedDate(item.starred) + ' 收藏</span></div></div>';
}
function renderBrowser() {
  const container = document.getElementById('browser');
  const scroll = container.querySelector('.browser-list')?.scrollTop || 0;
  const title = currentTitle();
  const items = matchingRepos();
  const shown = items.slice(0, state.visibleLimit);
  const onboarding = !state.repos.length && !state.jobs?.sync?.running;
  container.innerHTML = '<div class="browser-head"><div class="eyebrow">' + esc(title.eyebrow) + '</div><div class="browser-title-row"><div><h1 class="browser-title">' + esc(title.title) + '</h1><p class="browser-subtitle">' + esc(title.subtitle) + '</p></div><span class="title-icon">' + icon(state.activeScope === 'uncategorized' ? 'inbox' : 'book', 18) + '</span></div>' +
    '<div class="browser-toolbar"><div class="filter-tabs"><button class="filter-tab ' + (state.quickFilter === 'all' ? 'active' : '') + '" data-action="quick-filter" data-id="all">全部</button><button class="filter-tab ' + (state.quickFilter === 'noted' ? 'active' : '') + '" data-action="quick-filter" data-id="noted">有笔记</button><button class="filter-tab ' + (state.quickFilter === 'tagged' ? 'active' : '') + '" data-action="quick-filter" data-id="tagged">有标签</button></div>' +
    '<select class="sort-select" id="sort-select" aria-label="排序方式"><option value="starred" ' + (state.sort === 'starred' ? 'selected' : '') + '>最近收藏</option><option value="updated" ' + (state.sort === 'updated' ? 'selected' : '') + '>最近更新</option><option value="stars" ' + (state.sort === 'stars' ? 'selected' : '') + '>Star 最多</option><option value="name" ' + (state.sort === 'name' ? 'selected' : '') + '>名称 A–Z</option></select></div></div>' +
    '<div class="browser-list"><div class="list-intro"><span>' + (state.query ? '搜索结果' : '项目') + ' · ' + items.length.toLocaleString('zh-CN') + ' 个</span><span>拖放即可归类</span></div>' +
    (shown.length ? shown.map(renderRepoCard).join('') : onboarding ?
      '<div class="empty-state"><div class="empty-symbol">' + icon('star', 24) + '</div><h3>把你的 Star 带进来</h3><p>读取现有 GitHub Lists，建立可以搜索、标注和反复使用的本地资料库。</p><button class="primary-button" data-action="sync">开始导入</button></div>' :
      '<div class="empty-state"><div class="empty-symbol">' + icon('search', 24) + '</div><h3>这里暂时没有项目</h3><p>试试其他分类或搜索词。</p></div>') +
    (items.length > shown.length ? '<button class="show-more load-more" data-action="load-more">继续加载 · 还剩 ' + (items.length - shown.length) + ' 个</button>' : '') + '</div>' +
    (state.selectedIds.size ? '<div class="bulk-bar"><strong>已选 ' + state.selectedIds.size + ' 个</strong><span>批量加入分类</span><select id="bulk-category"><option value="">选择分类…</option>' +
      state.categories.map(cat => '<option value="' + esc(cat.id) + '">' + esc(cat.name) + '</option>').join('') + '</select><button data-action="clear-selection">取消</button></div>' : '');
  container.querySelector('.browser-list').scrollTop = scroll;
}

function inlineMarkdown(raw) {
  return esc(raw).replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,
      (_, label, url) => '<a href="' + esc(url) + '" target="_blank" rel="noopener noreferrer">' + label + '</a>');
}
function fallbackMarkdown(raw, limit = 200000) {
  const lines = raw.slice(0, limit).replace(/\r\n?/g, '\n').split('\n');
  const output = [];
  let inCode = false, inList = false, paragraph = [];
  const flushParagraph = () => { if (paragraph.length) { output.push('<p>' + inlineMarkdown(paragraph.join(' ')) + '</p>'); paragraph = []; } };
  const closeList = () => { if (inList) { output.push('</ul>'); inList = false; } };
  for (const line of lines) {
    if (/^\s*```/.test(line)) {
      flushParagraph(); closeList();
      output.push(inCode ? '</code></pre>' : '<pre><code>'); inCode = !inCode; continue;
    }
    if (inCode) { output.push(esc(line) + '\n'); continue; }
    if (!line.trim()) { flushParagraph(); closeList(); continue; }
    const heading = line.match(/^\s*(#{1,4})\s+(.+)$/);
    if (heading) { flushParagraph(); closeList(); const level = Math.min(heading[1].length + 1, 4); output.push(`<h${level}>${inlineMarkdown(heading[2])}</h${level}>`); continue; }
    const list = line.match(/^\s*[-*+]\s+(.+)$/);
    if (list) { flushParagraph(); if (!inList) { output.push('<ul>'); inList = true; } output.push('<li>' + inlineMarkdown(list[1]) + '</li>'); continue; }
    const quote = line.match(/^\s*>\s*(.+)$/);
    if (quote) { flushParagraph(); closeList(); output.push('<blockquote>' + inlineMarkdown(quote[1]) + '</blockquote>'); continue; }
    if (/^\s*[-*_]{3,}\s*$/.test(line)) { flushParagraph(); closeList(); output.push('<hr>'); continue; }
    closeList(); paragraph.push(line.trim());
  }
  flushParagraph(); closeList(); if (inCode) output.push('</code></pre>');
  return output.join('');
}
const markdown = window.markdownit ? window.markdownit({ html: !!window.DOMPurify, linkify: true, breaks: false }) : null;
if (markdown) {
  const defaultLink = markdown.renderer.rules.link_open || ((tokens, index, options, env, self) => self.renderToken(tokens, index, options));
  markdown.renderer.rules.link_open = (tokens, index, options, env, self) => {
    const token = tokens[index];
    const href = token.attrGet('href') || '';
    if (href && !/^[a-z][a-z\d+.-]*:/i.test(href) && !href.startsWith('#')) {
      token.attrSet('href', new URL(href, `https://github.com/${env.repo.id}/blob/${encodeURIComponent(env.repo.default_branch || 'main')}/`).href);
    }
    token.attrSet('target', '_blank'); token.attrSet('rel', 'noopener noreferrer');
    return defaultLink(tokens, index, options, env, self);
  };
  const defaultImage = markdown.renderer.rules.image || ((tokens, index, options, env, self) => self.renderToken(tokens, index, options));
  markdown.renderer.rules.image = (tokens, index, options, env, self) => {
    const token = tokens[index]; let src = token.attrGet('src') || '';
    if (!/^[a-z][a-z\d+.-]*:/i.test(src)) {
      src = new URL(src, `https://raw.githubusercontent.com/${env.repo.id}/${encodeURIComponent(env.repo.default_branch || 'main')}/`).href;
    }
    try {
      const host = new URL(src).hostname;
      if (!['raw.githubusercontent.com','github.com','user-images.githubusercontent.com','githubusercontent.com'].includes(host)) return '';
    } catch (_) { return ''; }
    token.attrSet('src', src); token.attrSet('loading', 'lazy');
    return defaultImage(tokens, index, options, env, self);
  };
}
function markdownToHtml(raw, item, limit = 200000) {
  if (!markdown) return fallbackMarkdown(raw, limit);
  const rendered = markdown.render(raw.slice(0, limit), { repo: item });
  if (!window.DOMPurify) return rendered;
  const safe = window.DOMPurify.sanitize(rendered, {
    USE_PROFILES: { html: true }, FORBID_TAGS: ['style', 'form', 'input', 'button', 'iframe', 'video', 'audio'],
    FORBID_ATTR: ['style']
  });
  const template = document.createElement('template');
  template.innerHTML = safe;
  template.content.querySelectorAll('a[href]').forEach(link => {
    const href = link.getAttribute('href');
    if (href && !/^[a-z][a-z\d+.-]*:/i.test(href) && !href.startsWith('#')) {
      try { link.href = new URL(href, `https://github.com/${item.id}/blob/${encodeURIComponent(item.default_branch || 'main')}/`).href; }
      catch (_) { link.removeAttribute('href'); }
    }
    link.target = '_blank'; link.rel = 'noopener noreferrer';
  });
  template.content.querySelectorAll('img[src]').forEach(img => {
    let src = img.getAttribute('src');
    try {
      if (!/^[a-z][a-z\d+.-]*:/i.test(src)) src = new URL(src, `https://raw.githubusercontent.com/${item.id}/${encodeURIComponent(item.default_branch || 'main')}/`).href;
      const host = new URL(src).hostname;
      if (!['raw.githubusercontent.com', 'github.com', 'user-images.githubusercontent.com', 'githubusercontent.com'].includes(host)) img.remove();
      else { img.src = src; img.loading = 'lazy'; }
    } catch (_) { img.remove(); }
  });
  return template.innerHTML;
}
function readmeMarkup(item, full) {
  const cached = state.readmes.get(item.id);
  if (!cached || cached.status === 'loading') return '<div class="markdown-body"><p>正在从 GitHub 读取 README…</p></div>';
  if (cached.status === 'missing') return '<div class="markdown-body"><p>这个仓库没有 README。</p></div>';
  if (cached.status === 'error') return '<div class="markdown-body"><p>' + esc(cached.error || 'README 暂时无法读取') + '</p><button class="subtle-action" data-action="retry-readme">重试</button></div>';
  return '<div class="markdown-body">' + markdownToHtml(cached.text || '', item, full ? 200000 : 2500) + '</div>';
}
function categoryChips(item) {
  const chips = joinedCategories(item).map(cat => '<span class="category-chip">' + icon('folder', 12) +
    '<button class="category-chip-link" type="button" data-action="category" data-id="' + esc(cat.id) + '" title="查看分类：' + esc(cat.name) + '">' + esc(cat.name) + '</button>' +
    '<button class="chip-remove" data-action="remove-category" data-id="' + esc(cat.id) + '" title="从此分类移除" aria-label="从此分类移除">' + icon('x', 11) + '</button></span>').join('');
  return '<div class="chip-list">' + (chips || '<span class="mini-tag uncategorized">尚未分类</span>') +
    (state.showCategoryPicker ? '<select id="detail-category-picker" class="inline-select"><option value="">选择分类…</option>' +
      state.categories.filter(cat => !item.categories.includes(cat.id)).map(cat => '<option value="' + esc(cat.id) + '">' + esc(cat.name) + '</option>').join('') + '</select>' :
      '<button class="add-chip" data-action="show-category-picker">' + icon('plus', 12) + '添加分类</button>') + '</div>';
}
function tagChips(item) {
  return '<div class="chip-list">' + item.tags.map(tag => '<span class="tag-chip">' + icon('tag', 11) + esc(tag) +
    '<button class="chip-remove" data-action="remove-tag" data-id="' + esc(tag) + '" title="移除标签" aria-label="移除标签">' + icon('x', 11) + '</button></span>').join('') +
    (state.showTagInput ? '<input id="new-tag-input" class="tag-input" placeholder="输入标签后回车" maxlength="40" />' :
      '<button class="add-chip" data-action="show-tag-input">' + icon('plus', 12) + '添加标签</button>') + '</div>';
}
function noteMarkup(item) {
  return '<div class="note-card"><textarea id="repo-note" placeholder="写下这个项目能解决什么问题、以后想怎么使用…" aria-label="个人笔记">' + esc(item.notes) + '</textarea>' +
    '<div class="note-foot"><span>' + icon('check', 12) + '保存在本地数据库</span><span id="note-status">自动保存</span></div></div>';
}
function renderDetail() {
  const container = document.getElementById('detail');
  const item = selectedRepo();
  if (!item) {
    container.innerHTML = '<div class="empty-state"><div class="empty-symbol">' + icon('book', 25) + '</div><h3>选择一个项目</h3><p>项目的 README、分类和笔记会显示在这里。</p></div>';
    return;
  }
  const firstCat = joinedCategories(item)[0];
  const crumb = firstCat?.name || '未分类';
  const [color, bg] = repoColor(item);
  const overview = '<section class="content-section"><div class="section-row"><h2 class="content-title">所属分类</h2><button class="subtle-action" data-action="new-category">新建分类</button></div>' + categoryChips(item) + '</section>' +
    '<section class="content-section"><div class="section-row"><h2 class="content-title">我的标签</h2></div>' + tagChips(item) + '</section>' +
    '<section class="content-section"><div class="section-row"><h2 class="content-title">README 预览</h2><button class="subtle-action" data-action="detail-tab" data-id="readme">阅读完整内容</button></div>' +
    '<div class="readme-card"><div class="readme-head"><span>' + icon('book', 13) + 'README.md</span><span>' + (item.readme_status === 'ready' ? '已缓存' : '从 GitHub 读取') + '</span></div><div class="readme-preview">' + readmeMarkup(item, false) + '</div>' +
    '<button class="readme-link" data-action="detail-tab" data-id="readme">展开 README ' + icon('chevron', 12) + '</button></div></section>' +
    '<section class="content-section"><div class="section-row"><h2 class="content-title">我的笔记</h2></div>' + noteMarkup(item) + '</section>';
  const readme = '<section class="content-section"><div class="section-row"><h2 class="content-title">仓库 README</h2><span class="breadcrumb">本地缓存</span></div><div class="readme-card readme-full">' + readmeMarkup(item, true) + '</div></section>';
  const notes = '<section class="content-section"><div class="section-row"><h2 class="content-title">分类</h2></div>' + categoryChips(item) + '</section>' +
    '<section class="content-section"><div class="section-row"><h2 class="content-title">标签</h2></div>' + tagChips(item) + '</section>' +
    '<section class="content-section"><div class="section-row"><h2 class="content-title">个人笔记</h2></div>' + noteMarkup(item) + '</section>';
  container.innerHTML = '<div class="detail-inner"><div class="detail-topline"><div class="breadcrumb"><button class="mobile-back" data-action="close-detail">' + icon('arrowLeft', 14) + '返回列表</button><span>资料库</span>' + icon('chevron', 11) + '<span>' + esc(crumb) + '</span></div>' +
    '<div class="detail-actions"><button class="icon-button" data-action="copy-link" title="复制 GitHub 链接" aria-label="复制 GitHub 链接">' + icon('external', 15) + '</button></div></div>' +
    '<div class="detail-hero"><div class="repo-avatar hero-avatar" style="--avatar-color:' + color + ';--avatar-bg:' + bg + '">' + esc(item.name.charAt(0).toUpperCase()) + '</div>' +
    '<div class="hero-main"><div class="hero-owner">' + esc(item.owner) + ' / repository</div><h1 class="hero-title">' + esc(item.name) + '</h1><p class="hero-desc">' + esc(item.description || '暂无描述') + '</p>' +
    '<div class="hero-actions"><a class="open-button" href="https://github.com/' + encodeURIComponent(item.owner) + '/' + encodeURIComponent(item.name) + '" target="_blank" rel="noopener noreferrer">' + icon('github', 14) + '在 GitHub 打开 ' + icon('external', 12) + '</a>' +
    '<button class="secondary-button" data-action="detail-tab" data-id="notes">' + icon('note', 13) + '添加笔记</button></div></div></div>' +
    '<div class="metrics"><div class="metric"><div class="metric-label">' + icon('star', 12) + 'GitHub Stars</div><div class="metric-value">' + formatNumber(item.stars) + '</div></div>' +
    '<div class="metric"><div class="metric-label"><i class="language-dot" style="--lang-color:' + color + '"></i>主要语言</div><div class="metric-value">' + esc(item.language) + '</div></div>' +
    '<div class="metric"><div class="metric-label">' + icon('clock', 12) + '最近更新</div><div class="metric-value">' + formattedDate(item.updated) + '</div></div>' +
    '<div class="metric"><div class="metric-label">' + icon('book', 12) + '收藏于</div><div class="metric-value">' + formattedDate(item.starred) + '</div></div></div>' +
    '<nav class="detail-tabs" aria-label="项目详情"><button class="detail-tab ' + (state.detailTab === 'overview' ? 'active' : '') + '" data-action="detail-tab" data-id="overview">概览</button>' +
    '<button class="detail-tab ' + (state.detailTab === 'readme' ? 'active' : '') + '" data-action="detail-tab" data-id="readme">README</button>' +
    '<button class="detail-tab ' + (state.detailTab === 'notes' ? 'active' : '') + '" data-action="detail-tab" data-id="notes">我的笔记</button></nav>' +
    '<div class="detail-body">' + (state.detailTab === 'readme' ? readme : state.detailTab === 'notes' ? notes : overview) + '</div></div>';
}
function renderOverlay() {
  const root = document.getElementById('overlay-root');
  if (!state.modal) { root.innerHTML = ''; return; }
  if (state.modal === 'auth') {
    root.innerHTML = '<div class="modal-backdrop" data-action="close-modal"><div class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><div class="modal-head"><div><h2 id="modal-title">连接 GitHub</h2><p>优先使用当前电脑的 gh 登录；也可以临时输入只读访问令牌。</p></div><button class="icon-button" data-action="close-modal" aria-label="关闭">' + icon('x', 17) + '</button></div>' +
      '<p class="auth-help">在终端运行 <code>gh auth login</code> 后重启 GitWiki，或输入具有 Starring（读取）权限的令牌。令牌仅保存在服务进程内存中。</p>' +
      '<label class="form-label" for="github-token">GitHub 访问令牌</label><input class="form-field" id="github-token" type="password" autocomplete="off" placeholder="github_pat_…" />' +
      '<div class="modal-actions"><button class="secondary-button" data-action="close-modal">取消</button><button class="primary-button" data-action="connect-github">连接</button></div></div></div>';
    return;
  }
  if (state.modal === 'edit-category') {
    const item = category(state.editCategoryId);
    if (!item) { root.innerHTML = ''; return; }
    const hasChildren = childrenOf(item.id).length > 0;
    root.innerHTML = '<div class="modal-backdrop" data-action="close-modal"><div class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><div class="modal-head"><div><h2 id="modal-title">编辑分类</h2><p>调整分类名称和所在主题。</p></div><button class="icon-button" data-action="close-modal" aria-label="关闭">' + icon('x', 17) + '</button></div>' +
      '<label class="form-label" for="category-name">分类名称</label><input class="form-field" id="category-name" maxlength="50" value="' + esc(item.name) + '" />' +
      '<label class="form-label" for="category-parent">上级分类</label><select class="form-field" id="category-parent"><option value="">顶层分类</option>' +
      state.categories.filter(cat => !cat.parent && cat.id !== item.id).map(cat => '<option value="' + esc(cat.id) + '" ' + (item.parent === cat.id ? 'selected' : '') + '>' + esc(cat.name) + '</option>').join('') + '</select>' +
      (state.confirmCategoryDelete ? '<p class="delete-warning">删除后，这个分类与项目的关联会移除。请再次点击确认。</p>' : '') +
      '<div class="modal-actions"><button class="delete-button" data-action="delete-category" ' + (hasChildren ? 'disabled title="请先移动或删除子分类"' : '') + '>' + (state.confirmCategoryDelete ? '确认删除' : '删除分类') + '</button><button class="secondary-button" data-action="close-modal">取消</button><button class="primary-button" data-action="save-category">保存</button></div></div></div>';
    return;
  }
  root.innerHTML = '<div class="modal-backdrop" data-action="close-modal"><div class="modal" role="dialog" aria-modal="true" aria-labelledby="modal-title"><div class="modal-head"><div><h2 id="modal-title">新建分类</h2><p>把收藏整理成属于你自己的知识地图。</p></div><button class="icon-button" data-action="close-modal" aria-label="关闭">' + icon('x', 17) + '</button></div>' +
    '<label class="form-label" for="category-name">分类名称</label><input class="form-field" id="category-name" maxlength="50" placeholder="例如：文献发现工具" />' +
    '<label class="form-label" for="category-parent">上级分类</label><select class="form-field" id="category-parent"><option value="">顶层分类</option>' +
    state.categories.filter(cat => !cat.parent).map(cat => '<option value="' + esc(cat.id) + '" ' + (state.activeScope === 'category:' + cat.id ? 'selected' : '') + '>' + esc(cat.name) + '</option>').join('') + '</select>' +
    '<div class="modal-actions"><button class="secondary-button" data-action="close-modal">取消</button><button class="primary-button" data-action="create-category">创建分类</button></div></div></div>';
}
function renderAll() { renderHeader(); renderSidebar(); renderBrowser(); renderDetail(); renderOverlay(); }
function showToast(message) {
  const root = document.getElementById('toast-root');
  root.innerHTML = '<div class="toast">' + icon('check', 16) + esc(message) + '</div>';
  clearTimeout(state.toastTimer);
  state.toastTimer = setTimeout(() => { root.innerHTML = ''; }, 3600);
}

async function loadState(quiet = false) {
  const data = await api('/api/state');
  state.repos = data.repos;
  state.categories = data.categories;
  state.connected = data.connected;
  state.username = data.username;
  state.lastSync = data.last_sync;
  state.jobs = data.jobs;
  if (!state.expanded.size) state.categories.filter(cat => !cat.parent).slice(0, 2).forEach(cat => state.expanded.add(cat.id));
  ensureSelectedVisible();
  renderAll();
  if (state.selectedId) loadReadme(state.selectedId);
  if (!quiet && state.repos.length) showToast(`已载入 ${state.repos.length.toLocaleString('zh-CN')} 个项目`);
}
async function loadReadme(repoId, force = false) {
  if (state.readmes.has(repoId) && !force) return;
  state.readmes.set(repoId, { status: 'loading' });
  if (state.selectedId === repoId) renderDetail();
  try {
    const data = await api('/api/readme?id=' + encodeURIComponent(repoId));
    state.readmes.set(repoId, { status: data.status, text: data.readme });
    const item = repo(repoId); if (item) item.readme_status = data.status;
  } catch (error) {
    state.readmes.set(repoId, { status: 'error', error: error.message });
  }
  if (state.selectedId === repoId) renderDetail();
}
function updateLocalCategories(repoIds, categoryIds, mode) {
  for (const id of repoIds) {
    const item = repo(id); if (!item) continue;
    if (mode === 'remove') item.categories = item.categories.filter(cat => !categoryIds.includes(cat));
    else if (mode === 'replace') item.categories = categoryIds.slice();
    else item.categories = [...new Set([...item.categories, ...categoryIds])];
  }
  ensureSelectedVisible(); renderSidebar(); renderBrowser(); renderDetail();
}
async function setCategories(repoIds, categoryIds, mode) {
  await post('/api/repo-categories', { repo_ids: repoIds, category_ids: categoryIds, mode });
  updateLocalCategories(repoIds, categoryIds, mode);
}
async function setTags(item, tags) {
  await post('/api/tags', { repo_id: item.id, tags });
  item.tags = tags; renderBrowser(); renderDetail();
}
async function pollStatus() {
  try {
    const data = await api('/api/status');
    const before = state.jobs?.sync?.phase;
    const beforeClassified = state.jobs?.classification?.current || 0;
    const beforeClassificationPhase = state.jobs?.classification?.phase;
    const beforeReadmesPhase = state.jobs?.readmes?.phase;
    state.jobs = data.jobs;
    state.connected = data.connected;
    state.username = data.username;
    state.lastSync = data.last_sync;
    if (document.activeElement?.id !== 'global-search') renderHeader();
    if (beforeClassificationPhase !== data.jobs.classification.phase || beforeReadmesPhase !== data.jobs.readmes.phase) renderSidebar();
    const classProgress = document.querySelector('#job-progress [data-job="classification"]');
    const readmeProgress = document.querySelector('#job-progress [data-job="readmes"]');
    if (classProgress) classProgress.textContent = data.jobs.classification.running ? `分类 ${data.jobs.classification.current}/${data.jobs.classification.total}` : '分类已完成';
    if (readmeProgress) readmeProgress.textContent = data.jobs.readmes.running ? `README ${data.jobs.readmes.current}/${data.jobs.readmes.total}` : 'README 已完成';
    if (before === 'stars' || before === 'lists' || before === 'connecting') {
      if (data.jobs.sync.phase === 'complete') { await loadState(true); showToast(data.jobs.sync.message); }
    }
    if (data.jobs.sync.phase === 'error' && before !== 'error') showToast(data.jobs.sync.error || '同步失败');
    if (data.jobs.classification.current > beforeClassified) state.pendingStateRefresh = true;
    if (state.pendingStateRefresh && !['global-search', 'repo-note', 'new-tag-input', 'category-name'].includes(document.activeElement?.id)) {
      state.pendingStateRefresh = false;
      await loadState(true);
    }
  } catch (_) { /* A stopped local server will be visible on the next user action. */ }
}

document.addEventListener('click', async event => {
  const target = event.target.closest('[data-action]');
  if (!target) return;
  const action = target.dataset.action, id = target.dataset.id;
  if (action === 'close-modal' && target.classList.contains('modal-backdrop') && event.target !== target) return;
  try {
    if (action === 'theme') {
      state.theme = state.theme === 'light' ? 'dark' : 'light';
      document.body.dataset.theme = state.theme; localStorage.setItem('gitwiki-theme', state.theme); renderHeader();
    } else if (action === 'sync') {
      if (!state.connected) { state.modal = 'auth'; renderOverlay(); return; }
      const result = await post('/api/sync', {});
      state.jobs = result.jobs; renderHeader(); showToast(result.started ? '开始同步 GitHub Star' : '同步正在进行');
    } else if (action === 'retry-classify' || action === 'retry-readmes') {
      const result = await post(action === 'retry-classify' ? '/api/classify' : '/api/readmes', {});
      showToast(result.started ? '已从剩余项目继续' : '后台任务正在进行');
      const status = await api('/api/status'); state.jobs = status.jobs; renderHeader(); renderSidebar();
    } else if (action === 'scope' || action === 'category') {
      state.activeScope = action === 'scope' ? id : 'category:' + id;
      if (action === 'category') {
        expandCategoryPath(id);
        state.query = ''; state.readmeHits = new Set();
        const search = document.getElementById('global-search'); if (search) search.value = '';
      }
      state.quickFilter = 'all'; state.visibleLimit = 80; state.selectedIds.clear();
      ensureSelectedVisible(); renderSidebar(); renderBrowser(); renderDetail();
      document.getElementById('browser').querySelector('.browser-list').scrollTop = 0;
      document.getElementById('app-shell').classList.remove('show-nav', 'detail-open');
      if (state.selectedId) loadReadme(state.selectedId);
    } else if (action === 'toggle-category') {
      if (state.expanded.has(id)) state.expanded.delete(id); else state.expanded.add(id);
      state.showAllCategories = false; renderSidebar();
    } else if (action === 'show-categories') {
      state.showAllCategories = !state.showAllCategories; renderSidebar();
    } else if (action === 'select-repo') {
      state.selectedId = target.dataset.repoId; state.detailTab = 'overview';
      state.showCategoryPicker = false; state.showTagInput = false;
      renderBrowser(); renderDetail(); loadReadme(state.selectedId);
      document.getElementById('app-shell').classList.add('detail-open');
    } else if (action === 'toggle-select') {
      event.stopPropagation();
      if (state.selectedIds.has(id)) state.selectedIds.delete(id); else state.selectedIds.add(id);
      renderBrowser();
    } else if (action === 'clear-selection') {
      state.selectedIds.clear(); renderBrowser();
    } else if (action === 'load-more') {
      state.visibleLimit += 80; renderBrowser();
    } else if (action === 'quick-filter') {
      state.quickFilter = id; state.visibleLimit = 80; ensureSelectedVisible();
      renderBrowser(); renderDetail(); if (state.selectedId) loadReadme(state.selectedId);
    } else if (action === 'detail-tab') {
      state.detailTab = id; state.showCategoryPicker = false; state.showTagInput = false;
      renderDetail(); document.getElementById('detail').scrollTop = 0;
      if (id === 'notes') document.getElementById('repo-note')?.focus();
      if (id === 'readme' && state.selectedId) loadReadme(state.selectedId);
    } else if (action === 'show-category-picker') {
      state.showCategoryPicker = true; renderDetail(); document.getElementById('detail-category-picker')?.focus();
    } else if (action === 'show-tag-input') {
      state.showTagInput = true; renderDetail(); document.getElementById('new-tag-input')?.focus();
    } else if (action === 'remove-category') {
      await setCategories([state.selectedId], [id], 'remove'); showToast('已从分类中移除');
    } else if (action === 'remove-tag') {
      const item = selectedRepo(); if (item) { await setTags(item, item.tags.filter(tag => tag !== id)); showToast('标签已移除'); }
    } else if (action === 'new-category') {
      state.modal = 'category'; renderOverlay(); document.getElementById('category-name')?.focus();
    } else if (action === 'edit-category') {
      state.editCategoryId = id; state.confirmCategoryDelete = false; state.modal = 'edit-category';
      renderOverlay(); document.getElementById('category-name')?.focus();
    } else if (action === 'close-modal') {
      state.modal = null; renderOverlay();
    } else if (action === 'create-category') {
      const name = document.getElementById('category-name').value.trim();
      const parent = document.getElementById('category-parent').value || null;
      if (!name) { document.getElementById('category-name').focus(); return; }
      const created = await post('/api/categories', { name, parent });
      state.categories.push(created); if (parent) state.expanded.add(parent);
      state.modal = null; state.activeScope = 'category:' + created.id; renderAll(); showToast('已创建分类「' + name + '」');
    } else if (action === 'save-category') {
      const name = document.getElementById('category-name').value.trim();
      const parent = document.getElementById('category-parent').value || null;
      const updated = await post('/api/category-update', { id: state.editCategoryId, name, parent });
      Object.assign(category(updated.id), updated); state.modal = null; renderAll(); showToast('分类已更新');
    } else if (action === 'delete-category') {
      if (!state.confirmCategoryDelete) { state.confirmCategoryDelete = true; renderOverlay(); return; }
      const deletedId = state.editCategoryId;
      await post('/api/category-delete', { id: deletedId });
      state.categories = state.categories.filter(cat => cat.id !== deletedId);
      state.repos.forEach(item => { item.categories = item.categories.filter(cat => cat !== deletedId); });
      if (state.activeScope === 'category:' + deletedId) state.activeScope = 'all';
      state.modal = null; ensureSelectedVisible(); renderAll(); showToast('分类已删除');
    } else if (action === 'connect-github') {
      const token = document.getElementById('github-token').value.trim();
      const result = await post('/api/auth', { token });
      state.username = result.username; state.connected = true; state.modal = null;
      renderOverlay(); renderHeader(); showToast('已连接 GitHub：' + result.username);
    } else if (action === 'copy-link') {
      if (state.selectedId) { await navigator.clipboard.writeText('https://github.com/' + state.selectedId); showToast('GitHub 链接已复制'); }
    } else if (action === 'close-detail') {
      document.getElementById('app-shell').classList.remove('detail-open');
    } else if (action === 'mobile-nav') {
      document.getElementById('app-shell').classList.toggle('show-nav');
    } else if (action === 'retry-readme') {
      state.readmes.delete(state.selectedId); loadReadme(state.selectedId, true);
    }
  } catch (error) { showToast(error.message || '操作失败'); }
});

let searchTimer;
document.addEventListener('input', event => {
  if (event.target.id === 'global-search') {
    state.query = event.target.value; state.visibleLimit = 80; state.readmeHits = new Set();
    ensureSelectedVisible(); renderBrowser(); renderDetail();
    clearTimeout(searchTimer);
    const query = state.query.trim();
    if (query) searchTimer = setTimeout(async () => {
      try {
        const result = await api('/api/search-readme?q=' + encodeURIComponent(query));
        if (state.query.trim() !== query) return;
        state.readmeHits = new Set(result.ids); ensureSelectedVisible(); renderBrowser(); renderDetail();
      } catch (_) { /* Metadata search remains available. */ }
    }, 350);
  } else if (event.target.id === 'repo-note') {
    const item = selectedRepo(); if (!item) return;
    item.notes = event.target.value;
    const repoId = item.id, value = item.notes;
    const status = document.getElementById('note-status'); if (status) status.textContent = '保存中…';
    clearTimeout(state.noteTimer);
    state.noteTimer = setTimeout(async () => {
      try { await post('/api/notes', { repo_id: repoId, note: value });
        const indicator = document.getElementById('note-status'); if (indicator && state.selectedId === repoId) indicator.textContent = '已保存';
      } catch (error) { showToast(error.message); }
    }, 500);
  }
});
document.addEventListener('change', async event => {
  try {
    if (event.target.id === 'sort-select') {
      state.sort = event.target.value;
      renderBrowser();
      document.getElementById('browser').querySelector('.browser-list').scrollTop = 0;
    }
    else if (event.target.id === 'detail-category-picker') {
      if (event.target.value && state.selectedId) await setCategories([state.selectedId], [event.target.value], 'add');
      state.showCategoryPicker = false; renderDetail();
    } else if (event.target.id === 'bulk-category') {
      if (event.target.value) { await setCategories([...state.selectedIds], [event.target.value], 'add'); state.selectedIds.clear(); renderBrowser(); showToast('已批量加入分类'); }
    }
  } catch (error) { showToast(error.message); }
});
document.addEventListener('keydown', async event => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault(); document.getElementById('global-search')?.focus();
  } else if (event.key === '/' && !['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)) {
    event.preventDefault(); document.getElementById('global-search')?.focus();
  } else if (event.key === 'Escape') {
    if (state.modal) { state.modal = null; renderOverlay(); }
    else document.getElementById('app-shell').classList.remove('detail-open','show-nav');
  } else if (event.key === 'Enter' && event.target.id === 'new-tag-input') {
    const value = event.target.value.trim(); const item = selectedRepo();
    if (value && item && !item.tags.includes(value)) {
      try { await setTags(item, [...item.tags, value]); state.showTagInput = false; renderDetail(); showToast('已添加标签「' + value + '」'); }
      catch (error) { showToast(error.message); }
    }
  } else if (event.key === 'Enter' && event.target.id === 'category-name') {
    event.preventDefault(); document.querySelector(state.modal === 'edit-category' ? '[data-action="save-category"]' : '[data-action="create-category"]')?.click();
  }
});
document.addEventListener('dragstart', event => {
  const card = event.target.closest('.repo-card'); if (!card) return;
  const id = card.dataset.repoId;
  event.dataTransfer.setData('text/plain', JSON.stringify(state.selectedIds.has(id) ? [...state.selectedIds] : [id]));
  event.dataTransfer.effectAllowed = 'copy'; card.classList.add('dragging');
});
document.addEventListener('dragend', () => document.querySelectorAll('.dragging,.drop-target').forEach(el => el.classList.remove('dragging','drop-target')));
document.addEventListener('dragover', event => {
  const row = event.target.closest('.category-row'); if (!row) return;
  event.preventDefault(); event.dataTransfer.dropEffect = 'copy'; row.classList.add('drop-target');
});
document.addEventListener('dragleave', event => {
  const row = event.target.closest('.category-row'); if (row && !row.contains(event.relatedTarget)) row.classList.remove('drop-target');
});
document.addEventListener('drop', async event => {
  const row = event.target.closest('.category-row'); if (!row) return;
  event.preventDefault(); row.classList.remove('drop-target');
  try {
    const ids = JSON.parse(event.dataTransfer.getData('text/plain'));
    if (!Array.isArray(ids) || !ids.length) return;
    await setCategories(ids, [row.dataset.categoryId], 'add');
    state.selectedIds.clear(); renderBrowser(); showToast(`已将 ${ids.length} 个项目加入「${category(row.dataset.categoryId)?.name || '分类'}」`);
  } catch (error) { showToast(error.message || '拖放失败'); }
});

loadState().catch(error => showToast('资料库加载失败：' + error.message));
setInterval(pollStatus, 3000);

const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
  tg.setHeaderColor?.('#080a12');
  tg.setBackgroundColor?.('#080a12');
}

<<<<<<< HEAD
const state = { me: null, results: [], favorites: [], history: [], admin: null };
=======
const state = { me: null, results: [], favorites: [], history: [] };
>>>>>>> 62099b501c3b233b74dc679cd52b2d63cf3c34bd
const $ = (id) => document.getElementById(id);
const initData = tg?.initData || '';

function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  headers.set('X-Telegram-Init-Data', initData);
  if (options.body) headers.set('Content-Type', 'application/json');
  return fetch(path, { ...options, headers }).then(async (response) => {
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || 'Server xatosi');
    return payload;
  });
}

function toast(message) {
  const node = $('toast');
  node.textContent = message;
  node.classList.add('show');
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => node.classList.remove('show'), 2200);
}

function formatDuration(ms) {
  if (!ms) return '';
  const total = Math.floor(ms / 1000);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
}

function escapeHtml(value = '') {
  const div = document.createElement('div');
  div.textContent = value;
  return div.innerHTML;
}

function trackRow(track, favoriteMode = false) {
  const cover = track.image_url
    ? `<img class="track-cover" src="${escapeHtml(track.image_url)}" alt="Album rasmi">`
    : `<div class="track-cover">♫</div>`;
  const openUrl = track.youtube_url || track.spotify_url;
  return `<article class="track-item">
    ${cover}
    <div class="track-copy">
      <strong>${escapeHtml(track.title || 'Noma’lum')}</strong>
      <span>${escapeHtml(track.artist || 'Noma’lum ijrochi')}${track.duration_ms ? ` · ${formatDuration(track.duration_ms)}` : ''}</span>
    </div>
    <div class="track-actions">
      ${openUrl ? `<a href="${escapeHtml(openUrl)}" target="_blank" rel="noopener" aria-label="Ochish">▶</a>` : ''}
      <button class="favorite-action" data-track="${encodeURIComponent(JSON.stringify(track))}" aria-label="Sevimli">${favoriteMode ? '♥' : '♡'}</button>
    </div>
  </article>`;
}

function renderTracks(target, tracks, empty, favoriteMode = false) {
  const node = $(target);
  if (!tracks.length) {
    node.className = 'track-list empty-state';
    node.textContent = empty;
    return;
  }
  node.className = 'track-list';
  node.innerHTML = tracks.map((track) => trackRow(track, favoriteMode)).join('');
}

function setTab(tab) {
<<<<<<< HEAD
  if (tab === 'admin' && !state.me?.is_admin) return;
=======
>>>>>>> 62099b501c3b233b74dc679cd52b2d63cf3c34bd
  document.querySelectorAll('.view').forEach((view) => view.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach((button) => button.classList.toggle('active', button.dataset.tab === tab));
  const view = $(`${tab}View`);
  if (view) view.classList.add('active');
}

<<<<<<< HEAD
function adminUserRow(user) {
  const name = user.full_name || 'Telegram user';
  const username = user.username ? `@${user.username}` : 'username yo‘q';
  const initial = name.slice(0, 1).toUpperCase();
  return `<article class="user-row" data-admin-user="${user.user_id}">
    <div class="user-avatar">${escapeHtml(initial)}</div>
    <div class="user-copy">
      <strong>${escapeHtml(name)}</strong>
      <span>${escapeHtml(username)} · ID ${user.user_id}</span>
      <span>Kirdi: ${escapeHtml((user.joined_at || '').slice(0, 16))} · Oxirgi: ${escapeHtml((user.last_seen || '').slice(0, 16))}</span>
    </div>
    <div class="user-stats"><strong>${user.searches || 0}</strong>qidiruv<br>${user.actions || 0} harakat</div>
  </article>`;
}

function renderAdminUsers(users) {
  const node = $('adminUsersList');
  if (!users.length) {
    node.className = 'user-list empty-state';
    node.textContent = 'Foydalanuvchi topilmadi.';
    return;
  }
  node.className = 'user-list';
  node.innerHTML = users.map(adminUserRow).join('');
}

function renderAdmin(data) {
  state.admin = data;
  const m = data.metrics || {};
  $('adminUsers').textContent = m.users || 0;
  $('adminNewToday').textContent = `Bugun +${m.new_today || 0}`;
  $('adminActiveToday').textContent = m.active_today || 0;
  $('adminActiveWeek').textContent = `7 kun: ${m.active_week || 0}`;
  $('adminSearches').textContent = m.searches || 0;
  $('adminSearchesToday').textContent = `Bugun: ${m.searches_today || 0}`;
  $('adminHistory').textContent = m.history || 0;
  $('adminHistoryToday').textContent = `Bugun: ${m.history_today || 0}`;
  $('adminFavorites').textContent = m.favorites || 0;
  $('adminLibrary').textContent = m.library || 0;
  $('adminUsersMeta').textContent = `${(data.users || []).length} ta ko‘rsatildi`;
  renderAdminUsers(data.users || []);

  const queries = data.top_queries || [];
  const queryNode = $('adminQueries');
  if (queries.length) {
    queryNode.className = 'query-list';
    queryNode.innerHTML = queries.map((item) => `<div class="query-row"><span>${escapeHtml(item.query || '—')}</span><strong>${item.count || 0}</strong></div>`).join('');
  } else {
    queryNode.className = 'query-list empty-state';
    queryNode.textContent = 'Qidiruv statistikasi hali yo‘q.';
  }

  const activity = data.recent_activity || [];
  const activityNode = $('adminActivity');
  if (activity.length) {
    activityNode.className = 'activity-list';
    activityNode.innerHTML = activity.map((item) => `<div class="activity-row"><span><b>${escapeHtml(item.action || 'action')}</b> · ${escapeHtml(item.query || '—')} · ID ${item.user_id}</span><small>${escapeHtml((item.created_at || '').slice(0,16))}</small></div>`).join('');
  } else {
    activityNode.className = 'activity-list empty-state';
    activityNode.textContent = 'Faoliyat hali yo‘q.';
  }
}

async function loadAdmin() {
  if (!state.me?.is_admin) return;
  $('adminUsersList').textContent = 'Yangilanmoqda…';
  try {
    const data = await api('/api/admin/dashboard');
    renderAdmin(data);
  } catch (error) {
    toast(error.message);
    $('adminUsersList').textContent = 'Admin ma’lumotlarini yuklab bo‘lmadi.';
  }
}

=======
>>>>>>> 62099b501c3b233b74dc679cd52b2d63cf3c34bd
async function loadMe() {
  if (!initData) {
    $('connectionLabel').textContent = 'Mini App’ni Telegram ichida oching';
    $('recentList').textContent = 'Bu sahifani botdagi Mini App tugmasidan oching.';
    return;
  }
  try {
    const data = await api('/api/me');
    state.me = data;
    state.favorites = data.favorites || [];
    state.history = data.history || [];
<<<<<<< HEAD
    $('adminNav').classList.toggle('hidden', !data.is_admin);
    document.querySelector('.bottom-nav').style.gridTemplateColumns = data.is_admin ? 'repeat(6, 1fr)' : 'repeat(5, 1fr)';
=======
>>>>>>> 62099b501c3b233b74dc679cd52b2d63cf3c34bd
    const user = data.user || {};
    const profile = data.profile || {};
    $('connectionLabel').textContent = `Salom, ${user.first_name || 'do‘stim'}`;
    $('searchCount').textContent = profile.searches || 0;
    $('favoriteCount').textContent = profile.favorites || 0;
    $('libraryCount').textContent = profile.library || 0;
    $('profileName').textContent = [user.first_name, user.last_name].filter(Boolean).join(' ') || 'Telegram user';
    $('profileUsername').textContent = user.username ? `@${user.username}` : 'username yo‘q';
    $('profileId').textContent = user.id || '—';
    $('profileSearches').textContent = profile.searches || 0;
    $('profileFavorites').textContent = profile.favorites || 0;
    $('profileAvatar').textContent = (user.first_name || 'M').slice(0, 1).toUpperCase();
    $('favoriteMeta').textContent = `${state.favorites.length} ta`;
    $('historyMeta').textContent = `${state.history.length} ta`;
    renderTracks('favoritesList', state.favorites, 'Sevimlilar hozircha bo‘sh.', true);
    const historyTracks = state.history.map((item) => item.track).filter(Boolean);
    renderTracks('historyList', historyTracks, 'Tarix hozircha bo‘sh.');
    renderTracks('recentList', historyTracks.slice(0, 4), 'Tarix hozircha bo‘sh.');
<<<<<<< HEAD
    if (data.is_admin) loadAdmin();
=======
>>>>>>> 62099b501c3b233b74dc679cd52b2d63cf3c34bd
  } catch (error) {
    $('connectionLabel').textContent = 'Ulanishda xato';
    toast(error.message);
  }
}

async function runSearch(query) {
  query = query.trim();
  if (query.length < 2) return toast('Kamida 2 ta belgi yozing');
  setTab('search');
  $('searchHint').textContent = 'Qidirilmoqda…';
  $('resultList').className = 'track-list empty-state';
  $('resultList').textContent = 'Natijalar tayyorlanmoqda…';
  try {
    const data = await api(`/api/search?q=${encodeURIComponent(query)}`);
    state.results = data.tracks || [];
    $('resultMeta').textContent = `${state.results.length} ta natija`;
    $('searchHint').textContent = state.results.length ? 'Eng mos natijalar tayyor.' : 'Hech narsa topilmadi.';
    renderTracks('resultList', state.results, 'Hech narsa topilmadi.');
    loadMe();
  } catch (error) {
    $('searchHint').textContent = error.message;
    renderTracks('resultList', [], 'Qidiruvda xato yuz berdi.');
  }
}

$('searchButton').addEventListener('click', () => runSearch($('searchInput').value));
$('searchInput').addEventListener('keydown', (event) => {
  if (event.key === 'Enter') runSearch(event.currentTarget.value);
});
$('closeButton').addEventListener('click', () => tg?.close());

document.addEventListener('click', async (event) => {
  const tabButton = event.target.closest('[data-tab]');
<<<<<<< HEAD
  if (tabButton) {
    setTab(tabButton.dataset.tab);
    if (tabButton.dataset.tab === 'admin') loadAdmin();
  }
=======
  if (tabButton) setTab(tabButton.dataset.tab);
>>>>>>> 62099b501c3b233b74dc679cd52b2d63cf3c34bd

  const chip = event.target.closest('[data-query]');
  if (chip) {
    $('searchInput').value = chip.dataset.query;
    runSearch(chip.dataset.query);
  }

  const favorite = event.target.closest('.favorite-action');
  if (favorite) {
    try {
      const track = JSON.parse(decodeURIComponent(favorite.dataset.track));
      const result = await api('/api/favorite', { method: 'POST', body: JSON.stringify(track) });
      toast(result.added ? 'Sevimlilarga qo‘shildi ♥' : 'Sevimlilardan olib tashlandi');
      tg?.HapticFeedback?.notificationOccurred?.('success');
      await loadMe();
    } catch (error) {
      toast(error.message);
    }
  }
});

<<<<<<< HEAD

$('adminRefresh')?.addEventListener('click', loadAdmin);
$('adminUserFilter')?.addEventListener('input', (event) => {
  const query = event.currentTarget.value.trim().toLowerCase();
  const users = state.admin?.users || [];
  const filtered = !query ? users : users.filter((user) => {
    return String(user.user_id).includes(query)
      || (user.full_name || '').toLowerCase().includes(query)
      || (user.username || '').toLowerCase().includes(query);
  });
  $('adminUsersMeta').textContent = `${filtered.length} ta ko‘rsatildi`;
  renderAdminUsers(filtered);
});

=======
>>>>>>> 62099b501c3b233b74dc679cd52b2d63cf3c34bd
loadMe();

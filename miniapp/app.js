const tg = window.Telegram?.WebApp;
if (tg) {
  tg.ready();
  tg.expand();
  tg.setHeaderColor?.('#080a12');
  tg.setBackgroundColor?.('#080a12');
}

const state = { me: null, results: [], favorites: [], history: [] };
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
  document.querySelectorAll('.view').forEach((view) => view.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach((button) => button.classList.toggle('active', button.dataset.tab === tab));
  const view = $(`${tab}View`);
  if (view) view.classList.add('active');
}

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
  if (tabButton) setTab(tabButton.dataset.tab);

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

loadMe();

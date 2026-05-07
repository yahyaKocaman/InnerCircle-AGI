/* ═══════════════════════════════════════════════
   InnerCircle AGI — Frontend Application Logic
   DeepSeek-R1 Chain-of-Thought UX + SSE streaming
   ═══════════════════════════════════════════════ */

const API = '';
let token = localStorage.getItem('ic_token');
let currentUser = null;
let currentAgentRole = null;
let currentSessionId = null;
let agentMetadata = [];
let profileExists = false;
let isStreaming = false;

// DeepSeek-R1 streaming state
const THINK_START = '__THINKING_START__';
const THINK_END   = '__THINKING_END__';

/* ══════════════════════════════════════════════
   AUTH
   ══════════════════════════════════════════════ */
function switchTab(tab) {
  document.getElementById('login-form').classList.toggle('hidden', tab !== 'login');
  document.getElementById('register-form').classList.toggle('hidden', tab !== 'register');
  document.getElementById('tab-login').classList.toggle('active', tab === 'login');
  document.getElementById('tab-register').classList.toggle('active', tab === 'register');
}

async function handleLogin(e) {
  e.preventDefault();
  const btn = document.getElementById('login-btn');
  const errEl = document.getElementById('login-error');
  toggleBtn(btn, true);
  errEl.classList.add('hidden');
  try {
    const res = await apiFetch('/auth/login', 'POST', {
      username: document.getElementById('login-username').value,
      password: document.getElementById('login-password').value,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Giriş başarısız');
    setAuthData(data);
    initApp();
  } catch (err) {
    errEl.textContent = err.message;
    errEl.classList.remove('hidden');
  } finally {
    toggleBtn(btn, false);
  }
}

async function handleRegister(e) {
  e.preventDefault();
  const btn = document.getElementById('reg-btn');
  const errEl = document.getElementById('reg-error');
  toggleBtn(btn, true);
  errEl.classList.add('hidden');
  try {
    const res = await apiFetch('/auth/register', 'POST', {
      username: document.getElementById('reg-username').value,
      email: document.getElementById('reg-email').value,
      full_name: document.getElementById('reg-fullname').value,
      password: document.getElementById('reg-password').value,
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Kayıt başarısız');
    const loginRes = await apiFetch('/auth/login', 'POST', {
      username: document.getElementById('reg-username').value,
      password: document.getElementById('reg-password').value,
    });
    const loginData = await loginRes.json();
    if (!loginRes.ok) throw new Error('Kayıt başarılı ancak giriş yapılamadı');
    setAuthData(loginData);
    initApp();
  } catch (err) {
    errEl.textContent = err.message;
    errEl.classList.remove('hidden');
  } finally {
    toggleBtn(btn, false);
  }
}

function setAuthData(data) {
  token = data.access_token;
  currentUser = data.user;
  localStorage.setItem('ic_token', token);
}

function logout() {
  token = null; currentUser = null;
  localStorage.removeItem('ic_token');
  document.getElementById('auth-screen').classList.remove('hidden');
  document.getElementById('app-screen').classList.add('hidden');
}

/* ══════════════════════════════════════════════
   APP INIT
   ══════════════════════════════════════════════ */
async function initApp() {
  document.getElementById('auth-screen').classList.add('hidden');
  document.getElementById('app-screen').classList.remove('hidden');

  const initials = (currentUser.full_name || currentUser.username || '?').charAt(0).toUpperCase();
  document.getElementById('sidebar-avatar').textContent = initials;
  document.getElementById('sidebar-username').textContent = currentUser.username;

  await loadAgents();
  await loadSessions();
  await loadInsights();
  await loadProfile();
  
  startDashboardPolling();
}

/* ══════════════════════════════════════════════
   VIEW SWITCHING (Dashboard vs Chat)
   ══════════════════════════════════════════════ */
function switchView(viewName) {
  const dashView = document.getElementById('dashboard-view');
  const chatView = document.getElementById('chat-view');
  const navItems = document.querySelectorAll('.dash-nav .nav-item');
  const agentNav = document.getElementById('agent-nav');
  
  if(!dashView || !chatView) return;

  navItems.forEach(item => item.classList.remove('active'));

  if (viewName === 'dashboard') {
    dashView.classList.remove('view-hidden');
    dashView.classList.add('view-active');
    chatView.classList.remove('view-active');
    chatView.classList.add('view-hidden');
    navItems[0].classList.add('active');
    if(agentNav) agentNav.classList.add('hidden');
  } else if (viewName === 'chat') {
    dashView.classList.remove('view-active');
    dashView.classList.add('view-hidden');
    chatView.classList.remove('view-hidden');
    chatView.classList.add('view-active');
    navItems[1].classList.add('active');
    if(agentNav) agentNav.classList.remove('hidden');
  }
}

function openComingSoon(featureName) {
  showToast(`${featureName} modülü henüz yapım aşamasında.`, 'info');
}

function openAgentChat(agentType) {
  switchView('chat');
  
  // Map dashboard concepts to backend roles
  const roleMap = {
    'research': 'career',
    'code': 'performance',
    'learning': 'synthesizer',
    'security': 'investment'
  };
  
  const mappedRole = roleMap[agentType] || 'synthesizer';
  selectAgent(mappedRole);
}

/* ══════════════════════════════════════════════
   AGENTS
   ══════════════════════════════════════════════ */
async function loadAgents() {
  try {
    const res = await apiFetch('/council/agents');
    agentMetadata = await res.json();
  } catch (err) {
    console.error('Failed to load agents:', err);
    agentMetadata = [
      { role: 'life_coach',   name: 'Yaşam Koçu',            icon: '🧭', color: '#8B5CF6', title: 'Yaşam Koçu',          description: 'Değer tabanlı hayat tasarımı' },
      { role: 'investment',   name: 'Yatırım & Finans',       icon: '📈', color: '#F59E0B', title: 'Finans Stratejisti',   description: 'Portföy ve makroekonomik analiz' },
      { role: 'performance',  name: 'Performans Koçu',        icon: '⚡', color: '#10B981', title: 'Performans Koçu',     description: 'Spor bilimi ve optimizasyon' },
      { role: 'career',       name: 'Kariyer Stratejisti',    icon: '🚀', color: '#3B82F6', title: 'Kariyer Uzmanı',      description: 'Kariyer kapitali ve marka' },
      { role: 'health',       name: 'Sağlık & Zihin Mimarı', icon: '🧬', color: '#EF4444', title: 'Sağlık Mimarı',       description: 'Longevity ve nörobilim' },
      { role: 'synthesizer',  name: 'Sentezci',               icon: '🔮', color: '#6B7280', title: 'Sentezci',            description: 'Bütünsel konsey sentezi' },
    ];
  }
  renderAgentNav();
  renderAgentQuickGrid();
}

function renderAgentNav() {
  const nav = document.getElementById('agent-nav');
  if (!nav) return;
  
  const defaultAgentIcon = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-top:2px"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle><path d="M23 21v-2a4 4 0 0 0-3-3.87"></path><path d="M16 3.13a4 4 0 0 1 0 7.75"></path></svg>`;
  
  nav.innerHTML = '<div style="padding: 12px 14px 6px; font-size: 10px; font-weight: 600; color: var(--dash-muted); text-transform: uppercase; letter-spacing: 1px;">Konsey Üyeleri</div>' + agentMetadata.map(a => `
    <div class="agent-nav-item ${currentAgentRole === a.role ? 'active' : ''}"
         onclick="selectAgent('${a.role}')" id="nav-${a.role}">
      <span class="agent-nav-icon">${defaultAgentIcon}</span>
      <div class="agent-nav-info">
        <div class="agent-nav-name">${a.name}</div>
        <div class="agent-nav-role">${a.title}</div>
      </div>
      <div class="agent-nav-dot" style="background:${a.color}"></div>
    </div>
  `).join('');

  const autoEl = document.createElement('div');
  autoEl.className = `agent-nav-item ${!currentAgentRole ? 'active' : ''}`;
  autoEl.id = 'nav-auto';
  autoEl.onclick = () => clearAgentFilter();
  autoEl.innerHTML = `
    <span class="agent-nav-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-top:2px"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg></span>
    <div class="agent-nav-info">
      <div class="agent-nav-name">Otomatik Yönlendirme</div>
      <div class="agent-nav-role">Sentezci</div>
    </div>
    <div class="agent-nav-dot" style="background:#6B7280"></div>
  `;
  nav.insertBefore(autoEl, nav.childNodes[1]);
}

function renderAgentQuickGrid() {
  const grid = document.getElementById('agent-quick-grid');
  if (!grid) return;
  grid.innerHTML = agentMetadata.map(a => `
    <div class="agent-quick-card" onclick="selectAgent('${a.role}')"
         style="--agent-color:${a.color}">
      <div class="quick-icon">${a.icon}</div>
      <div class="quick-name">${a.name}</div>
      <div class="quick-desc">${a.description}</div>
    </div>
  `).join('');
}

function selectAgent(role) {
  currentAgentRole = role;
  const agent = agentMetadata.find(a => a.role === role);
  document.querySelectorAll('.agent-nav-item').forEach(el => el.classList.remove('active'));
  const navEl = document.getElementById(`nav-${role}`);
  if (navEl) navEl.classList.add('active');
  const autoEl = document.getElementById('nav-auto');
  if (autoEl) autoEl.classList.remove('active');

  if (agent) {
    document.getElementById('header-agent-icon').textContent = agent.icon;
    document.getElementById('header-agent-name').textContent = agent.name;
    document.getElementById('header-agent-desc').textContent = agent.description;
    document.getElementById('header-agent-icon').style.borderColor = `${agent.color}40`;
    document.getElementById('chat-header').style.setProperty('--agent-accent', agent.color);
    
    // WOW factor: Update global cyber orb color to match agent
    const orb = document.getElementById('global-cyber-orb');
    if (orb) orb.style.background = agent.color;
  }

  const badge = document.getElementById('input-agent-badge');
  badge.classList.add('has-agent');
  document.getElementById('badge-icon').textContent = agent?.icon || '🔮';
  document.getElementById('badge-name').textContent = agent?.name || role;
  document.getElementById('badge-clear').style.display = '';

  newSession();
}

function clearAgentFilter() {
  currentAgentRole = null;
  document.querySelectorAll('.agent-nav-item').forEach(el => el.classList.remove('active'));
  const autoEl = document.getElementById('nav-auto');
  if (autoEl) autoEl.classList.add('active');

  document.getElementById('header-agent-icon').textContent = '🔮';
  document.getElementById('header-agent-name').textContent = 'Konsey';
  document.getElementById('header-agent-desc').textContent = 'Bir konsey üyesi seçin ya da doğrudan yazmaya başlayın';
  document.getElementById('header-agent-icon').style.borderColor = '';
  document.getElementById('chat-header').style.setProperty('--agent-accent', 'transparent');

  // WOW factor: Reset orb to gold for Synthesizer (Auto)
  const orb = document.getElementById('global-cyber-orb');
  if (orb) orb.style.background = '#c9a84c';

  const badge = document.getElementById('input-agent-badge');
  badge.classList.remove('has-agent');
  document.getElementById('badge-icon').textContent = '🔮';
  document.getElementById('badge-name').textContent = 'Otomatik';
  document.getElementById('badge-clear').style.display = 'none';

  newSession();
}

/* ══════════════════════════════════════════════
   SESSIONS
   ══════════════════════════════════════════════ */
async function loadSessions() {
  try {
    const res = await apiFetch('/council/sessions?limit=15');
    const sessions = await res.json();
    renderSessionList(sessions);
  } catch (err) {
    console.error('Sessions load error:', err);
  }
}

function renderSessionList(sessions) {
  const el = document.getElementById('session-list');
  if (!sessions.length) {
    el.innerHTML = '<div class="session-empty">Henüz oturum yok</div>';
    return;
  }
  el.innerHTML = sessions.map(s => {
    const agent = agentMetadata.find(a => a.role === s.agent_role);
    const icon = agent?.icon || '💬';
    const date = new Date(s.started_at).toLocaleDateString('tr-TR', { month: 'short', day: 'numeric' });
    return `
      <div class="session-item ${s.id === currentSessionId ? 'active' : ''}"
           onclick="loadSession(${s.id})" id="session-item-${s.id}">
        <div class="session-title">${icon} ${s.title || 'Oturum'}</div>
        <div class="session-meta">${date} · ${s.message_count} mesaj</div>
      </div>
    `;
  }).join('');
}

async function loadSession(sessionId) {
  try {
    const res = await apiFetch(`/council/sessions/${sessionId}`);
    const data = await res.json();
    currentSessionId = sessionId;

    const sessionRole = data.session.agent_role;
    if (sessionRole) selectAgent(sessionRole);

    const area = document.getElementById('messages-area');
    area.innerHTML = '';
    document.getElementById('welcome-state')?.remove();

    data.messages.forEach(msg => {
      const agent = agentMetadata.find(a => a.role === msg.agent_role);
      appendMessage({
        role: msg.role,
        content: msg.content,
        agentIcon: agent?.icon || '🔮',
        agentName: msg.role === 'assistant' ? (agent?.name || 'Konsey') : currentUser.username,
        agentColor: agent?.color || '#6B7280',
        agentRole: msg.agent_role,
        modelUsed: null,
        time: new Date(msg.created_at),
      });
    });

    area.scrollTop = area.scrollHeight;
    updateSessionItems(sessionId);
    await loadSessions();
  } catch (err) {
    showToast('Oturum yüklenemedi', 'error');
  }
}

function newSession() {
  currentSessionId = null;
  const area = document.getElementById('messages-area');
  area.innerHTML = '';
  const agentRole = currentAgentRole ? agentMetadata.find(a => a.role === currentAgentRole) : null;
  area.innerHTML = `
    <div class="welcome-state" id="welcome-state">
      <div class="welcome-emblem">${agentRole?.icon || '◈'}</div>
      <h2 class="welcome-title">${agentRole ? agentRole.name + ' hazır.' : 'Konseyin sizi bekliyor.'}</h2>
      <p class="welcome-sub">${agentRole ? agentRole.description : 'Sorunuzu yazın, konsey size yönlendirsin.'}</p>
      <div class="agent-quick-grid" id="agent-quick-grid"></div>
    </div>
  `;
  renderAgentQuickGrid();
  document.getElementById('chat-input').focus();
}

function updateSessionItems(activeId) {
  document.querySelectorAll('.session-item').forEach(el => {
    el.classList.toggle('active', el.id === `session-item-${activeId}`);
  });
}

/* ══════════════════════════════════════════════
   CHAT / MESSAGING — with DeepSeek-R1 CoT UX
   ══════════════════════════════════════════════ */
function handleInputKey(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
}

function autoResize(el) {
  el.style.height = 'auto';
  el.style.height = Math.min(el.scrollHeight, 200) + 'px';
}

async function sendMessage() {
  const input = document.getElementById('chat-input');
  const message = input.value.trim();
  if (!message || isStreaming) return;

  const welcomeEl = document.getElementById('welcome-state');
  if (welcomeEl) welcomeEl.remove();

  input.value = '';
  input.style.height = 'auto';

  const userInitial = (currentUser.full_name || currentUser.username || '?').charAt(0).toUpperCase();
  appendMessage({
    role: 'user',
    content: message,
    agentIcon: userInitial,
    agentName: currentUser.username,
    time: new Date(),
  });

  isStreaming = true;
  document.getElementById('btn-send').disabled = true;

  const payload = {
    message,
    agent_role: currentAgentRole || null,
    session_id: currentSessionId || null,
  };

  // Use streaming endpoint for rich DeepSeek-R1 CoT experience
  await sendMessageStream(payload, message);
}

async function sendMessageStream(payload, message) {
  // Create a message container immediately (for streaming into)
  const area = document.getElementById('messages-area');
  const msgId = 'stream-msg-' + Date.now();

  // Placeholder agent (will update after first SSE event)
  const placeholderAgent = currentAgentRole
    ? agentMetadata.find(a => a.role === currentAgentRole)
    : { icon: '🔮', name: 'Konsey', color: '#6B7280', role: null };

  // Create streaming message element
  const msgEl = createStreamingMessage(msgId, placeholderAgent);
  area.appendChild(msgEl);
  scrollToBottom();

  // Thinking panel state
  let inThinking = false;
  let thinkingText = '';
  let answerText = '';
  let sessionId = null;
  let resolvedAgent = null;

  try {
    const res = await fetch(API + '/council/ask/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Konsey yanıt vermedi');
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const raw = line.slice(6).trim();
        if (!raw) continue;

        let evt;
        try { evt = JSON.parse(raw); } catch { continue; }

        // ── Start event ──────────────────────────
        if (evt.event === 'start') {
          sessionId = evt.session_id;
          currentSessionId = sessionId;
          // Update agent display if known at start
          if (evt.agent_role) {
            const ag = agentMetadata.find(a => a.role === evt.agent_role);
            if (ag) updateStreamingMessageAgent(msgEl, ag);
          }
          continue;
        }

        // ── Done event ───────────────────────────
        if (evt.event === 'done') {
          finalizeStreamingMessage(msgEl, answerText, resolvedAgent);
          await loadSessions();
          continue;
        }

        // ── Error event ──────────────────────────
        if (evt.event === 'error') {
          setStreamingError(msgEl, evt.detail || 'Bilinmeyen hata');
          continue;
        }

        // ── Token events ─────────────────────────
        if (evt.token !== undefined) {
          const token_val = evt.token;

          if (token_val === THINK_START) {
            inThinking = true;
            showThinkingPanel(msgEl, true);
            continue;
          }

          if (token_val === THINK_END) {
            inThinking = false;
            finalizeThinkingPanel(msgEl, thinkingText);
            showAnswerSection(msgEl);
            continue;
          }

          if (inThinking) {
            thinkingText += token_val;
            appendThinkingToken(msgEl, token_val);
          } else {
            answerText += token_val;
            appendAnswerToken(msgEl, token_val);
          }
          scrollToBottom();
        }
      }
    }

    // If no done event (non-chunked fallback)
    if (answerText) {
      finalizeStreamingMessage(msgEl, answerText, resolvedAgent);
    }

  } catch (err) {
    console.error('Streaming error:', err);
    setStreamingError(msgEl, err.message);
  } finally {
    isStreaming = false;
    document.getElementById('btn-send').disabled = false;
    scrollToBottom();
  }
}

/* ── Streaming Message DOM Helpers ──────────────── */

function createStreamingMessage(id, agent) {
  const el = document.createElement('div');
  el.className = 'message assistant streaming';
  el.id = id;
  el.innerHTML = `
    <div class="msg-avatar">${agent?.icon || '🔮'}</div>
    <div class="msg-body">
      <div class="msg-header">
        <span class="msg-name">${agent?.name || 'Konsey'}</span>
        <span class="msg-time"></span>
      </div>
      <div class="msg-agent-label" id="${id}-label" style="display:none;
           background:${agent?.color || '#6B7280'}18;
           color:${agent?.color || '#6B7280'};
           border:1px solid ${agent?.color || '#6B7280'}30">
        ${agent?.icon || '🔮'} ${agent?.name || 'Konsey'}
      </div>

      <!-- DeepSeek-R1 Thinking Panel -->
      <div class="msg-thinking" id="${id}-thinking" style="display:none">
        <button class="thinking-toggle" onclick="toggleThinkingPanel('${id}-thinking')"
                aria-expanded="true">
          <span class="thinking-icon">🧠</span>
          <span class="thinking-label">Analiz ediliyor…</span>
          <span class="thinking-chevron">▾</span>
        </button>
        <div class="thinking-content" id="${id}-thinking-content"></div>
      </div>

      <!-- Answer -->
      <div class="msg-bubble" id="${id}-bubble">
        <span class="stream-cursor"></span>
      </div>

      <!-- Model badge (shown after done) -->
      <div class="msg-model-badge" id="${id}-model-badge" style="display:none"></div>
    </div>
  `;
  return el;
}

function updateStreamingMessageAgent(msgEl, agent) {
  const avatar = msgEl.querySelector('.msg-avatar');
  const nameEl = msgEl.querySelector('.msg-name');
  const label  = msgEl.querySelector('.msg-agent-label');
  if (avatar) avatar.textContent = agent.icon;
  if (nameEl) nameEl.textContent = agent.name;
  if (label) {
    label.style.background = `${agent.color}18`;
    label.style.color = agent.color;
    label.style.borderColor = `${agent.color}30`;
    label.innerHTML = `${agent.icon} ${agent.name}`;
    label.style.display = 'inline-flex';
  }
}

function showThinkingPanel(msgEl, open) {
  const panel = msgEl.querySelector('[id$="-thinking"]');
  if (panel) panel.style.display = 'block';
}

function appendThinkingToken(msgEl, token_val) {
  const content = msgEl.querySelector('[id$="-thinking-content"]');
  if (!content) return;
  content.textContent += token_val;
}

function finalizeThinkingPanel(msgEl, thinkingText) {
  const toggle = msgEl.querySelector('.thinking-toggle');
  const label  = msgEl.querySelector('.thinking-label');
  const chevron = msgEl.querySelector('.thinking-chevron');
  if (label) label.textContent = `Analiz tamamlandı (${thinkingText.split(' ').length} kelime)`;
  if (toggle) toggle.setAttribute('aria-expanded', 'true');
  // Auto-collapse after a moment
  setTimeout(() => {
    const panel = msgEl.querySelector('[id$="-thinking"]');
    if (panel) collapseThinkingPanel(panel);
  }, 2000);
}

function collapseThinkingPanel(panelEl) {
  const content = panelEl.querySelector('[id$="-thinking-content"]');
  const toggle = panelEl.querySelector('.thinking-toggle');
  const chevron = panelEl.querySelector('.thinking-chevron');
  if (content) content.style.display = 'none';
  if (toggle) toggle.setAttribute('aria-expanded', 'false');
  if (chevron) chevron.textContent = '▸';
}

function toggleThinkingPanel(panelId) {
  const panelEl = document.getElementById(panelId);
  if (!panelEl) return;
  const content = document.getElementById(panelId + '-content');
  const toggle = panelEl.querySelector('.thinking-toggle');
  const chevron = panelEl.querySelector('.thinking-chevron');
  const isOpen = toggle && toggle.getAttribute('aria-expanded') === 'true';
  if (content) content.style.display = isOpen ? 'none' : 'block';
  if (toggle) toggle.setAttribute('aria-expanded', isOpen ? 'false' : 'true');
  if (chevron) chevron.textContent = isOpen ? '▸' : '▾';
}

function showAnswerSection(msgEl) {
  const bubble = msgEl.querySelector('.msg-bubble');
  if (bubble) bubble.innerHTML = '<span class="stream-cursor"></span>';
}

function appendAnswerToken(msgEl, token_val) {
  const bubble = msgEl.querySelector('.msg-bubble');
  if (!bubble) return;
  // Remove cursor, append text, re-add cursor
  const cursor = bubble.querySelector('.stream-cursor');
  if (cursor) cursor.remove();
  bubble.innerHTML += escapeHtml(token_val);
  bubble.innerHTML += '<span class="stream-cursor"></span>';
}

function finalizeStreamingMessage(msgEl, answerText, agent) {
  msgEl.classList.remove('streaming');
  const bubble = msgEl.querySelector('.msg-bubble');
  if (bubble) {
    bubble.innerHTML = escapeHtml(answerText);
  }
  const timeEl = msgEl.querySelector('.msg-time');
  if (timeEl) {
    timeEl.textContent = new Date().toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
  }
  // Show model badge
  const modelBadge = msgEl.querySelector('[id$="-model-badge"]');
  if (modelBadge) {
    modelBadge.textContent = '⚡ gpt-4o-mini · openai';
    modelBadge.style.display = 'block';
  }
}

function setStreamingError(msgEl, errorMsg) {
  msgEl.classList.remove('streaming');
  const bubble = msgEl.querySelector('.msg-bubble');
  if (bubble) bubble.innerHTML = `<span style="color:#EF4444">⚠️ ${escapeHtml(errorMsg)}</span>`;
}

/* ── Regular (non-streaming) message append ── */
function appendMessage({ role, content, agentIcon, agentName, agentColor, agentRole, modelUsed, time }) {
  const area = document.getElementById('messages-area');
  const timeStr = time ? time.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' }) : '';

  const el = document.createElement('div');
  el.className = `message ${role}`;

  const agentLabelHtml = (role === 'assistant' && agentRole) ? `
    <div class="msg-agent-label" style="background:${agentColor}18;color:${agentColor};border:1px solid ${agentColor}30">
      ${agentIcon} ${agentName}
    </div>
  ` : '';

  const modelBadgeHtml = (role === 'assistant' && modelUsed) ? `
    <div class="msg-model-badge">⚡ ${escapeHtml(modelUsed)}</div>
  ` : '';

  el.innerHTML = `
    <div class="msg-avatar">${agentIcon}</div>
    <div class="msg-body">
      <div class="msg-header">
        <span class="msg-name">${escapeHtml(agentName)}</span>
        <span class="msg-time">${timeStr}</span>
      </div>
      ${agentLabelHtml}
      <div class="msg-bubble">${escapeHtml(content)}</div>
      ${modelBadgeHtml}
    </div>
  `;
  area.appendChild(el);
}

function scrollToBottom() {
  const area = document.getElementById('messages-area');
  area.scrollTop = area.scrollHeight;
}

/* ══════════════════════════════════════════════
   INSIGHTS
   ══════════════════════════════════════════════ */
async function loadInsights() {
  try {
    const [insightsRes, countRes] = await Promise.all([
      apiFetch('/insights/?unread_only=false&limit=20'),
      apiFetch('/insights/count'),
    ]);
    const insights = await insightsRes.json();
    const countData = await countRes.json();
    renderInsights(insights);
    updateInsightBadge(countData.unread_count);
  } catch (err) {
    console.error('Insights load error:', err);
  }
}

function renderInsights(insights) {
  const feed = document.getElementById('insight-feed');
  if (!insights.length) {
    feed.innerHTML = `
      <div class="insight-empty">
        <span>🔮</span>
        <p>Konsey içgörüleri burada görünür.<br>Celery worker'ın çalışmasını bekleyin.</p>
      </div>`;
    return;
  }
  feed.innerHTML = insights.map(ins => {
    const agent = agentMetadata.find(a => a.role === ins.agent_role);
    return `
      <div class="insight-card ${ins.is_read ? '' : 'unread'}"
           onclick="markInsightRead(${ins.id}, this)" id="insight-${ins.id}">
        <div class="insight-card-header">
          <span class="insight-agent-label">${agent?.icon || '🔮'} ${agent?.name || ins.agent_role}</span>
          <button class="insight-dismiss" onclick="dismissInsight(event, ${ins.id})">✕</button>
        </div>
        <div class="insight-title">${escapeHtml(ins.title)}</div>
        <div class="insight-content">${escapeHtml(ins.content)}</div>
      </div>`;
  }).join('');
}

async function markInsightRead(id, cardEl) {
  if (!cardEl.classList.contains('unread')) return;
  try {
    await apiFetch(`/insights/${id}/read`, 'PATCH');
    cardEl.classList.remove('unread');
    const count = document.querySelectorAll('.insight-card.unread').length;
    updateInsightBadge(count);
  } catch (err) { console.error(err); }
}

async function dismissInsight(e, id) {
  e.stopPropagation();
  try {
    await apiFetch(`/insights/${id}`, 'DELETE');
    const el = document.getElementById(`insight-${id}`);
    if (el) { el.style.opacity = '0'; el.style.transition = 'opacity 0.3s'; setTimeout(() => el.remove(), 300); }
    showToast('İçgörü kaldırıldı', 'success');
    await loadInsights();
  } catch (err) { showToast('Silinemedi', 'error'); }
}

function updateInsightBadge(count) {
  const badge = document.getElementById('insight-count-badge');
  badge.textContent = count;
  badge.classList.toggle('zero', count === 0);
}

/* ══════════════════════════════════════════════
   PROFILE
   ══════════════════════════════════════════════ */
async function loadProfile() {
  try {
    const res = await apiFetch('/profile/');
    if (res.ok) {
      const profile = await res.json();
      profileExists = true;
      renderProfileSummary(profile);
      populateProfileForm(profile);
    } else { profileExists = false; }
  } catch (err) { console.error('Profile load error:', err); }
}

function renderProfileSummary(profile) {
  const el = document.getElementById('profile-summary');
  const items = [];
  if (profile.age)          items.push({ key: 'Yaş', val: profile.age });
  if (profile.occupation)   items.push({ key: 'Meslek', val: profile.occupation });
  if (profile.career_stage) items.push({ key: 'Kariyer', val: profile.career_stage });
  if (profile.risk_tolerance) items.push({ key: 'Risk', val: profile.risk_tolerance });

  el.innerHTML = items.map(i => `
    <div class="profile-item">
      <span class="profile-key">${i.key}</span>
      <span class="profile-val">${i.val}</span>
    </div>
  `).join('') + `
    <button class="btn-outline-sm" onclick="openProfileModal()" style="margin-top:6px">Profili Düzenle</button>
  `;
}

function populateProfileForm(profile) {
  const fields = {
    'pf-age': profile.age || '',
    'pf-occupation': profile.occupation || '',
    'pf-career-stage': profile.career_stage || '',
    'pf-risk': profile.risk_tolerance || '',
    'pf-goals': (profile.goals || []).join(', '),
    'pf-interests': (profile.interests || []).join(', '),
    'pf-health': profile.health_focus || '',
    'pf-financial': profile.financial_context || '',
  };
  Object.entries(fields).forEach(([id, val]) => {
    const el = document.getElementById(id);
    if (el) el.value = val;
  });
}

function openProfileModal()  { document.getElementById('profile-modal').classList.remove('hidden'); }
function closeProfileModal() { document.getElementById('profile-modal').classList.add('hidden');    }
function closeProfileOutside(e) { if (e.target === document.getElementById('profile-modal')) closeProfileModal(); }

async function handleSaveProfile(e) {
  e.preventDefault();
  const btn = document.getElementById('save-profile-btn');
  toggleBtn(btn, true);

  const toList = v => v ? v.split(',').map(s => s.trim()).filter(Boolean) : [];
  const payload = {
    age: parseInt(document.getElementById('pf-age').value) || null,
    occupation: document.getElementById('pf-occupation').value || null,
    career_stage: document.getElementById('pf-career-stage').value || null,
    risk_tolerance: document.getElementById('pf-risk').value || null,
    goals: toList(document.getElementById('pf-goals').value),
    interests: toList(document.getElementById('pf-interests').value),
    health_focus: document.getElementById('pf-health').value || null,
    financial_context: document.getElementById('pf-financial').value || null,
  };

  try {
    const method = profileExists ? 'PUT' : 'POST';
    const res = await apiFetch('/profile/', method, payload);
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'Kayıt başarısız');
    profileExists = true;
    renderProfileSummary(data);
    closeProfileModal();
    showToast('Profil kaydedildi ✓', 'success');
  } catch (err) {
    showToast(err.message, 'error');
  } finally {
    toggleBtn(btn, false);
  }
}

/* ══════════════════════════════════════════════
   UTILITIES
   ══════════════════════════════════════════════ */
async function apiFetch(path, method = 'GET', body = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (token) opts.headers['Authorization'] = `Bearer ${token}`;
  if (body)  opts.body = JSON.stringify(body);
  return fetch(API + path, opts);
}

function toggleBtn(btn, loading) {
  const text    = btn.querySelector('.btn-text');
  const spinner = btn.querySelector('.btn-spinner');
  btn.disabled = loading;
  if (text)    text.classList.toggle('hidden', loading);
  if (spinner) spinner.classList.toggle('hidden', !loading);
}

function escapeHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/\n/g, '<br>');
}

function showToast(msg, type = 'info') {
  const container = document.getElementById('toast-container');
  const el = document.createElement('div');
  const icons = { success: '✓', error: '✕', info: 'ℹ' };
  el.className = `toast ${type}`;
  el.innerHTML = `<span>${icons[type] || ''}</span> ${escapeHtml(msg)}`;
  container.appendChild(el);
  setTimeout(() => {
    el.style.opacity = '0';
    el.style.transition = 'opacity 0.3s';
    setTimeout(() => el.remove(), 300);
  }, 3500);
}

/* ══════════════════════════════════════════════
   BOOTSTRAP
   ══════════════════════════════════════════════ */
document.addEventListener('DOMContentLoaded', async () => {
  if (token) {
    try {
      const res = await apiFetch('/auth/me');
      if (res.ok) {
        currentUser = await res.json();
        initApp();
      } else {
        token = null; localStorage.removeItem('ic_token');
      }
    } catch {
      token = null; localStorage.removeItem('ic_token');
    }
  }

  document.getElementById('badge-clear').style.display = 'none';

  // Reload insights every 60s
  setInterval(async () => {
    if (token) await loadInsights();
  }, 60000);
});

/* ══════════════════════════════════════════════
   DASHBOARD METRICS (Real-time updates)
   ══════════════════════════════════════════════ */
let dashboardPollInterval = null;

function startDashboardPolling() {
  if(dashboardPollInterval) clearInterval(dashboardPollInterval);
  fetchDashboardMetrics(); // fetch immediately
  dashboardPollInterval = setInterval(fetchDashboardMetrics, 10000); // every 10 seconds
}

async function fetchDashboardMetrics() {
  if(!token) return;
  try {
    const res = await apiFetch('/dashboard/metrics');
    if(!res.ok) return;
    const data = await res.json();
    
    // 1. System Status
    if(data.system) {
      const cpuVal = document.getElementById('sys-cpu-val');
      if (cpuVal) cpuVal.textContent = `${data.system.cpu.toFixed(1)}%`;
      const cpuFill = document.getElementById('sys-cpu-fill');
      if (cpuFill) cpuFill.style.width = `${data.system.cpu}%`;
      
      const memVal = document.getElementById('sys-mem-val');
      if (memVal) memVal.textContent = `${data.system.mem.toFixed(1)}%`;
      const memFill = document.getElementById('sys-mem-fill');
      if (memFill) memFill.style.width = `${data.system.mem}%`;
      
      const netVal = document.getElementById('sys-net-val');
      if (netVal) netVal.textContent = `${data.system.net}%`;
      const netFill = document.getElementById('sys-net-fill');
      if (netFill) netFill.style.width = `${data.system.net}%`;
    }
    
    // 2. Active Agents
    if(data.active_agents && data.active_agents.length > 0) {
      const activeAgentsList = document.getElementById('active-agents-list');
      if(activeAgentsList) {
        activeAgentsList.innerHTML = data.active_agents.map(a => {
          const color = a.status === 'Running' ? '#3b82f6' : (a.status === 'Training' ? '#ec4899' : '#f59e0b');
          return `
            <div class="aa-item" onclick="openAgentChat('${a.role}')">
              <div class="aa-icon" style="background: ${color}20; color: ${color};"><svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg></div>
              <div class="aa-info"><h4>${a.name}</h4><span>${a.status}</span></div>
              <div class="aa-graph"><svg viewBox="0 0 50 20" stroke="${color}" fill="none" stroke-width="2"><polyline points="0,10 10,15 20,5 30,12 40,8 50,10"></polyline></svg></div>
            </div>
          `;
        }).join('');
      }
    }
    
    // 3. Recent Tasks
    if(data.recent_tasks) {
      const recentTasksList = document.getElementById('recent-tasks-list');
      if(recentTasksList) {
        recentTasksList.innerHTML = data.recent_tasks.length === 0 ? '<div style="color:var(--dash-muted);font-size:0.85rem">Henüz görev yok.</div>' : data.recent_tasks.map(t => {
          const statusClass = t.status === 'Completed' ? 'status-done' : 'status-progress';
          return `
            <div class="task-item">
              <div class="task-info">${t.title}</div>
              <div class="task-status ${statusClass}">${t.status}</div>
              <div class="task-val">${t.progress}%</div>
            </div>
            <div class="task-bar-bg"><div class="task-bar-fill" style="width: ${t.progress}%"></div></div>
          `;
        }).join('');
      }
    }
    
    // 4. Activity Stream
    if(data.activity_stream) {
      const activityStreamList = document.getElementById('activity-stream-list');
      if(activityStreamList) {
        activityStreamList.innerHTML = data.activity_stream.length === 0 ? '<div style="color:var(--dash-muted);font-size:0.85rem">Aktivite bulunamadı.</div>' : data.activity_stream.map(act => {
          return `
            <div class="act-item">
              <div class="act-icon" style="color:var(--dash-neon)"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg></div>
              <div class="act-info">
                <strong>${act.text}</strong>
                <p>${act.subtext}</p>
              </div>
              <div class="act-time">${act.time_ago}</div>
            </div>
          `;
        }).join('');
      }
    }
    
    // 5. Network Status
    if(data.network) {
      const netCount = document.getElementById('network-members-count');
      if(netCount) netCount.textContent = data.network.members_online;
    }
    
  } catch(e) {
    console.error('Failed to fetch dashboard metrics:', e);
  }
}

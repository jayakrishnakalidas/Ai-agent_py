let state = {}, selected = null, files = [];

const $ = s => document.querySelector(s);
const el = (tag, attrs = {}, text = '') => {
  let x = document.createElement(tag);
  Object.assign(x, attrs);
  x.textContent = text;
  return x;
};

// Theme Management Engine
function applyTheme(themeName) {
  let validThemes = [
    'classic-dark', 'classic-light', 'telegram-official', 'instagram-gradient',
    'midnight-cyber', 'emerald-matrix', 'sunset-gold', 'nordic-frost',
    'tokyo-night', 'crimson-vampire', 'dracula-purple', 'rose-pine',
    'ocean-breeze', 'synthwave-80s', 'monochrome-oled'
  ];
  let t = validThemes.includes(themeName) ? themeName : 'classic-dark';
  document.documentElement.setAttribute('data-theme', t);
  localStorage.setItem('bot_panel_theme', t);
  if ($('#themeSelect')) {
    $('#themeSelect').value = t;
  }
}

let savedTheme = localStorage.getItem('bot_panel_theme') || 'classic-dark';
applyTheme(savedTheme);

async function api(path, method = 'GET', body) {
  let r = await fetch(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body && JSON.stringify(body)
  });
  let d;
  try {
    d = await r.json();
  } catch (e) {
    if (!r.ok) throw Error(`Server error (${r.status}). Please restart python app.py.`);
    throw Error('Invalid server response');
  }
  if (!r.ok) throw Error(d.error || 'Request failed');
  return d;
}

let lastStateHash = '';
let autoPollTimer = null;
let currentPollIntervalMs = 1500;

function updateAutoPollSpeed(ms) {
  let targetMs = ms || 1500;
  if (targetMs !== currentPollIntervalMs || !autoPollTimer) {
    currentPollIntervalMs = targetMs;
    if (autoPollTimer) clearInterval(autoPollTimer);
    autoPollTimer = setInterval(autoPoll, currentPollIntervalMs);
  }
}

async function refresh() {
  state = await api('/api/state');
  updateAutoPollSpeed(state.polling_config?.speed_ms);
  lastStateHash = JSON.stringify({
    msgCount: state.messages?.length,
    lastMsgId: state.messages?.[state.messages.length - 1]?.id,
    contactsCount: state.contacts?.length,
    activeBot: state.active_bot_id,
    polls: state.polls,
    pCfg: state.polling_config
  });
  renderContacts();
  renderSettings();
  if (selected) renderChat();
}

async function autoPoll() {
  try {
    let newState = await api('/api/state');
    updateAutoPollSpeed(newState.polling_config?.speed_ms);
    let newHash = JSON.stringify({
      msgCount: newState.messages?.length,
      lastMsgId: newState.messages?.[newState.messages.length - 1]?.id,
      contactsCount: newState.contacts?.length,
      activeBot: newState.active_bot_id,
      polls: newState.polls,
      pCfg: newState.polling_config
    });
    if (newHash !== lastStateHash) {
      lastStateHash = newHash;
      state = newState;
      renderContacts();
      if (selected) renderChat();
    }
  } catch (e) {
    // Silent background poll error
  }
}

updateAutoPollSpeed(1500);

function active() {
  return (state.bots || []).find(b => b.id === state.active_bot_id);
}

function esc(s) {
  return String(s || '').replace(/[&<>"']/g, x => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[x]));
}

function renderContacts() {
  let q = ($('#search').value || '').toLowerCase();
  let box = $('#contacts');
  box.innerHTML = '';
  (state.contacts || [])
    .filter(c => (c.name || '').toLowerCase().includes(q) || (c.username || '').toLowerCase().includes(q))
    .forEach(c => {
      let isGroup = c.type === 'group' || c.type === 'supergroup' || String(c.id).startsWith('-');
      let row = el('div', { className: 'contact ' + (selected === c.id ? 'selected' : '') });
      let avatarChar = isGroup ? '👥' : ((c.name || '?')[0]?.toUpperCase() || '?');
      row.append(el('div', { className: 'avatar' }, avatarChar));
      let info = el('div', { className: 'info' });
      let sub = (isGroup ? '👥 Group • ' : '') + (c.username ? '@' + c.username : c.id);
      info.append(el('div', { className: 'name' }, c.name), el('small', {}, sub));
      row.append(info);
      row.onclick = () => {
        selected = c.id;
        let appNode = $('.app');
        if (appNode) appNode.classList.add('mobile-chat-active');
        renderContacts();
        renderChat();
      };
      box.append(row);
    });
}

function attachment(a) {
  if (!a) return '';
  let rawName = typeof a === 'string' ? a : (a.label || a.name || '');
  let fileName = typeof a === 'string' ? a : (a.name || a.label || '');
  let cleanPath = fileName.split('\\').join('/');
  let url = '/uploads/' + cleanPath.split('/').map(encodeURIComponent).join('/');
  let name = esc(rawName || fileName || 'Attachment');
  let ext = (rawName || fileName).includes('.') ? (rawName || fileName).split('.').pop().toLowerCase() : '';

  if (['mp4', 'webm', 'mov', 'mkv'].includes(ext)) {
    return `<div class="attachment" style="margin-top:6px;"><video controls src="${url}" style="max-width:100%;max-height:320px;border-radius:10px;display:block;outline:none;"></video></div>`;
  }
  if (['mp3', 'wav', 'ogg', 'm4a', 'aac'].includes(ext)) {
    return `<div class="attachment" style="margin-top:6px;"><audio controls src="${url}" style="width:100%;max-width:320px;display:block;"></audio></div>`;
  }
  if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(ext)) {
    return `<div class="attachment" style="margin-top:6px;"><a href="${url}" target="_blank" title="Click to view full image"><img src="${url}" style="max-width:100%;max-height:300px;border-radius:10px;display:block;box-shadow:0 2px 8px rgba(0,0,0,0.15);" /></a></div>`;
  }
  return `<div class="attachment" style="margin-top:6px;"><a href="${url}" download="${name}" style="display:inline-flex;align-items:center;gap:6px;color:var(--green);font-weight:600;text-decoration:none;">📄 ${name} <span style="font-size:11px;color:var(--muted);">(Download)</span></a></div>`;
}

function getPollForMessage(m) {
  if (!m) return null;
  if (m.poll_id && state.polls?.[m.poll_id]) {
    return { poll: state.polls[m.poll_id], id: m.poll_id };
  }
  if (m.text && (m.text.startsWith('📊') || m.text.startsWith('📊 Poll:'))) {
    let lines = m.text.split('\n').map(l => l.trim()).filter(Boolean);
    let question = lines[0].replace(/^📊\s*(Poll:\s*)?/, '');
    let matchedId = Object.keys(state.polls || {}).find(k => state.polls[k].question === question);
    if (matchedId) return { poll: state.polls[matchedId], id: matchedId };
    let options = lines.slice(1).map(l => l.replace(/^[•\-\*]\s*/, ''));
    return { poll: { question, options, votes: {} }, id: null };
  }
  return null;
}

window.votePollOption = async function(pollId, option) {
  if (!pollId || pollId === 'null' || !option) return;
  try {
    await api('/api/poll-vote', 'POST', {
      bot_id: state.active_bot_id,
      poll_id: pollId,
      option: option,
      user_id: 'admin_panel'
    });
    await refresh();
  } catch (err) {
    console.error('Poll vote error:', err);
  }
};

function renderPollCard(pollData) {
  if (!pollData) return '';
  let poll = pollData.poll || pollData;
  let pollId = pollData.id || null;
  if (!poll) return '';

  let counts = {};
  (poll.options || []).forEach(o => counts[o] = 0);

  if (poll.option_counts && Object.keys(poll.option_counts).length > 0) {
    Object.assign(counts, poll.option_counts);
  } else {
    let userVotes = poll.votes || {};
    Object.values(userVotes).forEach(choice => {
      (choice || '').split(', ').forEach(c => {
        if (counts[c] !== undefined) counts[c]++;
      });
    });
  }

  let userVotes = poll.votes || {};
  let total = (poll.total_voter_count !== undefined && poll.total_voter_count > 0)
    ? poll.total_voter_count
    : Object.values(counts).reduce((a, b) => a + b, 0);

  let html = `<div class="tg-poll-card">`;
  html += `<div class="tg-poll-header">
    <div class="tg-poll-badge">📊 Anonymous Poll</div>
    <div class="tg-poll-question">${esc(poll.question)}</div>
  </div>`;

  html += `<div class="tg-poll-options">`;
  (poll.options || []).forEach(opt => {
    let count = counts[opt] || 0;
    let pct = total > 0 ? Math.round((count / total) * 100) : 0;
    let isVoted = userVotes['admin_panel'] === opt;

    html += `
      <div class="tg-poll-option-item ${isVoted ? 'voted' : ''}" onclick="votePollOption('${esc(pollId || '')}', '${esc(opt)}')">
        <div class="tg-poll-option-top">
          <div class="tg-poll-radio ${isVoted ? 'checked' : ''}"></div>
          <span class="tg-poll-opt-text">${esc(opt)}</span>
          <span class="tg-poll-opt-stats">${pct}% <small>(${count} ${count === 1 ? 'vote' : 'votes'})</small></span>
        </div>
        <div class="tg-poll-bar-track">
          <div class="tg-poll-bar-fill" style="width: ${pct}%;"></div>
        </div>
      </div>
    `;
  });
  html += `</div>`;

  html += `<div class="tg-poll-footer">
    <span>👥 ${total} ${total === 1 ? 'vote' : 'votes'}</span>
    <span class="tg-poll-hint">${pollId ? 'Click option to vote' : 'Live Poll'}</span>
  </div>`;
  html += `</div>`;

  return html;
}

function renderChat() {
  let c = (state.contacts || []).find(x => x.id === selected);
  if (!c) {
    if ($('#empty')) $('#empty').hidden = false;
    if ($('#messages')) $('#messages').hidden = true;
    if ($('#composer')) $('#composer').hidden = true;
    if ($('#headerTitle')) $('#headerTitle').textContent = 'Select a contact';
    if ($('#headerSubtitle')) $('#headerSubtitle').textContent = 'Telegram Bot Panel';
    if ($('#headerAvatar')) $('#headerAvatar').textContent = 'B';
    return;
  }
  if ($('#empty')) $('#empty').hidden = true;
  if ($('#messages')) $('#messages').hidden = false;
  if ($('#composer')) $('#composer').hidden = false;
  let isGroup = c.type === 'group' || c.type === 'supergroup' || String(c.id).startsWith('-');
  if ($('#headerAvatar')) $('#headerAvatar').textContent = isGroup ? '👥' : ((c.name || '?')[0]?.toUpperCase() || '?');
  if ($('#headerTitle')) $('#headerTitle').textContent = c.name;
  if ($('#headerSubtitle')) $('#headerSubtitle').textContent = (isGroup ? '👥 Group Chat • ' : '') + (c.username ? '@' + c.username : c.id);
  
  let box = $('#messages');
  let isNearBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 120;
  let isNewContact = box.dataset.contactId !== selected;
  box.dataset.contactId = selected;

  box.innerHTML = '';
  (state.messages || [])
    .filter(m => String(m.contact_id) === String(selected))
    .forEach(m => {
      let pollData = getPollForMessage(m);
      let b = el('div', { className: 'bubble ' + (m.direction === 'out' ? 'out' : '') });
      
      if (m.sender_name && m.direction === 'in') {
        let senderTag = el('div', { style: 'font-weight:700;font-size:11px;color:var(--green);margin-bottom:3px;letter-spacing:0.3px' }, '👤 ' + m.sender_name);
        b.append(senderTag);
      }

      if (m.is_broadcast) {
        let bcastTag = el('div', { style: 'margin-bottom:4px;' });
        bcastTag.innerHTML = '<span style="background:rgba(245,158,11,0.2);color:#f59e0b;padding:2px 7px;border-radius:10px;font-size:10px;font-weight:700;display:inline-flex;align-items:center;gap:4px;">📢 Broadcast</span>';
        b.append(bcastTag);
      }

      if (!pollData) {
        let textDiv = el('div', {}, m.text);
        b.append(textDiv);
      }
      if (m.attachments?.length) {
        b.insertAdjacentHTML('beforeend', m.attachments.map(attachment).join(''));
      }
      if (pollData) {
        b.insertAdjacentHTML('beforeend', renderPollCard(pollData));
      }

      let menuBtn = el('button', { className: 'msg-menu-btn', title: 'Options' }, '▼');
      let dropdown = el('div', { className: 'msg-dropdown', hidden: true });
      let optDelLocal = el('button', { type: 'button' }, '🗑️ Delete for me');
      let optDelAll = el('button', { type: 'button', className: 'opt-del-all' }, '❌ Delete for bot user');

      optDelLocal.onclick = async (e) => {
        e.stopPropagation();
        dropdown.hidden = true;
        try {
          await api('/api/delete-message', 'POST', { bot_id: state.active_bot_id, message_id: m.id, delete_telegram: false, delete_all: false });
          await refresh();
        } catch (err) {
          alert('Delete error: ' + err.message);
        }
      };

      optDelAll.onclick = async (e) => {
        e.stopPropagation();
        dropdown.hidden = true;
        if (!confirm('Delete message from Telegram & local chat?')) return;
        try {
          await api('/api/delete-message', 'POST', { bot_id: state.active_bot_id, message_id: m.id, delete_telegram: true, delete_all: true });
          await refresh();
        } catch (err) {
          alert('Delete error: ' + err.message);
        }
      };

      dropdown.append(optDelLocal);
      if (m.telegram_msg_id) dropdown.append(optDelAll);

      menuBtn.onclick = (e) => {
        e.stopPropagation();
        document.querySelectorAll('.msg-dropdown').forEach(d => { if (d !== dropdown) d.hidden = true; });
        dropdown.hidden = !dropdown.hidden;
      };

      b.append(menuBtn, dropdown);
      b.append(el('span', { className: 'time' }, m.time));
      box.append(b);
    });

  if (isNewContact || isNearBottom) {
    box.scrollTop = box.scrollHeight;
  }
}

async function connectionStatus() {
  let node = $('#connection');
  if (!node) {
    node = el('div', { id: 'connection' });
    node.style.cssText = 'padding:10px;border-radius:7px;background:var(--line);color:var(--ink);margin-bottom:12px';
    $('.settings header').insertAdjacentElement('afterend', node);
  }
  let result = await api('/api/connection');
  node.textContent = result.message;
  node.style.background = result.ok ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)';
  node.style.color = result.ok ? 'var(--green)' : '#ef4444';
}

function action(text, fn, danger = false) {
  let b = el('button', {}, text);
  if (danger) b.style.background = '#c0392b';
  b.onclick = fn;
  return b;
}

function renderSettings() {
  let bot = active(), select = $('#activeBot');
  select.innerHTML = (state.bots || []).length ? '' : '<option>No bot added</option>';
  (state.bots || []).forEach(b => select.append(el('option', { value: b.id, selected: b.id === state.active_bot_id }, b.name)));

  if ($('#themeSelect')) {
    let curTheme = localStorage.getItem('bot_panel_theme') || 'classic-dark';
    $('#themeSelect').value = curTheme;
    $('#themeSelect').onchange = (e) => {
      applyTheme(e.target.value);
    };
  }

  let bots = $('#bots');
  bots.innerHTML = '';
  (state.bots || []).forEach(b => {
    let r = el('div', { className: 'row' });
    r.style.gridTemplateColumns = 'minmax(90px,1fr) minmax(100px,1fr) auto auto auto';
    let name = el('input', { value: b.name }),
      token = el('input', { type: 'password', placeholder: b.masked_token || 'Bot token' }),
      toggle = el('input', { type: 'checkbox', checked: b.enabled !== false, title: 'Run this bot in background' });
    toggle.onchange = async () => {
      await api('/api/bot-enabled', 'POST', { id: b.id, enabled: toggle.checked });
      await refresh();
    };
    r.append(
      name, token, toggle,
      action('Save', async () => {
        await api('/api/bot-update', 'POST', { id: b.id, name: name.value, token: token.value });
        await refresh();
      }),
      action('Delete', async () => {
        if (confirm(`Delete ${b.name}?`)) {
          await api('/api/bot-delete', 'POST', { id: b.id });
          await refresh();
        }
      }, true)
    );
    bots.append(r);
    let status = el('small', {}, b.enabled !== false ? 'Background: ON' : 'Background: OFF');
    status.style.margin = '-7px 0 8px';
    status.style.display = 'block';
    bots.append(status);
  });

  $('#commandBotName').textContent = bot ? 'for ' + bot.name : '';
  $('#adminBotName').textContent = bot ? 'for ' + bot.name : '';
  $('#aiBotName').textContent = bot ? 'for ' + bot.name : '';

  let commands = $('#commands');
  commands.innerHTML = '';
  (state.commands || [])
    .filter(c => c.admin_only)
    .forEach(c => {
      let r = el('div', { className: 'command' }), info = el('div');
      info.innerHTML = `<strong>/${esc(c.name)} enabled: &nbsp; ${bot ? (bot.command_states[c.name] !== false ? 'ON' : 'OFF') : ''}</strong><small>/${esc(c.name)} is admin-only</small>`;
      let check = el('input', { type: 'checkbox', className: 'toggle', checked: bot ? bot.command_states[c.name] !== false : false, disabled: !bot });
      check.onchange = async () => {
        await api('/api/command-toggle', 'POST', { bot_id: bot.id, command: c.name, enabled: check.checked });
        await refresh();
      };
      r.append(info, check);
      commands.append(r);
    });

  let advList = $('#advancedCommandsList');
  advList.innerHTML = '';
  let renderGroup = (cmds, title) => {
    if (title) {
      let h = el('h3', {});
      h.style.marginTop = '20px';
      h.textContent = title;
      advList.append(h);
    }
    cmds.forEach(c => {
      let r = el('div', { style: 'margin-top:15px' });
      r.innerHTML = `<strong>› /${esc(c.name)} ${c.admin_only ? '(admin only)' : ''}</strong>`;
      (state.bots || []).forEach(b => {
        let br = el('div', { style: 'display:flex;align-items:center;gap:8px;margin:8px 0 0 20px' });
        let check = el('input', { type: 'checkbox', checked: b.command_states[c.name] !== false });
        check.onchange = async () => {
          await api('/api/command-toggle', 'POST', { bot_id: b.id, command: c.name, enabled: check.checked });
          await refresh();
        };
        br.append(check, el('span', {}, b.name));
        r.append(br);
      });
      advList.append(r);
    });
  };
  renderGroup((state.commands || []).filter(c => !c.admin_only), '');
  renderGroup((state.commands || []).filter(c => c.admin_only), 'admin commands');

  let admins = $('#admins');
  admins.innerHTML = '';
  (bot?.admins || []).forEach(a => {
    let r = el('div', { className: 'row' });
    r.style.gridTemplateColumns = '1fr 1fr auto auto';
    let name = el('input', { value: a.name }), id = el('input', { value: a.telegram_id });
    r.append(
      name, id,
      action('Save', async () => {
        await api('/api/admin-update', 'POST', { bot_id: bot.id, id: a.id, name: name.value, telegram_id: id.value });
        await refresh();
      }),
      action('Delete', async () => {
        if (confirm(`Delete admin ${a.name}?`)) {
          await api('/api/admin-delete', 'POST', { bot_id: bot.id, id: a.id });
          await refresh();
        }
      }, true)
    );
    admins.append(r);
  });

  let aiBox = $('#aiSettings');
  aiBox.innerHTML = '';
  if (bot) {
    let ai = bot.ai || { enabled: false, url: 'http://localhost:1234/v1', model: '' };
    let wrap = el('div');
    wrap.style.cssText = 'display:flex;flex-direction:column;gap:16px';

    // =========================================================
    // CARD 1: 💻 Connect to AI (LM Studio Local Base URL)
    // =========================================================
    let localAiCard = el('div', { style: 'background:var(--card-bg, rgba(255,255,255,0.03));border:1px solid var(--line);border-radius:10px;padding:14px;display:flex;flex-direction:column;gap:12px;' });
    
    let localTitle = el('strong', { style: 'font-size:0.95rem;display:flex;align-items:center;gap:6px;' }, '💻 Connect to AI (LM Studio Local Base URL)');

    let toggleRow = el('div', { style: 'display:flex;align-items:center;gap:10px' });
    let aiToggle = el('input', { type: 'checkbox', className: 'toggle', checked: ai.enabled });
    let aiLabel = el('span', {}, ai.enabled ? 'Telegram AI Chat: ON' : 'Telegram AI Chat: OFF');
    aiLabel.style.fontWeight = '600';
    toggleRow.append(aiToggle, aiLabel);

    let localUrlLabel = el('label', { style: 'font-size:0.85rem;color:var(--hint);' }, 'LM Studio Local URL');
    let localUrlInput = el('input', { value: ai.url || 'http://localhost:1234/v1', placeholder: 'http://localhost:1234/v1' });
    localUrlInput.style.cssText = 'display:block;width:100%;padding:10px;margin-top:5px;border:1px solid var(--line);border-radius:7px;font:inherit;background:var(--input-bg);color:var(--ink)';
    localUrlLabel.append(localUrlInput);

    let modelLabel = el('label', { style: 'font-size:0.85rem;color:var(--hint);' }, 'Model name (optional)');
    let modelInput = el('input', { value: ai.model || '', placeholder: 'Leave empty for auto-detect' });
    modelInput.style.cssText = 'display:block;width:100%;padding:10px;margin-top:5px;border:1px solid var(--line);border-radius:7px;font:inherit;background:var(--input-bg);color:var(--ink)';
    modelLabel.append(modelInput);

    let saveLocalBtn = action('Save Local AI Config', async () => {
      await api('/api/ai-config', 'POST', { bot_id: bot.id, enabled: aiToggle.checked, url: localUrlInput.value, model: modelInput.value });
      await refresh();
    });

    localAiCard.append(localTitle, toggleRow, localUrlLabel, modelLabel, saveLocalBtn);

    // =========================================================
    // CARD 2: 🌐 Cloudflare Public Tunnel Control
    // =========================================================
    let tunnelCard = el('div', { style: 'background:var(--card-bg, rgba(255,255,255,0.03));border:1px solid var(--line);border-radius:10px;padding:14px;display:flex;flex-direction:column;gap:12px;' });
    
    let tStatus = state.tunnel_status || { running: false, url: null, active_hours: 0, remaining_seconds: 0 };
    
    // Header with status badge
    let headerRow = el('div', { style: 'display:flex;justify-content:space-between;align-items:center;' });
    let cardTitle = el('strong', { style: 'font-size:0.95rem;display:flex;align-items:center;gap:6px;' }, '🌐 Cloudflare Public Tunnel Control');
    let badge = el('span', {
      style: `padding:4px 10px;border-radius:20px;font-size:0.75rem;font-weight:700;letter-spacing:0.5px;` +
             (tStatus.running
                ? 'background:rgba(34,197,94,0.15);color:#22c55e;border:1px solid rgba(34,197,94,0.4);'
                : 'background:rgba(239,68,68,0.15);color:#ef4444;border:1px solid rgba(239,68,68,0.4);')
    }, tStatus.running ? '🟢 RUNNING' : '🔴 STOPPED');
    headerRow.append(cardTitle, badge);

    // Public Tunnel URL Input + Copy Link Button
    let tunnelUrlLabel = el('label', { style: 'font-size:0.85rem;color:var(--hint);display:flex;flex-direction:column;gap:5px;' }, 'Public Cloudflare Tunnel Link (For External Access / WhatsApp AI)');
    let tunnelUrlRow = el('div', { style: 'display:flex;gap:8px;' });
    let tunnelUrlInput = el('input', { value: tStatus.url || '', placeholder: 'Tunnel offline (Click Turn ON Tunnel to start)', readonly: true });
    tunnelUrlInput.style.cssText = 'flex:1;padding:10px;border:1px solid var(--line);border-radius:7px;font:inherit;background:var(--input-bg);color:var(--ink)';
    
    let copyBtn = el('button', {
      type: 'button',
      className: 'outline',
      style: 'padding:8px 14px;font-weight:600;display:flex;align-items:center;gap:6px;white-space:nowrap;cursor:pointer;'
    }, '📋 Copy Link');

    copyBtn.onclick = () => {
      let val = tunnelUrlInput.value.trim();
      if (!val || val.includes('offline')) return;
      navigator.clipboard.writeText(val).then(() => {
        copyBtn.textContent = '✅ Copied!';
        copyBtn.style.borderColor = '#22c55e';
        copyBtn.style.color = '#22c55e';
        setTimeout(() => {
          copyBtn.textContent = '📋 Copy Link';
          copyBtn.style.borderColor = '';
          copyBtn.style.color = '';
        }, 2000);
      });
    };
    tunnelUrlRow.append(tunnelUrlInput, copyBtn);
    tunnelUrlLabel.append(tunnelUrlRow);

    // Editable Local Target URL to Forward
    let targetLocalLabel = el('label', { style: 'font-size:0.85rem;color:var(--hint);display:flex;flex-direction:column;gap:5px;' }, 'Local Target URL to Forward (e.g. http://localhost:1234 or http://192.168.43.2:4567/v1)');
    let targetLocalInput = el('input', { value: tStatus.target_local || 'http://localhost:1234', placeholder: 'http://localhost:1234' });
    targetLocalInput.style.cssText = 'width:100%;padding:10px;border:1px solid var(--line);border-radius:7px;font:inherit;background:var(--input-bg);color:var(--ink)';
    targetLocalLabel.append(targetLocalInput);

    // Duration Hours selector & Manual Toggle ON/OFF button row
    let controlRow = el('div', { style: 'display:flex;align-items:flex-end;gap:10px;flex-wrap:wrap;' });
    
    let durationBox = el('div', { style: 'flex:1;min-width:150px;' });
    let durLabel = el('label', { style: 'font-size:0.85rem;color:var(--hint);display:block;margin-bottom:5px;' }, 'Active Duration (Hours)');
    let durSelect = el('select', { style: 'width:100%;padding:10px;border:1px solid var(--line);border-radius:7px;font:inherit;background:var(--input-bg);color:var(--ink)' });
    
    let hourOptions = [
      { val: '0', text: '♾️ Unlimited (Always ON)' },
      { val: '1', text: '⏱️ 1 Hour' },
      { val: '2', text: '⏱️ 2 Hours' },
      { val: '4', text: '⏱️ 4 Hours' },
      { val: '6', text: '⏱️ 6 Hours' },
      { val: '8', text: '⏱️ 8 Hours' },
      { val: '12', text: '⏱️ 12 Hours' },
      { val: '24', text: '⏱️ 24 Hours' }
    ];

    let currentHours = tStatus.active_hours ? String(tStatus.active_hours) : '0';
    hourOptions.forEach(opt => {
      let o = el('option', { value: opt.val, selected: opt.val === currentHours }, opt.text);
      durSelect.append(o);
    });
    durationBox.append(durLabel, durSelect);

    // Manual Toggle Button
    let toggleBtn = el('button', {
      type: 'button',
      style: tStatus.running
        ? 'padding:10px 18px;border-radius:7px;font-weight:700;border:none;background:#ef4444;color:white;cursor:pointer;display:flex;align-items:center;gap:6px;'
        : 'padding:10px 18px;border-radius:7px;font-weight:700;border:none;background:#22c55e;color:white;cursor:pointer;display:flex;align-items:center;gap:6px;'
    }, tStatus.running ? '🛑 Turn OFF Tunnel' : '⚡ Turn ON Tunnel');

    let isBusy = false;
    toggleBtn.onclick = async () => {
      if (isBusy) return;
      isBusy = true;
      toggleBtn.disabled = true;
      toggleBtn.textContent = '⏳ Processing...';
      try {
        let act = tStatus.running ? 'stop' : 'start';
        let hrs = parseFloat(durSelect.value) || 0;
        let targetLoc = targetLocalInput.value.trim() || 'http://localhost:1234';
        let res = await api('/api/tunnel-toggle', 'POST', { action: act, hours: hrs, target_local: targetLoc });
        if (res.ok) {
          if (res.url) tunnelUrlInput.value = res.url;
          await refresh();
        }
      } catch (err) {
        alert('Tunnel Error: ' + err.message);
      } finally {
        isBusy = false;
        toggleBtn.disabled = false;
      }
    };

    controlRow.append(durationBox, toggleBtn);

    // Live Countdown timer bar
    let timerNotice = el('div', {
      id: 'tunnelCountdownNotice',
      style: 'font-size:0.85rem;font-weight:600;padding:8px 12px;border-radius:6px;background:rgba(255,255,255,0.05);color:var(--ink);display:flex;align-items:center;gap:8px;'
    });

    function updateCountdown() {
      if (!tStatus.running) {
        timerNotice.innerHTML = '<span style="color:var(--hint);">🔴 Tunnel is offline. Click <b>Turn ON Tunnel</b> to start.</span>';
        return;
      }
      if (!tStatus.expiry_time || tStatus.expiry_time === 0) {
        timerNotice.innerHTML = '<span>♾️ Tunnel is active continuously (No auto-shutdown timer set).</span>';
        return;
      }
      let now = Date.now() / 1000;
      let rem = Math.max(0, Math.floor(tStatus.expiry_time - now));
      if (rem <= 0) {
        timerNotice.innerHTML = '<span style="color:#ef4444;">⏱️ Tunnel duration expired! Auto-stopping...</span>';
        refresh();
      } else {
        let hrs = Math.floor(rem / 3600);
        let mins = Math.floor((rem % 3600) / 60);
        let secs = rem % 60;
        let pad = n => String(n).padStart(2, '0');
        timerNotice.innerHTML = `⏱️ <b>Auto-shutdown in:</b> <span style="color:#eab308;font-family:monospace;font-size:0.95rem;">${pad(hrs)}h ${pad(mins)}m ${pad(secs)}s</span>`;
      }
    }

    updateCountdown();
    if (window._tunnelInterval) clearInterval(window._tunnelInterval);
    if (tStatus.running && tStatus.expiry_time > 0) {
      window._tunnelInterval = setInterval(updateCountdown, 1000);
    }

    tunnelCard.append(headerRow, targetLocalLabel, tunnelUrlLabel, controlRow, timerNotice);

    wrap.append(localAiCard, tunnelCard);
    aiBox.append(wrap);
  } else {
    aiBox.textContent = 'Add a bot first.';
  }

  let pBox = $('#pollingSettings');
  pBox.innerHTML = '';
  let pCfg = state.polling_config || { mode: 'multithread_1.5' };
  let pWrap = el('div', { style: 'display:flex;flex-direction:column;gap:12px' });
  let pLabel = el('label', {}, 'Select Polling & Refresh Speed');
  let pSelect = el('select', {});
  pSelect.style.cssText = 'display:block;width:100%;padding:10px;margin-top:5px;border:1px solid var(--line);border-radius:7px;font:inherit;background:var(--input-bg);color:var(--ink)';

  let pOptions = [
    { val: 'multithread_1.5', text: '⚡ Multi-Threading (1.5s - Ultra Fast)' },
    { val: 'multithread_2.0', text: '⚡ Multi-Threading (2.0s - Fast)' },
    { val: '1s', text: '⚡ Single-Threaded (1.0 Second)' },
    { val: '1.5s', text: '🐢 Single-Threaded (1.5 Seconds)' },
    { val: '2.0s', text: '🐢 Single-Threaded (2.0 Seconds)' },
    { val: '2.5s', text: '🐢 Single-Threaded (2.5 Seconds)' },
    { val: '3.0s', text: '🐢 Single-Threaded (3.0 Seconds)' }
  ];

  pOptions.forEach(opt => {
    let o = el('option', { value: opt.val, selected: opt.val === pCfg.mode }, opt.text);
    pSelect.append(o);
  });

  pLabel.append(pSelect);
  let pSaveBtn = action('Save Polling Speed', async () => {
    await api('/api/polling-config', 'POST', { mode: pSelect.value });
    await refresh();
  });
  pWrap.append(pLabel, pSaveBtn);
  pBox.append(pWrap);

  // Drive Storage Settings Rendering
  let driveCfg = state.drive_config || { default_limit_mb: 500, premium_users: [] };
  if ($('#driveDefaultLimit')) $('#driveDefaultLimit').value = driveCfg.default_limit_mb || 500;

  let driveList = $('#drivePremiumList');
  if (driveList) {
    driveList.innerHTML = '';
    let pUsers = driveCfg.premium_users || [];
    if (pUsers.length === 0) {
      driveList.innerHTML = '<div style="color:var(--muted);font-size:13px;padding:8px 0;">No premium users added yet. Default limit applies to everyone.</div>';
    } else {
      pUsers.forEach(pu => {
        let r = el('div', { className: 'row', style: 'display:flex;align-items:center;gap:10px;margin-bottom:8px;' },
          el('span', { style: 'font-weight:600;min-width:140px;' }, `👤 ${pu.telegram_id}`),
          el('span', { style: 'color:var(--green);font-weight:600;' }, `🌟 ${pu.label || pu.quota_mb + ' MB'}`),
          action('Delete', async () => {
            if (confirm(`Remove premium quota for User ID ${pu.telegram_id}?`)) {
              await api('/api/drive-premium-delete', 'POST', { telegram_id: pu.telegram_id });
              await refresh();
            }
          }, true)
        );
        driveList.append(r);
      });
    }
  }
}

// Event Listeners
if ($('#saveDriveDefault')) {
  $('#saveDriveDefault').onclick = async () => {
    let limit = parseInt($('#driveDefaultLimit').value) || 500;
    await api('/api/drive-config', 'POST', { default_limit_mb: limit });
    alert('✅ Default storage limit updated to ' + limit + ' MB!');
    await refresh();
  };
}

if ($('#addDrivePremium')) {
  $('#addDrivePremium').onclick = async () => {
    let tid = ($('#drivePremiumUser').value || '').trim();
    if (!tid) return alert('Please enter a Telegram User ID.');
    let quotaMb = parseInt($('#drivePremiumQuota').value) || 5120;
    let label = $('#drivePremiumQuota').options[$('#drivePremiumQuota').selectedIndex].text;
    await api('/api/drive-premium-add', 'POST', { telegram_id: tid, quota_mb: quotaMb, label: label });
    $('#drivePremiumUser').value = '';
    alert(`✅ User ${tid} updated with ${label} storage quota!`);
    await refresh();
  };
}

if ($('#backBtn')) {
  $('#backBtn').onclick = () => {
    let appNode = $('.app');
    if (appNode) appNode.classList.remove('mobile-chat-active');
  };
}

$('#search').oninput = renderContacts;
$('#settings').onclick = () => { $('#settingsDialog').showModal(); connectionStatus(); };
$('#closeSettings').onclick = () => $('#settingsDialog').close();
$('#addContact').onclick = () => $('#contactDialog').showModal();
$('#addBot').onclick = () => $('#botDialog').showModal();
$('#openAdvancedCommands').onclick = e => { e.preventDefault(); $('#advancedCommandsDialog').showModal(); };
$('#closeAdvancedCommands').onclick = () => $('#advancedCommandsDialog').close();

$('#saveContact').onclick = async e => {
  e.preventDefault();
  let name = ($('#contactName').value || '').trim();
  let telegramId = ($('#contactId').value || '').trim();
  let username = ($('#contactUsername').value || '').trim();

  if (!name || !telegramId) {
    alert('⚠️ Please fill in both Name and Telegram Chat ID before saving.');
    return;
  }

  try {
    await api('/api/contacts', 'POST', { name, telegram_id: telegramId, username });
    $('#contactName').value = '';
    $('#contactId').value = '';
    $('#contactUsername').value = '';
    $('#contactDialog').close();
    await refresh();
  } catch (err) {
    alert('Failed to save contact: ' + err.message);
  }
};

$('#saveBot').onclick = async e => {
  e.preventDefault();
  let name = ($('#botName').value || '').trim();
  let token = ($('#botToken').value || '').trim();

  if (!name || !token) {
    alert('⚠️ Please fill in both Bot Label and Bot Token before saving.');
    return;
  }

  try {
    await api('/api/bots', 'POST', { name, token });
    $('#botName').value = '';
    $('#botToken').value = '';
    $('#botDialog').close();
    await refresh();
  } catch (err) {
    alert('Failed to add bot: ' + err.message);
  }
};

$('#activeBot').onchange = async e => {
  await api('/api/active-bot', 'POST', { id: e.target.value });
  await refresh();
};

$('#addAdmin').onclick = async () => {
  let bot = active();
  if (!bot) return alert('Add a bot first.');
  let name = prompt('Admin name');
  if (!name) return;
  let telegram_id = prompt('Telegram numeric user ID');
  if (!telegram_id) return;
  await api('/api/admins', 'POST', { bot_id: bot.id, name, telegram_id });
  await refresh();
};

$('#clearChat').onclick = async () => {
  if (!selected) return alert('Select a contact first.');
  let c = state.contacts.find(x => x.id === selected);
  if (!confirm(`Clear chat history for ${c ? c.name : 'this contact'}?`)) return;
  try {
    await api('/api/clear-chat', 'POST', { contact_id: selected });
    await refresh();
  } catch (err) {
    alert('Clear chat error: ' + err.message);
  }
};

// WhatsApp-style Attachment Menu
$('#attach').onclick = e => {
  e.stopPropagation();
  let menu = $('#attachMenu');
  menu.hidden = !menu.hidden;
};

document.addEventListener('click', e => {
  let menu = $('#attachMenu');
  if (menu && !menu.hidden && !menu.contains(e.target) && e.target !== $('#attach')) {
    menu.hidden = true;
  }
  document.querySelectorAll('.msg-dropdown').forEach(d => {
    if (!d.hidden && !d.contains(e.target) && !e.target.classList.contains('msg-menu-btn')) {
      d.hidden = true;
    }
  });
});

$('#optMedia').onclick = () => {
  $('#attachMenu').hidden = true;
  $('#fileInput').accept = 'image/*,video/*';
  $('#fileInput').click();
};

$('#optDocument').onclick = () => {
  $('#attachMenu').hidden = true;
  $('#fileInput').accept = '*/*';
  $('#fileInput').click();
};

$('#optPoll').onclick = () => {
  $('#attachMenu').hidden = true;
  if (!selected) return alert('Select a contact first.');
  $('#pollDialog').showModal();
};

// Poll Dialog Handlers
$('#addPollOption').onclick = () => {
  let container = $('#pollOptions');
  let count = container.querySelectorAll('.poll-opt').length + 1;
  let label = el('label', {}, `Option ${count}`);
  label.append(el('input', { className: 'poll-opt', required: true, placeholder: `Option ${count}` }));
  container.append(label);
};

$('#closePoll').onclick = () => $('#pollDialog').close();

$('#sendPollBtn').onclick = async e => {
  e.preventDefault();
  let question = $('#pollQuestion').value.trim();
  let opts = Array.from(document.querySelectorAll('.poll-opt'))
    .map(i => i.value.trim())
    .filter(Boolean);

  if (!question) return alert('Please enter a poll question.');
  if (opts.length < 2) return alert('Poll must have at least 2 options.');

  try {
    await api('/api/poll', 'POST', { contact_id: selected, question, options: opts });
    $('#pollDialog').close();
    $('#pollQuestion').value = '';
    $('#pollOptions').innerHTML = '<label>Option 1<input class="poll-opt" required placeholder="Option 1"></label><label>Option 2<input class="poll-opt" required placeholder="Option 2"></label>';
    await refresh();
  } catch (err) {
    alert('Poll error: ' + err.message);
  }
};

$('#fileInput').onchange = () => {
  for (let f of $('#fileInput').files) files.push(f);
  $('#fileInput').value = '';
  renderFiles();
};

function renderFiles() {
  let box = $('#files');
  box.innerHTML = '';
  files.forEach((f, i) => {
    let tag = el('span', { className: 'file-tag' }, f.name + ' ');
    let del = el('span', { style: 'cursor:pointer;font-weight:bold;' }, '×');
    del.onclick = () => { files.splice(i, 1); renderFiles(); };
    tag.append(del);
    box.append(tag);
  });
}

$('#send').onclick = async () => {
  let txt = $('#messageText').value.trim();
  if (!txt && !files.length) return;
  $('#send').disabled = true;
  try {
    let payload = { bot_id: state.active_bot_id, contact_id: selected, text: txt, attachments: [] };
    for (let file of files) {
      let form = new FormData();
      form.append('file', file);
      let res = await fetch('/api/upload', { method: 'POST', body: form });
      let data = await res.json();
      payload.attachments.push(data.filename);
    }
    await api('/api/send', 'POST', payload);
    $('#messageText').value = '';
    files = [];
    renderFiles();
    refresh();
  } catch (err) {
    alert('Send failed: ' + err.message);
  } finally {
    $('#send').disabled = false;
  }
};

$('#messageText').onkeydown = e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    $('#send').click();
  }
};

// Services Modal Logic & Service Money Tracker (INR ₹)
const SERVICE_KEYS = ['whoowesme', 'denomination', 'smssystem', 'whatsappai'];

if ($('#btnServices')) {
  $('#btnServices').onclick = async () => {
    $('#servicesDialog').showModal();
    await loadServicePrices();
    await loadDaemonConfig();
  };
}

if ($('#closeServices')) {
  $('#closeServices').onclick = () => $('#servicesDialog').close();
}

async function loadDaemonConfig() {
  try {
    let res = await api('/api/daemon-config');
    let cfg = res.config || { interval: '60s', last_run: 0 };
    if ($('#daemonIntervalSelect')) {
      $('#daemonIntervalSelect').value = cfg.interval || '60s';
    }
    if ($('#daemonStatusBadge')) {
      let lastStr = cfg.last_run ? new Date(cfg.last_run * 1000).toLocaleTimeString() : 'Never';
      $('#daemonStatusBadge').textContent = `● Interval: ${cfg.interval} | Last Run: ${lastStr}`;
    }
  } catch (err) {
    console.error('Failed to load daemon config:', err);
  }
}

if ($('#btnSaveDaemonInterval')) {
  $('#btnSaveDaemonInterval').onclick = async () => {
    let val = $('#daemonIntervalSelect').value;
    try {
      await api('/api/daemon-config', 'POST', { interval: val });
      alert(`✅ Daemon interval updated to: ${val}`);
      await loadDaemonConfig();
    } catch (err) {
      alert('Failed to save daemon config: ' + err.message);
    }
  };
}

if ($('#btnRunDaemonNow')) {
  $('#btnRunDaemonNow').onclick = async () => {
    try {
      let res = await api('/api/daemon-run-now', 'POST');
      alert(`✅ Subscription check completed!\nChecked: ${res.subscribers_checked} subscribers.`);
      await loadDaemonConfig();
      if ($('#premiumDialog') && $('#premiumDialog').open) {
        await loadPremiumUsers();
      }
    } catch (err) {
      alert('Failed to run daemon check: ' + err.message);
    }
  };
}

async function loadServicePrices() {
  try {
    let res = await api('/api/service-prices');
    let prices = res.prices || {};
    SERVICE_KEYS.forEach(svc => {
      let info = prices[svc] || { price: 0, status: 'free' };
      let badge = $(`#badge_${svc}`);
      if (badge) {
        if (info.status === 'free' || info.price <= 0) {
          badge.style.background = 'rgba(16,185,129,0.15)';
          badge.style.color = '#10b981';
          badge.style.border = '1px solid #10b981';
          badge.textContent = '⭕ [free]';
        } else {
          badge.style.background = 'rgba(99,102,241,0.15)';
          badge.style.color = '#6366f1';
          badge.style.border = '1px solid #6366f1';
          badge.textContent = `₹ ${parseFloat(info.price).toLocaleString('en-IN')} [Paid]`;
        }
      }
      let statusSelect = document.querySelector(`.svc-status-select[data-svc="${svc}"]`);
      let priceInput = document.querySelector(`.svc-price-input[data-svc="${svc}"]`);
      if (statusSelect) statusSelect.value = info.status || 'free';
      if (priceInput) priceInput.value = info.price || 0;
    });
  } catch (err) {
    console.error('Failed to load service prices:', err);
  }
}

// Attach save handlers for service prices
document.querySelectorAll('.svc-save-price-btn').forEach(btn => {
  btn.onclick = async () => {
    let svc = btn.dataset.svc;
    let statusSelect = document.querySelector(`.svc-status-select[data-svc="${svc}"]`);
    let priceInput = document.querySelector(`.svc-price-input[data-svc="${svc}"]`);
    let price = priceInput ? parseFloat(priceInput.value) || 0 : 0;
    let status = statusSelect ? statusSelect.value : 'free';
    try {
      await api('/api/service-price-update', 'POST', { service: svc, price, status });
      alert(`✅ Updated pricing for service: ${svc}`);
      await loadServicePrices();
    } catch (err) {
      alert('Failed to update price: ' + err.message);
    }
  };
});

// Attach toggle handlers for all service down arrow buttons
document.querySelectorAll('.svc-toggle-btn').forEach(btn => {
  btn.onclick = () => {
    let svc = btn.dataset.svc;
    let collapseDiv = $(`#moneyCollapse_${svc}`);
    if (collapseDiv) {
      let isHidden = collapseDiv.hidden;
      collapseDiv.hidden = !isHidden;
      btn.textContent = isHidden ? '▲ Hide Options' : '▼ Set Price (₹)';
    }
  };
});

// Premium Users Modal & Subscription Manager
if ($('#btnPremium')) {
  $('#btnPremium').onclick = async () => {
    $('#premiumDialog').showModal();
    await loadPremiumUsers();
  };
}

if ($('#closePremium')) {
  $('#closePremium').onclick = () => $('#premiumDialog').close();
}

async function loadPremiumUsers() {
  try {
    let res = await api('/api/premium-subscribers');
    let users = res.users || [];
    let container = $('#premiumUsersContainer');
    container.innerHTML = '';

    if (!users.length) {
      container.innerHTML = '<div style="color:var(--muted);font-size:13px;text-align:center;padding:16px;background:var(--card-bg);border:1px solid var(--line);border-radius:8px;">No active premium users found. Add one above!</div>';
      return;
    }

    users.forEach(u => {
      let card = el('div', {
        style: 'background:var(--card-bg);border:1px solid var(--line);border-radius:8px;padding:14px 16px;display:flex;flex-direction:column;gap:10px;'
      });

      let topRow = el('div', { style: 'display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;width:100%;' });

      let userInfo = el('div', {});
      let title = el('div', { style: 'font-weight:700;font-size:14px;color:var(--ink);' }, u.name || `User ${u.telegram_id}`);
      let sub = el('div', { style: 'font-size:12px;color:var(--muted);margin-top:2px;' }, `Telegram ID: ${u.telegram_id}`);
      userInfo.append(title, sub);

      let rightBox = el('div', { style: 'display:flex;align-items:center;gap:10px;flex-wrap:wrap;' });

      // Days counter badge & status indicator
      let badgeBg = 'rgba(245,158,11,0.15)', badgeColor = '#f59e0b', badgeBorder = '1px solid #f59e0b', badgeText = `⏳ ${u.days_left} Days Left`;

      if (u.is_expired || u.days_left <= 0) {
        badgeBg = 'rgba(244,63,94,0.15)'; badgeColor = '#f43f5e'; badgeBorder = '1px solid #f43f5e'; badgeText = '❌ EXPIRED';
      } else if (u.auto_stopped) {
        badgeBg = 'rgba(244,63,94,0.15)'; badgeColor = '#f43f5e'; badgeBorder = '1px solid #f43f5e'; badgeText = '⏸ Services Auto-Stopped';
      } else if (u.scheduled_stop_ts > 0) {
        badgeBg = 'rgba(251,146,60,0.15)'; badgeColor = '#fb923c'; badgeBorder = '1px solid #fb923c'; badgeText = '🌙 Stop Scheduled (11:59 PM)';
      } else if (u.days_left <= 3) {
        badgeBg = 'rgba(251,146,60,0.15)'; badgeColor = '#fb923c'; badgeBorder = '1px solid #fb923c'; badgeText = `⚠️ ${u.days_left} Days Left`;
      } else {
        badgeBg = 'rgba(16,185,129,0.15)'; badgeColor = '#10b981'; badgeBorder = '1px solid #10b981'; badgeText = `✓ ${u.days_left} Days Left`;
      }

      let daysBadge = el('div', {
        style: `background:${badgeBg};color:${badgeColor};border:${badgeBorder};padding:4px 12px;border-radius:20px;font-size:13px;font-weight:700;`
      }, badgeText);

      // Buttons container (+30, -30, Delete)
      let btnGroup = el('div', { style: 'display:flex;gap:6px;' });

      let add30Btn = el('button', {
        type: 'button',
        style: 'background:var(--surface);border:1px solid var(--green);color:var(--green);padding:4px 10px;border-radius:6px;font-weight:700;cursor:pointer;font-size:13px;',
        title: 'Add 30 Days'
      }, '+ 30 Days');
      add30Btn.onclick = async () => {
        await api('/api/premium-subscriber-adjust', 'POST', { telegram_id: u.telegram_id, days_delta: 30 });
        await loadPremiumUsers();
      };

      let sub30Btn = el('button', {
        type: 'button',
        style: 'background:var(--surface);border:1px solid #f43f5e;color:#f43f5e;padding:4px 10px;border-radius:6px;font-weight:700;cursor:pointer;font-size:13px;',
        title: 'Deduct 30 Days'
      }, '- 30 Days');
      sub30Btn.onclick = async () => {
        await api('/api/premium-subscriber-adjust', 'POST', { telegram_id: u.telegram_id, days_delta: -30 });
        await loadPremiumUsers();
      };

      let delBtn = el('button', {
        type: 'button',
        style: 'background:rgba(244,63,94,0.15);border:1px solid #f43f5e;color:#f43f5e;padding:4px 10px;border-radius:6px;font-weight:600;cursor:pointer;font-size:13px;',
        title: 'Delete Premium Member'
      }, '🗑️ Delete');
      delBtn.onclick = async () => {
        if (confirm(`Remove premium access for ${u.name || u.telegram_id}?`)) {
          await api('/api/premium-subscriber-delete', 'POST', { telegram_id: u.telegram_id });
          await loadPremiumUsers();
        }
      };

      btnGroup.append(add30Btn, sub30Btn, delBtn);
      rightBox.append(daysBadge, btnGroup);
      topRow.append(userInfo, rightBox);

      // Service Checkboxes Row for each User
      let allowedList = u.allowed_services || ['whoowesme', 'denomination', 'smssystem', 'whatsappai'];
      let svcRow = el('div', { style: 'padding-top:8px;border-top:1px solid var(--line);display:flex;gap:12px;flex-wrap:wrap;align-items:center;font-size:12px;' });
      svcRow.append(el('span', { style: 'font-weight:700;color:var(--ink);' }, 'Activated Services:'));

      SERVICE_KEYS.forEach(svc => {
        let lbl = el('label', { style: 'display:inline-flex;align-items:center;gap:4px;cursor:pointer;color:var(--ink);' });
        let chk = el('input', { type: 'checkbox', checked: allowedList.includes(svc), value: svc });
        chk.onchange = async () => {
          let newAllowed = Array.from(svcRow.querySelectorAll('input:checked')).map(i => i.value);
          await api('/api/premium-subscriber-services', 'POST', { telegram_id: u.telegram_id, allowed_services: newAllowed });
        };
        lbl.append(chk, el('span', {}, svc));
        svcRow.append(lbl);
      });

      card.append(topRow, svcRow);
      container.append(card);
    });
  } catch (err) {
    console.error('Failed to load premium users:', err);
  }
}

if ($('#btnAddPremUser')) {
  $('#btnAddPremUser').onclick = async () => {
    let tid = ($('#newPremTid').value || '').trim();
    let name = ($('#newPremName').value || '').trim();
    if (!tid) return alert('Please enter a Telegram User ID.');
    
    let selectedServices = Array.from(document.querySelectorAll('.new-prem-svc:checked')).map(cb => cb.value);

    try {
      await api('/api/premium-subscriber-add', 'POST', {
        telegram_id: tid,
        name: name || `User ${tid}`,
        allowed_services: selectedServices
      });
      $('#newPremTid').value = '';
      $('#newPremName').value = '';
      alert(`✅ Premium user ${tid} added successfully!`);
      await loadPremiumUsers();
    } catch (err) {
      alert('Add failed: ' + err.message);
    }
  };
}

refresh();

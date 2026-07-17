let _chatInited = false;
let _composing = false;
let _sending = false;
let _attachedFile = null;
let _currentSessionId = null;
let _timerId = null;

// Fake Prompts Library for "/"
const PROMPTS = [
  {title: 'Translate to English', desc: 'Translate the following text to professional English.', content: 'Please translate the following text to professional English:\n\n'},
  {title: 'Code Review', desc: 'Review the following code and suggest improvements.', content: 'Please review the following code, point out any bugs or security issues, and suggest improvements:\n\n'},
  {title: 'Summarize', desc: 'Provide a brief summary of the text.', content: 'Please provide a brief summary of the following text:\n\n'}
];
let promptSelectedIndex = 0;

function showTab(t) {
  document.getElementById('page-chat').classList.remove('active');
  document.getElementById('page-schedule').classList.remove('active');
  document.getElementById('page-' + t).classList.add('active');
  if (t === 'chat' && !_chatInited) initChat();
}

function toggleSidebar() {
  const sb = document.getElementById('sidebar');
  sb.style.display = sb.style.display === 'none' ? 'flex' : 'none';
}

function loadSessions() {
  pywebview.api.list_sessions().then(sessions => {
    const list = document.getElementById('session-list');
    list.innerHTML = '';
    sessions.forEach(s => {
      const btn = document.createElement('button');
      btn.className = 'nav-item' + (s.id === _currentSessionId ? ' active' : '');
      btn.innerHTML = `<span>💬 ${s.title}</span><span class="del-btn" title="Delete">🗑️</span>`;
      btn.onclick = (e) => {
        if (e.target.closest('.del-btn')) {
          e.stopPropagation();
          pywebview.api.delete_session(s.id).then(() => {
            if (s.id === _currentSessionId) newChat();
            else loadSessions();
          });
        } else {
          loadSession(s.id);
        }
      };
      list.appendChild(btn);
    });
  });
}

function loadSession(id) {
  pywebview.api.load_session(id).then(r => {
    if (r.error) return alert(r.error);
    _currentSessionId = id;
    showTab('chat');
    clearMessagesUI();
    r.history.forEach(msg => {
      if (msg.role === 'user') appendUserUI(msg.content);
      else if (msg.role === 'assistant') appendAssistantUI(msg.content);
    });
    if (r.model) document.getElementById('model-select').value = r.model;
    loadSessions(); // update active state
    scrollBottom();
  });
}

function newChat() {
  pywebview.api.clear_history().then(() => {
    _currentSessionId = null;
    clearMessagesUI();
    loadSessions();
    showTab('chat');
  });
}

function initChat() {
  _chatInited = true;
  pywebview.api.list_models().then(models => {
    const sel = document.getElementById('model-select');
    sel.innerHTML = '';
    models.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m; opt.textContent = m;
      sel.appendChild(opt);
    });
    pywebview.api.current_model().then(cur => { sel.value = cur; });
  });
  
  loadSessions();
  
  const ta = document.getElementById('chat-input');
  ta.addEventListener('compositionstart', () => { _composing = true; });
  ta.addEventListener('compositionend', () => { _composing = false; });
  ta.addEventListener('input', () => autoResize(ta));
}

function autoResize(ta) {
  ta.style.height = 'auto';
  ta.style.height = Math.min(ta.scrollHeight, 200) + 'px';
}

function handleInput() {
  const ta = document.getElementById('chat-input');
  const dd = document.getElementById('prompts-dropdown');
  const val = ta.value;
  if (val.startsWith('/')) {
    const q = val.substring(1).toLowerCase();
    const filtered = PROMPTS.filter(p => p.title.toLowerCase().includes(q));
    if (filtered.length > 0) {
      dd.style.display = 'block';
      dd.innerHTML = '';
      filtered.forEach((p, i) => {
        const div = document.createElement('div');
        div.className = 'prompt-item' + (i === promptSelectedIndex ? ' selected' : '');
        div.innerHTML = `<div class="prompt-title">${p.title}</div><div class="prompt-desc">${p.desc}</div>`;
        div.onclick = () => {
          ta.value = p.content;
          dd.style.display = 'none';
          ta.focus();
          autoResize(ta);
        };
        dd.appendChild(div);
      });
    } else {
      dd.style.display = 'none';
    }
  } else {
    dd.style.display = 'none';
  }
}

function onInputKey(e) {
  const dd = document.getElementById('prompts-dropdown');
  if (dd.style.display === 'block') {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      const items = dd.querySelectorAll('.prompt-item');
      if (items.length === 0) return;
      items[promptSelectedIndex].classList.remove('selected');
      if (e.key === 'ArrowDown') promptSelectedIndex = (promptSelectedIndex + 1) % items.length;
      else promptSelectedIndex = (promptSelectedIndex - 1 + items.length) % items.length;
      items[promptSelectedIndex].classList.add('selected');
      items[promptSelectedIndex].scrollIntoView({block: 'nearest'});
      return;
    }
    if (e.key === 'Enter') {
      e.preventDefault();
      dd.querySelectorAll('.prompt-item')[promptSelectedIndex].click();
      return;
    }
  }
  
  if (e.key === 'Enter' && !e.shiftKey && !_composing) {
    e.preventDefault();
    sendMessage();
  }
}

function onModelChange() {
  const m = document.getElementById('model-select').value;
  pywebview.api.set_model(m);
}

function openFile() {
  pywebview.api.open_file_dialog().then(path => {
    if (path) {
      _attachedFile = path;
      document.getElementById('file-name').textContent = path.split('\\').pop().split('/').pop();
      document.getElementById('file-preview').style.display = 'inline-block';
    }
  });
}

function clearFile() {
  _attachedFile = null;
  document.getElementById('file-preview').style.display = 'none';
}

function sendMessage() {
  if (_sending) return;
  const ta = document.getElementById('chat-input');
  const text = ta.value.trim();
  if (!text) return;

  _sending = true;
  document.getElementById('chat-send').disabled = true;
  ta.value = '';
  autoResize(ta);
  document.getElementById('prompts-dropdown').style.display = 'none';

  appendUserUI(text + (_attachedFile ? '\n[📎 ' + document.getElementById('file-name').textContent + ']' : ''));
  document.getElementById('chat-typing').style.display = 'block';
  
  const timerSpan = document.getElementById('chat-timer');
  timerSpan.textContent = '0';
  let elapsed = 0;
  _timerId = setInterval(() => { elapsed++; timerSpan.textContent = elapsed; }, 1000);
  scrollBottom();

  const fileToSend = _attachedFile;
  clearFile();

  pywebview.api.send_message(text, fileToSend).then(result => {
    clearInterval(_timerId);
    document.getElementById('chat-typing').style.display = 'none';
    _sending = false;
    document.getElementById('chat-send').disabled = false;

    if (result.error) {
      appendAssistantUI('⚠ Error: ' + result.error);
    } else {
      appendAssistantUI(result.content);
      if (result.degraded) {
         // Optionally append degraded UI
      }
    }
    loadSessions(); // refresh history list
    scrollBottom();
    ta.focus();
  });
}

function clearMessagesUI() {
  document.getElementById('chat-messages').innerHTML = '';
}

function appendUserUI(text) {
  const el = document.createElement('div');
  el.className = 'msg msg-user';
  const content = document.createElement('div');
  content.className = 'msg-content';
  content.innerHTML = `<div class="avatar avatar-user">U</div><div class="bubble"></div>`;
  const bubble = content.querySelector('.bubble');
  renderMarkdownLite(text, bubble);
  el.appendChild(content);
  document.getElementById('chat-messages').appendChild(el);
}

function appendAssistantUI(text) {
  const el = document.createElement('div');
  el.className = 'msg msg-assistant';
  const content = document.createElement('div');
  content.className = 'msg-content';
  content.innerHTML = `<div class="avatar avatar-ai">🐱</div><div class="bubble"></div>`;
  const bubble = content.querySelector('.bubble');
  renderMarkdownLite(text, bubble);
  
  const actions = document.createElement('div');
  actions.className = 'msg-actions';
  
  if (text.includes('# Slide')) {
    const pptBtn = document.createElement('button');
    pptBtn.innerHTML = '📽️ PPT';
    pptBtn.title = 'Export to PowerPoint';
    pptBtn.onclick = () => {
      pptBtn.innerHTML = '⌛';
      pywebview.api.export_ppt(text).then(r => {
        pptBtn.innerHTML = r.error ? '⚠' : '✓';
      });
    };
    actions.appendChild(pptBtn);
  }
  
  const copyBtn = document.createElement('button');
  copyBtn.innerHTML = '📋';
  copyBtn.title = 'Copy response';
  copyBtn.onclick = () => {
    navigator.clipboard.writeText(text).then(() => {
      copyBtn.innerHTML = '✓';
      setTimeout(() => copyBtn.innerHTML = '📋', 2000);
    });
  };
  actions.appendChild(copyBtn);
  
  bubble.appendChild(actions);
  el.appendChild(content);
  document.getElementById('chat-messages').appendChild(el);
}

function scrollBottom() {
  const c = document.getElementById('chat-messages');
  c.scrollTop = c.scrollHeight;
}

function renderMarkdownLite(text, container) {
  const parts = text.split(/```(.*?)[\r\n]+([\s\S]*?)```/g);
  for (let i = 0; i < parts.length; i++) {
    if (i % 3 === 0) {
      if (parts[i]) {
        const div = document.createElement('div');
        // Simple bold rendering
        let t = parts[i].replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        div.innerHTML = t.replace(/\n/g, '<br>');
        div.style.marginBottom = '8px';
        container.appendChild(div);
      }
    } else if (i % 3 === 1) {
      const lang = parts[i].trim();
      const code = parts[i+1];
      
      const preWrapper = document.createElement('div');
      
      const header = document.createElement('div');
      header.className = 'code-header';
      header.innerHTML = `<span>${lang}</span>`;
      
      const copyCodeBtn = document.createElement('button');
      copyCodeBtn.innerHTML = '📋 Copy Code';
      copyCodeBtn.onclick = () => {
        navigator.clipboard.writeText(code).then(() => {
          copyCodeBtn.innerHTML = '✓ Copied!';
          setTimeout(() => copyCodeBtn.innerHTML = '📋 Copy Code', 2000);
        });
      };
      header.appendChild(copyCodeBtn);
      
      const pre = document.createElement('pre');
      const codeEl = document.createElement('code');
      if (lang) codeEl.className = 'language-' + lang;
      codeEl.textContent = code;
      pre.appendChild(codeEl);
      
      preWrapper.appendChild(header);
      preWrapper.appendChild(pre);
      container.appendChild(preWrapper);
      
      // Apply syntax highlighting
      try { hljs.highlightElement(codeEl); } catch (e) {}
      
      i++; // skip the code part
    }
  }
}

function exportChat() {
  pywebview.api.export_chat().then(r => {
    alert(r.error ? 'Export failed: ' + r.error : 'Exported to: ' + r.path);
  });
}

// Schedule logic bindings...
function syncFields() {
  const t = document.getElementById('f-type').value;
  document.getElementById('f-day-wrap').style.display = t === 'weekly' ? '' : 'none';
  document.getElementById('f-time-wrap').style.display = t === 'hourly' ? 'none' : '';
  document.getElementById('f-minute-wrap').style.display = t === 'hourly' ? '' : 'none';
}
function submitForm() {
  const t = document.getElementById('f-type').value;
  const item = {
    id: document.getElementById('f-id').value || undefined,
    title: document.getElementById('f-title').value.trim(),
    type: t,
    lead_min: parseInt(document.getElementById('f-lead').value || '0', 10),
    enabled: true,
  };
  if (t === 'weekly') item.day = document.getElementById('f-day').value;
  if (t !== 'hourly') item.time = document.getElementById('f-time').value;
  if (t === 'hourly') item.minute = parseInt(document.getElementById('f-minute').value, 10);
  pywebview.api.upsert_schedule(item).then(r => {
    document.getElementById('f-msg').innerText = r.error ? ('⚠ ' + r.error) : 'Saved!';
    if (!r.error) { renderSchedule({items: r.items, errors: []}); resetForm(); }
  });
}
function renderSchedule(data) {
  const tb = document.getElementById('list');
  tb.innerHTML = '';
  for (const it of data.items) {
    const tr = document.createElement('tr');
    tr.className = 'rowline';
    tr.innerHTML = `<td><input type="checkbox" ${it.enabled ? 'checked' : ''}></td>
      <td>${it.title}</td><td>${it.type} ${it.time || ''}</td>
      <td><button class="del">Delete</button></td>`;
    tr.querySelector('input').onclick = (e) => {
      e.stopPropagation();
      it.enabled = e.target.checked;
      pywebview.api.upsert_schedule(it).then(r => renderSchedule({items: r.items, errors: []}));
    };
    tr.querySelector('.del').onclick = (e) => {
      e.stopPropagation();
      pywebview.api.delete_schedule(it.id).then(r => renderSchedule({items: r.items, errors: []}));
    };
    tr.onclick = () => {
      document.getElementById('f-id').value = it.id;
      document.getElementById('f-title').value = it.title;
      document.getElementById('f-type').value = it.type;
      syncFields();
    };
    tb.appendChild(tr);
  }
}
function resetForm() {
  document.getElementById('f-id').value = '';
  document.getElementById('f-title').value = '';
  document.getElementById('f-msg').innerText = '';
}

window.addEventListener('pywebviewready', () => {
  try {
    syncFields();
    pywebview.api.get_tab().then(t => showTab(t)).catch(e => alert('Error in get_tab: ' + e));
    pywebview.api.list_schedules().then(renderSchedule).catch(e => alert('Error in list_schedules: ' + e));
  } catch (err) {
    alert('pywebviewready error: ' + err);
  }
});

window.addEventListener('error', function(e) {
  alert('JS Error: ' + e.message + ' at ' + e.filename + ':' + e.lineno);
});
window.addEventListener('unhandledrejection', function(e) {
  alert('Unhandled Rejection: ' + e.reason);
});
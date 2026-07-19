let _chatInited = false;
let _composing = false;
let _sending = false;
let _attachedFile = null;
let _currentSessionId = null;
let _timerId = null;
let _editingEnabled = true;
let _currentDocumentId = null;
let _workflowPollId = null;
let _workflowStarting = false;

// Fake Prompts Library for "/"
const PROMPTS = [
  {title: 'Translate to English', desc: 'Translate the following text to professional English.', content: 'Please translate the following text to professional English:\n\n'},
  {title: 'Code Review', desc: 'Review the following code and suggest improvements.', content: 'Please review the following code, point out any bugs or security issues, and suggest improvements:\n\n'},
  {title: 'Summarize', desc: 'Provide a brief summary of the text.', content: 'Please provide a brief summary of the following text:\n\n'}
];
let promptSelectedIndex = 0;

function escapeHtml(value) {
  const el = document.createElement('div');
  el.textContent = String(value);
  return el.innerHTML;
}

function showTab(t) {
  document.querySelectorAll('.page').forEach(page => page.classList.remove('active'));
  document.querySelectorAll('.nav-item-static').forEach(item => item.classList.remove('active'));
  document.getElementById('page-' + t).classList.add('active');
  const nav = document.getElementById('nav-' + t);
  if (nav) nav.classList.add('active');
  if (t === 'chat' && !_chatInited) initChat();
  if (t === 'documents') {
    loadDocuments();
    pywebview.api.latest_workflow_run().then(renderWorkflowRun);
  }
  if (t === 'settings') loadToolboxSettings();
}

function chooseDocument() {
  pywebview.api.open_document_dialog().then(path => {
    if (!path) return;
    document.getElementById('document-status').textContent = '正在建立本機索引…';
    pywebview.api.ingest_document(path).then(result => {
      document.getElementById('document-status').textContent = result.error || '已完成分析';
      if (result.document) {
        _currentDocumentId = result.document.id;
        document.getElementById('document-question-box').style.display = '';
        document.getElementById('document-actions').style.display = '';
      }
      loadDocuments();
    });
  });
}

function loadDocuments() {
  pywebview.api.list_documents().then(documents => {
    const list = document.getElementById('document-list');
    const compare = document.getElementById('compare-document');
    list.innerHTML = '';
    compare.innerHTML = '<option value="">選擇另一份文件</option>';
    documents.forEach(doc => {
      if (doc.id !== _currentDocumentId) {
        const option = document.createElement('option');
        option.value = doc.id;
        option.textContent = doc.name;
        compare.appendChild(option);
      }
      const row = document.createElement('div');
      row.className = 'document-row' + (doc.id === _currentDocumentId ? ' active' : '');
      row.innerHTML = `<button class="document-select">📄 ${escapeHtml(doc.name)} <small>${doc.chunk_count} 個區塊</small></button><button class="document-remove" title="只移除本機索引">×</button>`;
      row.querySelector('.document-select').onclick = () => {
        _currentDocumentId = doc.id;
        document.getElementById('document-question-box').style.display = '';
        document.getElementById('document-actions').style.display = '';
        document.getElementById('document-status').textContent = `文件：${doc.name}，已完成分析`;
        loadDocuments();
      };
      row.querySelector('.document-remove').onclick = () => pywebview.api.remove_document(doc.id).then(() => {
        if (_currentDocumentId === doc.id) {
          _currentDocumentId = null;
          document.getElementById('document-question-box').style.display = 'none';
          document.getElementById('document-actions').style.display = 'none';
        }
        loadDocuments();
      });
      list.appendChild(row);
    });
  });
}

function askDocument() {
  const input = document.getElementById('document-question');
  const question = input.value.trim();
  if (!_currentDocumentId || !question) return;
  const answer = document.getElementById('document-answer');
  answer.textContent = '正在本機檢索…';
  pywebview.api.query_document(_currentDocumentId, question).then(renderDocumentResult);
}

function runDocumentAction(action) {
  if (!_currentDocumentId) return;
  const answer = document.getElementById('document-answer');
  answer.textContent = '正在依文件來源整理…';
  pywebview.api.document_action(_currentDocumentId, action).then(renderDocumentResult);
}

function compareDocuments() {
  const otherId = document.getElementById('compare-document').value;
  if (!_currentDocumentId || !otherId) return;
  const answer = document.getElementById('document-answer');
  answer.textContent = '正在依兩份文件來源比較…';
  pywebview.api.compare_documents(_currentDocumentId, otherId).then(renderDocumentResult);
}

function useDocumentQuestion(question) {
  document.getElementById('document-question').value = question;
  askDocument();
}

function renderDocumentResult(result) {
  const answer = document.getElementById('document-answer');
    if (result.error) { answer.textContent = result.error; return; }
    answer.innerHTML = `<p>${escapeHtml(result.answer)}</p>`;
    const coverage = result.coverage;
    if (coverage && coverage.total_chunks && !coverage.complete) {
      const note = document.createElement('p');
      note.className = 'document-coverage-note';
      note.textContent = `此結果抽樣涵蓋 ${coverage.included_chunks}/${coverage.total_chunks} 個文件區塊，非完整文件結論。`;
      answer.appendChild(note);
    }
    (result.sources || []).forEach(item => {
      const source = item.source;
      const card = document.createElement('div');
      card.className = 'document-source';
      card.innerHTML = `<strong>📄 ${escapeHtml(source.document_name)} · ${escapeHtml(source.locator || '來源定位不可用')}</strong><p></p>`;
      card.querySelector('p').textContent = item.excerpt;
      answer.appendChild(card);
    });
}

function startMeetingPack() {
  if (!_currentDocumentId || _workflowStarting) return;
  _workflowStarting = true;
  document.getElementById('meeting-pack-start').disabled = true;
  const translate = document.getElementById('meeting-pack-translate').checked;
  const box = document.getElementById('document-workflow');
  box.textContent = '正在建立 Workflow…';
  pywebview.api.start_document_meeting_pack(_currentDocumentId, translate).then(run => {
    renderWorkflowRun(run);
    if (run.error) return;
    if (_workflowPollId) clearInterval(_workflowPollId);
    _workflowPollId = setInterval(() => {
      pywebview.api.get_workflow_run(run.run_id).then(renderWorkflowRun);
    }, 700);
  }).catch(error => {
    box.textContent = 'Workflow 啟動失敗：' + error;
    _workflowStarting = false;
    document.getElementById('meeting-pack-start').disabled = false;
  });
}

function cancelWorkflow(runId) {
  pywebview.api.cancel_workflow_run(runId).then(renderWorkflowRun);
}

function retryWorkflow(runId) {
  if (_workflowStarting) return;
  _workflowStarting = true;
  pywebview.api.retry_workflow_run(runId).then(run => {
    renderWorkflowRun(run);
    if (run.error) {
      _workflowStarting = false;
      return;
    }
    if (_workflowPollId) clearInterval(_workflowPollId);
    _workflowPollId = setInterval(() => {
      pywebview.api.get_workflow_run(run.run_id).then(renderWorkflowRun);
    }, 700);
  }).catch(error => {
    document.getElementById('document-workflow').textContent = '重新執行失敗：' + error;
    _workflowStarting = false;
  });
}

function clearWorkflowHistory() {
  if (!window.confirm('清除已結束的 Workflow 與 Markdown 成果？執行中的工作會保留。')) return;
  pywebview.api.clear_workflow_history().then(result => {
    const box = document.getElementById('document-workflow');
    if (result.error) { box.textContent = result.error; return; }
    box.textContent = `已清除 ${result.removed_runs} 筆 Run、${result.removed_artifacts} 個成果；保留 ${result.active_runs_preserved} 筆執行中工作。`;
  });
}

function renderWorkflowRun(run) {
  const box = document.getElementById('document-workflow');
  if (!run || run.error) {
    if (run && run.error !== '尚無 Workflow 執行紀錄。') box.textContent = run.error;
    _workflowStarting = false;
    const start = document.getElementById('meeting-pack-start');
    if (start) start.disabled = false;
    return;
  }
  box.innerHTML = '';
  const title = document.createElement('strong');
  title.textContent = `文件會議包 · ${run.status}`;
  box.appendChild(title);
  const steps = document.createElement('div');
  steps.className = 'workflow-steps';
  (run.steps || []).forEach(step => {
    const row = document.createElement('div');
    row.textContent = `${step.status === 'completed' ? '✓' : step.status === 'failed' ? '✕' : step.status === 'running' ? '●' : '○'} ${step.id}${step.error ? '：' + step.error : ''}`;
    steps.appendChild(row);
  });
  box.appendChild(steps);
  const coverage = run.coverage;
  if (coverage && coverage.total_chunks) {
    const note = document.createElement('div');
    note.className = 'document-coverage-note';
    note.textContent = coverage.complete
      ? `來源涵蓋：${coverage.total_chunks}/${coverage.total_chunks} 個文件區塊（完整）`
      : `來源涵蓋：${coverage.included_chunks}/${coverage.total_chunks} 個文件區塊（抽樣，非完整結論）`;
    box.appendChild(note);
  }
  if ((run.sources || []).length) {
    const sourceTitle = document.createElement('div');
    sourceTitle.className = 'workflow-source-title';
    sourceTitle.textContent = '來源';
    box.appendChild(sourceTitle);
    (run.sources || []).forEach(source => {
      const row = document.createElement('div');
      row.className = 'workflow-source';
      row.textContent = `📄 ${source.document_name} · ${source.locator || '來源定位不可用'}`;
      box.appendChild(row);
    });
  }
  (run.artifacts || []).forEach(artifact => {
    const path = document.createElement('div');
    path.className = 'workflow-artifact';
    path.textContent = `${artifact.status === 'complete' ? '成果' : '部分成果'}：${artifact.path}`;
    box.appendChild(path);
  });
  if (run.status === 'pending' || run.status === 'running') {
    const start = document.getElementById('meeting-pack-start');
    if (start) start.disabled = true;
    const cancel = document.createElement('button');
    cancel.className = 'secondary';
    cancel.textContent = '取消';
    cancel.onclick = () => cancelWorkflow(run.run_id);
    box.appendChild(cancel);
  } else if (run.status === 'failed' || run.status === 'cancelled') {
    _workflowStarting = false;
    const start = document.getElementById('meeting-pack-start');
    if (start) start.disabled = false;
    if (_workflowPollId) {
      clearInterval(_workflowPollId);
      _workflowPollId = null;
    }
    const retry = document.createElement('button');
    retry.className = 'secondary';
    retry.textContent = '重新執行';
    retry.onclick = () => retryWorkflow(run.run_id);
    box.appendChild(retry);
  } else if (_workflowPollId) {
    _workflowStarting = false;
    const start = document.getElementById('meeting-pack-start');
    if (start) start.disabled = false;
    clearInterval(_workflowPollId);
    _workflowPollId = null;
  }
}

function toggleSidebar() {
  const sb = document.getElementById('sidebar');
  const handle = document.getElementById('sidebar-resize');
  sb.classList.toggle('collapsed');
  if (sb.classList.contains('collapsed')) {
    handle.style.display = 'none';
  } else {
    handle.style.display = '';
  }
}

// Sidebar resize drag
(function() {
  const handle = document.getElementById('sidebar-resize');
  if (!handle) return;
  const sb = document.getElementById('sidebar');
  let dragging = false;
  let startX = 0;
  let startW = 0;

  handle.addEventListener('mousedown', function(e) {
    dragging = true;
    startX = e.clientX;
    startW = sb.offsetWidth;
    handle.classList.add('dragging');
    sb.style.transition = 'none';
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    e.preventDefault();
  });

  document.addEventListener('mousemove', function(e) {
    if (!dragging) return;
    let newW = startW + (e.clientX - startX);
    if (newW < 140) newW = 140;
    if (newW > 500) newW = 500;
    sb.style.width = newW + 'px';
  });

  document.addEventListener('mouseup', function() {
    if (!dragging) return;
    dragging = false;
    handle.classList.remove('dragging');
    sb.style.transition = '';
    document.body.style.cursor = '';
    document.body.style.userSelect = '';
  });
})();

function loadSessions() {
  pywebview.api.list_sessions().then(sessions => {
    const list = document.getElementById('session-list');
    list.innerHTML = '';
    sessions.forEach(s => {
      const btn = document.createElement('button');
      btn.className = 'nav-item' + (s.id === _currentSessionId ? ' active' : '');
      btn.innerHTML = `<span>💬 ${escapeHtml(s.title)}</span><span class="del-btn" title="Delete">🗑️</span>`;
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
    updateEmptyState();
    // Saved sessions contain a concrete model id, while this selector contains
    // user-facing routing modes. Keep the current mode instead of blanking it.
    pywebview.api.current_model_mode().then(mode => { document.getElementById('model-select').value = mode; });
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
  pywebview.api.list_model_modes().then(modes => {
    const sel = document.getElementById('model-select');
    sel.innerHTML = '';
    modes.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m.id; opt.textContent = m.label;
      sel.appendChild(opt);
    });
    pywebview.api.current_model_mode().then(cur => { sel.value = cur; });
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
  const mode = document.getElementById('model-select').value;
  pywebview.api.set_model_mode(mode).then(result => {
    if (result.error) alert(result.error);
  });
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
  document.querySelectorAll('#chat-messages .msg').forEach(msg => msg.remove());
  updateEmptyState();
}

function updateEmptyState() {
  const messages = document.getElementById('chat-messages');
  const empty = document.getElementById('empty-state');
  if (!empty) return;
  empty.classList.toggle('hidden', messages.querySelector('.msg') !== null);
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
  updateEmptyState();
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
  updateEmptyState();
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
        let t = escapeHtml(parts[i]).replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
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
      header.innerHTML = `<span>${escapeHtml(lang)}</span>`;
      
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
    enabled: _editingEnabled,
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
      <td>${escapeHtml(it.title)}</td><td>${escapeHtml(it.type)} ${escapeHtml(it.time || '')}</td>
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
      document.getElementById('f-lead').value = it.lead_min;
      document.getElementById('f-day').value = it.day || 'MO';
      document.getElementById('f-time').value = it.time || '09:00';
      document.getElementById('f-minute').value = it.minute ?? 0;
      _editingEnabled = it.enabled;
      syncFields();
    };
    tb.appendChild(tr);
  }
}
function resetForm() {
  document.getElementById('f-id').value = '';
  document.getElementById('f-title').value = '';
  document.getElementById('f-msg').innerText = '';
  _editingEnabled = true;
}

function runJsonTool(action) {
  const input = document.getElementById('json-input').value;
  const query = document.getElementById('json-search').value;
  const status = document.getElementById('json-status');
  status.textContent = '處理中…';
  pywebview.api.json_tool(input, action, query).then(result => {
    if (result.error) {
      status.textContent = result.error;
      if (typeof result.line === 'number') document.getElementById('json-input').focus();
      return;
    }
    status.textContent = result.text || 'JSON 格式正確。';
    if (action === 'format' || action === 'minify') document.getElementById('json-output').value = result.text;
    if (result.data !== undefined) renderJsonTree(result.data, '$');
    if (action === 'search') renderJsonMatches(result.matches || []);
  }).catch(error => { status.textContent = 'JSON 工具失敗：' + error; });
}

function renderJsonMatches(matches) {
  const container = document.getElementById('json-matches');
  container.innerHTML = '';
  if (!matches.length) { container.textContent = '沒有相符項目。'; return; }
  matches.forEach(match => {
    const button = document.createElement('button');
    button.className = 'json-match';
    button.textContent = `${match.path}  ·  ${match.preview}`;
    button.onclick = () => { document.getElementById('json-path').textContent = match.path; };
    container.appendChild(button);
  });
}

function renderJsonTree(value, rootPath) {
  const container = document.getElementById('json-tree');
  container.innerHTML = '';
  container.appendChild(jsonTreeNode(value, rootPath, 'root'));
}

function expandJsonTree() {
  document.querySelectorAll('#json-tree details').forEach(node => { node.open = true; });
}

function collapseJsonTree() {
  document.querySelectorAll('#json-tree details').forEach(node => { node.open = false; });
}

function jsonTreeNode(value, path, name) {
  const scalar = value === null || typeof value !== 'object';
  const label = document.createElement('span');
  const valueType = value === null ? 'null' : (Array.isArray(value) ? 'array' : typeof value);
  label.className = scalar ? `json-scalar json-${valueType}` : `json-key json-${valueType}`;
  label.textContent = scalar ? `${name}: ${JSON.stringify(value)}` : `${name} ${Array.isArray(value) ? `[${value.length}]` : `{${Object.keys(value).length}}`}`;
  label.onclick = () => { document.getElementById('json-path').textContent = path; };
  if (scalar) return label;
  const details = document.createElement('details');
  details.open = path === '$';
  const summary = document.createElement('summary');
  summary.appendChild(label);
  details.appendChild(summary);
  const children = document.createElement('div');
  children.className = 'json-children';
  if (Array.isArray(value)) {
    value.forEach((child, index) => children.appendChild(jsonTreeNode(child, `${path}[${index}]`, `[${index}]`)));
  } else {
    Object.keys(value).forEach(key => children.appendChild(jsonTreeNode(value[key], `${path}[${JSON.stringify(key)}]`, key)));
  }
  details.appendChild(children);
  return details;
}

function copyText(value, status) {
  if (!value) { if (status) status.textContent = '沒有可複製的內容。'; return; }
  const fallback = () => {
    const area = document.createElement('textarea');
    area.value = value; document.body.appendChild(area); area.select();
    document.execCommand('copy'); area.remove();
  };
  const copy = navigator.clipboard && navigator.clipboard.writeText ? navigator.clipboard.writeText(value) : Promise.resolve().then(fallback);
  copy.then(() => { if (status) status.textContent = '已複製。'; }).catch(() => { fallback(); if (status) status.textContent = '已複製。'; });
}

function copyJsonResult() {
  copyText(document.getElementById('json-output').value, document.getElementById('json-status'));
}

function translateText() {
  const text = document.getElementById('translation-input').value;
  const status = document.getElementById('translation-status');
  status.textContent = '翻譯中…';
  const options = {
    target: document.getElementById('translation-target').value,
    mode: document.getElementById('translation-mode').value,
    preserve_code: document.getElementById('translation-code').checked,
    preserve_tables: document.getElementById('translation-table').checked,
    use_glossary: document.getElementById('translation-glossary').checked,
  };
  pywebview.api.translate_text(text, options).then(result => {
    if (result.error) { status.textContent = result.error; return; }
    document.getElementById('translation-output').value = result.content || '';
    status.textContent = result.model ? `完成（${result.model}）` : '完成。';
  }).catch(error => { status.textContent = '翻譯失敗：' + error; });
}

function copyTranslation() {
  copyText(document.getElementById('translation-output').value, document.getElementById('translation-status'));
}

function loadToolboxSettings() {
  pywebview.api.toolbox_settings().then(settings => {
    document.getElementById('llm-provider').value = settings.provider || 'company';
    document.getElementById('llm-base-url').value = settings.base_url || '';
    document.getElementById('llm-model').value = settings.model || '';
    document.getElementById('llm-timeout').value = settings.request_timeout || 120;
    const modes = settings.model_modes || {}, tasks = settings.task_models || {};
    ['fast', 'quality', 'code', 'translation'].forEach(key => { document.getElementById('mode-' + key).value = modes[key] || ''; });
    ['chat', 'translation', 'document', 'code'].forEach(key => { document.getElementById('task-' + key).value = tasks[key] || ''; });
    document.getElementById('task-error-analysis').value = tasks.error_analysis || '';
  }).catch(error => { document.getElementById('settings-status').textContent = '無法讀取設定：' + error; });
}

function saveToolboxSettings() {
  const payload = {
    provider: document.getElementById('llm-provider').value,
    base_url: document.getElementById('llm-base-url').value,
    model: document.getElementById('llm-model').value,
    model_modes: {}, task_models: {},
  };
  const timeout = document.getElementById('llm-timeout').value.trim();
  if (timeout) payload.request_timeout = timeout;
  ['fast', 'quality', 'code', 'translation'].forEach(key => { payload.model_modes[key] = document.getElementById('mode-' + key).value; });
  ['chat', 'translation', 'document', 'code'].forEach(key => { payload.task_models[key] = document.getElementById('task-' + key).value; });
  payload.task_models.error_analysis = document.getElementById('task-error-analysis').value;
  const status = document.getElementById('settings-status');
  status.textContent = '儲存中…';
  pywebview.api.save_toolbox_settings(payload).then(result => {
    if (result.error) { status.textContent = result.error; return; }
    status.textContent = '已儲存。';
    pywebview.api.current_model_mode().then(mode => { document.getElementById('model-select').value = mode; });
  }).catch(error => { status.textContent = '儲存失敗：' + error; });
}

function runHealthCheck() {
  const status = document.getElementById('settings-status');
  status.textContent = '正在測試模型連線…';
  pywebview.api.health_check().then(result => {
    status.textContent = result.online ? `模型在線（${result.model || '預設模型'}）` : (result.error || '模型離線。');
  }).catch(error => { status.textContent = '連線測試失敗：' + error; });
}

function useStarter(text) {
  showTab('chat');
  const input = document.getElementById('chat-input');
  input.value = text;
  input.focus();
  autoResize(input);
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

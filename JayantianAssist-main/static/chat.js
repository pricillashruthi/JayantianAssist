const log = document.getElementById('log');
const form = document.getElementById('form');
const input = document.getElementById('input');
const chips = document.getElementById('chips');
const micBtn = document.getElementById('mic-btn');
const exportBtn = document.getElementById('export-btn');
const clearBtn = document.getElementById('clear-btn');
const themeBtn = document.getElementById('theme-btn');
const profileBtn = document.getElementById('profile-btn');
const portalBtn = document.getElementById('portal-btn');
const profileModal = document.getElementById('profile-modal');
const portalModal = document.getElementById('portal-modal');

// Escaping and basic Markdown formatting (bold, links, newlines)
function render(text) {
  const esc = s => s.replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
  return esc(text)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/(https?:\/\/[^\s<)]+)/g, '<a href="$1" target="_blank" rel="noopener noreferrer">$1</a>')
    .replace(/\n/g, '<br>');
}

function sourcesHtml(sources) {
  if (!sources || !sources.length) return '';
  return '<div class="src">Source: ' + sources.map(s =>
    `<a href="${encodeURI(s.url)}" target="_blank" rel="noopener noreferrer">${s.title.replace(/</g,'&lt;')}</a>`
  ).join(' · ') + '</div>';
}

// Strip HTML for Text-to-Speech and Clipboard
function stripHtml(html) {
  const tmp = document.createElement('div');
  tmp.innerHTML = html;
  return tmp.textContent || tmp.innerText || '';
}

// Create message action buttons (Read aloud, Copy, Feedback)
function createActions(rawText) {
  const actions = document.createElement('div');
  actions.className = 'msg-actions';

  // Read aloud (TTS)
  const speakBtn = document.createElement('button');
  speakBtn.type = 'button';
  speakBtn.className = 'msg-act-btn';
  speakBtn.innerHTML = '🔊 Read';
  speakBtn.title = 'Listen to answer';
  speakBtn.addEventListener('click', () => {
    if (!window.speechSynthesis) return;
    if (speechSynthesis.speaking) {
      speechSynthesis.cancel();
      speakBtn.innerHTML = '🔊 Read';
      speakBtn.classList.remove('active');
      return;
    }
    const clean = stripHtml(rawText);
    const utter = new SpeechSynthesisUtterance(clean);
    utter.rate = 1.0;
    utter.onend = () => {
      speakBtn.innerHTML = '🔊 Read';
      speakBtn.classList.remove('active');
    };
    utter.onerror = () => {
      speakBtn.innerHTML = '🔊 Read';
      speakBtn.classList.remove('active');
    };
    speakBtn.innerHTML = '⏹ Stop';
    speakBtn.classList.add('active');
    speechSynthesis.speak(utter);
  });

  // Copy to clipboard
  const copyBtn = document.createElement('button');
  copyBtn.type = 'button';
  copyBtn.className = 'msg-act-btn';
  copyBtn.innerHTML = '📋 Copy';
  copyBtn.title = 'Copy answer to clipboard';
  copyBtn.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(stripHtml(rawText));
      copyBtn.innerHTML = '✅ Copied!';
      setTimeout(() => { copyBtn.innerHTML = '📋 Copy'; }, 2000);
    } catch {
      copyBtn.innerHTML = '❌ Failed';
    }
  });

  // Helpful feedback (Thumbs Up / Down)
  const upBtn = document.createElement('button');
  upBtn.type = 'button';
  upBtn.className = 'msg-act-btn';
  upBtn.innerHTML = '👍';
  upBtn.title = 'Helpful';
  upBtn.addEventListener('click', () => {
    upBtn.classList.add('active');
    downBtn.classList.remove('active');
    upBtn.title = 'Thanks for your feedback!';
  });

  const downBtn = document.createElement('button');
  downBtn.type = 'button';
  downBtn.className = 'msg-act-btn';
  downBtn.innerHTML = '👎';
  downBtn.title = 'Not helpful';
  downBtn.addEventListener('click', () => {
    downBtn.classList.add('active');
    upBtn.classList.remove('active');
    downBtn.title = 'Thanks for your feedback!';
  });

  actions.append(speakBtn, copyBtn, upBtn, downBtn);
  return actions;
}

// Append a message to the chat log
function add(cls, html, rawText = '', sources = []) {
  const el = document.createElement('div');
  el.className = 'msg ' + cls;
  el.innerHTML = html;

  if (sources && sources.length) {
    el.innerHTML += sourcesHtml(sources);
  }

  if (cls.includes('bot') && !cls.includes('intro-msg') && !cls.includes('typing')) {
    el.appendChild(createActions(rawText || html));
  }

  log.appendChild(el);
  log.scrollTop = log.scrollHeight;
  return el;
}

// Animated typing indicator
function showTyping() {
  const el = document.createElement('div');
  el.id = 'typing-indicator';
  el.className = 'msg bot typing';
  el.innerHTML = '<span class="t-dot"></span><span class="t-dot"></span><span class="t-dot"></span>';
  log.appendChild(el);
  log.scrollTop = log.scrollHeight;
  return el;
}

function removeTyping() {
  const el = document.getElementById('typing-indicator');
  if (el) el.remove();
}

// Ask the bot
async function ask(text) {
  add('user', render(text));
  showTyping();

  try {
    const res = await fetch('/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-CSRF-Token': window.CSRF},
      body: JSON.stringify({message: text})
    });
    if (res.redirected || res.status === 401) { location.href = '/login'; return; }
    const data = await res.json();
    removeTyping();

    const ans = data.answer || data.error || 'Something went wrong.';
    add('bot', render(ans), ans, data.sources || []);
  } catch (e) {
    removeTyping();
    add('bot', 'Network error. Please check your connection and try again.');
  }
  log.scrollTop = log.scrollHeight;
}

// Load chat history from SQLite
async function loadHistory() {
  try {
    const res = await fetch('/api/history');
    if (!res.ok) return;
    const history = await res.json();
    if (history && history.length > 0) {
      log.innerHTML = '';
      history.forEach(m => {
        add(m.role, render(m.content), m.content, m.sources || []);
      });
    }
  } catch (err) {
    console.warn('Could not load chat history:', err);
  }
}

// Form submit
form.addEventListener('submit', e => {
  e.preventDefault();
  const t = input.value.trim();
  if (!t) return;
  input.value = '';
  ask(t);
});

// Starter prompt chips
chips.addEventListener('click', e => {
  if (e.target.tagName === 'BUTTON') {
    ask(e.target.textContent);
  }
});

// Voice Input (Speech-to-Text)
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
if (SpeechRecognition && micBtn) {
  const recognition = new SpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.lang = 'en-US';

  micBtn.addEventListener('click', () => {
    if (micBtn.classList.contains('recording')) {
      recognition.stop();
    } else {
      try {
        recognition.start();
      } catch (err) {
        recognition.stop();
      }
    }
  });

  recognition.onstart = () => {
    micBtn.classList.add('recording');
    micBtn.title = 'Listening... Speak now';
  };

  recognition.onresult = (e) => {
    const text = e.results[0][0].transcript;
    input.value = text;
    micBtn.classList.remove('recording');
    form.dispatchEvent(new Event('submit'));
  };

  recognition.onerror = () => {
    micBtn.classList.remove('recording');
    micBtn.title = 'Voice input (Click to speak)';
  };

  recognition.onend = () => {
    micBtn.classList.remove('recording');
    micBtn.title = 'Voice input (Click to speak)';
  };
} else if (micBtn) {
  micBtn.style.display = 'none';
}

// Clear chat history
if (clearBtn) {
  clearBtn.addEventListener('click', async () => {
    if (!confirm('Clear all conversation history?')) return;
    try {
      await fetch('/api/clear', {
        method: 'POST',
        headers: {'X-CSRF-Token': window.CSRF}
      });
      log.innerHTML = `<div class="msg bot intro-msg">
        Hi <strong>${window.USER_NAME ? window.USER_NAME.split(' ')[0] : 'there'}</strong>! 👋 Chat history cleared. Ask me anything about Kristu Jayanti University!
      </div>`;
    } catch {
      alert('Failed to clear chat. Please try again.');
    }
  });
}

// Export conversation as text file
if (exportBtn) {
  exportBtn.addEventListener('click', () => {
    const msgs = Array.from(log.querySelectorAll('.msg'));
    if (!msgs.length) {
      alert('No conversation to export.');
      return;
    }
    let content = `JayantianAssist Chat Export\nGenerated: ${new Date().toLocaleString()}\n${'='.repeat(45)}\n\n`;
    msgs.forEach(m => {
      const isUser = m.classList.contains('user');
      const sender = isUser ? (window.USER_NAME || 'You') : 'JayantianAssist';
      const text = stripHtml(m.innerHTML.split('<div class="msg-actions"')[0].split('<div class="src"')[0]).trim();
      if (text) {
        content += `[${sender}]:\n${text}\n\n`;
      }
    });

    const blob = new Blob([content], {type: 'text/plain;charset=utf-8'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `jayantianassist_chat_${new Date().toISOString().slice(0, 10)}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  });
}

// Modals Handling
function setupModal(triggerBtn, modalEl) {
  if (!triggerBtn || !modalEl) return;
  triggerBtn.addEventListener('click', () => modalEl.showModal());
  modalEl.addEventListener('click', (e) => {
    if (e.target === modalEl) modalEl.close();
  });
  modalEl.querySelectorAll('[data-close]').forEach(b => {
    b.addEventListener('click', () => modalEl.close());
  });
}

setupModal(profileBtn, profileModal);
setupModal(portalBtn, portalModal);

// Theme Toggle
if (themeBtn) {
  const updateIcon = () => {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    themeBtn.textContent = isDark ? '☀️' : '🌙';
  };
  updateIcon();
  themeBtn.addEventListener('click', () => {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('ja_theme', next);
    updateIcon();
  });
}

// Initialize on page load
loadHistory();

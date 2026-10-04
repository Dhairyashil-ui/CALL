// Astra AI Verification Dashboard & Voice Client

document.addEventListener('DOMContentLoaded', () => {
  // Initialize Lucide icons
  if (window.lucide) {
    window.lucide.createIcons();
  }

  // Visualizer initialization
  const visualizer = new window.AudioVisualizer('audio-visualizer');

  // State
  let candidatesData = [];
  let currentFilter = 'all';
  let isListening = false;
  let speechRecognition = null;
  const sessionId = 'web-session-' + Math.random().toString(36).substring(2, 9);

  // DOM Elements
  const chatStream = document.getElementById('chat-stream');
  const textInput = document.getElementById('text-input');
  const btnSend = document.getElementById('btn-send-message');
  const btnMic = document.getElementById('btn-mic-toggle');
  const voiceStateText = document.getElementById('voice-state-text');
  const candidateGrid = document.getElementById('candidate-grid');
  const candidateCount = document.getElementById('candidate-count');
  const searchInput = document.getElementById('candidate-search');
  const filterPills = document.querySelectorAll('.filter-pills .pill');
  const tabBtns = document.querySelectorAll('.tab-btn');
  const tabContents = document.querySelectorAll('.tab-content');
  const btnStartCall = document.getElementById('btn-start-call');
  const dialerPhoneInput = document.getElementById('dialer-phone-input');
  const dialerBaseUrl = document.getElementById('dialer-base-url');
  const dialerFeedback = document.getElementById('dialer-feedback');
  const modal = document.getElementById('candidate-modal');
  const btnCloseModal = document.getElementById('btn-close-modal');
  const modalBody = document.getElementById('modal-body');
  const modalIdBadge = document.getElementById('modal-candidate-id');
  const btnModalTestVoice = document.getElementById('btn-modal-test-voice');
  const btnRefreshStatus = document.getElementById('btn-refresh-status');
  const statusLabel = document.getElementById('status-label');
  const dossierToggle = document.getElementById('dossier-toggle');
  const dossierBody = document.getElementById('dossier-body');
  const dossierChevron = document.getElementById('dossier-chevron');

  let activeModalCandidate = null;

  // Initialize Speech Recognition if supported
  const SpeechRecognitionAPI = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (SpeechRecognitionAPI) {
    speechRecognition = new SpeechRecognitionAPI();
    speechRecognition.continuous = false;
    speechRecognition.interimResults = false;
    speechRecognition.lang = 'en-US';

    speechRecognition.onstart = () => {
      isListening = true;
      btnMic.classList.add('listening');
      voiceStateText.textContent = 'Listening to your speech...';
      visualizer.setActive(true);
    };

    speechRecognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      voiceStateText.textContent = `Heard: "${transcript}"`;
      handleUserSubmit(transcript);
    };

    speechRecognition.onerror = (event) => {
      console.warn('Speech recognition error:', event.error);
      voiceStateText.textContent = 'Speech detection ended. Try clicking mic again or type.';
      stopListening();
    };

    speechRecognition.onend = () => {
      stopListening();
    };
  } else {
    btnMic.title = 'Speech recognition not supported in this browser. Please type below.';
    voiceStateText.textContent = 'Speech recognition unavailable in browser. Type your inquiries below.';
  }

  function stopListening() {
    isListening = false;
    btnMic.classList.remove('listening');
    visualizer.setActive(false);
  }

  // Toggle Microphone
  btnMic.addEventListener('click', () => {
    if (!speechRecognition) {
      alert('Voice input is not supported in this browser. Please type in the input box.');
      return;
    }
    if (isListening) {
      speechRecognition.stop();
      stopListening();
    } else {
      window.speechSynthesis.cancel();
      try {
        speechRecognition.start();
      } catch (e) {
        console.error('Failed to start recognition:', e);
      }
    }
  });

  // Text-To-Speech Output
  function speakResponse(text) {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.05;
    utterance.pitch = 1.0;

    // Pick a natural English voice if available
    const voices = window.speechSynthesis.getVoices();
    const naturalVoice = voices.find(v => v.lang.startsWith('en') && (v.name.includes('Natural') || v.name.includes('Google') || v.name.includes('Samantha')));
    if (naturalVoice) {
      utterance.voice = naturalVoice;
    }

    utterance.onstart = () => {
      voiceStateText.textContent = 'Alex is speaking...';
      visualizer.setActive(true);
    };

    utterance.onend = () => {
      voiceStateText.textContent = 'Ready for your next inquiry.';
      visualizer.setActive(false);
    };

    utterance.onerror = () => {
      visualizer.setActive(false);
    };

    window.speechSynthesis.speak(utterance);
  }

  // Tab switching
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      tabContents.forEach(c => c.classList.remove('active'));
      btn.classList.add('active');
      const target = document.getElementById(`tab-${btn.dataset.tab}`);
      if (target) target.classList.add('active');
    });
  });

  // Dossier Toggle
  if (dossierToggle) {
    let dossierOpen = true;
    dossierToggle.addEventListener('click', () => {
      dossierOpen = !dossierOpen;
      dossierBody.style.display = dossierOpen ? 'flex' : 'none';
      dossierChevron.style.transform = dossierOpen ? 'rotate(0deg)' : 'rotate(-90deg)';
    });
  }

  // Send Chat Message
  async function handleUserSubmit(message) {
    const text = message.trim();
    if (!text) return;

    // Append user message
    appendMessage('user', text);
    textInput.value = '';

    // Show typing state
    voiceStateText.textContent = 'Verifying against Astra AI registry...';
    visualizer.setActive(true);

    try {
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text, session_id: sessionId })
      });
      const data = await response.json();
      const reply = data.reply || 'No response received.';

      appendMessage('agent', reply);
      speakResponse(reply);
    } catch (err) {
      console.error('Chat error:', err);
      appendMessage('agent', 'I encountered a connection error. Please try again.');
      visualizer.setActive(false);
    }
  }

  function appendMessage(sender, text) {
    const isAgent = sender === 'agent';
    const msgDiv = document.createElement('div');
    msgDiv.className = `chat-message ${isAgent ? 'agent-msg' : 'user-msg'}`;

    const now = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    msgDiv.innerHTML = `
      <div class="avatar-ring ${isAgent ? 'agent-avatar' : 'user-avatar'}">
        <i data-lucide="${isAgent ? 'bot' : 'user'}"></i>
      </div>
      <div class="msg-bubble">
        <div class="msg-author">
          ${isAgent ? 'Alex <span class="role-badge">Astra AI Verification Rep</span>' : 'You (Inquiring HR)'}
        </div>
        <p>${escapeHTML(text)}</p>
        <span class="msg-time">${now}</span>
      </div>
    `;

    chatStream.appendChild(msgDiv);
    chatStream.scrollTop = chatStream.scrollHeight;
    if (window.lucide) window.lucide.createIcons();
  }

  function escapeHTML(str) {
    const p = document.createElement('p');
    p.textContent = str;
    return p.innerHTML;
  }

  // Submit on Enter
  textInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      handleUserSubmit(textInput.value);
    }
  });

  btnSend.addEventListener('click', () => {
    handleUserSubmit(textInput.value);
  });

  // Quick Chips
  document.querySelectorAll('.quick-chips .chip').forEach(chip => {
    chip.addEventListener('click', () => {
      const query = chip.dataset.query;
      handleUserSubmit(query);
    });
  });

  // Fetch Candidates
  async function loadCandidates() {
    try {
      const res = await fetch('/api/candidates');
      const data = await res.json();
      candidatesData = data.candidates || [];
      renderCandidates();
    } catch (e) {
      console.error('Failed to load candidates:', e);
    }
  }

  function renderCandidates() {
    const query = searchInput.value.toLowerCase().trim();

    const filtered = candidatesData.filter(cand => {
      // Filter tab
      if (currentFilter === 'featured' && cand.name !== 'Dhairyashil Shinde') return false;
      if (currentFilter === 'india' && cand.region !== 'India') return false;
      if (currentFilter === 'us' && cand.region !== 'United States') return false;

      // Search query
      if (!query) return true;
      const matchName = cand.name.toLowerCase().includes(query);
      const matchId = cand.id.toLowerCase().includes(query);
      const matchRole = cand.role.toLowerCase().includes(query);
      const matchDomain = cand.technical_domain.toLowerCase().includes(query);
      const matchRegion = cand.region.toLowerCase().includes(query);
      return matchName || matchId || matchRole || matchDomain || matchRegion;
    });

    candidateCount.textContent = `${filtered.length} Verified Interns`;

    candidateGrid.innerHTML = '';
    filtered.forEach(cand => {
      const isDhairyashil = cand.name === 'Dhairyashil Shinde';
      const card = document.createElement('div');
      card.className = `candidate-card ${isDhairyashil ? 'featured-card' : ''}`;

      const flag = cand.region === 'India' ? '🇮🇳' : '🇺🇸';

      card.innerHTML = `
        ${isDhairyashil ? '<div class="featured-banner">Featured AI Intern</div>' : ''}
        <div class="card-top">
          <div class="cand-name-wrap">
            <h3>${cand.name} ${flag}</h3>
            <div class="cand-role">${cand.role}</div>
          </div>
          <div class="cand-code-badge">${cand.id}</div>
        </div>

        <div class="card-details">
          <div class="detail-item">
            <i data-lucide="clock"></i>
            <span>${cand.duration} &bull; ${cand.working_hours}</span>
          </div>
          <div class="detail-item ${cand.night_meetings.toLowerCase().includes('yes') ? 'highlight-night' : ''}">
            <i data-lucide="moon"></i>
            <span>${cand.night_meetings.toLowerCase().includes('yes') ? 'Attends Evening/Night Sync Meetings' : 'Daytime Syncs'}</span>
          </div>
        </div>

        <div class="cand-domain">
          <strong>Domain:</strong> ${cand.technical_domain}
        </div>

        <div class="card-actions">
          <button class="btn-card-ask" data-cand-name="${cand.name}">
            <i data-lucide="message-square"></i> Verify Candidate
          </button>
          <button class="btn-card-view" data-cand-id="${cand.id}" title="View Full Verification File">
            <i data-lucide="external-link"></i>
          </button>
        </div>
      `;

      candidateGrid.appendChild(card);
    });

    if (window.lucide) window.lucide.createIcons();

    // Attach card event listeners
    document.querySelectorAll('.btn-card-ask').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const name = btn.dataset.candName;
        // Switch to simulator tab if on dialer
        const simTabBtn = document.querySelector('[data-tab="voice-sim"]');
        if (simTabBtn) simTabBtn.click();
        handleUserSubmit(`Could you verify candidate ${name}?`);
      });
    });

    document.querySelectorAll('.btn-card-view').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const candId = btn.dataset.candId;
        const candidate = candidatesData.find(c => c.id === candId);
        if (candidate) openModal(candidate);
      });
    });
  }

  // Search and filter listeners
  searchInput.addEventListener('input', renderCandidates);

  filterPills.forEach(pill => {
    pill.addEventListener('click', () => {
      filterPills.forEach(p => p.classList.remove('active'));
      pill.classList.add('active');
      currentFilter = pill.dataset.filter;
      renderCandidates();
    });
  });

  // Modal handlers
  function openModal(cand) {
    activeModalCandidate = cand;
    modalIdBadge.textContent = `Candidate ID: ${cand.id}`;

    const flag = cand.region === 'India' ? '🇮🇳 India' : '🇺🇸 United States';

    modalBody.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: flex-start;">
        <div>
          <h2 style="font-family: var(--font-display); font-size: 1.4rem;">${cand.name}</h2>
          <p style="color: var(--accent-cyan); font-weight: 500;">${cand.role} &bull; ${cand.department}</p>
        </div>
        <span style="font-size: 0.85rem; color: var(--text-muted); background: rgba(255,255,255,0.06); padding: 0.2rem 0.6rem; border-radius: 4px;">
          ${flag}
        </span>
      </div>

      <div style="background: rgba(0,0,0,0.3); padding: 1rem; border-radius: 8px; border: 1px solid var(--border-subtle); display: flex; flex-direction: column; gap: 0.5rem; font-size: 0.84rem;">
        <div><strong>Tenure:</strong> ${cand.duration} (${cand.period})</div>
        <div><strong>Verification Status:</strong> <span style="color: #34d399;">${cand.status}</span></div>
        <div><strong>Work Schedule:</strong> ${cand.working_hours}</div>
        <div><strong>Night/Evening Syncs:</strong> ${cand.night_meetings}</div>
        <div><strong>Core Technical Domain:</strong> ${cand.technical_domain}</div>
      </div>

      <div>
        <h4 style="font-size: 0.88rem; color: #a5b4fc; margin-bottom: 0.4rem;">Key Projects & Benchmarking Responsibilities:</h4>
        <ul style="padding-left: 1.25rem; font-size: 0.82rem; color: var(--text-muted); display: flex; flex-direction: column; gap: 0.35rem;">
          ${cand.responsibilities.map(r => `<li>${r}</li>`).join('')}
        </ul>
      </div>

      <div style="background: rgba(99, 102, 241, 0.08); border-left: 3px solid #818cf8; padding: 0.75rem 1rem; border-radius: 0 6px 6px 0; font-size: 0.8rem; color: #c7d2fe;">
        <strong>Supervisor Assessment:</strong> "${cand.supervisor_recommendation}"
      </div>
    `;

    modal.style.display = 'flex';
    if (window.lucide) window.lucide.createIcons();
  }

  btnCloseModal.addEventListener('click', () => {
    modal.style.display = 'none';
  });

  window.addEventListener('click', (e) => {
    if (e.target === modal) modal.style.display = 'none';
  });

  btnModalTestVoice.addEventListener('click', () => {
    if (activeModalCandidate) {
      modal.style.display = 'none';
      const simTabBtn = document.querySelector('[data-tab="voice-sim"]');
      if (simTabBtn) simTabBtn.click();
      handleUserSubmit(`Please verify the complete record for ${activeModalCandidate.name}.`);
    }
  });

  // Outbound Call Trigger
  btnStartCall.addEventListener('click', async () => {
    const phone = dialerPhoneInput.value.trim();
    const baseUrl = dialerBaseUrl.value.trim();

    if (!phone) {
      showFeedback('Please enter a phone number with country code (e.g. +91XXXXXXXXXX or +1XXXXXXXXXX)', 'error');
      return;
    }

    btnStartCall.disabled = true;
    btnStartCall.innerHTML = '<i data-lucide="loader"></i> Placing Call...';
    if (window.lucide) window.lucide.createIcons();

    try {
      const res = await fetch('/api/make-call', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ to_phone: phone, base_url: baseUrl })
      });
      const data = await res.json();

      if (data.success) {
        showFeedback(`Call successfully placed to ${phone}! SID: ${data.call_sid}. Pick up your phone to speak with Alex.`, 'success');
      } else {
        showFeedback(`Failed to place call: ${data.error || 'Unknown error'}`, 'error');
      }
    } catch (e) {
      showFeedback(`Network error: ${e.message}`, 'error');
    } finally {
      btnStartCall.disabled = false;
      btnStartCall.innerHTML = '<i data-lucide="phone"></i> Initiate Verification Call';
      if (window.lucide) window.lucide.createIcons();
    }
  });

  function showFeedback(msg, type) {
    dialerFeedback.style.display = 'block';
    dialerFeedback.className = `dialer-feedback ${type}`;
    dialerFeedback.textContent = msg;
  }

  // Refresh System Status
  async function refreshStatus() {
    try {
      const res = await fetch('/api/status');
      const data = await res.json();
      if (data.status === 'online') {
        statusLabel.textContent = `Online • Model: ${data.groq.active_model.split('/').pop()}`;
      }
    } catch (e) {
      statusLabel.textContent = 'Offline / Connecting';
    }
  }

  btnRefreshStatus.addEventListener('click', refreshStatus);

  // Initial load
  loadCandidates();
  refreshStatus();
});

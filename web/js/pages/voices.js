function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value ?? "";
  return div.innerHTML;
}

function hexToBlobUrl(hex, mimeType = "audio/mpeg") {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < hex.length; i += 2) {
    bytes[i / 2] = parseInt(hex.substring(i, i + 2), 16);
  }
  const blob = new Blob([bytes], { type: mimeType });
  return URL.createObjectURL(blob);
}

function renderSystemVoiceCards(voices) {
  if (!voices.length) return '<p class="hint">暂无系统音色数据</p>';
  return `<div class="voice-grid">${voices
    .map(
      (v) => `
      <div class="voice-card">
        <div class="voice-name">${escapeHtml(v.voice_name || v.voice_id)}</div>
        <div class="voice-id">${escapeHtml(v.voice_id)}</div>
        <div class="voice-desc">${escapeHtml((v.description || []).join(" "))}</div>
      </div>`
    )
    .join("")}</div>`;
}

function renderLocalVoiceCards(voices, kind) {
  if (!voices.length) return `<p class="hint">暂无${kind}音色</p>`;
  return `<div class="voice-grid">${voices
    .map(
      (v) => `
      <div class="voice-card" data-voice-id="${escapeHtml(v.voice_id)}">
        <div class="voice-name">${escapeHtml(v.voice_id)}</div>
        <div class="voice-desc">${v.activated ? "已生效" : "首次合成后生效（7 天内需使用一次）"}</div>
        ${v.sample_path ? `<audio controls src="${escapeHtml(v.sample_path)}"></audio>` : ""}
        <div class="voice-note-row">
          <input type="text" class="voice-note-input" value="${escapeHtml(v.note || "")}" placeholder="备注" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" />
          <button class="save-note secondary">保存备注</button>
          <button class="delete-voice secondary">删除</button>
        </div>
      </div>`
    )
    .join("")}</div>`;
}

function bindLocalVoiceActions(container, reload) {
  container.querySelectorAll(".save-note").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const card = btn.closest(".voice-card");
      const voiceId = card.dataset.voiceId;
      const note = card.querySelector(".voice-note-input").value;
      await fetch(`/api/voices/${encodeURIComponent(voiceId)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note }),
      });
    });
  });

  container.querySelectorAll(".delete-voice").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const card = btn.closest(".voice-card");
      const voiceId = card.dataset.voiceId;
      if (!confirm(`删除本地音色记录 ${voiceId}？（不会影响 MiniMax 端音色）`)) return;
      await fetch(`/api/voices/${encodeURIComponent(voiceId)}`, { method: "DELETE" });
      reload();
    });
  });
}

async function loadVoicesPage(container) {
  container.innerHTML = `
    <div class="page voices-page">
      <h1>音色库</h1>

      <section class="card">
        <h2>音色克隆</h2>
        <form id="clone-form">
          <div class="field-row">
            <label>音频文件</label>
            <input type="file" id="clone-file" accept=".mp3,.wav,.m4a" required />
          </div>
          <div class="field-row">
            <label>Voice ID</label>
            <input type="text" id="clone-voice-id" placeholder="至少8位字母开头，如 MyVoice001" required autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" />
          </div>
          <div class="field-row">
            <label>预览文案</label>
            <input type="text" id="clone-preview-text" placeholder="可选，用于试听" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" />
          </div>
          <div class="field-row">
            <label>克隆提示词（可选）</label>
            <input type="text" id="clone-prompt" placeholder="用于引导克隆风格的参考文本" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" />
          </div>
          <div class="field-row">
            <label>备注</label>
            <input type="text" id="clone-note" placeholder="可选" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" />
          </div>
          <div class="field-row">
            <button type="submit">开始克隆</button>
            <span id="clone-result"></span>
          </div>
        </form>
      </section>

      <section class="card">
        <h2>音色设计</h2>
        <form id="design-form">
          <div class="field-row">
            <label>音色描述</label>
            <input type="text" id="design-prompt" placeholder="如：沉稳可靠的中年男声" required autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" />
          </div>
          <div class="field-row">
            <label>预览文案</label>
            <input type="text" id="design-preview-text" placeholder="用于生成试听音频" required autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" />
          </div>
          <div class="field-row">
            <label>备注</label>
            <input type="text" id="design-note" placeholder="可选" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" />
          </div>
          <div class="field-row">
            <button type="submit">生成音色</button>
            <span id="design-result"></span>
          </div>
        </form>
        <audio id="design-preview-audio" controls style="display:none; margin-top:8px;"></audio>
      </section>

      <section class="card">
        <h2>系统音色</h2>
        <div id="system-voices"><p class="hint">加载中...</p></div>
      </section>

      <section class="card">
        <h2>我的克隆音色</h2>
        <div id="cloned-voices"><p class="hint">加载中...</p></div>
      </section>

      <section class="card">
        <h2>我的设计音色</h2>
        <div id="designed-voices"><p class="hint">加载中...</p></div>
      </section>
    </div>
  `;

  async function reload() {
    const response = await fetch("/api/voices");
    if (!window.__isPageActive?.()) return;
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      const message = body.detail || "加载音色列表失败";
      container.querySelector("#system-voices").innerHTML = `<p class="error">${escapeHtml(message)}</p>`;
      container.querySelector("#cloned-voices").innerHTML = "";
      container.querySelector("#designed-voices").innerHTML = "";
      return;
    }
    const data = await response.json();
    container.querySelector("#system-voices").innerHTML = renderSystemVoiceCards(data.system || []);
    container.querySelector("#cloned-voices").innerHTML = renderLocalVoiceCards(data.cloned || [], "克隆");
    container.querySelector("#designed-voices").innerHTML = renderLocalVoiceCards(data.designed || [], "设计");
    bindLocalVoiceActions(container.querySelector("#cloned-voices"), reload);
    bindLocalVoiceActions(container.querySelector("#designed-voices"), reload);
  }

  container.querySelector("#clone-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const resultEl = container.querySelector("#clone-result");
    const fileInput = container.querySelector("#clone-file");
    if (!fileInput.files.length) return;

    const formData = new FormData();
    formData.append("file", fileInput.files[0]);
    formData.append("voice_id", container.querySelector("#clone-voice-id").value);
    formData.append("note", container.querySelector("#clone-note").value);
    const previewText = container.querySelector("#clone-preview-text").value;
    if (previewText) formData.append("preview_text", previewText);
    const clonePrompt = container.querySelector("#clone-prompt").value;
    if (clonePrompt) formData.append("clone_prompt", clonePrompt);

    resultEl.textContent = "克隆中...";
    const response = await fetch("/api/voices/clone", { method: "POST", body: formData });
    const body = await response.json();
    if (!response.ok) {
      if (window.VoiceMaxApiErrors?.handleApiError(body.detail)) return;
      resultEl.textContent = body.detail || "克隆失败";
      resultEl.className = "error";
      return;
    }
    resultEl.textContent = "克隆成功";
    resultEl.className = "ok";
    event.target.reset();
    reload();
  });

  container.querySelector("#design-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const resultEl = container.querySelector("#design-result");
    const payload = {
      prompt: container.querySelector("#design-prompt").value,
      preview_text: container.querySelector("#design-preview-text").value,
      note: container.querySelector("#design-note").value,
    };
    resultEl.textContent = "生成中...";
    const response = await fetch("/api/voices/design", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await response.json();
    if (!response.ok) {
      if (window.VoiceMaxApiErrors?.handleApiError(body.detail)) return;
      resultEl.textContent = body.detail || "生成失败";
      resultEl.className = "error";
      return;
    }
    resultEl.textContent = `生成成功：${body.voice_id}`;
    resultEl.className = "ok";
    if (body.trial_audio_hex) {
      const audioEl = container.querySelector("#design-preview-audio");
      audioEl.src = hexToBlobUrl(body.trial_audio_hex);
      audioEl.style.display = "block";
    }
    event.target.reset();
    reload();
  });

  await reload();
}

window.VoiceMaxPages = window.VoiceMaxPages || {};
window.VoiceMaxPages.voices = loadVoicesPage;

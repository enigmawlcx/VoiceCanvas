const MODEL_OPTIONS = [
  "speech-2.8-hd",
  "speech-2.8-turbo",
  "speech-2.6-hd",
  "speech-2.6-turbo",
  "speech-02-hd",
  "speech-02-turbo",
];
const FORMAT_OPTIONS = ["mp3", "wav", "flac"];
const SAMPLE_RATE_OPTIONS = [8000, 16000, 22050, 24000, 32000, 44100];
const BITRATE_OPTIONS = [32000, 64000, 128000, 256000];

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value ?? "";
  return div.innerHTML;
}

function optionsHtml(options, current) {
  return options
    .map((value) => `<option value="${value}" ${String(value) === String(current) ? "selected" : ""}>${value}</option>`)
    .join("");
}

async function fetchSettings() {
  const response = await fetch("/api/settings");
  return response.json();
}

function renderSettingsPage(container, settings, hint) {
  container.innerHTML = `
    <div class="page settings-page">
      <h1>配置</h1>

      <section class="card">
        <h2>API Key</h2>
        ${hint ? `<p class="hint error">${escapeHtml(hint)}</p>` : ""}
        <p class="hint">API Key 保存在 macOS Keychain，界面仅显示掩码。</p>
        <div class="field-row">
          <span class="api-key-status">${
            settings.has_api_key ? `已配置：${settings.api_key_masked}` : "尚未配置"
          }</span>
        </div>
        <div class="field-row">
          <input type="password" id="api-key-input" placeholder="输入新的 API Key" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" />
          <button id="save-api-key">保存</button>
          ${settings.has_api_key ? '<button id="clear-api-key" class="secondary">清除</button>' : ""}
        </div>
        <div class="field-row">
          <button id="test-connection">测试连接</button>
          <span id="test-connection-result"></span>
        </div>
      </section>

      <section class="card">
        <h2>默认参数</h2>
        <div class="field-row">
          <label>默认模型</label>
          <select id="default_model">${optionsHtml(MODEL_OPTIONS, settings.default_model)}</select>
        </div>
        <div class="field-row">
          <label>默认格式</label>
          <select id="default_format">${optionsHtml(FORMAT_OPTIONS, settings.default_format)}</select>
        </div>
        <div class="field-row">
          <label>默认采样率</label>
          <select id="default_sample_rate">${optionsHtml(SAMPLE_RATE_OPTIONS, settings.default_sample_rate)}</select>
        </div>
        <div class="field-row">
          <label>默认比特率</label>
          <select id="default_bitrate">
            ${BITRATE_OPTIONS.map(
              (value) =>
                `<option value="${value}" ${value === settings.default_bitrate ? "selected" : ""}>${value / 1000} kbps</option>`
            ).join("")}
          </select>
          <span id="bitrate-format-hint" class="hint">仅适用于 MP3</span>
        </div>
        <div class="field-row">
          <label>保存目录</label>
          <input type="text" id="save_dir" value="${settings.save_dir}" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" />
        </div>
      </section>

      <section class="card">
        <h2>费用估算（可选）</h2>
        <p class="hint">填写本地参考单价，报表将估算费用；填 0 表示不估算。</p>
        <div class="field-row">
          <label>每千字符单价</label>
          <input type="number" id="price_per_1k_chars" min="0" step="0.0001" value="${settings.price_per_1k_chars ?? 0}" />
        </div>
        <div class="field-row">
          <label>每千 Token 单价</label>
          <input type="number" id="price_per_1k_tokens" min="0" step="0.0001" value="${settings.price_per_1k_tokens ?? 0}" />
        </div>
      </section>

      <section class="card">
        <h2>高级</h2>
        <div class="field-row">
          <label>API Base URL</label>
          <input type="text" id="base_url" value="${settings.base_url}" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" />
        </div>
        <div class="field-row">
          <label>Group ID（可选）</label>
          <input type="text" id="group_id" value="${settings.group_id || ""}" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" />
        </div>
      </section>

      <div class="field-row">
        <button id="save-settings">保存设置</button>
        <span id="save-settings-result"></span>
      </div>
    </div>
  `;

  const formatSelect = container.querySelector("#default_format");
  const bitrateSelect = container.querySelector("#default_bitrate");
  const bitrateHint = container.querySelector("#bitrate-format-hint");

  function syncBitrateAvailability() {
    const default_format = formatSelect.value;
    const isMp3 = default_format === "mp3";
    bitrateSelect.disabled = !isMp3;
    bitrateHint.style.display = isMp3 ? "none" : "inline";
  }

  formatSelect.addEventListener("change", syncBitrateAvailability);
  syncBitrateAvailability();

  container.querySelector("#save-settings").addEventListener("click", async () => {
    const resultEl = container.querySelector("#save-settings-result");
    const payload = {
      default_model: container.querySelector("#default_model").value,
      default_format: container.querySelector("#default_format").value,
      default_sample_rate: Number(container.querySelector("#default_sample_rate").value),
      default_bitrate: Number(container.querySelector("#default_bitrate").value),
      save_dir: container.querySelector("#save_dir").value,
      base_url: container.querySelector("#base_url").value,
      group_id: container.querySelector("#group_id").value,
      price_per_1k_chars: Number(container.querySelector("#price_per_1k_chars").value),
      price_per_1k_tokens: Number(container.querySelector("#price_per_1k_tokens").value),
    };
    const response = await fetch("/api/settings", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    resultEl.textContent = response.ok ? "已保存" : "保存失败";
  });

  container.querySelector("#save-api-key").addEventListener("click", async () => {
    const input = container.querySelector("#api-key-input");
    if (!input.value) return;
    const response = await fetch("/api/settings/api-key", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ api_key: input.value }),
    });
    if (response.ok) {
      const body = await response.json();
      if (!window.__isPageActive?.()) return;
      loadSettingsPage(container, body);
    }
  });

  const clearBtn = container.querySelector("#clear-api-key");
  if (clearBtn) {
    clearBtn.addEventListener("click", async () => {
      await fetch("/api/settings/api-key", { method: "DELETE" });
      const fresh = await fetchSettings();
      if (!window.__isPageActive?.()) return;
      renderSettingsPage(container, fresh);
    });
  }

  container.querySelector("#test-connection").addEventListener("click", async () => {
    const resultEl = container.querySelector("#test-connection-result");
    resultEl.textContent = "测试中...";
    const response = await fetch("/api/settings/test-connection", { method: "POST" });
    const body = await response.json();
    resultEl.textContent = body.message;
    resultEl.classList.toggle("ok", body.ok);
    resultEl.classList.toggle("error", !body.ok);
  });
}

async function loadSettingsPage(container) {
  const hint = sessionStorage.getItem("voicemax.settings.hint");
  if (hint) sessionStorage.removeItem("voicemax.settings.hint");
  const settings = await fetchSettings();
  if (!window.__isPageActive?.()) return;
  renderSettingsPage(container, settings, hint);
}

window.VoiceMaxPages = window.VoiceMaxPages || {};
window.VoiceMaxPages.settings = loadSettingsPage;

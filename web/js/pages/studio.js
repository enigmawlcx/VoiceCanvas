const STUDIO_DRAFT_ID_KEY = "voicemax.studio.draftId";
const STUDIO_AUTOSAVE_DELAY_MS = 10000;

let studioDraftId = null;
let studioMemoryText = null;
let studioAutosaveTimer = null;
let studioDirty = false;
let studioSaveGeneration = 0;

function studioHexToBlobUrl(hex, mimeType = "audio/mpeg") {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < hex.length; i += 2) {
    bytes[i / 2] = parseInt(hex.substring(i, i + 2), 16);
  }
  return URL.createObjectURL(new Blob([bytes], { type: mimeType }));
}

function studioEscapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value ?? "";
  return div.innerHTML;
}

async function fetchVoiceGroups() {
  const response = await fetch("/api/voices");
  if (!response.ok) return { system: [], cloned: [], designed: [] };
  return response.json();
}

function buildVoiceOptionsHtml(voiceData) {
  const groups = [
    { label: "我的克隆音色", items: voiceData.cloned || [], nameKey: "voice_id" },
    { label: "我的设计音色", items: voiceData.designed || [], nameKey: "voice_id" },
    { label: "系统音色", items: voiceData.system || [], nameKey: "voice_name" },
  ];
  const groupsHtml = groups
    .filter((g) => g.items.length)
    .map(
      (g) => `<optgroup label="${g.label}">${g.items
        .map(
          (item) =>
            `<option value="${studioEscapeHtml(item.voice_id)}">${studioEscapeHtml(
              item[g.nameKey] || item.voice_id
            )}</option>`
        )
        .join("")}</optgroup>`
    )
    .join("");
  if (!groupsHtml) return '<option value="">暂无可用音色，请先在音色库添加</option>';
  return `<option value="">请选择音色</option>${groupsHtml}`;
}

async function fetchStudioTags() {
  const response = await fetch("/api/studio/tags");
  if (!response.ok) return { emotions: [], interjections: [] };
  return response.json();
}

function buildTagButtonsHtml(tags, className) {
  return tags
    .map(
      (tag) =>
        `<button type="button" class="${className}" data-id="${studioEscapeHtml(tag.id)}">${studioEscapeHtml(
          tag.label
        )}</button>`
    )
    .join("");
}

function insertEmotionTag(textarea, emotionId, validEmotionIds) {
  const value = textarea.value;
  const cursor = textarea.selectionStart;
  const lineStart = value.lastIndexOf("\n", cursor - 1) + 1;
  const nextBreak = value.indexOf("\n", cursor);
  const lineEnd = nextBreak === -1 ? value.length : nextBreak;
  const line = value.slice(lineStart, lineEnd);

  const match = line.match(/^\[([a-zA-Z-]+)\]\s*/);
  const hasValidTag = Boolean(match && validEmotionIds.includes(match[1].toLowerCase()));
  const rest = hasValidTag ? line.slice(match[0].length) : line;
  const newLine = `[${emotionId}] ${rest}`;

  textarea.value = value.slice(0, lineStart) + newLine + value.slice(lineEnd);

  const cursorOffsetInLine = cursor - lineStart;
  const oldPrefixLength = hasValidTag ? match[0].length : 0;
  const newPrefixLength = `[${emotionId}] `.length;
  const newCursorOffset = Math.max(0, cursorOffsetInLine - oldPrefixLength) + newPrefixLength;
  const newCursor = lineStart + newCursorOffset;

  textarea.selectionStart = textarea.selectionEnd = newCursor;
  textarea.focus();
  textarea.dispatchEvent(new Event("input"));
}

function insertInterjectionTag(textarea, tagId) {
  const value = textarea.value;
  const cursor = textarea.selectionStart;
  const before = value.slice(0, cursor);
  const after = value.slice(cursor);
  const needSpaceBefore = before.length > 0 && !/\s$/.test(before);
  const needSpaceAfter = after.length > 0 && !/^\s/.test(after);
  const insertion = `${needSpaceBefore ? " " : ""}(${tagId})${needSpaceAfter ? " " : ""}`;

  textarea.value = before + insertion + after;
  const newCursor = cursor + insertion.length;
  textarea.selectionStart = textarea.selectionEnd = newCursor;
  textarea.focus();
  textarea.dispatchEvent(new Event("input"));
}

async function restoreStudioContent() {
  if (studioMemoryText !== null) {
    return { text: studioMemoryText, draftId: studioDraftId };
  }
  const storedId = localStorage.getItem(STUDIO_DRAFT_ID_KEY);
  if (!storedId) {
    return { text: "", draftId: null };
  }
  const response = await fetch(`/api/studio/projects/${storedId}`);
  if (!response.ok) {
    localStorage.removeItem(STUDIO_DRAFT_ID_KEY);
    return { text: "", draftId: null };
  }
  const project = await response.json();
  return { text: project.annotated_text || project.source_text || "", draftId: project.id };
}

async function saveStudioDraft(text, generation) {
  if (studioDraftId) {
    const response = await fetch(`/api/studio/projects/${studioDraftId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source_text: text, annotated_text: text }),
    });
    if (!response.ok) {
      if (generation !== studioSaveGeneration) {
        return false;
      }
      throw new Error("草稿保存失败");
    }
    return generation === studioSaveGeneration;
  }
  const response = await fetch("/api/studio/projects", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      title: text.trim().slice(0, 20) || "未命名项目",
      source_text: text,
      annotated_text: text,
    }),
  });
  if (!response.ok) {
    throw new Error("草稿保存失败");
  }
  const project = await response.json();
  if (generation !== studioSaveGeneration) {
    // 保存请求进行期间用户已清空工作台，丢弃这次结果并删除刚创建的草稿，避免复活
    await fetch(`/api/studio/projects/${project.id}`, { method: "DELETE" }).catch(() => {});
    return false;
  }
  studioDraftId = project.id;
  localStorage.setItem(STUDIO_DRAFT_ID_KEY, String(project.id));
  return true;
}

async function loadStudioPage(container) {
  container.innerHTML = `
    <div class="page studio-page">
      <h1>工作台</h1>

      <div class="studio-toolbar">
        <button id="polish-btn">润色</button>
        <button id="parse-btn" class="secondary">解析分段</button>
        <button id="save-project-btn" class="secondary">保存草稿</button>
        <button id="clear-workspace-btn" class="secondary">清空工作台</button>
        <span id="polish-result"></span>
      </div>

      <div class="studio-main">
        <section class="card studio-editor-col">
          <textarea id="studio-text" class="editor-textarea studio-big-textarea" placeholder="粘贴或输入原文..." autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false"></textarea>
        </section>

        <aside class="card studio-tag-panel">
          <h2>情绪</h2>
          <div id="emotion-buttons" class="tag-grid"></div>
          <h2>语气词</h2>
          <div id="interjection-buttons" class="tag-grid"></div>
        </aside>
      </div>

      <section class="card">
        <h2>合成设置</h2>
        <div class="field-row">
          <label>音色</label>
          <select id="voice-select"><option>加载中...</option></select>
        </div>
        <div class="field-row">
          <label>语速 <span id="speed-value">1.0</span></label>
          <input type="range" id="speed" min="0.5" max="2" step="0.05" value="1" />
        </div>
        <div class="field-row">
          <label>音量 <span id="vol-value">1.0</span></label>
          <input type="range" id="vol" min="0.1" max="10" step="0.1" value="1" />
        </div>
        <div class="field-row">
          <label>Pitch <span id="pitch-value">0</span></label>
          <input type="range" id="pitch" min="-12" max="12" step="1" value="0" />
        </div>
        <h2>音效器（可选）</h2>
        <div class="field-row">
          <label>音高 <span id="vm-pitch-value">0</span></label>
          <input type="range" id="vm-pitch" min="-100" max="100" step="1" value="0" />
        </div>
        <div class="field-row">
          <label>强度 <span id="vm-intensity-value">0</span></label>
          <input type="range" id="vm-intensity" min="-100" max="100" step="1" value="0" />
        </div>
        <div class="field-row">
          <label>音色 <span id="vm-timbre-value">0</span></label>
          <input type="range" id="vm-timbre" min="-100" max="100" step="1" value="0" />
        </div>
        <div class="field-row">
          <label>空间音效</label>
          <select id="vm-sound-effects">
            <option value="">无</option>
            <option value="spacious_echo">空旷回声</option>
            <option value="auditorium_echo">礼堂回声</option>
            <option value="lofi_telephone">电话音质</option>
            <option value="robotic">机械感</option>
          </select>
        </div>
      </section>

      <section class="card">
        <div class="field-row">
          <h2 style="flex:1;">分段列表</h2>
          <button id="synthesize-full-btn">整篇合成并导出</button>
          <span id="synthesize-full-result"></span>
        </div>
        <div id="segment-list"><p class="hint">点击"解析分段"后，分段将显示在此处</p></div>
      </section>
    </div>
  `;

  const els = {
    text: container.querySelector("#studio-text"),
    voiceSelect: container.querySelector("#voice-select"),
    speed: container.querySelector("#speed"),
    vol: container.querySelector("#vol"),
    pitch: container.querySelector("#pitch"),
    vmPitch: container.querySelector("#vm-pitch"),
    vmIntensity: container.querySelector("#vm-intensity"),
    vmTimbre: container.querySelector("#vm-timbre"),
    vmSoundEffects: container.querySelector("#vm-sound-effects"),
    segmentList: container.querySelector("#segment-list"),
    emotionButtons: container.querySelector("#emotion-buttons"),
    interjectionButtons: container.querySelector("#interjection-buttons"),
    polishResult: container.querySelector("#polish-result"),
  };

  const SLIDER_BINDINGS = [
    ["speed", "speed-value"],
    ["vol", "vol-value"],
    ["pitch", "pitch-value"],
    ["vm-pitch", "vm-pitch-value"],
    ["vm-intensity", "vm-intensity-value"],
    ["vm-timbre", "vm-timbre-value"],
  ];

  SLIDER_BINDINGS.forEach(([inputId, labelId]) => {
    const input = container.querySelector(`#${inputId}`);
    const label = container.querySelector(`#${labelId}`);
    input.addEventListener("input", () => (label.textContent = input.value));
  });

  function resetSlidersToDefault() {
    els.speed.value = "1";
    els.vol.value = "1";
    els.pitch.value = "0";
    els.vmPitch.value = "0";
    els.vmIntensity.value = "0";
    els.vmTimbre.value = "0";
    els.vmSoundEffects.value = "";
    SLIDER_BINDINGS.forEach(([inputId, labelId]) => {
      container.querySelector(`#${labelId}`).textContent = container.querySelector(`#${inputId}`).value;
    });
  }

  const voiceData = await fetchVoiceGroups();
  if (!window.__isPageActive?.()) return;
  els.voiceSelect.innerHTML = buildVoiceOptionsHtml(voiceData);

  const tags = await fetchStudioTags();
  if (!window.__isPageActive?.()) return;
  const validEmotionIds = tags.emotions.map((tag) => tag.id);
  els.emotionButtons.innerHTML = buildTagButtonsHtml(tags.emotions, "tag-btn tag-btn-emotion");
  els.interjectionButtons.innerHTML = buildTagButtonsHtml(tags.interjections, "tag-btn tag-btn-interjection");

  els.emotionButtons.querySelectorAll(".tag-btn-emotion").forEach((btn) => {
    btn.addEventListener("click", () => insertEmotionTag(els.text, btn.dataset.id, validEmotionIds));
  });
  els.interjectionButtons.querySelectorAll(".tag-btn-interjection").forEach((btn) => {
    btn.addEventListener("click", () => insertInterjectionTag(els.text, btn.dataset.id));
  });

  const restored = await restoreStudioContent();
  if (!window.__isPageActive?.()) return;
  studioDraftId = restored.draftId;
  studioMemoryText = restored.text;
  els.text.value = restored.text;

  function scheduleAutosave() {
    studioDirty = true;
    clearTimeout(studioAutosaveTimer);
    const generation = studioSaveGeneration;
    studioAutosaveTimer = setTimeout(async () => {
      if (!studioDirty || generation !== studioSaveGeneration) return;
      try {
        const saved = await saveStudioDraft(studioMemoryText, generation);
        if (saved) {
          studioDirty = false;
        }
      } catch (error) {
        els.polishResult.textContent = `自动保存失败：${error.message}`;
        els.polishResult.className = "error";
      }
    }, STUDIO_AUTOSAVE_DELAY_MS);
  }

  els.text.addEventListener("input", () => {
    studioMemoryText = els.text.value;
    scheduleAutosave();
  });

  function currentSynthesisParams() {
    const vmPitch = Number(els.vmPitch.value);
    const vmIntensity = Number(els.vmIntensity.value);
    const vmTimbre = Number(els.vmTimbre.value);
    const soundEffects = els.vmSoundEffects.value || null;
    const voiceModify =
      vmPitch || vmIntensity || vmTimbre || soundEffects
        ? {
            pitch: vmPitch,
            intensity: vmIntensity,
            timbre: vmTimbre,
            ...(soundEffects ? { sound_effects: soundEffects } : {}),
          }
        : null;
    return {
      voice_id: els.voiceSelect.value,
      speed: Number(els.speed.value),
      vol: Number(els.vol.value),
      pitch: Number(els.pitch.value),
      voice_modify: voiceModify,
    };
  }

  async function fetchAudioConfigSnapshot() {
    const response = await fetch("/api/settings");
    const body = await response.json();
    if (!response.ok) throw new Error(body.detail || "读取音频配置失败");
    return {
      format: body.default_format,
      sample_rate: body.default_sample_rate,
      bitrate: body.default_bitrate,
    };
  }

  function renderSegments(segments, failures = {}, audioConfigSnapshot = null) {
    els.segmentList._audioConfigSnapshot = audioConfigSnapshot;
    if (!segments.length) {
      els.segmentList.innerHTML = '<p class="hint">没有解析到分段</p>';
      els.segmentList._segments = [];
      els.segmentList._failures = {};
      return;
    }
    els.segmentList.innerHTML = `<div class="segment-list">${segments
      .map(
        (seg, index) => `
        <div class="segment-item${failures[index] ? " segment-failed" : ""}" data-index="${index}">
          <span class="segment-emotion">${seg.emotion ? `[${studioEscapeHtml(seg.emotion)}]` : ""}</span>
          <span class="segment-text">${studioEscapeHtml(seg.text)}</span>
          <button class="segment-play secondary">${failures[index] ? "重试" : "试听"}</button>
          <audio class="segment-audio" controls style="display:none;"></audio>
        </div>`
      )
      .join("")}</div>`;

    async function synthesizeOneSegment(index, btn) {
      const item = btn.closest(".segment-item");
      const segment = segments[index];
      const params = currentSynthesisParams();
      if (!params.voice_id) {
        alert("请先选择音色");
        return null;
      }
      btn.textContent = "合成中...";
      btn.disabled = true;
      let audioConfigSnapshot = els.segmentList._audioConfigSnapshot;
      try {
        audioConfigSnapshot = audioConfigSnapshot || (await fetchAudioConfigSnapshot());
        const response = await fetch("/api/studio/synthesize/segment", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            text: segment.text,
            emotion: segment.emotion,
            ...params,
            audio_config: audioConfigSnapshot,
          }),
        });
        const body = await response.json();
        if (!response.ok) {
          if (window.VoiceMaxApiErrors?.handleApiError(body.detail)) return null;
          throw new Error(body.detail || "合成失败");
        }
        failures[index] = null;
        delete failures[index];
        item.classList.remove("segment-failed");
        btn.textContent = "试听";
        const audioEl = item.querySelector(".segment-audio");
        audioEl.src = studioHexToBlobUrl(body.audio_hex);
        audioEl.style.display = "block";
        audioEl.play();
        return body.audio_hex;
      } catch (error) {
        failures[index] = error.message;
        renderSegments(segments, failures, audioConfigSnapshot);
        return null;
      } finally {
        btn.disabled = false;
      }
    }

    els.segmentList.querySelectorAll(".segment-play").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const index = Number(btn.closest(".segment-item").dataset.index);
        await synthesizeOneSegment(index, btn);
      });
    });

    els.segmentList._segments = segments;
    els.segmentList._failures = failures;
    els.segmentList._synthesizeOneSegment = synthesizeOneSegment;
  }

  async function parseAnnotatedText() {
    const response = await fetch("/api/studio/annotate/parse", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ annotated_text: els.text.value }),
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      els.segmentList.innerHTML = `<p class="hint error">${studioEscapeHtml(body.detail || "解析失败")}</p>`;
      els.segmentList._segments = [];
      els.segmentList._audioConfigSnapshot = null;
      return [];
    }
    const segments = await response.json();
    renderSegments(segments);
    return segments;
  }

  container.querySelector("#parse-btn").addEventListener("click", parseAnnotatedText);

  container.querySelector("#polish-btn").addEventListener("click", async () => {
    if (!els.text.value.trim()) return;
    els.polishResult.textContent = "润色中...";
    els.polishResult.className = "";
    try {
      const response = await fetch("/api/studio/polish", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source_text: els.text.value }),
      });
      const body = await response.json();
      if (!response.ok) {
        if (window.VoiceMaxApiErrors?.handleApiError(body.detail)) return;
        throw new Error(body.detail || "润色失败");
      }
      els.text.value = body.annotated_text;
      studioMemoryText = body.annotated_text;
      scheduleAutosave();
      if (body.notice) {
        els.polishResult.textContent = body.notice;
        els.polishResult.className = "error";
      } else {
        els.polishResult.textContent = "润色完成";
        els.polishResult.className = "ok";
      }
    } catch (error) {
      els.polishResult.textContent = error.message;
      els.polishResult.className = "error";
    }
  });

  container.querySelector("#save-project-btn").addEventListener("click", async () => {
    clearTimeout(studioAutosaveTimer);
    const generation = studioSaveGeneration;
    try {
      const saved = await saveStudioDraft(els.text.value, generation);
      if (saved) {
        studioDirty = false;
        els.polishResult.textContent = "草稿已保存";
        els.polishResult.className = "ok";
      }
    } catch (error) {
      els.polishResult.textContent = error.message;
      els.polishResult.className = "error";
    }
  });

  container.querySelector("#clear-workspace-btn").addEventListener("click", async () => {
    studioSaveGeneration += 1;
    clearTimeout(studioAutosaveTimer);
    if (studioDraftId) {
      await fetch(`/api/studio/projects/${studioDraftId}`, { method: "DELETE" }).catch(() => {});
    }
    studioDraftId = null;
    studioMemoryText = "";
    studioDirty = false;
    localStorage.removeItem(STUDIO_DRAFT_ID_KEY);

    els.text.value = "";
    resetSlidersToDefault();
    els.voiceSelect.value = "";
    els.segmentList.innerHTML = '<p class="hint">点击"解析分段"后，分段将显示在此处</p>';
    els.segmentList._segments = undefined;
    els.segmentList._audioConfigSnapshot = null;
    els.polishResult.textContent = "";
    els.polishResult.className = "";
  });

  container.querySelector("#synthesize-full-btn").addEventListener("click", async () => {
    const resultEl = container.querySelector("#synthesize-full-result");
    const fullBtn = container.querySelector("#synthesize-full-btn");
    const segments = els.segmentList._segments || (await parseAnnotatedText());
    if (!segments.length) {
      resultEl.textContent = "没有可合成的分段";
      resultEl.className = "error";
      return;
    }
    const params = currentSynthesisParams();
    if (!params.voice_id) {
      resultEl.textContent = "请先选择音色";
      resultEl.className = "error";
      return;
    }

    let audioConfigSnapshot;
    try {
      audioConfigSnapshot = await fetchAudioConfigSnapshot();
    } catch (error) {
      resultEl.textContent = error.message;
      resultEl.className = "error";
      return;
    }

    const failures = { ...(els.segmentList._failures || {}) };
    const audioHexList = [];
    fullBtn.disabled = true;
    resultEl.className = "";

    try {
      for (let index = 0; index < segments.length; index += 1) {
        resultEl.textContent = `已完成 ${index}/${segments.length} 段…`;
        const segment = segments[index];
        try {
          const response = await fetch("/api/studio/synthesize/segment", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              text: segment.text,
              emotion: segment.emotion,
              ...params,
              audio_config: audioConfigSnapshot,
            }),
          });
          const body = await response.json();
          if (!response.ok) {
            if (window.VoiceMaxApiErrors?.handleApiError(body.detail)) return;
            throw new Error(body.detail || "合成失败");
          }
          delete failures[index];
          audioHexList.push(body.audio_hex);
        } catch (error) {
          failures[index] = error.message;
        }
        resultEl.textContent = `已完成 ${index + 1}/${segments.length} 段…`;
      }

      renderSegments(segments, failures, audioConfigSnapshot);

      if (!audioHexList.length) {
        resultEl.textContent = "所有分段合成均失败";
        resultEl.className = "error";
        return;
      }

      resultEl.textContent = "正在拼接导出…";
      try {
        const response = await fetch("/api/studio/synthesize/concat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            audio_hex_list: audioHexList,
            audio_config: audioConfigSnapshot,
          }),
        });
        const body = await response.json();
        if (!response.ok) {
          if (window.VoiceMaxApiErrors?.handleApiError(body.detail)) return;
          throw new Error(body.detail || "拼接导出失败");
        }
        const failedCount = Object.keys(failures).length;
        resultEl.textContent =
          failedCount > 0
            ? `已导出：${body.file_path}（${failedCount} 段失败，可点击重试）`
            : `已导出：${body.file_path}`;
        resultEl.className = failedCount > 0 ? "error" : "ok";
      } catch (error) {
        resultEl.textContent = error.message;
        resultEl.className = "error";
      }
    } finally {
      fullBtn.disabled = false;
    }
  });
}

window.VoiceMaxPages = window.VoiceMaxPages || {};
window.VoiceMaxPages.studio = loadStudioPage;

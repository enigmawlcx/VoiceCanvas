function usageEscapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value ?? "";
  return div.innerHTML;
}

function formatDateInput(date) {
  return date.toISOString().slice(0, 10);
}

function renderTrendChart(periods, granularity = "day") {
  if (!periods.length) return '<p class="hint">所选时间范围内暂无用量数据</p>';

  const width = 640;
  const height = 200;
  const padding = 30;
  const maxChars = Math.max(...periods.map((d) => d.characters), 1);
  const stepX = periods.length > 1 ? (width - padding * 2) / (periods.length - 1) : 0;

  const points = periods.map((d, i) => {
    const label = d.period || d.day;
    const x = padding + i * stepX;
    const y = height - padding - (d.characters / maxChars) * (height - padding * 2);
    return { x, y, label, characters: d.characters };
  });

  const polyline = points.map((p) => `${p.x},${p.y}`).join(" ");
  const circles = points
    .map(
      (p) =>
        `<circle cx="${p.x}" cy="${p.y}" r="3" fill="#0071e3"><title>${p.label}: ${p.characters} 字符</title></circle>`
    )
    .join("");
  const labels = points
    .filter((_, i) => i === 0 || i === points.length - 1 || i % Math.ceil(points.length / 6) === 0)
    .map((p) => {
      const shortLabel = granularity === "week" ? p.label : p.label.slice(5);
      return `<text x="${p.x}" y="${height - 8}" font-size="10" text-anchor="middle" fill="#86868b">${shortLabel}</text>`;
    })
    .join("");

  return `
    <svg viewBox="0 0 ${width} ${height}" class="trend-chart">
      <polyline points="${polyline}" fill="none" stroke="#0071e3" stroke-width="2" />
      ${circles}
      ${labels}
    </svg>
  `;
}

function renderTotalsSummary(totals) {
  if (!totals) return "";
  const cost = Number(totals.cost_estimate || 0);
  const costText = cost > 0 ? `，估算费用 ¥${cost.toFixed(4)}` : "";
  return `<p class="hint">合计：${totals.characters} 字符，${totals.tokens} Token${costText}</p>`;
}

function renderFeatureBreakdown(byFeature) {
  if (!byFeature.length) return '<p class="hint">暂无数据</p>';
  const maxCharacters = Math.max(...byFeature.map((f) => f.characters), 1);
  return `
    <table class="usage-table">
      <thead><tr><th>功能</th><th>调用次数</th><th>字符数</th><th>Token数</th><th></th></tr></thead>
      <tbody>
        ${byFeature
          .map(
            (f) => `
          <tr>
            <td>${usageEscapeHtml(f.feature)}</td>
            <td>${f.count}</td>
            <td>${f.characters}</td>
            <td>${f.tokens}</td>
            <td style="width:40%;">
              <div class="bar-track"><div class="bar-fill" style="width:${(f.characters / maxCharacters) * 100}%"></div></div>
            </td>
          </tr>`
          )
          .join("")}
      </tbody>
    </table>
  `;
}

function renderLogsTable(items) {
  if (!items.length) return '<p class="hint">暂无明细记录</p>';
  return `
    <table class="usage-table">
      <thead>
        <tr><th>时间</th><th>功能</th><th>模型</th><th>字符数</th><th>Token数</th><th>音色</th><th>状态</th></tr>
      </thead>
      <tbody>
        ${items
          .map(
            (item) => `
          <tr>
            <td>${usageEscapeHtml(item.timestamp)}</td>
            <td>${usageEscapeHtml(item.feature)}</td>
            <td>${usageEscapeHtml(item.model || "-")}</td>
            <td>${item.characters ?? "-"}</td>
            <td>${item.tokens ?? "-"}</td>
            <td>${usageEscapeHtml(item.voice_id || "-")}</td>
            <td>${usageEscapeHtml(item.status)}</td>
          </tr>`
          )
          .join("")}
      </tbody>
    </table>
  `;
}

async function loadUsagePage(container) {
  const today = new Date();
  const monthAgo = new Date(today.getTime() - 29 * 24 * 60 * 60 * 1000);

  container.innerHTML = `
    <div class="page usage-page">
      <h1>报表</h1>

      <section class="card">
        <div class="field-row">
          <label>开始日期</label>
          <input type="date" id="usage-start" value="${formatDateInput(monthAgo)}" />
          <label>结束日期</label>
          <input type="date" id="usage-end" value="${formatDateInput(today)}" />
          <button id="usage-query">查询</button>
          <button id="usage-export" class="secondary">导出 CSV</button>
          <label>趋势粒度</label>
          <select id="usage-granularity">
            <option value="day" selected>按天</option>
            <option value="week">按周</option>
          </select>
        </div>
      </section>

      <section class="card">
        <h2 id="trend-title">用量趋势（按天，字符数）</h2>
        <div id="usage-totals"></div>
        <div id="trend-chart"><p class="hint">加载中...</p></div>
      </section>

      <section class="card">
        <h2>按功能拆分</h2>
        <div id="feature-breakdown"><p class="hint">加载中...</p></div>
      </section>

      <section class="card">
        <div class="field-row">
          <h2 style="flex:1;">明细记录</h2>
          <select id="usage-feature-filter">
            <option value="">全部功能</option>
            <option value="synthesize">合成</option>
            <option value="polish">润色</option>
            <option value="clone">克隆</option>
            <option value="design">设计</option>
          </select>
        </div>
        <div id="logs-table"><p class="hint">加载中...</p></div>
        <div class="field-row" id="pagination-row">
          <button id="prev-page" class="secondary">上一页</button>
          <span id="page-info"></span>
          <button id="next-page" class="secondary">下一页</button>
        </div>
      </section>
    </div>
  `;

  const state = { page: 1, pageSize: 20, granularity: "day" };

  function currentRange() {
    return {
      start: container.querySelector("#usage-start").value,
      end: container.querySelector("#usage-end").value,
      feature: container.querySelector("#usage-feature-filter").value,
      granularity: container.querySelector("#usage-granularity").value,
    };
  }

  async function loadSummary() {
    const { start, end, granularity } = currentRange();
    const params = new URLSearchParams({ start, end, granularity });
    const response = await fetch(`/api/usage/summary?${params}`);
    const data = await response.json();
    if (!window.__isPageActive?.()) return;
    state.granularity = data.granularity || granularity;
    const periods = data.by_day || data.by_week || [];
    container.querySelector("#trend-title").textContent =
      state.granularity === "week" ? "用量趋势（按周，字符数）" : "用量趋势（按天，字符数）";
    container.querySelector("#usage-totals").innerHTML = renderTotalsSummary(data.totals);
    container.querySelector("#trend-chart").innerHTML = renderTrendChart(periods, state.granularity);
    container.querySelector("#feature-breakdown").innerHTML = renderFeatureBreakdown(data.by_feature || []);
  }

  async function loadLogs() {
    const { start, end, feature } = currentRange();
    const params = new URLSearchParams({
      start,
      end,
      page: state.page,
      page_size: state.pageSize,
    });
    if (feature) params.set("feature", feature);
    const response = await fetch(`/api/usage/logs?${params}`);
    const data = await response.json();
    if (!window.__isPageActive?.()) return;
    container.querySelector("#logs-table").innerHTML = renderLogsTable(data.items || []);
    const totalPages = Math.max(Math.ceil(data.total / state.pageSize), 1);
    container.querySelector("#page-info").textContent = `第 ${state.page} / ${totalPages} 页（共 ${data.total} 条）`;
  }

  async function reloadAll() {
    await Promise.all([loadSummary(), loadLogs()]);
  }

  container.querySelector("#usage-query").addEventListener("click", () => {
    state.page = 1;
    reloadAll();
  });

  container.querySelector("#usage-granularity").addEventListener("change", () => {
    loadSummary();
  });

  container.querySelector("#usage-feature-filter").addEventListener("change", () => {
    state.page = 1;
    loadLogs();
  });

  container.querySelector("#prev-page").addEventListener("click", () => {
    if (state.page > 1) {
      state.page -= 1;
      loadLogs();
    }
  });

  container.querySelector("#next-page").addEventListener("click", () => {
    state.page += 1;
    loadLogs();
  });

  container.querySelector("#usage-export").addEventListener("click", () => {
    const { start, end, feature } = currentRange();
    const params = new URLSearchParams({ start, end });
    if (feature) params.set("feature", feature);
    window.open(`/api/usage/export?${params}`, "_blank");
  });

  await reloadAll();
}

window.VoiceMaxPages = window.VoiceMaxPages || {};
window.VoiceMaxPages.usage = loadUsagePage;

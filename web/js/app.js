let pageGeneration = 0;

function navigateToSettings(hint) {
  if (hint) sessionStorage.setItem("voicemax.settings.hint", hint);
  switchPage("settings");
}

window.VoiceMaxNavigate = { toSettings: navigateToSettings };

function switchPage(page) {
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.classList.toggle("active", item.dataset.page === page);
  });

  const content = document.getElementById("content");
  const loader = window.VoiceMaxPages && window.VoiceMaxPages[page];
  pageGeneration += 1;
  const generation = pageGeneration;
  window.__isPageActive = () => pageGeneration === generation;

  if (loader) {
    content.innerHTML = "";
    Promise.resolve(loader(content)).catch((error) => {
      if (!window.__isPageActive()) return;
      console.error(`加载页面 ${page} 失败`, error);
      content.innerHTML = `<p class="error">页面加载失败：${error.message || error}</p>`;
    });
  } else {
    content.innerHTML = "<p>页面内容占位，后续模块开发中填充。</p>";
  }
}

function checkHealth() {
  const indicator = document.getElementById("health-indicator");
  fetch("/api/health")
    .then((response) => response.json())
    .then((data) => {
      const isOk = data.status === "ok";
      indicator.textContent = isOk ? "服务正常" : "服务异常";
      indicator.classList.toggle("ok", isOk);
    })
    .catch(() => {
      indicator.textContent = "无法连接";
      indicator.classList.remove("ok");
    });
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.addEventListener("click", () => switchPage(item.dataset.page));
  });
  checkHealth();

  const initialPage = document.querySelector(".nav-item.active")?.dataset.page || "settings";
  switchPage(initialPage);
});

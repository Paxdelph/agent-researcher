(function () {
  let watchId = null;
  var ARTIFACT_KEY = "agentResearcher.artifact";

  function currentArtifact() {
    var preview = document.getElementById("artifact-preview");
    if (preview && preview.dataset.artifact) return preview.dataset.artifact;
    try {
      return sessionStorage.getItem(ARTIFACT_KEY) || "plan";
    } catch (_) {
      return "plan";
    }
  }

  function rememberArtifact(id) {
    if (!id) return;
    try {
      sessionStorage.setItem(ARTIFACT_KEY, id);
    } catch (_) {}
  }

  function wireChatEnter() {
    const form = document.querySelector(".chat-form");
    if (!form) return;
    const ta = form.querySelector("textarea");
    if (!ta || ta.dataset.wired === "1") return;
    ta.dataset.wired = "1";
    ta.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        if (!ta.disabled && ta.value.trim()) {
          form.requestSubmit();
        }
      }
    });
  }

  function scrollChatOnly() {
    const log = document.getElementById("chat-log");
    if (log) log.scrollTop = log.scrollHeight;
  }

  function stopWatch() {
    if (watchId !== null) {
      clearInterval(watchId);
      watchId = null;
    }
    document.body.classList.remove("job-running");
  }

  function refreshLivePanels() {
    const chat = document.getElementById("lead-chat");
    if (chat) htmx.trigger(chat, "refresh");
    const callLog = document.getElementById("call-log");
    if (callLog) htmx.trigger(callLog, "refresh");
    const status = document.getElementById("header-status");
    if (status) htmx.trigger(status, "refresh");
  }

  function refreshShellOnce() {
    stopWatch();
    var art = currentArtifact();
    rememberArtifact(art);
    const body = document.getElementById("app-body");
    if (body) {
      htmx.ajax("GET", "/partials/app?artifact=" + encodeURIComponent(art), {
        target: "#app-body",
        swap: "outerHTML",
      });
    }
    const status = document.getElementById("header-status");
    if (status) htmx.trigger(status, "refresh");
  }

  async function fetchHealth() {
    const r = await fetch("/health", { cache: "no-store" });
    if (!r.ok) throw new Error("health failed");
    return r.json();
  }

  function startJobWatch() {
    if (watchId !== null) return;
    document.body.classList.add("job-running");
    refreshLivePanels();
    watchId = setInterval(async function () {
      try {
        const j = await fetchHealth();
        if (j.status !== "running") {
          document.body.classList.remove("job-running");
          refreshShellOnce();
          return;
        }
        refreshLivePanels();
      } catch (_) {
        /* keep watching */
      }
    }, 1200);
  }

  function activateBriefTab(tabId) {
    var panel = document.getElementById("brief-panel");
    if (!panel || !tabId) return;
    panel.querySelectorAll(".brief-tab").forEach(function (btn) {
      var on = btn.dataset.briefTab === tabId;
      btn.classList.toggle("is-active", on);
      btn.setAttribute("aria-selected", on ? "true" : "false");
    });
    panel.querySelectorAll(".brief-pane").forEach(function (pane) {
      var on = pane.dataset.briefPane === tabId;
      pane.classList.toggle("is-active", on);
      if (on) pane.removeAttribute("hidden");
      else pane.setAttribute("hidden", "");
    });
    try {
      sessionStorage.setItem("agentResearcher.briefTab", tabId);
    } catch (_) {}
  }

  function restoreBriefTab() {
    var saved = null;
    try {
      saved = sessionStorage.getItem("agentResearcher.briefTab");
    } catch (_) {}
    if (saved === "question" || saved === "context") activateBriefTab(saved);
  }

  document.body.addEventListener("click", function (e) {
    var btn = e.target && e.target.closest ? e.target.closest(".brief-tab") : null;
    if (!btn) return;
    e.preventDefault();
    activateBriefTab(btn.dataset.briefTab);
  });

  document.body.addEventListener("htmx:afterSwap", function (e) {
    wireChatEnter();
    restoreBriefTab();
    var target = e && e.detail && e.detail.target;
    if (target && target.id === "artifact-preview" && target.dataset.artifact) {
      rememberArtifact(target.dataset.artifact);
    }
    if (target && target.id === "lead-chat") scrollChatOnly();
  });

  document.body.addEventListener("htmx:configRequest", function (e) {
    var elt = e && e.detail && e.detail.elt;
    if (elt && elt.classList && elt.classList.contains("artifact-tab")) {
      rememberArtifact(elt.dataset.artifact);
    }
  });

  document.body.addEventListener("jobWatch", startJobWatch);
  document.body.addEventListener("jobDone", refreshShellOnce);
  document.body.addEventListener("refreshChat", function () {
    const chat = document.getElementById("lead-chat");
    if (chat) htmx.trigger(chat, "refresh");
  });
  document.body.addEventListener("refreshStatus", function () {
    const status = document.getElementById("header-status");
    if (status) htmx.trigger(status, "refresh");
  });

  wireChatEnter();
  restoreBriefTab();
  rememberArtifact(currentArtifact());

  fetchHealth()
    .then(function (j) {
      if (j.status === "running") startJobWatch();
    })
    .catch(function () {});
})();

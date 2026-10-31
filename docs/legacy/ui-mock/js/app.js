// ---------------------------------------------------------------------------
// Persona Forge — product mock behavior
// Operates entirely on TENANTS data from mockData.js. No backend, no real
// model — a clickable prototype for design-partner walkthroughs.
// ---------------------------------------------------------------------------

let currentConversationId = null;
let auditPage = 0;
const AUDIT_PAGE_SIZE = 8;
let auditFilter = "all";

document.addEventListener("DOMContentLoaded", () => {
  wireLogin();
  checkExistingSession();
  wireNav();
  wireDropdowns();
  wireTenantSwitcher();
  wireChat();
  wireAuditFilters();
  wireAuditPagination();
  wireInviteUser();
  wireReviewDrawer();
  wireProfileDrawer();
  wireSignOut();
  wireLockedFeatures();
  wireManageUserDrawer();
});

// --- Login / sign out --------------------------------------------------

function wireLogin() {
  document.getElementById("login-form").addEventListener("submit", (e) => {
    e.preventDefault();
    setSession(true);
    enterApp();
  });
}

// If the person already "logged in" from the landing page's login modal
// (../index.html), a flag is set in localStorage before redirecting here —
// skip this screen's own login form and open straight to the dashboard.
// Opening app/index.html directly still shows the login form as normal.
function checkExistingSession() {
  if (hasSession()) enterApp();
}

function hasSession() {
  try {
    return localStorage.getItem("pf_authenticated") === "true";
  } catch (err) {
    return false;
  }
}

function setSession(value) {
  try {
    if (value) localStorage.setItem("pf_authenticated", "true");
    else localStorage.removeItem("pf_authenticated");
  } catch (err) {
    // localStorage unavailable (e.g. private browsing) — session just
    // won't persist across reloads, login form still works either way.
  }
}

function enterApp() {
  document.getElementById("login-screen").style.display = "none";
  document.getElementById("app-shell").style.display = "flex";
  setActiveView("dashboard");
  renderAll();
}

function wireSignOut() {
  document.getElementById("sign-out-btn").addEventListener("click", () => {
    setSession(false);
    document.getElementById("app-shell").style.display = "none";
    document.getElementById("login-screen").style.display = "flex";
    closeAllDropdowns();
  });
}

// --- Nav / view routing ---------------------------------------------------

function wireNav() {
  document.querySelectorAll(".pf-nav-btn[data-view]").forEach((btn) => {
    btn.addEventListener("click", () => setActiveView(btn.dataset.view));
  });
  document.querySelectorAll("a[data-view]").forEach((link) => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      setActiveView(link.dataset.view);
    });
  });
}

function setActiveView(viewName) {
  document.querySelectorAll(".pf-view").forEach((section) => {
    section.classList.toggle("is-active", section.dataset.view === viewName);
  });
  document.querySelectorAll(".pf-nav-btn[data-view]").forEach((btn) => {
    btn.classList.toggle("is-active", btn.dataset.view === viewName);
  });
}

// --- Dropdowns (org switcher, notifications, avatar menu) -----------------

function wireDropdowns() {
  bindDropdown("org-switcher-btn", "org-dropdown");
  bindDropdown("bell-btn", "notif-dropdown");
  bindDropdown("avatar-btn", "avatar-dropdown");

  document.addEventListener("click", (e) => {
    if (!e.target.closest(".pf-org-wrap")) closeAllDropdowns();
  });

  document.querySelectorAll("#org-dropdown [data-tenant]").forEach((btn) => {
    btn.addEventListener("click", () => {
      currentTenantId = btn.dataset.tenant;
      closeAllDropdowns();
      renderAll();
      showToast(`Switched to ${getTenant().name}`);
    });
  });

  document.getElementById("menu-profile-btn").addEventListener("click", () => {
    closeAllDropdowns();
    openProfileDrawer();
  });
}

function bindDropdown(btnId, dropdownId) {
  const btn = document.getElementById(btnId);
  const dropdown = document.getElementById(dropdownId);
  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    const wasOpen = dropdown.classList.contains("is-open");
    closeAllDropdowns();
    if (!wasOpen) dropdown.classList.add("is-open");
  });
}

function closeAllDropdowns() {
  document.querySelectorAll(".pf-dropdown").forEach((d) => d.classList.remove("is-open"));
}

function wireTenantSwitcher() {
  // kept separate from bindDropdown wiring above for clarity; no-op placeholder
}

// --- Master render: called on login and every tenant switch ---------------

function renderAll() {
  const tenant = getTenant();

  document.getElementById("org-avatar").textContent = tenant.initials;
  document.getElementById("org-name").textContent = tenant.name;
  document.getElementById("avatar-btn").textContent = tenant.currentUser.initials;
  document.getElementById("avatar-menu-name").textContent = tenant.currentUser.name;

  auditPage = 0;
  auditFilter = "all";
  document.querySelectorAll("#audit-filters .pf-chip").forEach((c) => c.classList.remove("is-active"));
  document.querySelector('#audit-filters [data-filter="all"]').classList.add("is-active");

  renderNotifications();
  renderDashboard();
  renderPersona();
  renderAgents();
  populateChatAgentSelect();
  renderConversationList();
  resetChat();
  renderReviewQueue();
  renderAuditLog();
  renderUsers();
  renderBilling();
  renderAllowanceAlert();
  renderAgentUsageTable();
  renderAddOns();
  renderAuthMethods();
  renderAdminActivityLog();
}

// --- Notifications ----------------------------------------------------

function renderNotifications() {
  const tenant = getTenant();
  const list = document.getElementById("notif-list");
  list.innerHTML = tenant.notifications
    .map(
      (n) => `
      <div class="pf-notif-item">
        <div class="pf-notif-title">${escapeHtml(n.title)}</div>
        <div class="pf-notif-detail">${escapeHtml(n.detail)}</div>
        <div class="pf-notif-time">${escapeHtml(n.time)}</div>
      </div>`
    )
    .join("");

  const hasUnread = tenant.notifications.some((n) => n.unread);
  document.getElementById("bell-dot").style.display = hasUnread ? "block" : "none";
}

// --- Dashboard ------------------------------------------------------------

function renderDashboard() {
  const tenant = getTenant();

  document.getElementById("dashboard-sub").textContent =
    `${tenant.persona.name} persona · ${tenant.persona.version} · ${tenant.usage.activeUsers} active users`;

  const usedM = (tenant.billing.tokensUsed / 1_000_000).toFixed(2);
  const includedM = (tenant.billing.tokensIncluded / 1_000_000).toFixed(0);
  const pct = Math.round((tenant.billing.tokensUsed / tenant.billing.tokensIncluded) * 100);

  document.getElementById("stat-tokens-used").textContent = `${usedM}M`;
  document.getElementById("stat-tokens-bar").style.width = `${Math.min(pct, 100)}%`;
  document.getElementById("stat-tokens-note").textContent = `${pct}% of ${includedM}M included`;

  document.getElementById("stat-active-users").textContent = tenant.usage.activeUsers;
  document.getElementById("stat-seats-note").textContent = `of ${tenant.usage.licensedSeats} licensed seats`;

  document.getElementById("stat-conformance").textContent = `${tenant.usage.conformanceRate}%`;

  const openCount = tenant.reviewQueue.filter((r) => r.status === "Open").length;
  document.getElementById("stat-flagged-count").textContent = openCount;

  document.getElementById("dashboard-activity").innerHTML = tenant.auditLog
    .slice(0, 4)
    .map(rowHtmlForActivity)
    .join("");

  const bars = document.getElementById("dashboard-usage-bars");
  const max = Math.max(...tenant.usageByWeek);
  bars.innerHTML = tenant.usageByWeek
    .map((v) => `<div class="pf-week-bar" style="height:${Math.round((v / max) * 100)}%;"></div>`)
    .join("");
}

function rowHtmlForActivity(entry) {
  return `
    <div class="pf-row">
      <div class="pf-row-main">
        <div class="pf-row-title">${escapeHtml(entry.agent)}</div>
        <div class="pf-row-meta">${escapeHtml(entry.snippet)}</div>
      </div>
      ${badgeHtml(entry.outcome)}
    </div>`;
}

function badgeHtml(outcome) {
  if (outcome === "Verified") {
    return `<span class="pf-badge pf-badge--verified"><span class="pf-badge-dot"></span>Verified</span>`;
  }
  return `<span class="pf-badge pf-badge--flagged"><span class="pf-badge-dot"></span>Flagged</span>`;
}

// --- Persona ----------------------------------------------------------

function renderPersona() {
  const p = getTenant().persona;

  document.getElementById("persona-name").textContent = p.name;
  document.getElementById("persona-meta").textContent =
    `Version ${p.version.replace("v", "")} · updated ${p.updatedAt} by ${p.updatedBy}`;
  document.getElementById("persona-tone").textContent = p.tone;
  document.getElementById("persona-scope").textContent = p.scope;
  document.getElementById("persona-forbidden").innerHTML = p.forbiddenTopics
    .map((t) => `<li>${escapeHtml(t)}</li>`)
    .join("");
  document.getElementById("persona-escalation").textContent = p.escalation;

  const validatedBadge = document.getElementById("persona-validated-badge");
  validatedBadge.style.display = p.validated ? "inline-flex" : "none";

  const transcript = document.getElementById("persona-example-transcript");
  transcript.innerHTML = (p.exampleTranscript || [])
    .map(
      (line) =>
        `<div class="pf-mini-msg pf-mini-msg--${line.who === "user" ? "user" : "agent"}">${escapeHtml(line.text)}</div>`
    )
    .join("");

  const history = document.getElementById("persona-history");
  const currentRow = `
    <div class="pf-row">
      <div class="pf-row-main">
        <div class="pf-row-title">${escapeHtml(p.version)} — current</div>
        <div class="pf-row-meta">${escapeHtml(p.updatedAt)} · ${escapeHtml(p.updatedBy)}</div>
      </div>
      <span class="pf-badge pf-badge--verified">Active</span>
    </div>`;
  const priorRows = p.priorVersions
    .map(
      (v) => `
      <div class="pf-row">
        <div class="pf-row-main">
          <div class="pf-row-title">${escapeHtml(v.version)}</div>
          <div class="pf-row-meta">${escapeHtml(v.updatedAt)} · ${escapeHtml(v.note)}</div>
        </div>
      </div>`
    )
    .join("");
  history.innerHTML = currentRow + priorRows;
}

// --- Agents -----------------------------------------------------------

function renderAgents() {
  const grid = document.getElementById("agents-grid");
  grid.innerHTML = getTenant()
    .agents.map(
      (agent) => `
      <div class="pf-agent-card">
        <div class="pf-agent-name">${escapeHtml(agent.name)}</div>
        <div class="pf-agent-desc">${escapeHtml(agent.description)}</div>
        <div class="pf-agent-meta">
          <span>Inputs: ${escapeHtml(agent.inputs)}</span>
          <span>Connectors: ${escapeHtml(agent.connectors)}</span>
        </div>
        <button class="pf-btn pf-btn--ghost" data-open-agent="${agent.id}">Open in chat</button>
      </div>`
    )
    .join("");

  grid.querySelectorAll("[data-open-agent]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.getElementById("chat-agent-select").value = btn.dataset.openAgent;
      setActiveView("chat");
    });
  });
}

// --- Chat ---------------------------------------------------------------

function populateChatAgentSelect() {
  const select = document.getElementById("chat-agent-select");
  select.innerHTML = getTenant()
    .agents.map((a) => `<option value="${a.id}">${escapeHtml(a.name)}</option>`)
    .join("");

  document.getElementById("chat-persona-badge").innerHTML =
    `<span class="pf-badge-dot"></span>Persona: ${escapeHtml(getTenant().persona.name)} ${escapeHtml(getTenant().persona.version)}`;
}

function renderConversationList() {
  const tenant = getTenant();
  const list = document.getElementById("chat-conversation-list");
  currentConversationId = tenant.conversations[0] ? tenant.conversations[0].id : null;

  list.innerHTML = tenant.conversations
    .map(
      (c) => `
      <div class="pf-chat-list-item ${c.id === currentConversationId ? "is-active" : ""}" data-conv-id="${c.id}">
        <div class="pf-chat-list-title">${escapeHtml(c.title)}</div>
        <div class="pf-chat-list-meta">${escapeHtml(c.agent)} · ${escapeHtml(c.time)}</div>
      </div>`
    )
    .join("");

  list.querySelectorAll("[data-conv-id]").forEach((item) => {
    item.addEventListener("click", () => {
      currentConversationId = item.dataset.convId;
      list.querySelectorAll(".pf-chat-list-item").forEach((el) =>
        el.classList.toggle("is-active", el.dataset.convId === currentConversationId)
      );
      resetChat();
    });
  });
}

function wireChat() {
  document.getElementById("new-conversation-btn").addEventListener("click", () => {
    currentConversationId = null;
    document
      .querySelectorAll("#chat-conversation-list .pf-chat-list-item")
      .forEach((el) => el.classList.remove("is-active"));
    resetChat(true);
  });

  const form = document.getElementById("chat-form");
  const input = document.getElementById("chat-input");

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;

    const body = document.getElementById("chat-body");
    appendChatMessage(body, "user", text);
    input.value = "";
    body.scrollTop = body.scrollHeight;

    showTyping(body);
    const match = matchChatScript(text);
    setTimeout(() => {
      removeTyping(body);
      appendChatMessage(body, "agent", match.reply, match.verified, match.flagReason);
      body.scrollTop = body.scrollHeight;
    }, 600);
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      form.requestSubmit();
    }
  });
}

function resetChat(isNew) {
  const body = document.getElementById("chat-body");
  body.innerHTML = "";
  const tenant = getTenant();

  if (isNew || !currentConversationId) {
    appendChatMessage(body, "agent", "Hi — ask me anything about the current deal room. I'll only answer from what's attached, and I'll flag anything outside my scope.", true);
    return;
  }

  const convo = tenant.conversations.find((c) => c.id === currentConversationId);
  const seedText = convo ? convo.title.replace(/ — declined$/, "") : "customer concentration";
  appendChatMessage(body, "user", `What's the story on ${seedText.toLowerCase()}?`);
  const match = matchChatScript(seedText);
  appendChatMessage(body, "agent", match.reply, match.verified, match.flagReason);
}

function matchChatScript(text) {
  const lower = text.toLowerCase();
  const found = getTenant().chatScript.find((entry) => entry.keywords.some((kw) => lower.includes(kw)));
  return found || getTenant().chatDefaultReply;
}

function showTyping(container) {
  const el = document.createElement("div");
  el.className = "pf-msg-group pf-msg-group--agent";
  el.id = "typing-indicator";
  el.innerHTML = `<div class="pf-msg pf-msg--agent pf-typing"><span></span><span></span><span></span></div>`;
  container.appendChild(el);
  container.scrollTop = container.scrollHeight;
}

function removeTyping(container) {
  const el = document.getElementById("typing-indicator");
  if (el) container.removeChild(el);
}

function appendChatMessage(container, from, text, verified, flagReason) {
  const now = new Date();
  const time = now.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });

  const group = document.createElement("div");
  group.className = `pf-msg-group pf-msg-group--${from}`;

  if (from === "user") {
    group.innerHTML = `<div class="pf-msg pf-msg--user">${escapeHtml(text)}</div><div class="pf-msg-time">${time}</div>`;
  } else {
    const flaggedClass = verified === false ? " is-flagged" : "";
    const badge =
      verified === false
        ? `<span class="pf-badge pf-badge--flagged"><span class="pf-badge-dot"></span>Flagged — ${escapeHtml(flagReason || "Routed for review")}</span>`
        : `<span class="pf-badge pf-badge--verified"><span class="pf-badge-dot"></span>Verified against ${escapeHtml(getTenant().persona.version)}</span>`;
    group.innerHTML = `
      <div class="pf-msg pf-msg--agent${flaggedClass}">${escapeHtml(text)}</div>
      <div class="pf-msg-badge-row">${badge}</div>
      <div class="pf-msg-time">${time}</div>`;
  }

  container.appendChild(group);
}

// --- Review queue -------------------------------------------------------

function renderReviewQueue() {
  const body = document.getElementById("review-queue-body");
  body.innerHTML = getTenant()
    .reviewQueue.map(
      (item) => `
      <tr class="pf-table-row--clickable" data-review-id="${item.id}">
        <td>${escapeHtml(item.agent)}</td>
        <td>${escapeHtml(item.category)}</td>
        <td>${escapeHtml(item.severity)}</td>
        <td><span class="pf-badge ${item.status === "Open" ? "pf-badge--flagged" : "pf-badge--muted"}">${escapeHtml(item.status)}</span></td>
        <td>${escapeHtml(item.time)}</td>
      </tr>`
    )
    .join("");

  body.querySelectorAll("tr[data-review-id]").forEach((row) => {
    row.addEventListener("click", () => openReviewDrawer(row.dataset.reviewId));
  });
}

function openReviewDrawer(id) {
  const item = getTenant().reviewQueue.find((r) => r.id === id);
  if (!item) return;

  document.getElementById("review-drawer-title").textContent = item.category;
  document.getElementById("review-drawer-sub").textContent = `${item.agent} · ${item.time}`;
  document.getElementById("review-drawer-body").innerHTML = `
    <div class="pf-drawer-row"><span class="pf-drawer-row-label">Severity</span><span>${escapeHtml(item.severity)}</span></div>
    <div class="pf-drawer-row"><span class="pf-drawer-row-label">Status</span><span>${escapeHtml(item.status)}</span></div>
    <div class="pf-drawer-row" style="display:block;">
      <span class="pf-drawer-row-label">What happened</span>
      <p style="margin:6px 0 0; font-size:13px; line-height:1.6;">${escapeHtml(item.snippet)}</p>
    </div>`;

  const backdrop = document.getElementById("review-drawer-backdrop");
  backdrop.classList.add("is-open");
  backdrop.dataset.currentId = id;

  const resolveBtn = document.getElementById("review-resolve-btn");
  resolveBtn.style.display = item.status === "Open" ? "inline-block" : "none";
}

function wireReviewDrawer() {
  const backdrop = document.getElementById("review-drawer-backdrop");
  document.getElementById("review-drawer-close").addEventListener("click", () => backdrop.classList.remove("is-open"));
  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop) backdrop.classList.remove("is-open");
  });
  document.getElementById("review-resolve-btn").addEventListener("click", () => {
    const id = backdrop.dataset.currentId;
    const item = getTenant().reviewQueue.find((r) => r.id === id);
    if (item) item.status = "Resolved";
    renderReviewQueue();
    renderDashboard();
    backdrop.classList.remove("is-open");
    showToast("Marked resolved");
  });
}

// --- Audit log --------------------------------------------------------

function renderAuditLog() {
  const tenant = getTenant();
  const rows = tenant.auditLog.filter((e) => auditFilter === "all" || e.outcome === auditFilter);
  const totalPages = Math.max(1, Math.ceil(rows.length / AUDIT_PAGE_SIZE));
  auditPage = Math.min(auditPage, totalPages - 1);
  const pageRows = rows.slice(auditPage * AUDIT_PAGE_SIZE, auditPage * AUDIT_PAGE_SIZE + AUDIT_PAGE_SIZE);

  document.getElementById("audit-log-body").innerHTML = pageRows
    .map(
      (entry) => `
      <tr>
        <td>${escapeHtml(entry.agent)}</td>
        <td class="mono">${escapeHtml(entry.personaVersion)}</td>
        <td>${badgeHtml(entry.outcome)}</td>
        <td>${escapeHtml(entry.time)}</td>
      </tr>`
    )
    .join("");

  const start = rows.length === 0 ? 0 : auditPage * AUDIT_PAGE_SIZE + 1;
  const end = Math.min(rows.length, auditPage * AUDIT_PAGE_SIZE + AUDIT_PAGE_SIZE);
  document.getElementById("audit-page-info").textContent = `Showing ${start}–${end} of ${rows.length}`;
  document.getElementById("audit-prev-btn").disabled = auditPage === 0;
  document.getElementById("audit-next-btn").disabled = auditPage >= totalPages - 1;
}

function wireAuditFilters() {
  document.querySelectorAll("#audit-filters .pf-chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      document.querySelectorAll("#audit-filters .pf-chip").forEach((c) => c.classList.remove("is-active"));
      chip.classList.add("is-active");
      auditFilter = chip.dataset.filter;
      auditPage = 0;
      renderAuditLog();
    });
  });
}

function wireAuditPagination() {
  document.getElementById("audit-prev-btn").addEventListener("click", () => {
    auditPage = Math.max(0, auditPage - 1);
    renderAuditLog();
  });
  document.getElementById("audit-next-btn").addEventListener("click", () => {
    auditPage += 1;
    renderAuditLog();
  });
}

// --- Users --------------------------------------------------------------

function renderUsers() {
  const body = document.getElementById("users-table-body");
  body.innerHTML = getTenant()
    .users.map(
      (u) => `
      <tr>
        <td>${escapeHtml(u.name)}</td>
        <td>${escapeHtml(u.email)}</td>
        <td><span class="pf-badge pf-badge--muted">${escapeHtml(u.role)}</span></td>
        <td>${escapeHtml(u.lastActive || "—")}</td>
        <td><button class="pf-btn pf-btn--ghost" data-manage-user="${escapeHtml(u.email)}" style="padding:6px 12px; font-size:12.5px;">Manage</button></td>
      </tr>`
    )
    .join("");

  body.querySelectorAll("[data-manage-user]").forEach((btn) => {
    btn.addEventListener("click", () => openManageUserDrawer(btn.dataset.manageUser));
  });
}

// --- Manage user drawer -------------------------------------------------

function openManageUserDrawer(email) {
  const user = getTenant().users.find((u) => u.email === email);
  if (!user) return;

  document.getElementById("manage-user-title").textContent = user.name;
  document.getElementById("manage-user-email").textContent = user.email;
  document.getElementById("manage-user-role").value = user.role;
  const backdrop = document.getElementById("manage-user-drawer-backdrop");
  backdrop.dataset.currentEmail = email;
  backdrop.classList.add("is-open");
}

function wireManageUserDrawer() {
  const backdrop = document.getElementById("manage-user-drawer-backdrop");
  const close = () => backdrop.classList.remove("is-open");

  document.getElementById("manage-user-close-btn").addEventListener("click", close);
  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop) close();
  });

  document.getElementById("manage-user-save-btn").addEventListener("click", () => {
    const email = backdrop.dataset.currentEmail;
    const user = getTenant().users.find((u) => u.email === email);
    if (user) {
      user.role = document.getElementById("manage-user-role").value;
      renderUsers();
      showToast(`Updated role for ${user.name}`);
    }
    close();
  });

  document.getElementById("manage-user-remove-btn").addEventListener("click", () => {
    const email = backdrop.dataset.currentEmail;
    const tenant = getTenant();
    const user = tenant.users.find((u) => u.email === email);
    tenant.users = tenant.users.filter((u) => u.email !== email);
    renderUsers();
    close();
    if (user) showToast(`Removed ${user.name} (preview only)`);
  });
}

function wireInviteUser() {
  const backdrop = document.getElementById("invite-drawer-backdrop");
  document.getElementById("invite-user-btn").addEventListener("click", () => backdrop.classList.add("is-open"));
  document.getElementById("invite-drawer-close").addEventListener("click", () => backdrop.classList.remove("is-open"));
  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop) backdrop.classList.remove("is-open");
  });

  document.getElementById("invite-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const name = document.getElementById("invite-name").value.trim();
    const email = document.getElementById("invite-email").value.trim();
    const role = document.getElementById("invite-role").value;
    if (!name || !email) return;

    getTenant().users.push({ name, email, role, lastActive: "Just now" });
    renderUsers();
    e.target.reset();
    backdrop.classList.remove("is-open");
    showToast(`Invited ${name} (preview only — no email sent)`);
  });
}

// --- Billing --------------------------------------------------------------

function renderBilling() {
  const b = getTenant().billing;
  document.getElementById("billing-plan-name").textContent = `${b.plan} plan`;
  document.getElementById("billing-plan-price").textContent = b.priceLabel;

  const usedM = (b.tokensUsed / 1_000_000).toFixed(2);
  const includedM = (b.tokensIncluded / 1_000_000).toFixed(1);
  const pct = Math.round((b.tokensUsed / b.tokensIncluded) * 100);

  document.getElementById("billing-usage-sub").textContent = `${usedM}M of ${includedM}M included`;
  document.getElementById("billing-usage-bar").style.width = `${Math.min(pct, 100)}%`;
  document.getElementById("billing-overage-rate").textContent = `Overage: ${b.overageRate}`;
  document.getElementById("billing-next-date").textContent = b.nextInvoiceDate;

  document.getElementById("billing-invoices-body").innerHTML = b.invoices
    .map(
      (inv) => `
      <tr>
        <td>${escapeHtml(inv.date)}</td>
        <td>${escapeHtml(inv.amount)}</td>
        <td><span class="pf-badge pf-badge--verified">${escapeHtml(inv.status)}</span></td>
      </tr>`
    )
    .join("");
}

// --- Usage allowance alert (PRD §3.5: configurable alerts) ----------------

const ALLOWANCE_ALERT_THRESHOLD = 0.85;

function renderAllowanceAlert() {
  const b = getTenant().billing;
  const pct = b.tokensUsed / b.tokensIncluded;
  const banner = document.getElementById("allowance-alert");

  if (pct >= ALLOWANCE_ALERT_THRESHOLD) {
    const pctLabel = Math.round(pct * 100);
    document.getElementById("allowance-alert-text").textContent =
      `You're at ${pctLabel}% of this month's token allowance. Usage beyond it bills at ${b.overageRate.toLowerCase()}.`;
    banner.style.display = "flex";
  } else {
    banner.style.display = "none";
  }
}

// --- Per-agent usage (PRD §3.5) --------------------------------------

function renderAgentUsageTable() {
  const tenant = getTenant();
  const totalTokens = tenant.agentUsage.reduce((sum, a) => sum + a.tokens, 0);

  document.getElementById("dashboard-agent-usage-body").innerHTML = tenant.agentUsage
    .map((a) => {
      const share = Math.round((a.tokens / totalTokens) * 100);
      const tokensLabel = (a.tokens / 1_000_000).toFixed(2) + "M";
      return `
        <tr>
          <td>${escapeHtml(a.agent)}</td>
          <td>${a.conversations}</td>
          <td>${tokensLabel}</td>
          <td>
            <div style="display:flex; align-items:center; gap:8px;">
              <div class="pf-bar-track" style="flex:1; margin-top:0;"><div class="pf-bar-fill" style="width:${share}%;"></div></div>
              <span style="font-size:12px; color:#8A8577; width:32px;">${share}%</span>
            </div>
          </td>
        </tr>`;
    })
    .join("");
}

// --- Billing add-ons (Concept & Monetization §2.1/2.2) -----------------

function renderAddOns() {
  const list = document.getElementById("billing-addons-list");
  list.innerHTML = ADDONS.map(
    (addon) => `
      <div class="pf-addon-row">
        <div>
          <div class="pf-addon-name">${escapeHtml(addon.name)}</div>
          <div class="pf-addon-desc">${escapeHtml(addon.description)}</div>
          <div class="pf-addon-price">${escapeHtml(addon.price)}</div>
        </div>
        <button class="pf-btn pf-btn--ghost" data-addon="${escapeHtml(addon.name)}">Add</button>
      </div>`
  ).join("");

  list.querySelectorAll("[data-addon]").forEach((btn) => {
    btn.addEventListener("click", () => showToast(`Noted interest in ${btn.dataset.addon} (preview only)`));
  });
}

// --- Security: auth methods (PRD §3.6) -----------------------------------

function renderAuthMethods() {
  const list = document.getElementById("auth-methods-list");
  list.innerHTML = AUTH_METHODS.map((m, i) => {
    if (m.status === "active") {
      return `
        <div class="pf-auth-row">
          <div>
            <div class="pf-auth-name">${escapeHtml(m.name)}</div>
            <div class="pf-auth-note">${escapeHtml(m.note)}</div>
          </div>
          <span class="pf-badge pf-badge--verified"><span class="pf-badge-dot"></span>Active</span>
        </div>`;
    }
    return `
      <div class="pf-auth-row">
        <div>
          <div class="pf-auth-name">${escapeHtml(m.name)}</div>
          <div class="pf-auth-note">${escapeHtml(m.note)}</div>
        </div>
        <button class="pf-locked-btn" data-auth-locked="${i}">
          <svg class="pf-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" style="width:13px;height:13px;"><rect x="5" y="10" width="14" height="10" rx="2"/><path d="M8 10V7a4 4 0 018 0v3"/></svg>
          Locked
        </button>
      </div>`;
  }).join("");

  list.querySelectorAll("[data-auth-locked]").forEach((btn) => {
    btn.addEventListener("click", () =>
      openPhase2Modal({
        title: "SSO / SAML",
        body: "Enterprise single sign-on (OIDC / SAML2) is planned for the enterprise phase, alongside advanced RBAC and scheduled audit reporting.",
      })
    );
  });
}

// --- Admin activity log (PRD §3.6) ---------------------------------------

function renderAdminActivityLog() {
  document.getElementById("admin-activity-list").innerHTML = getTenant()
    .adminActivityLog.map(
      (entry) => `
      <div class="pf-row">
        <div class="pf-row-main">
          <div class="pf-row-title">${escapeHtml(entry.actor)} — ${escapeHtml(entry.action)}</div>
          <div class="pf-row-meta">${escapeHtml(entry.detail)}</div>
        </div>
        <span class="pf-row-meta">${escapeHtml(entry.time)}</span>
      </div>`
    )
    .join("");
}

// --- Phase 2 upsell modal --------------------------------------------

function openPhase2Modal({ title, body, tag = "Phase 2" }) {
  document.getElementById("phase2-modal-tag").textContent = tag;
  document.getElementById("phase2-modal-title").textContent = title;
  document.getElementById("phase2-modal-body").textContent = body;
  document.getElementById("phase2-modal-backdrop").classList.add("is-open");
}

function wireLockedFeatures() {
  const backdrop = document.getElementById("phase2-modal-backdrop");
  const close = () => backdrop.classList.remove("is-open");

  document.getElementById("phase2-modal-close").addEventListener("click", close);
  document.getElementById("phase2-modal-cta").addEventListener("click", () => {
    close();
    showToast("Noted — we'll reach out about early access (preview only)");
  });
  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop) close();
  });

  document.getElementById("nav-agent-builder-btn").addEventListener("click", () =>
    openPhase2Modal({
      title: "Agent-Creation UI",
      body: "A no-code interface for assembling a new agent from a persona, tool/data connectors, and a task definition — launching as a licensed, paid capability in Phase 2.",
    })
  );

  document.getElementById("add-persona-btn").addEventListener("click", () =>
    openPhase2Modal({
      title: "Additional personas",
      body: "The base license includes one active persona. Additional personas are licensed per persona per month, or bundled into a multi-persona tier at a discount, starting in Phase 2.",
    })
  );

  document.getElementById("schedule-report-btn").addEventListener("click", () =>
    openPhase2Modal({
      title: "Scheduled audit reports",
      body: "Periodic, exportable audit reports on a configurable cadence — summarizing violation rates, flagged incidents, and resolution status — arrive as part of the Controls & Audit service tier in Phase 2.",
    })
  );
}

// --- Profile drawer ---------------------------------------------------

function wireProfileDrawer() {
  const backdrop = document.getElementById("profile-drawer-backdrop");
  document.getElementById("profile-drawer-close").addEventListener("click", () => backdrop.classList.remove("is-open"));
  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop) backdrop.classList.remove("is-open");
  });
}

function openProfileDrawer() {
  const tenant = getTenant();
  document.getElementById("profile-name").textContent = tenant.currentUser.name;
  document.getElementById("profile-email").textContent = tenant.currentUser.email;
  document.getElementById("profile-tenant").textContent = tenant.name;
  document.getElementById("profile-drawer-backdrop").classList.add("is-open");
}

// --- Toast ----------------------------------------------------------------

let toastTimer = null;
function showToast(message) {
  const toast = document.getElementById("toast");
  toast.textContent = message;
  toast.classList.add("is-visible");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toast.classList.remove("is-visible"), 2600);
}

// --- Utility ----------------------------------------------------------

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = String(str ?? "");
  return div.innerHTML;
}

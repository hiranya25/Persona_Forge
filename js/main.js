// ---------------------------------------------------------------------------
// Persona Forge landing page — behavior
// No frameworks, no build step. Runs after the DOM is parsed.
// ---------------------------------------------------------------------------

document.addEventListener("DOMContentLoaded", () => {
  wireContactEmail();
  enableSmoothScroll();
  highlightActiveNavOnScroll();
  revealOnScroll();
  styleNavOnScroll();
  updateFormNotes();
  wireReachUsForm();
  wireWaitlistForm();
  wireLoginModal();
});

/**
 * Fills in the direct mailto link and visible email text from
 * SITE_CONFIG, so the address only has to be edited in one place
 * (js/config.js).
 */
function wireContactEmail() {
  const emailLink = document.getElementById("direct-email-link");
  const emailText = document.getElementById("contact-email-text");

  if (!window.SITE_CONFIG) return;

  const { contactEmail, applySubject } = window.SITE_CONFIG;
  const subject = encodeURIComponent(applySubject || "");

  if (emailLink) {
    emailLink.href = `mailto:${contactEmail}?subject=${subject}`;
  }
  if (emailText) {
    emailText.textContent = contactEmail;
  }
}

/**
 * The small print under each form differs depending on whether a backend
 * is configured (real send) or not (mailto fallback) — set once on load
 * so it matches what will actually happen.
 */
function updateFormNotes() {
  const usingBackend = Boolean(window.SITE_CONFIG && window.SITE_CONFIG.formEndpoint);
  const note = document.getElementById("reach-us-note");
  if (note) {
    note.textContent = usingBackend
      ? "Sent straight to us — you'll get a reply by email."
      : "Sends from your own email client — nothing is stored or transmitted by this page itself.";
  }
}

/**
 * Smooth-scrolls same-page anchor links (nav, hero "See how it works ↓").
 */
function enableSmoothScroll() {
  document.querySelectorAll('a[href^="#"]').forEach((link) => {
    link.addEventListener("click", (e) => {
      const targetId = link.getAttribute("href").slice(1);
      const target = document.getElementById(targetId);
      if (!target) return;
      e.preventDefault();
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });
}

/**
 * Adds an "active" style to the nav link matching the section currently
 * in view, using IntersectionObserver (no scroll-event polling).
 */
function highlightActiveNavOnScroll() {
  const sections = ["concept", "how", "roadmap", "waitlist", "connect"]
    .map((id) => document.getElementById(id))
    .filter(Boolean);

  const navLinks = Array.from(document.querySelectorAll(".pf-navlink"));
  if (!sections.length || !navLinks.length) return;

  const setActive = (id) => {
    navLinks.forEach((link) => {
      const isActive = link.getAttribute("href") === `#${id}`;
      link.classList.toggle("pf-navlink--active", isActive);
    });
  };

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) setActive(entry.target.id);
      });
    },
    { rootMargin: "-40% 0px -55% 0px", threshold: 0 }
  );

  sections.forEach((section) => observer.observe(section));
}

/**
 * Fades and lifts elements with the .reveal / .reveal-stagger classes into
 * place as they enter the viewport.
 */
function revealOnScroll() {
  const targets = document.querySelectorAll(".reveal, .reveal-stagger");
  if (!targets.length) return;

  const observer = new IntersectionObserver(
    (entries, obs) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          obs.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.15, rootMargin: "0px 0px -60px 0px" }
  );

  targets.forEach((el) => observer.observe(el));
}

/**
 * Adds a subtle shadow to the sticky nav once the page has scrolled.
 */
function styleNavOnScroll() {
  const nav = document.querySelector(".pf-nav");
  if (!nav) return;

  const update = () => {
    nav.classList.toggle("pf-nav--scrolled", window.scrollY > 8);
  };

  update();
  window.addEventListener("scroll", update, { passive: true });
}

// ---------------------------------------------------------------------------
// Form submission
//
// Both forms try the backend in /server first (POST to SITE_CONFIG.formEndpoint,
// which sends through your own SMTP account — see server/README.md). If no
// formEndpoint is configured, or the request fails (backend not deployed
// yet, offline, etc.), they fall back to opening a mailto: link instead, so
// the page always works even with zero backend setup.
// ---------------------------------------------------------------------------

async function submitForm({ path, payload, statusEl, mailtoSubject, mailtoBody }) {
  const { contactEmail, formEndpoint } = window.SITE_CONFIG || {};

  if (formEndpoint) {
    try {
      const res = await fetch(`${formEndpoint}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok && data.ok) {
        setStatus(statusEl, "Sent — we'll be in touch.", "ok");
        return true;
      }
      throw new Error(data.error || "Request failed");
    } catch (err) {
      console.warn("Form backend unavailable, falling back to mailto:", err);
      // fall through to mailto below
    }
  }

  const subject = encodeURIComponent(mailtoSubject);
  const body = encodeURIComponent(mailtoBody);
  window.location.href = `mailto:${contactEmail}?subject=${subject}&body=${body}`;
  setStatus(statusEl, "Opening your email client with this filled in — just hit send.", "ok");
  return true;
}

function setStatus(el, message, kind) {
  if (!el) return;
  el.textContent = message;
  el.classList.remove("pf-form-status--ok", "pf-form-status--error");
  el.classList.add(kind === "error" ? "pf-form-status--error" : "pf-form-status--ok");
}

function isHoneypotFilled(form) {
  const hp = form.elements["hp_website"];
  return Boolean(hp && hp.value.trim().length > 0);
}

function wireReachUsForm() {
  const form = document.getElementById("reach-us-form");
  const status = document.getElementById("reach-us-status");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (isHoneypotFilled(form)) return; // silently ignore likely-bot submissions

    const name = form.elements["name"].value.trim();
    const company = form.elements["company"].value.trim();
    const note = form.elements["note"].value.trim();

    if (!name || !company || !note) {
      setStatus(status, "Please fill in name, company, and a short note.", "error");
      return;
    }

    const submitBtn = form.querySelector('button[type="submit"]');
    if (submitBtn) submitBtn.disabled = true;

    await submitForm({
      path: "/api/contact",
      payload: { name, company, note },
      statusEl: status,
      mailtoSubject: `Design partner inquiry — ${company}`,
      mailtoBody: `Name: ${name}\nCompany: ${company}\n\n${note}`,
    });

    if (submitBtn) submitBtn.disabled = false;
    form.reset();
  });
}

// ---------------------------------------------------------------------------
// Login modal
//
// This is a marketing site with no real accounts — "logging in" here just
// takes a design partner into the product preview at app/index.html. On
// submit we set a flag in localStorage so the app shell skips its own
// login screen and opens straight to the dashboard; the app's own login
// screen still works on its own if someone opens app/index.html directly.
// ---------------------------------------------------------------------------

function wireLoginModal() {
  const backdrop = document.getElementById("login-modal-backdrop");
  const openBtn = document.getElementById("login-btn");
  const closeBtn = document.getElementById("login-modal-close");
  const form = document.getElementById("login-modal-form");
  if (!backdrop || !openBtn || !form) return;

  const open = () => {
    backdrop.classList.add("is-open");
    document.getElementById("login-modal-email").focus();
  };
  const close = () => backdrop.classList.remove("is-open");

  openBtn.addEventListener("click", open);
  closeBtn.addEventListener("click", close);
  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop) close();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && backdrop.classList.contains("is-open")) close();
  });

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    try {
      localStorage.setItem("pf_authenticated", "true");
    } catch (err) {
      // localStorage unavailable (e.g. private browsing) — the app's own
      // login screen will still work as a fallback.
    }
    window.location.href = "app/index.html";
  });
}

function wireWaitlistForm() {
  const form = document.getElementById("waitlist-form");
  const status = document.getElementById("waitlist-status");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (isHoneypotFilled(form)) return;

    const email = form.elements["email"].value.trim();
    if (!email || !email.includes("@")) {
      setStatus(status, "Enter a valid email address.", "error");
      return;
    }

    const submitBtn = form.querySelector('button[type="submit"]');
    if (submitBtn) submitBtn.disabled = true;

    await submitForm({
      path: "/api/waitlist",
      payload: { email },
      statusEl: status,
      mailtoSubject: "Waitlist signup",
      mailtoBody: `New waitlist signup: ${email}`,
    });

    if (submitBtn) submitBtn.disabled = false;
    form.reset();
  });
}

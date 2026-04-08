const menuToggle = document.querySelector(".menu-toggle");
const siteNav = document.querySelector(".site-nav");
const navLinks = document.querySelectorAll(".site-nav a");
const faqItems = document.querySelectorAll(".faq-item");
const requestForm = document.querySelector("#request-form");
const requestStatusBox = document.querySelector("#form-status");
const reviewForm = document.querySelector("#review-form");
const reviewStatusBox = document.querySelector("#review-status");
const reviewsList = document.querySelector("#reviews-list");
const footerCopyButton = document.querySelector(".footer-copy-button");
const footerCopyStatus = document.querySelector("#footer-copy-status");

if (menuToggle && siteNav) {
  menuToggle.addEventListener("click", () => {
    const expanded = menuToggle.getAttribute("aria-expanded") === "true";
    menuToggle.setAttribute("aria-expanded", String(!expanded));
    siteNav.classList.toggle("is-open", !expanded);
  });

  navLinks.forEach((link) => {
    link.addEventListener("click", () => {
      menuToggle.setAttribute("aria-expanded", "false");
      siteNav.classList.remove("is-open");
    });
  });
}

faqItems.forEach((item) => {
  const trigger = item.querySelector(".faq-question");
  if (!trigger) {
    return;
  }
  trigger.addEventListener("click", () => {
    item.classList.toggle("is-open");
  });
});

function setStatus(node, message, isError = false) {
  if (!node) {
    return;
  }
  node.textContent = message;
  node.classList.toggle("is-error", isError);
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

async function handleJsonSubmit(form, url, statusNode, pendingMessage) {
  if (!form) {
    return;
  }
  setStatus(statusNode, pendingMessage);
  const formData = new FormData(form);
  const payload = Object.fromEntries(formData.entries());

  try {
    const response = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) {
      const message = result.errors
        ? Object.values(result.errors)[0]
        : result.message || "Не удалось отправить форму.";
      throw new Error(message);
    }
    form.reset();
    setStatus(statusNode, result.message);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Ошибка соединения.";
    setStatus(statusNode, message, true);
  }
}

function renderReviews(items) {
  if (!reviewsList) {
    return;
  }
  if (!items.length) {
    reviewsList.innerHTML = `
      <article class="review-card">
        <p>Пока нет опубликованных отзывов. Ваш отзыв может стать первым после модерации.</p>
        <span>Ожидаю новые отклики</span>
      </article>
    `;
    return;
  }
  reviewsList.innerHTML = items.map((item) => `
    <article class="review-card">
      <p>"${escapeHtml(item.text)}"</p>
      <span>${escapeHtml(item.name)}, ${escapeHtml(item.role)}</span>
    </article>
  `).join("");
}

async function loadReviews() {
  try {
    const response = await fetch("/api/reviews");
    const result = await response.json();
    if (!response.ok) {
      throw new Error(result.message || "Не удалось загрузить отзывы.");
    }
    renderReviews(result.items || []);
  } catch (error) {
    renderReviews([]);
  }
}

if (requestForm) {
  requestForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await handleJsonSubmit(requestForm, "/api/requests", requestStatusBox, "Отправляю заявку...");
  });
}

if (reviewForm) {
  reviewForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await handleJsonSubmit(reviewForm, "/api/reviews", reviewStatusBox, "Отправляю отзыв...");
  });
}

if (footerCopyButton) {
  footerCopyButton.addEventListener("click", async () => {
    const email = footerCopyButton.getAttribute("data-copy-email") || "";
    try {
      await navigator.clipboard.writeText(email);
      setStatus(footerCopyStatus, "Почта скопирована.");
    } catch (error) {
      setStatus(footerCopyStatus, "Не удалось скопировать почту.", true);
    }
  });
}

loadReviews();

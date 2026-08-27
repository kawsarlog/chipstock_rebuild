(function () {
  function setStatus(statusEl, text, isError) {
    if (!statusEl) return;
    statusEl.textContent = text || "";
    statusEl.classList.toggle("is-error", !!isError);
    statusEl.classList.toggle("is-success", !isError && !!text);
  }

  function submitQuote(payload, submitBtn, statusEl, onSuccess) {
    submitBtn.disabled = true;
    setStatus(statusEl, "Submitting…", false);
    fetch("/api/request-quote", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    })
      .then(function (resp) {
        return resp.json().catch(function () { return {}; }).then(function (body) {
          return { ok: resp.ok, body: body };
        });
      })
      .then(function (result) {
        if (!result.ok || !result.body.ok) {
          throw new Error(result.body.error || "Request failed. Please try again.");
        }
        if (onSuccess) onSuccess();
        else window.location.href = "/thank-you";
      })
      .catch(function (error) {
        setStatus(statusEl, error.message || "Failed to submit. Please try again.", true);
      })
      .finally(function () { submitBtn.disabled = false; });
  }

  function buildPayload(form, extra) {
    var data = extra || {};
    ["name", "phone", "email", "quantity", "part_number", "message", "product_name", "page_url"].forEach(function (key) {
      var el = form.elements.namedItem(key);
      if (el) data[key] = String(el.value || "").trim();
    });
    if (!data.page_url) data.page_url = window.location.href;
    return data;
  }

  /* ── Modal form ── */
  var modal = document.getElementById("cs-quote-modal");
  var form = document.getElementById("cs-quote-form");
  var statusEl = document.getElementById("cs-quote-status");

  if (modal && form && statusEl) {
    var nameInput    = form.elements.namedItem("name");
    var phoneInput   = form.elements.namedItem("phone");
    var emailInput   = form.elements.namedItem("email");
    var qtyInput     = form.elements.namedItem("quantity");
    var partInput    = form.elements.namedItem("part_number");
    var messageInput = form.elements.namedItem("message");
    var productNameInput = form.elements.namedItem("product_name");
    var pageUrlInput = form.elements.namedItem("page_url");
    var submitBtn    = form.querySelector("button[type='submit']");
    var lastActive   = null;

    function openModal(trigger) {
      lastActive = trigger || document.activeElement;
      if (partInput && trigger && trigger.dataset.partNumber && !partInput.value) {
        partInput.value = trigger.dataset.partNumber;
      }
      if (productNameInput) {
        productNameInput.value = (trigger && trigger.dataset.productName) || "";
      }
      if (pageUrlInput) {
        pageUrlInput.value = window.location.href;
      }
      setStatus(statusEl, "", false);
      modal.classList.add("is-open");
      modal.setAttribute("aria-hidden", "false");
      document.body.classList.add("cs-modal-open");
      setTimeout(function () { if (nameInput) nameInput.focus(); }, 10);
    }

    function closeModal() {
      modal.classList.remove("is-open");
      modal.setAttribute("aria-hidden", "true");
      document.body.classList.remove("cs-modal-open");
      if (lastActive && typeof lastActive.focus === "function") lastActive.focus();
    }

    document.querySelectorAll("[data-open-quote-modal]").forEach(function (el) {
      el.addEventListener("click", function (e) { e.preventDefault(); openModal(el); });
    });
    modal.querySelectorAll("[data-close-quote-modal]").forEach(function (el) {
      el.addEventListener("click", closeModal);
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && modal.classList.contains("is-open")) closeModal();
    });

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var required = [nameInput, phoneInput, emailInput, qtyInput, messageInput];
      for (var i = 0; i < required.length; i++) {
        if (!required[i] || !String(required[i].value || "").trim()) {
          setStatus(statusEl, "Please fill in all required fields.", true);
          if (required[i]) required[i].focus();
          return;
        }
      }
      submitQuote(buildPayload(form), submitBtn, statusEl, function () {
        form.reset();
        window.location.href = "/thank-you";
      });
    });
  }

  /* ── Product detail inline form ── */
  var detailForm = document.getElementById("cs-detail-quote-form");
  var detailStatus = document.getElementById("cs-detail-quote-status");

  if (detailForm && detailStatus) {
    var detailSubmit = detailForm.querySelector("button[type='submit']");
    var detailPageUrl = detailForm.elements.namedItem("page_url");
    if (detailPageUrl) detailPageUrl.value = window.location.href;

    detailForm.addEventListener("submit", function (e) {
      e.preventDefault();
      var dName = detailForm.elements.namedItem("name");
      var dEmail = detailForm.elements.namedItem("email");
      if (!dName || !String(dName.value || "").trim()) {
        setStatus(detailStatus, "Please enter your name.", true);
        if (dName) dName.focus();
        return;
      }
      if (!dEmail || !String(dEmail.value || "").trim()) {
        setStatus(detailStatus, "Please enter your email.", true);
        if (dEmail) dEmail.focus();
        return;
      }
      submitQuote(buildPayload(detailForm), detailSubmit, detailStatus, function () {
        detailForm.reset();
        var pn = detailForm.elements.namedItem("part_number");
        if (pn && pn.defaultValue) pn.value = pn.defaultValue;
        window.location.href = "/thank-you";
      });
    });
  }
})();

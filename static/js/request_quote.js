(function () {
  var modal = document.getElementById("cs-quote-modal");
  var form = document.getElementById("cs-quote-form");
  var statusEl = document.getElementById("cs-quote-status");
  if (!modal || !form || !statusEl) return;

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

  function setStatus(text, isError) {
    statusEl.textContent = text || "";
    statusEl.classList.toggle("is-error", !!isError);
    statusEl.classList.toggle("is-success", !isError && !!text);
  }

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
    setStatus("", false);
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
        setStatus("Please fill in all required fields.", true);
        if (required[i]) required[i].focus();
        return;
      }
    }
    var payload = {
      name:         String(nameInput.value || "").trim(),
      phone:        String(phoneInput.value || "").trim(),
      email:        String(emailInput.value || "").trim(),
      quantity:     String(qtyInput.value || "").trim(),
      part_number:  String((partInput && partInput.value) || "").trim(),
      message:      String(messageInput.value || "").trim(),
      product_name: String((productNameInput && productNameInput.value) || "").trim(),
      page_url:     String((pageUrlInput && pageUrlInput.value) || window.location.href).trim(),
    };
    submitBtn.disabled = true;
    setStatus("Submitting…", false);
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
        form.reset();
        window.location.href = "/thank-you";
      })
      .catch(function (error) {
        setStatus(error.message || "Failed to submit. Please try again.", true);
      })
      .finally(function () { submitBtn.disabled = false; });
  });
})();

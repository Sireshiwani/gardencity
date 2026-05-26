(function () {
  function formatKsh(value) {
    var n = parseFloat(String(value).replace(/,/g, ""));
    if (Number.isNaN(n)) return String(value);
    if (Number.isInteger(n)) return n.toLocaleString("en-KE");
    return n.toLocaleString("en-KE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function formatFieldErrors(errors) {
    return Object.entries(errors)
      .flatMap(function (entry) {
        var field = entry[0];
        var msgs = entry[1];
        return msgs.map(function (m) {
          return field === "__all__" ? m : field + ": " + m;
        });
      })
      .join(" ");
  }

  function getCsrfToken() {
    var match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  var root = document.getElementById("booking-wizard-root");
  if (!root) return;

  var services = [];
  var team = [];
  try {
    var servicesEl = document.getElementById("booking-services-data");
    var teamEl = document.getElementById("booking-team-data");
    services = servicesEl ? JSON.parse(servicesEl.textContent) : [];
    team = teamEl ? JSON.parse(teamEl.textContent) : [];
  } catch (e) {
    services = [];
    team = [];
  }

  var step = 1;
  var feedbackEl = document.getElementById("booking-feedback");
  var form = document.getElementById("booking-wizard");
  var stepDots = root.querySelectorAll(".step-dot");
  var step1 = document.getElementById("step-1");
  var step2 = document.getElementById("step-2");
  var step3 = document.getElementById("step-3");
  var summaryEl = document.getElementById("booking-summary");
  var serviceSelect = document.getElementById("service_id");
  var submitBtn = document.getElementById("booking-submit");

  var fields = {
    customerName: document.getElementById("customer_name"),
    customerEmail: document.getElementById("customer_email"),
    customerPhone: document.getElementById("customer_phone"),
    referralCode: document.getElementById("referral_code"),
    serviceId: serviceSelect,
    appointmentTime: document.getElementById("appointment_time"),
    preferredBarber: document.getElementById("preferred_barber"),
    notes: document.getElementById("booking_notes"),
  };

  function showFeedback(message, isError) {
    if (!feedbackEl) return;
    feedbackEl.textContent = message;
    feedbackEl.classList.remove("hidden", "bg-red-500/15", "text-red-200", "bg-emerald-500/15", "text-emerald-200");
    feedbackEl.classList.add(isError ? "bg-red-500/15" : "bg-emerald-500/15");
    feedbackEl.classList.add(isError ? "text-red-200" : "text-emerald-200");
  }

  function hideFeedback() {
    if (feedbackEl) feedbackEl.classList.add("hidden");
  }

  function setStep(n) {
    step = n;
    stepDots.forEach(function (dot) {
      var s = parseInt(dot.dataset.step, 10);
      dot.classList.toggle("active", step >= s);
    });
    if (step1) step1.classList.toggle("hidden", step !== 1);
    if (step2) step2.classList.toggle("hidden", step !== 2);
    if (step3) step3.classList.toggle("hidden", step !== 3);
  }

  function populateServices() {
    if (!serviceSelect) return;
    var list = services.length ? services : [];
    if (!list.length) {
      fetch("/api/booking/options/")
        .then(function (r) {
          return r.json();
        })
        .then(function (data) {
          list = (data.services || []).map(function (s) {
            return {
              id: s.id,
              name: s.name,
              price: s.price,
              description: "",
            };
          });
          fillServiceOptions(list);
        })
        .catch(function () {});
      return;
    }
    fillServiceOptions(list);
  }

  function fillServiceOptions(list) {
    services = list;
    serviceSelect.innerHTML = '<option value="">Select a Service</option>';
    list.forEach(function (s) {
      var opt = document.createElement("option");
      opt.value = String(s.id);
      opt.textContent = s.name + " — Ksh " + formatKsh(s.price);
      serviceSelect.appendChild(opt);
    });
  }

  function selectedService() {
    return services.find(function (s) {
      return String(s.id) === fields.serviceId.value;
    });
  }

  function resolveStaffId() {
    var trimmed = (fields.preferredBarber.value || "").trim();
    if (!trimmed) return null;
    var byId = team.find(function (m) {
      return String(m.id) === trimmed;
    });
    if (byId) return byId.id;
    var lower = trimmed.toLowerCase();
    var byName = team.find(function (m) {
      return m.name.toLowerCase() === lower;
    });
    return byName ? byName.id : null;
  }

  function barberLabel() {
    var val = fields.preferredBarber.value;
    if (!val) return "Any available barber";
    var m = team.find(function (t) {
      return String(t.id) === val;
    });
    return m ? m.name : val;
  }

  function updateSummary() {
    if (!summaryEl) return;
    var svc = selectedService();
    summaryEl.innerHTML =
      "<p><strong>Name:</strong> " +
      escapeHtml(fields.customerName.value) +
      "</p>" +
      "<p><strong>Email:</strong> " +
      escapeHtml(fields.customerEmail.value || "—") +
      "</p>" +
      "<p><strong>Phone:</strong> " +
      escapeHtml(fields.customerPhone.value) +
      "</p>" +
      "<p><strong>Service:</strong> " +
      (svc ? escapeHtml(svc.name + " — Ksh " + formatKsh(svc.price)) : "—") +
      "</p>" +
      "<p><strong>Time:</strong> " +
      escapeHtml((fields.appointmentTime.value || "").replace("T", " ")) +
      "</p>" +
      "<p><strong>Referral/Membership:</strong> " +
      escapeHtml(fields.referralCode.value || "None") +
      "</p>" +
      "<p><strong>Preferred Barber:</strong> " +
      escapeHtml(barberLabel()) +
      "</p>" +
      (fields.notes.value
        ? "<p><strong>Notes:</strong> " + escapeHtml(fields.notes.value) + "</p>"
        : "");
  }

  function escapeHtml(str) {
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  populateServices();
  setStep(1);

  root.querySelectorAll("[data-wizard-next]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var from = parseInt(btn.dataset.wizardNext, 10);
      if (from === 1) {
        if (
          !fields.customerName.value.trim() ||
          !fields.customerPhone.value.trim()
        ) {
          showFeedback("Please complete all required personal details.", true);
          return;
        }
      }
      if (from === 2) {
        if (!fields.serviceId.value || !fields.appointmentTime.value) {
          showFeedback("Choose a service and appointment time before review.", true);
          return;
        }
        updateSummary();
      }
      hideFeedback();
      setStep(from + 1);
    });
  });

  root.querySelectorAll("[data-wizard-back]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      hideFeedback();
      setStep(parseInt(btn.dataset.wizardBack, 10) - 1);
    });
  });

  if (form) {
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (submitBtn) submitBtn.disabled = true;
      hideFeedback();

      var staffId = resolveStaffId();
      var extraNotes = [
        (fields.notes.value || "").trim(),
        fields.preferredBarber.value.trim() && !staffId
          ? "Preferred barber: " + fields.preferredBarber.value.trim()
          : "",
      ]
        .filter(Boolean)
        .join("\n");

      var payload = {
        customer_name: fields.customerName.value.trim(),
        customer_email: fields.customerEmail.value.trim(),
        customer_phone: fields.customerPhone.value.trim(),
        service: Number(fields.serviceId.value),
        staff: staffId,
        appointment_at: fields.appointmentTime.value,
        notes: extraNotes || undefined,
        referral_code: fields.referralCode.value.trim() || undefined,
      };

      fetch("/api/booking/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCsrfToken(),
        },
        body: JSON.stringify(payload),
      })
        .then(function (r) {
          return r.json().then(function (data) {
            return { ok: r.ok, data: data };
          });
        })
        .then(function (res) {
          if (submitBtn) submitBtn.disabled = false;
          if (res.data.ok) {
            var svc = selectedService();
            var msg = res.data.message || "Booking submitted.";
            if (svc && svc.price) {
              msg += " Estimated price: Ksh " + formatKsh(svc.price) + ".";
            }
            showFeedback(msg, false);
            form.reset();
            setStep(1);
            document.getElementById("booking")?.scrollIntoView({ behavior: "smooth" });
            return;
          }
          showFeedback(formatFieldErrors(res.data.errors || {}), true);
        })
        .catch(function () {
          if (submitBtn) submitBtn.disabled = false;
          showFeedback("Could not submit booking. Please try again.", true);
        });
    });
  }
})();

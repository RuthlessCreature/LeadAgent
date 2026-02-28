const state = {
  productProfile: null,
  icp: {
    geography: [],
    company_size: { min: null, max: null },
    industry: [],
    role_titles: [],
    revenue_range: { min: null, max: null, currency: "USD" },
    technology_stack: [],
  },
  leads: [],
  selectedLeadCard: null,
};

function normalizeBaseUrl(url) {
  return (url || "").trim().replace(/\/+$/, "");
}

const API_BASE = (() => {
  const stored = normalizeBaseUrl(localStorage.getItem("leadAgentApiBase"));
  if (stored) {
    return stored;
  }
  if (window.location.protocol === "http:" || window.location.protocol === "https:") {
    // If frontend is not served by FastAPI itself, fallback to the local backend.
    if (window.location.port === "8000") {
      return "";
    }
    return "http://127.0.0.1:8000";
  }
  return "http://127.0.0.1:8000";
})();

function buildApiUrl(path) {
  return API_BASE ? `${API_BASE}${path}` : path;
}

function $(id) {
  return document.getElementById(id);
}

function splitCsv(value) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

async function api(path, method = "GET", body = null, timeoutMs = 90000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  const options = { method, headers: {}, signal: controller.signal };
  if (body) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(buildApiUrl(path), options);
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error("Request timeout. Please reduce platforms or try SEARCH_MODE=mock.");
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed: ${response.status}`);
  }
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    return response.json();
  }
  return response.text();
}

function setStatus(message, isError = false) {
  const status = $("status");
  status.textContent = message;
  status.style.color = isError ? "#b10000" : "#2f6b00";
}

function renderJson(elementId, data) {
  $(elementId).textContent = JSON.stringify(data, null, 2);
}

function renderLeadsTable() {
  const tbody = $("leadsTable").querySelector("tbody");
  tbody.innerHTML = "";
  state.leads.forEach((lead) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${lead.company || ""}</td>
      <td>${lead.contact_name || ""}</td>
      <td>${lead.platform || ""}</td>
      <td>${Number(lead.scores?.industry || 0).toFixed(1)}</td>
      <td>${Number(lead.scores?.intent || 0).toFixed(1)}</td>
      <td>${Number(lead.scores?.contact || 0).toFixed(1)}</td>
      <td>${Number(lead.scores?.overall || 0).toFixed(1)}</td>
    `;
    tr.addEventListener("click", () => loadLeadCard(lead.lead_id));
    tbody.appendChild(tr);
  });
}

function getIcpFromForm() {
  return {
    geography: splitCsv($("icpGeography").value),
    company_size: {
      min: $("icpCompanyMin").value ? Number($("icpCompanyMin").value) : null,
      max: $("icpCompanyMax").value ? Number($("icpCompanyMax").value) : null,
    },
    industry: splitCsv($("icpIndustry").value),
    role_titles: splitCsv($("icpRoles").value),
    revenue_range: {
      min: $("icpRevenueMin").value ? Number($("icpRevenueMin").value) : null,
      max: $("icpRevenueMax").value ? Number($("icpRevenueMax").value) : null,
      currency: $("icpCurrency").value || "USD",
    },
    technology_stack: splitCsv($("icpTech").value),
  };
}

async function loadLeadCard(leadId) {
  try {
    const card = await api(`/api/v1/leads/${leadId}/card`);
    state.selectedLeadCard = card;
    renderJson("leadCardOutput", card);
  } catch (error) {
    setStatus(`Load lead card failed: ${error.message}`, true);
  }
}

async function loadTasks() {
  const tasks = await api("/api/v1/tasks");
  $("tasksOutput").innerHTML = tasks
    .map(
      (task) =>
        `<li>${task.platform} | ${task.status} | ${task.results_count} results | ${new Date(task.last_run).toLocaleString()}</li>`
    )
    .join("");
}

async function loadNotifications() {
  const notes = await api("/api/v1/notifications");
  $("notificationsOutput").innerHTML = notes
    .slice(0, 8)
    .map((note) => `<li>${new Date(note.created_at).toLocaleString()} - ${note.message}</li>`)
    .join("");
}

async function loadDashboard() {
  const metrics = await api("/api/v1/dashboard");
  renderJson("dashboardOutput", metrics);
}

async function refreshAll() {
  const leads = await api("/api/v1/leads");
  state.leads = leads;
  renderLeadsTable();
  await Promise.all([loadTasks(), loadNotifications(), loadDashboard()]);
}

$("parseProductBtn").addEventListener("click", async () => {
  try {
    const description = $("productDescription").value.trim();
    const priceHint = $("priceHint").value.trim();
    if (!description) {
      setStatus("Please enter a product description first.", true);
      return;
    }
    const profile = await api("/api/v1/input/parse-product", "POST", {
      description: `${description}\n${priceHint}`,
      llm_provider: $("llmProvider").value,
    });
    state.productProfile = profile;
    renderJson("productProfileOutput", profile);
    setStatus("Product parsed.");
  } catch (error) {
    setStatus(`Parse failed: ${error.message}`, true);
  }
});

$("normalizeIcpBtn").addEventListener("click", async () => {
  try {
    const icp = await api("/api/v1/input/icp/normalize", "POST", getIcpFromForm());
    state.icp = icp;
    renderJson("icpOutput", icp);
    setStatus("ICP normalized.");
  } catch (error) {
    setStatus(`ICP normalize failed: ${error.message}`, true);
  }
});

$("runSearchBtn").addEventListener("click", async () => {
  const runBtn = $("runSearchBtn");
  runBtn.disabled = true;
  try {
    let query = $("searchQuery").value.trim();
    if (!query) {
      query = "b2b supplier sourcing software";
      $("searchQuery").value = query;
      setStatus(`Query was empty, using default: ${query}`);
    }
    setStatus("Searching... (live mode may take 10-30s)");
    const selectedPlatforms = Array.from(
      $("platformSelector").querySelectorAll("input[type='checkbox']:checked")
    ).map((input) => input.value);
    if (!selectedPlatforms.length) {
      setStatus("Please select at least one platform.", true);
      return;
    }

    const response = await api("/api/v1/search/run", "POST", {
      query,
      icp: state.icp,
      platforms: selectedPlatforms,
      limit_per_platform: Number($("searchLimit").value || 5),
    });
    state.leads = response.leads || [];
    renderLeadsTable();
    await Promise.all([loadTasks(), loadDashboard()]);
    const allZero = state.leads.length > 0 && state.leads.every((lead) => Number(lead?.scores?.overall || 0) === 0);
    if (allZero) {
      setStatus(`Search completed with ${state.leads.length} people leads. Click "Score Leads" to calculate scores.`);
    } else {
      setStatus(`Search completed with ${state.leads.length} leads.`);
    }
  } catch (error) {
    setStatus(`Search failed: ${error.message}`, true);
  } finally {
    runBtn.disabled = false;
  }
});

$("scoreBtn").addEventListener("click", async () => {
  try {
    if (!state.leads.length) {
      setStatus("No leads to score. Run search first.", true);
      return;
    }
    const profile = state.productProfile || {
      product_name: "Default Product",
      industry_tags: [],
      feature_tags: [],
      use_cases: [],
      target_roles: [],
      price_range: "unknown",
      exclude_tags: [],
      llm_provider: "openai",
    };
    const response = await api("/api/v1/scoring/score", "POST", {
      product_profile: profile,
      icp: state.icp,
      leads: state.leads,
      weights: { industry: 0.4, intent: 0.35, contact: 0.25 },
    });
    state.leads = response.leads || [];
    renderLeadsTable();
    await Promise.all([loadDashboard(), loadNotifications()]);
    setStatus("Scoring completed.");
  } catch (error) {
    setStatus(`Scoring failed: ${error.message}`, true);
  }
});

$("dedupBtn").addEventListener("click", async () => {
  try {
    if (!state.leads.length) {
      setStatus("No leads to deduplicate.", true);
      return;
    }
    const response = await api("/api/v1/leads/deduplicate", "POST", { leads: state.leads });
    state.leads = response.leads || [];
    renderLeadsTable();
    setStatus(`Dedup completed. Removed ${response.removed_duplicates} duplicates.`);
  } catch (error) {
    setStatus(`Dedup failed: ${error.message}`, true);
  }
});

$("refreshBtn").addEventListener("click", async () => {
  try {
    await refreshAll();
    setStatus("Data refreshed.");
  } catch (error) {
    setStatus(`Refresh failed: ${error.message}`, true);
  }
});

$("templateBtn").addEventListener("click", async () => {
  try {
    if (!state.selectedLeadCard) {
      setStatus("Select one lead first.", true);
      return;
    }
    const templates = await api("/api/v1/outreach/templates", "POST", {
      lead_card: state.selectedLeadCard,
      language: $("templateLanguage").value,
    });
    renderJson("templateOutput", templates);
    setStatus("Templates generated.");
  } catch (error) {
    setStatus(`Template generation failed: ${error.message}`, true);
  }
});

$("strategyBtn").addEventListener("click", async () => {
  try {
    const query = $("searchQuery").value.trim() || "b2b lead generation";
    const result = await api("/api/v1/strategy/next", "POST", {
      query,
      lead_ids: state.leads.slice(0, 20).map((lead) => lead.lead_id),
    });
    renderJson("strategyOutput", result);
    setStatus("Strategy generated.");
  } catch (error) {
    setStatus(`Strategy failed: ${error.message}`, true);
  }
});

$("resetBtn").addEventListener("click", async () => {
  try {
    await api("/api/v1/demo/reset");
    state.productProfile = null;
    state.icp = getIcpFromForm();
    state.leads = [];
    state.selectedLeadCard = null;
    renderLeadsTable();
    $("productProfileOutput").textContent = "";
    $("icpOutput").textContent = "";
    $("leadCardOutput").textContent = "Select a lead row to load details.";
    $("templateOutput").textContent = "";
    $("strategyOutput").textContent = "";
    await Promise.all([loadTasks(), loadNotifications(), loadDashboard()]);
    setStatus("Demo state reset.");
  } catch (error) {
    setStatus(`Reset failed: ${error.message}`, true);
  }
});

function configureExportLinks() {
  const links = Array.from(document.querySelectorAll("a.link-btn[href^='/api/']"));
  for (const link of links) {
    link.href = buildApiUrl(link.getAttribute("href"));
  }
}

window.setLeadAgentApiBase = (url) => {
  const normalized = normalizeBaseUrl(url);
  if (!normalized) {
    localStorage.removeItem("leadAgentApiBase");
  } else {
    localStorage.setItem("leadAgentApiBase", normalized);
  }
  window.location.reload();
};

window.addEventListener("error", (event) => {
  setStatus(`Frontend error: ${event.message}`, true);
});

configureExportLinks();
setStatus(`API base: ${API_BASE || window.location.origin}`);
refreshAll().catch((error) => setStatus(`Initial load warning: ${error.message}`, true));

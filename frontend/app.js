const API_BASE = "/api/v1";

const state = {
    productProfile: null,
    icp: null,
    leads: [],
    dashboard: null,
    strategy: null,
    policy: null,
    selectedLeadId: "",
    complianceByLeadId: {},
    sourcingPlan: null,
    sourcingOffers: [],
    sourcingSuppliers: [],
    sourcingReport: null,
};

const STATUS_TEXT = {
    Idle: "待运行",
    Running: "运行中",
    Ready: "已完成",
    Error: "出错"
};

const PLATFORM_LABELS = {
    public_web: "公开网页",
    linkedin: "LinkedIn",
    google: "Google",
    b2b_db: "授权 B2B 数据库",
    facebook: "Facebook",
    instagram: "Instagram",
    tiktok: "TikTok",
    youtube: "YouTube",
    "1688": "1688",
    alibaba: "Alibaba",
    made_in_china: "Made-in-China",
    globalsources: "GlobalSources"
};

const SOURCE_TYPE_LABELS = {
    demo: "演示数据",
    public_web: "公开网页",
    first_party_social: "第一方社媒线索",
    licensed_database: "授权数据库",
    first_party: "第一方入站",
    customer_import: "客户自有导入",
    partner_referral: "合作伙伴推荐"
};

const CONSENT_LABELS = {
    unknown: "未知",
    legitimate_interest: "合法利益",
    consented: "已同意",
    not_applicable: "不适用",
    do_not_contact: "不可联系"
};

const VERIFY_LABELS = {
    unverified: "未验证",
    company_verified: "公司已验证",
    email_verified: "邮箱已验证",
    phone_verified: "电话已验证",
    fully_verified: "完整验证"
};

const RISK_LABELS = {
    low: "低",
    medium: "中",
    high: "高",
    "n/a": "无"
};

document.addEventListener("DOMContentLoaded", () => {
    bindEvents();
    hydrateDefaults();
    loadPolicy();
    refreshDashboard();
    refreshLeads();
});

function bindEvents() {
    document.getElementById("run-demo-btn").addEventListener("click", runDemoPipeline);
    document.getElementById("reset-demo-btn").addEventListener("click", resetDemo);
    document.getElementById("export-csv-btn").addEventListener("click", () => exportLeads("csv"));
    document.getElementById("export-pdf-btn").addEventListener("click", () => exportLeads("pdf"));
    document.getElementById("run-sourcing-btn").addEventListener("click", runSourcingPipeline);
    document.getElementById("filter-platform").addEventListener("change", refreshLeads);
    document.getElementById("filter-source").addEventListener("change", refreshLeads);
}

function hydrateDefaults() {
    document.getElementById("product-description").value =
        "商品：LeadAgent\n面向 B2B 工厂和外贸团队的 AI 找客工作台，用于买家发现、合规线索激活和 CRM 交接。";
    document.getElementById("campaign-query").value = "采购商 进口商 经销商";
    document.getElementById("icp-geo").value = "美国, 德国";
    document.getElementById("icp-industry").value = "制造业, 物流";
    document.getElementById("icp-roles").value = "采购负责人, 销售运营经理";
    document.getElementById("sourcing-product-description").value =
        "商品：不锈钢保温杯\n500ml，可定制 logo，出口包装，批发订单。";
    document.getElementById("supplier-regions").value = "中国, 广东, 浙江";
    document.getElementById("sourcing-moq").value = "500 件";
}

async function runDemoPipeline() {
    const description = document.getElementById("product-description").value.trim();
    if (!description) {
        window.alert("请先填写商品描述。");
        return;
    }

    setPipelineStatus("Running");
    clearLog();

    try {
        logStep("正在解析商品信息。");
        state.productProfile = await postJson("/input/parse-product", {
            description,
            llm_provider: "mock"
        });

        logStep("正在标准化客户画像。");
        state.icp = await postJson("/input/icp/normalize", buildIcpPayload());
        renderProductSummary();

        const query = document.getElementById("campaign-query").value.trim() || state.productProfile.product_name;
        const platforms = getSelectedPlatforms();
        logStep(`正在搜索平台：${platforms.map(labelPlatform).join("、")}。`);
        const searchResult = await postJson("/search/run", {
            query,
            icp: state.icp,
            platforms,
            limit_per_platform: 3
        });

        logStep(`正在为 ${searchResult.leads.length} 条线索评分。`);
        const scoreResult = await postJson("/scoring/score", {
            leads: searchResult.leads,
            product_profile: state.productProfile,
            icp: state.icp,
            weights: {
                industry: 0.4,
                intent: 0.35,
                contact: 0.25
            }
        });

        state.leads = scoreResult.leads;
        await refreshCompliance(state.leads.map((lead) => lead.lead_id));

        logStep("正在生成下一步策略。");
        state.strategy = await postJson("/strategy/next", {
            query,
            lead_ids: state.leads.map((lead) => lead.lead_id)
        });
        renderStrategy();

        await refreshDashboard();
        await refreshLeads();

        if (state.leads.length > 0) {
            await loadLeadDetail(state.leads[0].lead_id);
        }

        logStep("找客流程已完成。");
        setPipelineStatus("Ready");
    } catch (error) {
        logStep(error.message, true);
        setPipelineStatus("Error");
    }
}

async function runSourcingPipeline() {
    const description = document.getElementById("sourcing-product-description").value.trim()
        || document.getElementById("product-description").value.trim();
    if (!description) {
        window.alert("请先填写商品描述。");
        return;
    }

    setSourcingStatus("Running");
    const summary = document.getElementById("sourcing-summary");
    summary.innerHTML = "<p>正在生成找货计划...</p>";

    try {
        const plan = await postJson("/sourcing/plan", {
            product_description: description,
            target_platforms: getSelectedSourcingPlatforms(),
            supplier_regions: splitList(document.getElementById("supplier-regions").value),
            price_min: numberOrNull(document.getElementById("sourcing-price-min").value),
            price_max: numberOrNull(document.getElementById("sourcing-price-max").value),
            moq: document.getElementById("sourcing-moq").value.trim(),
            certifications: splitList(document.getElementById("sourcing-certifications").value),
            report_language: "CN"
        });

        state.sourcingPlan = plan;
        summary.innerHTML = "<p>正在搜索供应商来源...</p>";

        const searchResult = await postJson("/sourcing/search", {
            plan,
            limit_per_platform: 6
        });

        state.sourcingOffers = searchResult.offers || [];
        state.sourcingSuppliers = searchResult.suppliers || [];

        const report = await postJson("/sourcing/report", {
            product_name: plan.product_name,
            offers: state.sourcingOffers,
            suppliers: state.sourcingSuppliers,
            report_language: "CN"
        });

        state.sourcingReport = report;
        renderSourcingSummary();
        await refreshDashboard();
        setSourcingStatus("Ready");
    } catch (error) {
        summary.textContent = error.message;
        setSourcingStatus("Error");
    }
}

async function resetDemo() {
    await getJson("/demo/reset");
    state.productProfile = null;
    state.icp = null;
    state.leads = [];
    state.dashboard = null;
    state.strategy = null;
    state.selectedLeadId = "";
    state.complianceByLeadId = {};
    state.sourcingPlan = null;
    state.sourcingOffers = [];
    state.sourcingSuppliers = [];
    state.sourcingReport = null;

    renderProductSummary();
    renderStrategy();
    renderMetrics();
    renderLeads();
    renderLeadDetail(null, null, null);
    clearLog();
    setPipelineStatus("Idle");
    renderSourcingSummary();
}

async function refreshDashboard() {
    state.dashboard = await getJson("/dashboard");
    renderMetrics();
}

async function refreshLeads() {
    const params = new URLSearchParams();
    params.set("limit", "200");

    const platform = document.getElementById("filter-platform").value;
    const sourceType = document.getElementById("filter-source").value;

    if (platform) {
        params.set("platform", platform);
    }
    if (sourceType) {
        params.set("source_type", sourceType);
    }

    state.leads = await getJson(`/leads?${params.toString()}`);
    renderLeads();

    if (!state.selectedLeadId && state.leads.length > 0) {
        await loadLeadDetail(state.leads[0].lead_id);
    }
}

async function refreshCompliance(leadIds) {
    if (!leadIds.length) {
        state.complianceByLeadId = {};
        return;
    }

    const rows = await postJson("/compliance/scan", { lead_ids: leadIds });
    state.complianceByLeadId = rows.reduce((memo, row) => {
        memo[row.lead_id] = row;
        return memo;
    }, {});
}

async function loadLeadDetail(leadId) {
    state.selectedLeadId = leadId;
    renderLeads();

    const card = await getJson(`/leads/${leadId}/card`);
    const compliance = (await postJson("/compliance/scan", { lead_ids: [leadId] }))[0];
    const templates = await postJson("/outreach/templates", {
        lead_card: card,
        language: "CN"
    });

    state.complianceByLeadId[leadId] = compliance;
    renderLeadDetail(card, templates, compliance);
}

async function loadPolicy() {
    state.policy = await getJson("/compliance/data-policy");
    renderPolicy();
}

function buildIcpPayload() {
    return {
        geography: splitList(document.getElementById("icp-geo").value),
        company_size: {
            min: 0,
            max: 1000000
        },
        industry: splitList(document.getElementById("icp-industry").value),
        role_titles: splitList(document.getElementById("icp-roles").value),
        revenue_range: {
            min: 0,
            max: 1000000000,
            currency: "USD"
        },
        technology_stack: []
    };
}

function getSelectedPlatforms() {
    return ["linkedin", "google", "b2b_db"];
}

function getSelectedSourcingPlatforms() {
    return Array.from(document.getElementById("sourcing-platforms").selectedOptions).map((option) => option.value);
}

function splitList(raw) {
    return raw
        .split(",")
        .map((value) => value.trim())
        .filter(Boolean);
}

function numberOrNull(raw) {
    if (raw === null || raw === undefined || String(raw).trim() === "") {
        return null;
    }
    const value = Number(raw);
    return Number.isFinite(value) ? value : null;
}

function renderSourcingSummary() {
    const container = document.getElementById("sourcing-summary");
    if (!state.sourcingPlan && !state.sourcingReport) {
        container.innerHTML = "<p>还没有运行找货任务。</p>";
        return;
    }

    const plan = state.sourcingPlan;
    const report = state.sourcingReport;
    const topOffers = state.sourcingOffers.slice(0, 5);
    const topSuppliers = state.sourcingSuppliers.slice(0, 5);

    container.innerHTML = `
        <div class="stack">
            <div>
                <span class="metric-label">商品</span>
                <strong>${escapeHtml(plan.product_name)}</strong>
            </div>
            <div>
                <span class="metric-label">平台</span>
                <p>${formatList(plan.target_platforms.map(labelPlatform))}</p>
            </div>
            <div>
                <span class="metric-label">搜索词</span>
                <p>${formatList(plan.query_terms.slice(0, 12))}</p>
            </div>
            <div>
                <span class="metric-label">供应商 shortlist</span>
                ${renderSupplierList(topSuppliers)}
            </div>
            <div>
                <span class="metric-label">货源对比</span>
                ${renderOfferList(topOffers)}
            </div>
            <div>
                <span class="metric-label">报告摘要</span>
                <p>${escapeHtml(report ? report.summary : "-")}</p>
            </div>
        </div>
    `;
}

function renderSupplierList(suppliers) {
    if (!suppliers.length) {
        return "<p>没有找到供应商。</p>";
    }
    return suppliers.map((supplier) => `
        <div class="distribution-row">
            <span>${escapeHtml(supplier.supplier_name)}<br><span class="table-sub">${escapeHtml(labelPlatform(supplier.platform))} | ${escapeHtml(supplier.location || "-")}</span></span>
            <strong>${Number(supplier.score || 0).toFixed(1)}</strong>
        </div>
    `).join("");
}

function renderOfferList(offers) {
    if (!offers.length) {
        return "<p>没有找到货源。</p>";
    }
    return offers.map((offer) => {
        const price = offer.price_min && offer.price_max
            ? `${Number(offer.price_min).toFixed(2)}-${Number(offer.price_max).toFixed(2)} ${escapeHtml(offer.currency)}`
            : "-";
        return `
            <div class="distribution-row">
                <span>${escapeHtml(offer.title)}<br><span class="table-sub">${escapeHtml(price)} | 起订量 ${escapeHtml(offer.moq || "-")}</span></span>
                <strong>${Number(offer.score || 0).toFixed(1)}</strong>
            </div>
        `;
    }).join("");
}

function renderProductSummary() {
    const container = document.getElementById("product-summary");

    if (!state.productProfile || !state.icp) {
        container.innerHTML = "<p>还没有生成商品画像。</p>";
        return;
    }

    container.innerHTML = `
        <div class="stack">
            <div>
                <span class="metric-label">商品</span>
                <strong>${escapeHtml(state.productProfile.product_name)}</strong>
            </div>
            <div>
                <span class="metric-label">行业</span>
                <p>${formatList(state.productProfile.industry_tags)}</p>
            </div>
            <div>
                <span class="metric-label">功能标签</span>
                <p>${formatList(state.productProfile.feature_tags)}</p>
            </div>
            <div>
                <span class="metric-label">使用场景</span>
                <p>${formatList(state.productProfile.use_cases)}</p>
            </div>
            <div>
                <span class="metric-label">目标职位</span>
                <p>${formatList(state.icp.role_titles)}</p>
            </div>
            <div>
                <span class="metric-label">地区</span>
                <p>${formatList(state.icp.geography)}</p>
            </div>
        </div>
    `;
}

function renderStrategy() {
    const container = document.getElementById("strategy-summary");

    if (!state.strategy) {
        container.innerHTML = "<p>还没有下一步策略。</p>";
        return;
    }

    container.innerHTML = `
        <div class="stack">
            <div>
                <span class="metric-label">决策</span>
                <strong>${state.strategy.continue_search ? "继续搜索" : "进入跟进"}</strong>
            </div>
            <div>
                <span class="metric-label">原因</span>
                <p>${escapeHtml(state.strategy.reason || "暂无原因。")}</p>
            </div>
            <div>
                <span class="metric-label">下一批搜索词</span>
                <p>${formatList(state.strategy.next_queries)}</p>
            </div>
            <div>
                <span class="metric-label">下一批平台</span>
                <p>${formatList((state.strategy.next_platforms || []).map(labelPlatform))}</p>
            </div>
        </div>
    `;
}

function renderMetrics() {
    const metricsGrid = document.getElementById("metrics-grid");

    if (!state.dashboard) {
        metricsGrid.innerHTML = "<div class='metric-card'><span class='metric-label'>状态</span><strong>暂无数据</strong></div>";
        document.getElementById("platform-distribution").innerHTML = "<p>暂无数据。</p>";
        document.getElementById("source-distribution").innerHTML = "<p>暂无数据。</p>";
        return;
    }

    metricsGrid.innerHTML = `
        <div class="metric-card">
            <span class="metric-label">工作台线索数</span>
            <strong>${state.dashboard.new_leads}</strong>
        </div>
        <div class="metric-card">
            <span class="metric-label">高分线索占比</span>
            <strong>${formatPercent(state.dashboard.high_score_ratio)}</strong>
        </div>
        <div class="metric-card">
            <span class="metric-label">邮件打开率</span>
            <strong>${formatPercent(state.dashboard.email_open_rate)}</strong>
        </div>
        <div class="metric-card">
            <span class="metric-label">邮件回复率</span>
            <strong>${formatPercent(state.dashboard.email_reply_rate)}</strong>
        </div>
        <div class="metric-card">
            <span class="metric-label">合规线索</span>
            <strong>${state.dashboard.compliant_leads}</strong>
        </div>
    `;

    document.getElementById("platform-distribution").innerHTML = renderDistribution(state.dashboard.platform_contribution);
    document.getElementById("source-distribution").innerHTML = renderDistribution(state.dashboard.source_contribution);
}

function renderLeads() {
    const body = document.getElementById("leads-body");

    if (!state.leads.length) {
        body.innerHTML = "<tr><td colspan='7'>还没有线索。</td></tr>";
        return;
    }

    body.innerHTML = state.leads.map((lead) => {
        const compliance = state.complianceByLeadId[lead.lead_id];
        const risk = compliance ? compliance.source_risk_level : "n/a";
        const selectedClass = lead.lead_id === state.selectedLeadId ? "selected-row" : "";
        return `
            <tr class="${selectedClass}" data-lead-id="${lead.lead_id}">
                <td>
                    <button class="row-button" data-action="select" data-lead-id="${lead.lead_id}">
                        <strong>${escapeHtml(lead.company)}</strong>
                        <span>${escapeHtml(lead.raw_text_snippet || "-")}</span>
                    </button>
                </td>
                <td>${escapeHtml(lead.contact_name || "-")}<br><span class="table-sub">${escapeHtml(lead.role || "-")}</span></td>
                <td><span class="pill">${escapeHtml(labelPlatform(lead.platform))}</span></td>
                <td>
                    <span class="pill muted">${escapeHtml(labelSourceType(lead.source_type))}</span>
                    <span class="table-sub">${escapeHtml(lead.source_label || "-")}</span>
                </td>
                <td><span class="score-pill">${Number(lead.scores.overall || 0).toFixed(1)}</span></td>
                <td>
                    <span class="table-sub">${escapeHtml(labelConsent(lead.consent_status))}</span>
                    <span class="table-sub">风险：${escapeHtml(labelRisk(risk))}</span>
                </td>
                <td>${escapeHtml(labelVerify(lead.verification_status))}</td>
            </tr>
        `;
    }).join("");

    body.querySelectorAll("[data-action='select']").forEach((button) => {
        button.addEventListener("click", () => loadLeadDetail(button.dataset.leadId));
    });
}

function renderLeadDetail(card, templates, compliance) {
    const detail = document.getElementById("lead-detail");
    const templateBox = document.getElementById("lead-templates");

    if (!card) {
        detail.innerHTML = "<p>选择一条线索，查看评分、来源和可联系状态。</p>";
        templateBox.innerHTML = "<p>选择线索后会显示跟进话术。</p>";
        return;
    }

    const primaryContact = card.contacts[0] || {};

    detail.innerHTML = `
        <div class="stack">
            <div>
                <span class="metric-label">公司</span>
                <strong>${escapeHtml(card.company)}</strong>
            </div>
            <div>
                <span class="metric-label">主要联系人</span>
                <p>${escapeHtml(primaryContact.name || "-")} | ${escapeHtml(primaryContact.role || "-")}</p>
                <p>${escapeHtml(primaryContact.email || "-")}</p>
            </div>
            <div>
                <span class="metric-label">来源摘要</span>
                <p>${escapeHtml(card.source_summary || "-")}</p>
            </div>
            <div>
                <span class="metric-label">评分</span>
                <p>行业 ${Number(card.scores.industry || 0).toFixed(1)} | 意向 ${Number(card.scores.intent || 0).toFixed(1)} | 联系 ${Number(card.scores.contact || 0).toFixed(1)} | 总分 ${Number(card.scores.overall || 0).toFixed(1)}</p>
            </div>
            <div>
                <span class="metric-label">合规</span>
                <p>风险：${escapeHtml(labelRisk(compliance.source_risk_level))} | 保留期：${escapeHtml(String(compliance.retention_days))} 天</p>
                <p>${escapeHtml(compliance.recommended_action || "-")}</p>
            </div>
            <div>
                <span class="metric-label">匹配摘要</span>
                <p>${escapeHtml(card.product_fit_summary || "-")}</p>
            </div>
        </div>
    `;

    templateBox.innerHTML = `
        <div class="stack">
            <div>
                <span class="metric-label">首次触达</span>
                <pre>${escapeHtml(templates.first_touch)}</pre>
            </div>
            <div>
                <span class="metric-label">跟进</span>
                <pre>${escapeHtml(templates.follow_up)}</pre>
            </div>
            <div>
                <span class="metric-label">重启沟通</span>
                <pre>${escapeHtml(templates.restart)}</pre>
            </div>
        </div>
    `;
}

function renderPolicy() {
    if (!state.policy) {
        return;
    }

    document.getElementById("allowed-sources").innerHTML = renderPolicyItems(state.policy.allowed_sources);
    document.getElementById("prohibited-sources").innerHTML = renderPolicyItems(state.policy.prohibited_sources);
    document.getElementById("policy-notes").innerHTML = state.policy.notes.map((note) => `<p>${escapeHtml(note)}</p>`).join("");
}

function renderPolicyItems(items) {
    return items.map((item) => `
        <div class="policy-item">
            <strong>${escapeHtml(item.label)}</strong>
            <p>${escapeHtml(item.description)}</p>
        </div>
    `).join("");
}

function renderDistribution(data) {
    const entries = Object.entries(data || {});
    if (!entries.length) {
        return "<p>暂无数据。</p>";
    }

    return entries.map(([key, value]) => `
        <div class="distribution-row">
            <span>${escapeHtml(labelMetricKey(key))}</span>
            <strong>${escapeHtml(String(value))}</strong>
        </div>
    `).join("");
}

function setPipelineStatus(value) {
    document.getElementById("pipeline-status").textContent = STATUS_TEXT[value] || value;
}

function setSourcingStatus(value) {
    document.getElementById("sourcing-status").textContent = STATUS_TEXT[value] || value;
}

function clearLog() {
    document.getElementById("activity-log").innerHTML = "";
}

function logStep(message, isError = false) {
    const node = document.createElement("div");
    node.className = isError ? "log-row error" : "log-row";
    const timestamp = new Date().toLocaleTimeString();
    node.textContent = `[${timestamp}] ${message}`;
    document.getElementById("activity-log").appendChild(node);
}

function exportLeads(format) {
    window.location.href = `${API_BASE}/leads/export?format=${encodeURIComponent(format)}`;
}

async function getJson(path) {
    const response = await fetch(`${API_BASE}${path}`);
    return handleResponse(response);
}

async function postJson(path, payload) {
    const response = await fetch(`${API_BASE}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
    });
    return handleResponse(response);
}

async function handleResponse(response) {
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw new Error(body.detail || body.message || "请求失败。");
    }
    return body;
}

function labelPlatform(value) {
    return PLATFORM_LABELS[value] || value || "-";
}

function labelSourceType(value) {
    return SOURCE_TYPE_LABELS[value] || value || "-";
}

function labelConsent(value) {
    return CONSENT_LABELS[value] || value || "-";
}

function labelVerify(value) {
    return VERIFY_LABELS[value] || value || "-";
}

function labelRisk(value) {
    return RISK_LABELS[value] || value || "-";
}

function labelMetricKey(value) {
    return labelPlatform(labelSourceType(value));
}

function formatList(values) {
    if (!values || !values.length) {
        return "-";
    }
    return values.map((value) => escapeHtml(String(value))).join(", ");
}

function formatPercent(value) {
    return `${Math.round((Number(value) || 0) * 100)}%`;
}

function escapeHtml(value) {
    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
}

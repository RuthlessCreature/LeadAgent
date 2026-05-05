# LeadAgent 大改版优化 RFC

核对日期：2026-04-30
状态：实施前产品与架构文档

## 一句话结论

LeadAgent 现在已经不是纯脚本玩具了，它有 FastAPI 主线、前端工作台、公网页面找线索、合规字段、社媒连接器雏形。但它还没有变成你要的那个东西：

1. 输入商品信息，自动找到真实客人，尤其是真人联系人。
2. 输入商品信息，去 1688 等平台找货源，生成可交付报告。
3. 从旧 DeepSeek 接入升级到 DeepSeek V4。

本次大改版的核心不是多加几个按钮，而是补上中间层：

> 商品信息 -> 买家画像 -> 搜索计划 -> 来源执行 -> 真人/供应商证据 -> 评分 -> 报告

## 当前项目现状

### 主运行时

- `run.py` 启动 `uvicorn`。
- `backend/app/main.py` 是当前主要 FastAPI API。
- `frontend/index.html`、`frontend/app.js`、`frontend/styles.css` 是当前主前端。
- `backend/app/store.py` 用 `.runtime/leadagent_store.json` 做本地开发态持久化。

### 现有能力

- 商品/ICP 基础解析。
- demo 搜索和 lead scoring。
- 公网页面发现：DuckDuckGo、Yahoo、Bing HTML 搜索。
- 公网爬取：公司官网、联系页、团队页，能抓公司邮箱/电话，偶尔能抓到真人。
- 社媒连接器数据模型：LinkedIn Lead Sync、Meta Lead Ads 的 catalog 已经有了。
- 导出：CSV、PDF。
- 合规字段：source type、consent、verification 等已经打底。

### 主要问题

- 还不能只靠商品描述自动推导买家群体和搜索计划。
- `backend/app/services/search.py` 里还有 Selenium LinkedIn 抓取逻辑，和现有合规产品定位冲突。
- 现有社媒能力是连接器壳子，还没有真实 OAuth、webhook、backfill。
- `backend/app/services/llm.py` 仍然硬编码 `deepseek-chat`。
- 没有找货源页面、供应商模型、1688 connector、供应商报告。
- 老 Flask 路由、乱码注释、实验脚本还在项目里，后续需要隔离。

## 产品原则

### 找客必须是真人，但不能乱抓

你要的是“真实客人信息”，这里要分清楚：

- 可以要真实姓名、职位、公司、邮箱、社媒链接、来源页面。
- 不能把产品做成未经授权的 LinkedIn/Facebook/Instagram/TikTok 批量爬虫。
- 每条真人 lead 都必须带来源证据，不然就是瞎编数据。

LeadAgent 应支持这些来源：

- 官方/授权社媒线索：LinkedIn Lead Sync、Meta Lead Ads。
- 客户自有数据：CRM、广告表单、CSV、销售手工列表。
- 合法许可数据库：带合同、删除、退订、来源说明。
- 公开网页：公司官网、团队页、目录页、展会页、协会页。
- 公开搜索结果，但必须保留 URL 和 evidence snippet。

LeadAgent 不应默认支持：

- 登录态社媒批量抓 profile。
- 用 cookie/session 绕过平台限制。
- 自动复制私域或登录区联系人。
- 没有来源、没有 consent、没有 retention 的黑箱 lead。

实际对外承诺应该是：

> LeadAgent 从客户自有、许可、官方连接器和允许访问的公开来源中发现并验证潜在客户；真人联系人只有在证据足够时才输出。

## 新版产品结构

建议把前端从一个长 dashboard 改成工作台：

- `Dashboard`：总体指标、最近任务、风险提醒。
- `Find Customers`：输入商品，找真实买家和真人联系人。
- `Find Goods`：输入商品，找 1688/平台货源并生成报告。
- `Sources`：社媒连接器、公网、授权数据库、供应商平台。
- `Reports`：找客报告、找货报告、导出记录。
- `Settings`：DeepSeek/OpenAI/Claude 配置、API key、数据策略。

## Find Customers 设计

### 输入

- 商品描述。
- 目标国家/地区。
- 销售方式：批发、经销、代理、零售、电商、机构采购等。
- 客单价/价格带。
- 可用来源类型：公网、社媒授权线索、客户导入、许可数据库。

### 流程

1. 解析商品。
2. 生成买家画像。
3. 生成搜索计划。
4. 执行允许的来源。
5. 提取公司和真人。
6. 验证真人证据。
7. 评分：匹配度、购买可能性、可联系性、合规风险。
8. 生成客户发现报告。

### 输出

- 买家画像列表。
- 公司 lead 列表。
- 真人联系人列表。
- 每个真人的证据 URL、来源类型、置信度。
- 合规状态。
- 推荐跟进动作。
- CSV/PDF 报告。

### 新增模型建议

```python
class BuyerHypothesis(BaseModel):
    hypothesis_id: str
    buyer_type: str
    buyer_roles: list[str]
    company_types: list[str]
    geographies: list[str]
    search_language: list[str]
    source_plan: list[str]
    confidence: float
    rationale: str
```

```python
class PersonEvidence(BaseModel):
    evidence_id: str
    lead_id: str
    source_url: str
    source_platform: str
    evidence_type: str
    observed_name: str
    observed_role: str
    observed_company: str
    observed_contact: str
    confidence: float
    collected_at: datetime
```

规则：真人联系人必须至少有一条强证据，否则只能作为待核验线索。

## Find Goods 设计

### 目标

新增一个找货页面：输入商品信息，去 1688 等平台找货源，输出供应商对比和采购报告。

### 首批平台

- 1688。
- Alibaba.com。
- Made-in-China。
- GlobalSources。
- 供应商官网。
- 手工导入 CSV。

1688 应先做 connector 抽象和 mock/permitted workflow，等 API 凭证和接口范围确定后再接正式 connector。

### 输入

- 商品描述。
- 目标供应地区。
- MOQ。
- 价格带。
- 材质、尺寸、认证、定制要求。
- 报告语言。

### 流程

1. 商品解析：品类、关键词、中英文同义词、规格、用途。
2. 生成找货搜索计划。
3. 调用平台 connector 或允许的搜索流程。
4. 标准化 offer 和 supplier。
5. 评分：价格、MOQ、认证、交易信号、响应信号、风险。
6. 生成供应商对比表。
7. 生成采购报告和 RFQ 模板。

### 输出

- 供应商 shortlist。
- offer 对比。
- 价格/MOQ 区间。
- 平台链接和来源证据。
- 风险提示。
- 议价问题。
- RFQ 模板。
- HTML/PDF/CSV 报告。

### 新增模型建议

```python
class SupplierCandidate(BaseModel):
    supplier_id: str
    platform: str
    supplier_name: str
    supplier_url: str
    location: str = ""
    years_active: int | None = None
    verification_badges: list[str] = []
    response_rate: str = ""
    transaction_signals: list[str] = []
    risk_flags: list[str] = []
```

```python
class ProductOffer(BaseModel):
    offer_id: str
    supplier_id: str
    platform: str
    title: str
    product_url: str
    image_url: str = ""
    price_min: float | None = None
    price_max: float | None = None
    currency: str = "CNY"
    moq: str = ""
    attributes: dict[str, str] = {}
    source_evidence: list[str] = []
```

```python
class SourcingReport(BaseModel):
    report_id: str
    product_name: str
    query_terms: list[str]
    offers: list[ProductOffer]
    suppliers: list[SupplierCandidate]
    summary: str
    recommendations: list[str]
    generated_at: datetime
```

### Connector 抽象

```python
class SupplierSourceConnector(Protocol):
    source_key: str

    def search_offers(self, query: SourcingQuery) -> list[ProductOffer]:
        ...

    def get_supplier(self, supplier_url: str) -> SupplierCandidate:
        ...
```

先做：

- `Mock1688Connector`
- `PublicSupplierWebConnector`
- `CsvSupplierImportConnector`

再做：

- `Official1688Connector`
- `AlibabaConnector`
- `MadeInChinaConnector`
- `GlobalSourcesConnector`

## API 规划

### 找客

- `POST /api/v1/customer-discovery/plan`
  - 输入商品和约束。
  - 输出买家画像、搜索词、来源计划。

- `POST /api/v1/customer-discovery/run`
  - 输入选中的 plan。
  - 输出 lead、person evidence、任务状态。

- `POST /api/v1/customer-discovery/report`
  - 输入 lead IDs。
  - 输出客户发现报告。

### 找货

- `POST /api/v1/sourcing/plan`
  - 输入商品和找货约束。
  - 输出找货搜索计划。

- `POST /api/v1/sourcing/search`
  - 输入 sourcing plan。
  - 输出 offers 和 suppliers。

- `POST /api/v1/sourcing/report`
  - 输入 offer IDs、supplier IDs。
  - 输出找货报告。

- `GET /api/v1/sourcing/reports/{report_id}`
  - 获取历史报告。

### LLM

- `GET /api/v1/llm/models`
- `POST /api/v1/llm/test`
- `POST /api/v1/llm/json`
- `POST /api/v1/llm/report`

后续所有产品解析、买家画像、找货计划、报告生成，都走统一 LLM gateway，不要到处直接调用 `LLMClient`。

## DeepSeek V4 升级方案

### 官方状态

DeepSeek 官方 API 文档显示，DeepSeek-V4-0324-preview 于 2026-04-24 发布，API model 包括：

- `deepseek-v4-flash`
- `deepseek-v4-flash-thinking`
- `deepseek-v4-pro`
- `deepseek-v4-pro-thinking`

官方同页还说明旧模型：

- `deepseek-chat`
- `deepseek-reasoner`

计划于 2026-07-24 下线。

### 当前问题

`backend/app/services/llm.py` 里：

- DeepSeek 默认模型硬编码为 `deepseek-chat`。
- 没有 `DEEPSEEK_MODEL` 环境变量。
- 没有 fast/reasoning/report 分路。
- 没有强 JSON helper。
- 没有旧 alias warning。

### 建议环境变量

```env
DEFAULT_LLM=deepseek
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_REASONING_MODEL=deepseek-v4-flash-thinking
DEEPSEEK_REPORT_MODEL=deepseek-v4-pro
DEEPSEEK_REPORT_REASONING_MODEL=deepseek-v4-pro-thinking
DEEPSEEK_TIMEOUT_SECONDS=90
```

### 模型路由

- 普通解析：`deepseek-v4-flash`
- 买家画像/搜索计划：`deepseek-v4-flash-thinking`
- 找货报告：`deepseek-v4-pro`
- 多来源矛盾分析/复杂报告：`deepseek-v4-pro-thinking`

### 兼容策略

- 保留现有 `DEEPSEEK_API_KEY` 和 `DEEPSEEK_BASE_URL`。
- 如果用户没配 `DEEPSEEK_MODEL`，默认使用 `deepseek-v4-flash`。
- 允许显式配置旧模型，但启动时 warning。
- 不再把 `deepseek-chat` 写死在代码里。

## 实施阶段

### Phase 0：文档和边界

- 输出本 RFC。
- 更新 `.pm` 项目元数据。
- 明确社媒真人数据边界。

### Phase 1：DeepSeek V4 Gateway

- 重构 `backend/app/services/llm.py`。
- 更新 `.env.example`。
- 加 LLM model/test API。
- 加 JSON 解析测试。

验收：

- 默认模型是 `deepseek-v4-flash`。
- 旧 `deepseek-chat` 不再硬编码。
- 测试能覆盖 JSON 输出和 fallback。

### Phase 2：Product Intelligence

- 新增商品到买家画像。
- 新增商品到找货计划。
- 增加 source fit confidence。

验收：

- 单靠商品描述可以生成可审查的找客计划和找货计划。

### Phase 3：Find Customers V2

- 新增页面。
- 新增 person evidence。
- 社媒 connector 从壳子走向真实 OAuth/webhook。
- 默认 UI 隐藏 Selenium 抓取。

验收：

- 真人 lead 必须有来源证据。
- 社媒 lead 必须显示 owned/licensed/public/authorized source。

### Phase 4：Find Goods V1

- 新增供应商模型。
- 新增 mock 1688 connector。
- 新增找货页面。
- 新增报告生成。

验收：

- 用户输入商品后能得到供应商对比报告。

### Phase 5：真实平台 Connector

- 接入 1688 正式 API 或允许的 partner workflow。
- 加缓存、限速、去重、source audit。
- 再扩展 Alibaba、Made-in-China、GlobalSources。

验收：

- 真实 supplier 记录有 URL、采集时间、平台来源、风险状态。

## 风险

- 社媒平台 API 可能需要审批。
- 社媒 profile 抓取有法律、账号、平台 ToS 风险。
- 1688 等平台可能需要 API 凭证、开放平台权限或合作通道。
- LLM 生成买家画像会幻觉，必须绑定 evidence。
- DeepSeek V4 仍是 preview，行为和价格可能变。
- 当前 `.runtime` file store 不适合生产。
- 老 Flask 和实验脚本需要隔离，否则新产品边界会被污染。

## 近期开发 Backlog

1. 重构 `backend/app/services/llm.py`，支持 DeepSeek V4 model routing。
2. 更新 `.env.example`。
3. 新增 `BuyerHypothesis`、`PersonEvidence`。
4. 新增 `SupplierCandidate`、`ProductOffer`、`SourcingReport`。
5. 新增 `/api/v1/sourcing/plan`、`/search`、`/report`。
6. 新增 `Find Goods` 前端页面。
7. 新增供应商归一化和报告测试。
8. 把 `LinkedInSearcher` 改成 `SEARCH_MODE=experimental_selenium` 才可用。
9. 明确 LinkedIn/Meta 官方 connector 的 OAuth、webhook、token storage 任务。
10. 更新 README，把产品定义成“找客 + 找货”的双工作流。

## 官方来源

- DeepSeek V4 API 新闻，2026-04-30 核对：https://api-docs.deepseek.com/news/news260424
- DeepSeek API 价格/模型页，2026-04-30 核对：https://api-docs.deepseek.com/quick_start/pricing
- LinkedIn User Agreement，2026-04-30 核对：https://www.linkedin.com/legal/user-agreement
- Meta Automated Data Collection Terms，2026-04-30 核对：https://www.facebook.com/legal/automated_data_collection_terms
- Meta Lead Ads guide，2026-04-30 核对：https://developers.facebook.com/docs/marketing-api/guides/lead-ads/
- Alibaba Open Platform / 1688 API 入口，2026-04-30 核对：https://aop.alibaba.com/


# 项目框架详解

本项目为 “TikTok & YouTube 短视频数据分析平台”，整体由前端交互层、Flask 后端业务层、SQLite 数据层以及模板/查询元数据层构成。下文将按照系统架构、关键流程与各子模块逐一展开，帮助快速理解项目运行机制与扩展点。

---

## 1. 系统层级总览

1. **前端层**（`index.html`、`index_user.html`、`index_admin.html` + `static/css`, `static/css/js/script.js`）  
   - 登录页负责角色区分与跳转。  
   - 用户端 Dashboard 汇总 10 个分析功能，每个版块以输入组件 + 结果容器 + ECharts 图表构成。  
   - 管理端面板提供内容增删改查，表格与弹窗交互全部走 API。  

2. **后端层**（`app.py`）  
   - 负责 Flask 应用初始化、Session、字体配置与 Matplotlib 后端设置。  
   - 提供统一的 SQLite 连接函数及报表模板/查询的读写工具。  
   - 实现业务分析函数（global / hashtag / trend / publish timing / creator performance / region ad / platform dominance extended 等）。  
   - 定义登录/管理员鉴权、API 路由与数据校验逻辑。  

3. **数据层**（`Tiktok_youtube.db`、`user.db`）  
   - 主库集中内容、国家、创作者、设备、report_templates、report_queries 等表，供所有分析模块使用。  
   - 用户库仅存储登录账号和角色信息，用于 Session 验证。  

4. **模板与查询元数据**  
   - `report_queries`：维护所有业务 SQL，后端通过 slug 读取，便于统一管理与替换。  
   - `report_templates`：保存 Markdown/HTML 模板与必需字段元数据（`metadata.fields`），保证报告输出结构一致且可扩展。  

---

## 2. 典型请求流程

1. 用户在前端输入参数 → JS 进行基础校验。  
2. 使用 `fetch` 调用对应 `/api/...` 路由，提交 JSON 请求体。  
3. Flask 路由校验参数，创建 SQLite 连接，调用业务函数。  
4. 业务函数读取 `report_queries` SQL → 执行查询 → 聚合计算关键指标 → 校验模板必需字段 → 渲染报告。  
5. 返回 JSON（数据数组 + `extra_info` + `report_text/markdown/html` + 错误信息）。  
6. 前端解析 JSON，更新文本描述区，并用 ECharts 渲染图表。  

---

## 3. 前端模块拆解（`index_user.html` + `static/css/js/script.js`）

| 模块 | 前端元素 | 调用 API | 主要展示内容 |
| --- | --- | --- | --- |
| 登录页 | `index.html` | `/api/login` | 角色切换按钮、错误提示、登录后跳转 `/home` / `/admin` |
| Dashboard Home | `#home` | - | 平台介绍、CTA 跳转按钮 |
| 平台列表 | `#platforms` | `GET /api/platforms` | 平台卡片 + 下拉框填充 |
| 国家/地区列表 | `#countries` | `GET /api/countries` | 国家代码/名称/区域/语言 |
| 年月列表 | `#year-months` | `GET /api/year-months` | 各年月展示卡片 |
| 全球数据分析 | `#global` | `POST /api/global-analysis` | 国家/类别柱状图 + 报告文本 |
| 热门话题分析 | `#hashtag` | `POST /api/hashtag-report` | 数据表/列表 + 报告 |
| 内容趋势分析 | `#trend` | `POST /api/trend-report` | 趋势类别视图分布 + 报告 |
| 发布时间分析 | `#publish-timing` | `POST /api/publish-timing-analysis` | 时段/周/小时热力分布 + 最优/最差说明 |
| 创作者表现 | `#creator-performance` | `POST /api/creator-performance` | 视图趋势折线 / 创作者层级饼图 + 报告 |
| 区域广告推荐 | `#region-ad-reco` | `POST /api/region-ad-reco` | TikTok/YouTube 类别玫瑰图 + 建议 |
| 平台主导地位扩展 | `#platform-dominance-extended` | `POST /api/platform-dominance-extended` | 国家级平台对比柱状图 + 报告 |

### 3.1 模块级文字&可视化流程

以下全部基于 `static/css/js/script.js` 内对应函数及 `app.py` 中的业务路由，描述从用户输入 → 文本输出 → 图表渲染的完整链路。

1. **平台列表**  
   - 文字：`loadPlatforms()` 获取 `/api/platforms` 返回的数组后，直接用模板字符串生成平台卡片文本；若为空则显示 “No platform data available”。  
   - 可视化：无独立图表，但下拉框选项在成功回调中被动态填充，为其他模块绘图提供输入源。

2. **国家/地区列表**  
   - 文字：`loadCountries()` 将国家 code/name/region/language 拼成卡片段落，错误时显示统一 error div。  
   - 可视化：无图表，仅以卡片形式展示基础数据。

3. **年月列表**  
   - 文字：`loadYearMonths()` 将 `display` + `year_month` 组合为列表项。  
   - 可视化：无；同样服务于其他模块的输入提示。

4. **全球数据分析（Global Analysis）**  
   - 文字：`runGlobalAnalysis()` 发送 `{platform, year_month}` 至 `/api/global-analysis`，收到结果后优先展示 `result.report_html`（若为空则回退到 `report` 文本），外层加标题 `Country Distribution`。  
   - 可视化：  
     - 国家维度：`labels` + `values` 用于堆叠或普通柱状图（`echarts.init('#global-country-chart')` 内实现，代码在脚本后半部分）。  
     - 类别维度：`category_labels` + `category_values` 渲染第二个柱状/饼图。  
     - 图表标题与 tooltip 根据 `result.extra_info` 生成，支持 resize。

5. **热门话题分析（Trending Hashtags）**  
   - 文字：`runHashtagReport()` 将 `platform/country_code/min_views` 传给 `/api/hashtag-report`，结果中的 `report_html`/`report` 描述热门标签榜单；若包含 `top_hashtags` 等字段，则拼成有序/无序列表。  
   - 可视化：目前以文本表格为主；可选 chart 容器（如 `hashtag-bar`）在脚本中预留，可根据 `result.chart` 数据渲染柱状或词云。

6. **内容趋势分析（Content Trend）**  
   - 文字：`runTrendReport()` 输出报告 HTML，并在文本中列出各 trend type 的表现、最佳/最差类型说明。  
   - 可视化：  
     - 若 `result.data` 包含 `types` + `views`，则在 `trend-chart` 中绘制饼图或条形图。  
     - 参数 `country_code`、`date range` 会体现在图表标题和 tooltip 上。

7. **发布时间分析（Publish Timing）**  
   - 文字：`runPublishTimingAnalysis()` 根据 `time_analysis`（Hourly/Day Parts/Week Analysis）切换描述模板，后台 `generate_publish_timing_analysis()` 渲染出的 `report_html` 包含最佳/最差时间段、周末提升等语句。  
   - 可视化：  
     - `result.data.engagement_rates` + `days` / `hours` 转化为折线或柱状图。  
     - 不同粒度走不同渲染函数：例如 Week Analysis 使用条形对比、Hourly 使用折线。  
     - 额外的 `eng_diff_pct` 用于颜色映射，突出高低表现。

8. **创作者表现（Creator Performance）**  
   - 文字：`runCreatorPerformance()` 在结果中插入 `<h3>Creator Ecosystem...` 标题，并将 `report_html` 放入 `report-text`。内容会说明各 tier 的贡献、增长点等。  
   - 可视化：  
     - 如果 `result.data.monthly_trend` 存在，则调用 `renderCreatorMonthlyTrend()` 绘制时间序列折线，X 轴为月份，Y 轴为 views。  
     - 若返回 `tiers` + `tier_views`，则 `renderCreatorTierPie()` 构建环形饼图显示各层级占比。  
     - 两者互斥，根据数据自动选择。

9. **区域广告推荐（Region Ad Recommendation）**  
   - 文字：`runRegionAdReco()` 输出区域标题与 `report_html`，内容涵盖推荐策略、重点类别等。  
   - 可视化：  
     - `result.data.tiktok_top`、`youtube_top` 各包含三个类别（category、engagement），在两个 `<div>` 中调用 `renderRegionTopRose()` 渲染玫瑰图。  
     - 颜色方案根据平台切换（TikTok 暖色、YouTube 冷色），支持空数据提示。

10. **平台主导地位扩展（Platform Dominance Extended）**  
   - 文字：`runDominanceExtended()` 以 `report_html` 解读目标国家中 TikTok 与 YouTube 的对比（视图/内容/互动占比等）。  
   - 可视化：  
     - `result.data.comparison`（包含 `metric`, `tiktok`, `youtube`）驱动 `renderDominanceComparisonBar()`，生成分组柱状图，展示各指标的两平台差异。  
     - 图表标题动态带上 `country_name`。

11. **管理员内容管理（Content Management）**  
   - 文字：表格行展示 Content 字段（content_id、platform、views 等），分页信息通过 `.pagination-info` 文字表达当前页/总量。  
   - 可视化：无图表，强调数据表格的可操作性（编辑/删除按钮）。

其他前端要点：

- `initTabs()` 控制侧边栏导航与内容切换，并带动淡入动画。  
- `addLoadingStates()` 给所有操作按钮添加临时 loading、禁用状态，避免重复提交。  
- 每个分析函数都在结果容器中渲染标题、报告文本，并根据数据情况调度 ECharts（折线、饼图、玫瑰图、柱状图）。  
- 如果后端返回 `error` 字段，统一走 `showError()`（定义在脚本后段）显示友好提示。

---

## 4. 管理端模块（`index_admin.html` + JS 内联函数）

1. **内容列表展示**  
   - `loadContentList(page)`：调用 `GET /api/admin/list-content?page=&per_page=`，将返回的内容数组渲染为表格，并附带分页控件。

2. **新增内容**  
   - “Add New Content” 按钮 → 弹出表单 → `handleSubmit()` 识别 `form-action=add` → `POST /api/admin/add-content`。  
   - 后端会确保 Country/Author 记录存在，再插入 Content 数据。

3. **编辑内容**  
   - 表格中点击 Edit → 填充表单并将 `form-action=update` → 提交时调用 `/api/admin/update-content`。  
   - 后端按需更新平台、分类、数值、国家、作者、发布日期等字段。

4. **删除内容**  
   - Delete 按钮触发 `/api/admin/delete-content`，完成硬删除。  
   - 删除后会刷新当前页，若无数据则回退。

5. **安全控制**  
   - 所有 `/api/admin/*` 路由都检查 `session['user_type'] == 'admin'`。  
   - 未登录或权限不符会返回 `Unauthorized`。

---

## 5. 后端结构与关键函数（`app.py`）

### 5.1 初始化与工具函数

- Matplotlib 字体/后端设置，避免服务器渲染报错。  
- `create_connection()`：建立主库连接并启用 `sqlite3.Row`，保证后续查询可通过列名访问。  
- 模板/查询表初始化：`init_report_template_table()`、`init_report_queries_table()`。  
- 模板渲染：`render_report_from_db()` 结合 Jinja2 + markdown（可选）处理 report_templates，并统一转换 `<strong>` → `<span class="highlight-data">`。  
- 必需字段校验：`validate_context_fields_by_db()` 根据模板 metadata.fields 校验。  
- 通用工具：`nz`（None-safe）、`_is_missing`、`_format_comma` 等。

### 5.2 API 路由

| 路由 | 方法 | 说明 |
| --- | --- | --- |
| `/`、`/login` | GET | 登录页面（同 `index.html`） |
| `/home` | GET | 用户 Dashboard（需 Session 登录） |
| `/admin` | GET | 管理员页面（需 admin Session） |
| `/api/login` | POST | 登录验证，成功写入 Session |
| `/api/platforms` | GET | 调用 `list_all_platforms()` 返回平台列表 |
| `/api/countries` | GET | 调用 `list_all_countries()` 返回国家信息 |
| `/api/year-months` | GET | 调用 `list_all_year_months()` 返回所有年月 |
| `/api/global-analysis` | POST | 触发 `generate_global_analysis()` |
| `/api/hashtag-report` | POST | 触发 `generate_hashtag_report()` |
| `/api/trend-report` | POST | 触发 `generate_trend_report()` |
| `/api/publish-timing-analysis` | POST | 触发 `generate_publish_timing_analysis()` |
| `/api/creator-performance` | POST | 触发 `generate_creator_performance()` |
| `/api/region-ad-reco` | POST | 触发 `generate_region_ad_recommendation()` |
| `/api/platform-dominance-extended` | POST | 触发 `generate_platform_dominance_extended()` |
| `/api/admin/add-content` | POST | 管理员添加内容 |
| `/api/admin/update-content` | POST | 管理员更新内容 |
| `/api/admin/delete-content` | POST | 管理员删除内容 |
| `/api/admin/list-content` | GET | 管理员分页查询内容 |

### 5.3 业务分析函数快览（节选）

- `generate_global_analysis(conn, platform, year_month)`  
  - 读取 `global_summary/global_top_countries/global_category_dist/global_top_hashtag` SQL。  
  - 计算总内容、总播放、平均互动等指标；返回国家/类别列表供图表使用。  
  - 校验模板字段后渲染 `global_analysis` 报告。

- `generate_hashtag_report(conn, platform, country_code, min_views)`  
  - 检查国家是否存在，获取主要 SQL 执行结果，识别高热度标签列表，构建报告上下文。

- `generate_trend_report(conn, platform, country_code, start_date, end_date)`  
  - 统计不同 trend type 的累计视图/点赞分布，返回图表数据与报告模板渲染结果。

- `generate_publish_timing_analysis(conn, platform, time_analysis, period, start_month, end_month)`  
  - 根据时间粒度（Hourly / Day Parts / Week Analysis）选择 SQL，计算参与率、最佳/最差时间、周末对比等指标，供模板输出与图表使用。

- `generate_creator_performance(conn, platform, scope, start_month, end_month)`  
  - 支持多层级（Micro/Mid/Macro/Star）或单层级分析，返回视图占比、月度趋势等结构化数据。

- `generate_region_ad_recommendation(conn, region)`  
  - 聚合区域内 TikTok/YouTube 各类别表现，返回 top 类别列表及图表数据。

- `generate_platform_dominance_extended(conn, country_code)`  
  - 对比该国家在 TikTok/YouTube 上的内容量、播放、互动占比，提供柱状图所需数据。

---

## 6. 数据表与关系（摘要）

| 数据库 | 表 | 作用 |
| --- | --- | --- |
| `Tiktok_youtube.db` | `Content` | 核心短视频内容（platform、views、likes、country_id、author_id、publish_date_approx、year_month 等） |
|  | `Country` | 国家代码、名称、区域、语言；与 Content 关联 |
|  | `Author` | 创作者信息（author_handle、creator_tier 等） |
|  | `Device` | 设备信息（在流程图中提及，供扩展） |
|  | `report_templates` | 模板内容 + format + metadata.fields |
|  | `report_queries` | SQL 语句仓库，按 slug 唯一标识 |
| `user.db` | `users` | 登录账号（username/password/user_type） |

关系说明：

- `Content.country_id → Country.country_id`，`Content.author_id → Author.author_id`。  
- report_* 表被所有 generate 函数使用，用于提取 SQL 与渲染报告。  
- 管理员在 CRUD 时会自动插入不存在的 Country/Author 记录，保证引用完整性。  
- 用户登录只读取 `user.db`，避免与主库耦合。

---

## 7. 运行与扩展注意

1. **依赖**：  
   - `requirements.txt` 仅包含线上运行所需依赖（Flask/Jinja2/markdown/gunicorn 等），确保 Render/Heroku 安装过程保持轻量并避免因科学计算库而失败。  
   - 如需重新清洗 CSV 并刷新 `Tiktok_youtube.db`，先在本地执行 `python -m venv .venv && .venv/Scripts/activate`（或对应 shell 激活），再运行 `pip install -r requirements-data-clean.txt` 安装 pandas，最后执行 `python scripts/clean_and_reseed.py`。完成后将更新后的 `Tiktok_youtube.db` 与必要的 Python 代码同步到 GitHub 即可，无需把 pandas 打包进生产环境。  
2. **启动**：`python app.py`（或通过 `Procfile` 适配部署环境），会自动初始化 `user.db`、report_* 表。  
3. **模板扩展**：新增报告类型时，需要在 `report_queries` 中插入 SQL、在 `report_templates` 中定义模板与 metadata.fields，再在 `app.py` 中添加对应业务函数/路由。  
4. **权限**：登录后 Session 会区分 user/admin；管理员端操作必须保持 Session 有效，否则 API 返回 403。  
5. **错误处理**：前端捕获 `error` 字段统一提示；后端对参数/日期格式进行显式校验，减少异常 SQL 调用。  
6. **可视化**：所有图表使用 ECharts CDN，如需本地部署需自行下载或替换。  

---

## 8. 模块间协作图（概念性）

```
用户浏览器
 ├─ 登录页（index.html）→ /api/login → Session
 ├─ 用户端（index_user.html）
 │    ├─ JS 初始化：loadPlatforms/loadCountries/loadYearMonths
 │    ├─ 各分析模块 → /api/* → JSON → ECharts + 文本报告
 │    └─ 错误信息 showError
 └─ 管理端（index_admin.html）
      ├─ loadContentList → /api/admin/list-content
      ├─ handleSubmit(add/update) → /api/admin/add-content|update-content
      └─ deleteContent → /api/admin/delete-content

Flask 后端（app.py）
 ├─ create_connection / 模板&查询管理
 ├─ 登录/Session/权限控制
 ├─ 业务函数 generate_*（调用 report_queries SQL，使用 report_templates 渲染）
 └─ API 路由（普通用户 + 管理员）

SQLite
 ├─ Tiktok_youtube.db（Content/Country/Author/Device/report_*）
 └─ user.db（users）
```

---

通过上述拆解可以看到：项目以“配置驱动的数据分析”作为核心理念——SQL 与模板完全存储于数据库，后端负责参数校验与数据处理，前端则提供丰富的可视化呈现与角色分离。只需在 report_* 表中新增配置并适配相应 API，便能快速扩展新的分析模块，具备良好的可维护性与可扩展性。

---

## 9. 功能模块详细实现说明（通俗易懂版）

想象一下，这个系统就像一家餐厅：**前端（Frontend）**是服务员，负责接待客人、记录点单、上菜；**后端（Backend）**是厨房，负责处理订单、做菜、准备食材；**数据库（Database）**是仓库，存放所有食材和菜谱。

当客人（用户）想要一份报告（就像点一道菜），整个流程是这样的：
1. 服务员（前端）记录客人的要求（用户输入）
2. 服务员把订单送到厨房（发送请求到后端）
3. 厨师（后端函数）去仓库找食材（查询数据库）
4. 厨师按照菜谱做菜（处理数据、渲染模板）
5. 服务员把做好的菜端给客人（显示结果和图表）

下面我们用"全球数据分析"这个功能来详细说明，其他功能的原理都是一样的。

### 9.1 全球数据分析模块（Global Analysis）

#### 第一部分：用户点单（前端获取输入）

**通俗解释**：就像客人走进餐厅，服务员会问"您要什么菜？"一样，网页上也有一个表单让用户选择：
- 选择平台（TikTok 还是 YouTube？）
- 选择时间（比如 2025年4月）

这些选择框在网页文件 `index_user.html` 里定义好了，就像菜单上的选项。

当用户点击"生成报告"按钮时，就像客人说"我要这个！"，网页上的 JavaScript 代码（在 `script.js` 文件里）就会开始工作：

```javascript
function runGlobalAnalysis() {
    // 服务员（JavaScript）先看看客人（用户）选了啥
    const platform = document.getElementById('global-platform').value;  // 读取平台选择
    const yearMonth = document.getElementById('global-month').value;    // 读取年月输入
    
    // 如果客人没选完，服务员会提醒"请完整填写"
    if (!platform || !yearMonth) {
        showError('global-result', 'Please select platform and enter year-month');
        return;
    }

    // 服务员先给客人看"正在准备中..."的提示（显示加载动画）
    const resultEl = document.getElementById('global-result');
    resultEl.innerHTML = '<div style="text-align: center; padding: 20px;"><span class="loading"></span> Generating report...</div>';

    // 服务员把订单（用户的选择）打包成JSON格式，送到厨房（后端API）
    fetch('/api/global-analysis', {
        method: 'POST',  // 用POST方式发送（就像把订单送到厨房）
        headers: { 'Content-Type': 'application/json' },  // 告诉厨房"这是JSON格式的订单"
        body: JSON.stringify({ platform, year_month: yearMonth })  // 把选择打包成JSON
    })
    .then(res => res.json())  // 等厨房做好菜，把结果解析成JavaScript能用的格式
    .then(result => {
        // 收到做好的菜，准备上桌（显示结果）
    })
    .catch(error => {
        // 如果出错了（比如网络断了），告诉客人"抱歉，出错了"
        showError('global-result', 'Network error. Please try again.');
    });
}
```

**专业术语解释**：
- **JavaScript**：网页上用来做交互的编程语言，就像餐厅服务员的工作手册
- **fetch**：JavaScript 里用来发送网络请求的函数，就像服务员把订单送到厨房
- **JSON**：一种数据格式，就像把订单写成标准格式，方便厨房理解
- **API**：应用程序接口，就像厨房的接单窗口，专门接收订单

#### 第二部分：厨房接单（后端接收请求）

**通俗解释**：现在订单到了厨房（后端），厨房有个专门的接单窗口（Flask 路由），这个窗口专门处理"全球分析"这道菜。

在 `app.py` 文件里，有一个专门处理这个请求的函数：

```python
@app.route('/api/global-analysis', methods=['POST'])
def global_analysis():
    """API: Global analysis report"""
    # 接单员（这个函数）打开订单，看看客人要什么
    data = request.json  # 从请求中取出JSON格式的订单
    platform = data.get('platform')      # 客人要的平台（TikTok/YouTube）
    year_month = data.get('year_month')  # 客人要的时间（2025-04）
    
    # 接单员去仓库（数据库）拿食材，需要先打开仓库门（创建连接）
    conn = create_connection()
    
    # 接单员把订单交给厨师（业务函数），让厨师去做菜
    result = generate_global_analysis(conn, platform, year_month)
    
    # 做完菜后，关上仓库门（关闭数据库连接）
    conn.close()
    
    # 把做好的菜打包好（转换成JSON格式），准备送回给服务员
    return jsonify(result)
```

**专业术语解释**：
- **Flask 路由**：`@app.route` 是 Flask 框架的装饰器，用来定义"哪个网址对应哪个处理函数"，就像给每个接单窗口贴上标签
- **POST 方法**：HTTP 请求的一种方式，用来发送数据，就像把订单送到厨房
- **JSON**：这里 `request.json` 是从请求中提取 JSON 数据，就像打开订单看内容

#### 第三部分：厨师做菜（业务函数处理数据）

**通俗解释**：现在订单到了厨师手里（`generate_global_analysis` 函数），厨师需要：
1. 去仓库（数据库）找需要的食材（数据）
2. 按照菜谱（SQL 查询）准备食材
3. 把食材加工成菜（处理数据、计算指标）
4. 按照模板摆盘（渲染报告模板）

让我们看看厨师是怎么工作的：

```python
def generate_global_analysis(conn, platform, year_month):
    # conn 是仓库的连接，with conn 表示"在这个连接里工作，用完自动关闭"
    with conn:
        cursor = conn.cursor()  # cursor 是"仓库管理员"，负责帮我们找东西
        
        # 第一步：找总数据（就像找主料）
        # get_sql() 是从"菜谱本"（report_queries表）里找对应的SQL查询语句
        sql = get_sql(conn, "global_summary")
        # 让仓库管理员执行这个查询，把平台和年月作为条件
        cursor.execute(sql, (platform, year_month))
        # 取出查询结果：总内容数、总播放量、总点赞、平均互动率
        total_content, total_views, total_likes, avg_engagement = cursor.fetchone()
        
        # 如果仓库里没有这些数据，就告诉客人"抱歉，没有这个时间的数据"
        if not total_content:
            return {"error": f"No data found for {platform} in {year_month}"}
        
        # 处理空值：如果某个数据是空的，就当作0处理（nz函数的作用）
        total_views = nz(total_views, 0)
        total_likes = nz(total_likes, 0)
        avg_engagement = 0.0 if avg_engagement is None else float(avg_engagement)
        
        # 第二步：找TOP国家数据（就像找配菜）
        sql = get_sql(conn, "global_top_countries")
        cursor.execute(sql, (platform, year_month))
        top_countries = cursor.fetchall()  # 取出所有行
        country_names = [row[0] for row in top_countries]  # 提取国家名称列表
        country_views = [nz(row[1], 0) for row in top_countries]  # 提取播放量列表
        
        # 第三步：找热门标签（就像找调料）
        sql = get_sql(conn, "global_top_hashtag")
        cursor.execute(sql, (platform, year_month))
        hashtag_result = cursor.fetchone()
        top_hashtag = hashtag_result[0] if hashtag_result else "N/A"
        
        # 第四步：找类别分布（就像找配菜2）
        sql = get_sql(conn, "global_category_dist")
        cursor.execute(sql, (platform, year_month))
        category_results = cursor.fetchall()
        category_names = [row[0] for row in category_results]
        category_views = [nz(row[1], 0) for row in category_results]
        
        # 第五步：计算额外指标（就像计算菜的分量、热量等）
        top_country = country_names[0] if country_names else "N/A"
        top_country_views = country_views[0] if country_views else 0
        top_country_pct = (top_country_views / total_views * 100) if total_views and total_views > 0 else 0
        
        # 第六步：准备文字描述（就像准备菜单上的描述）
        country_list_text = ""
        if country_names:
            country_parts = [f"{name} ({views:,} views)" for name, views in zip(country_names, country_views)]
            country_list_text = ", ".join(country_parts)
        
        # 第七步：把所有数据整理成一个"上下文"字典（就像把所有食材放在一个托盘里）
        context = {
            "platform": platform,
            "year_month": year_month,
            "country_list_text": country_list_text,
            "total_views": total_views,
            "total_content": total_content,
            "avg_engagement": avg_engagement,
            "top_country": top_country,
            "top_country_views": top_country_views,
            "top_country_pct": top_country_pct,
            "top_hashtag": top_hashtag
        }
        
        # 第八步：检查模板需要的所有数据是否都有了（就像检查做菜的材料是否齐全）
        err = validate_context_fields_by_db(conn, "global_analysis", context)
        if err:
            # 如果缺材料，就返回错误，但也要把图表数据返回（至少能显示图表）
            return {
                "labels": country_names,
                "values": country_views,
                "category_labels": category_names,
                "category_values": category_views,
                "error": err
            }
        
        # 第九步：按照模板（菜谱）把数据填充进去，生成报告文字（就像按照模板摆盘）
        rendered = render_report_from_db(conn, "global_analysis", context)

        # 第十步：把所有东西打包好，准备送回给服务员
        return {
            "labels": country_names,           # 图表用的：国家名称列表
            "values": country_views,            # 图表用的：播放量列表
            "category_labels": category_names, # 图表用的：类别名称列表
            "category_values": category_views,  # 图表用的：类别播放量列表
            "extra_info": {                    # 额外信息（图表标题等）
                "platform": platform,
                "year_month": year_month,
                "total_content": total_content,
                "total_views": total_views,
                "avg_engagement": avg_engagement,
                "top_hashtag": top_hashtag,
                "top_country": top_country,
                "title": year_month + " " + platform + " Country Distribution"
            },
            "report": rendered["text"],        # 纯文本报告
            "report_markdown": rendered["markdown"],  # Markdown格式报告
            "report_html": rendered["html"],   # HTML格式报告（网页显示用）
            "error": ""
        }
```

**专业术语解释**：
- **SQL 查询**：用来从数据库里找数据的命令，就像在仓库里找东西的指令
- **cursor**：数据库游标，用来执行查询和获取结果，就像仓库管理员
- **fetchone()**：取出一行数据，就像从仓库里拿出一件东西
- **fetchall()**：取出所有行数据，就像从仓库里拿出一堆东西
- **context**：上下文，就是所有要传给模板的数据，就像做菜需要的所有材料
- **模板渲染**：把数据和模板结合起来，生成最终的文字，就像按照菜谱把食材做成菜

#### 第四部分：服务员上菜（前端显示结果）

**通俗解释**：现在厨房把做好的菜（数据）送回来了，服务员（前端 JavaScript）需要：
1. 检查菜有没有问题（检查错误）
2. 把菜摆到桌子上（显示报告文字）
3. 把配菜（图表）也摆好（绘制图表）

让我们看看服务员是怎么做的：

```javascript
.then(result => {
    // 服务员先检查菜有没有问题
    if (result.error) {
        showError('global-result', result.error);  // 如果有错误，告诉客人
        return;
    }
    
    // 服务员把菜里的信息整理一下
    const extraInfo = result.extra_info || {};  // 额外信息（标题等）
    let reportText = result.report_html || result.report || '';  // 报告文字（优先用HTML格式）
    
    // 服务员把菜摆到桌子上（把HTML内容插入到网页里）
    resultEl.innerHTML = `
        <h3>${extraInfo.year_month} ${extraInfo.platform} Global Data Analysis Report</h3>
        <div class="report-text"><div style="margin-top: 12px;">${reportText}</div></div>
        <div style="display: flex; gap: 20px; margin-top: 30px; flex-wrap: wrap;">
            <div class="chart-container" style="flex: 1; min-width: 300px; margin: 0;">
                <div id="global-echart" style="height: 450px; width: 100%;"></div>
            </div>
            <div class="chart-container" style="flex: 1; min-width: 300px; margin: 0;">
                <div id="global-echart-bar" style="height: 450px; width: 100%;"></div>
            </div>
        </div>
    `;
    
    // 等100毫秒后（让HTML先渲染完），再画第一个图表（国家分布饼图）
    setTimeout(() => {
        renderGlobalEchart(result.labels, result.values, extraInfo);
    }, 100);
    
    // 再等100毫秒，画第二个图表（类别分布柱状图）
    setTimeout(() => {
        renderGlobalCategoryChart(result.category_labels, result.category_values, extraInfo);
    }, 100);
})
```

**专业术语解释**：
- **innerHTML**：JavaScript 用来设置 HTML 内容的属性，就像把内容放到网页的某个位置
- **setTimeout**：延迟执行函数，就像"等一会儿再做什么"
- **DOM**：文档对象模型，就是网页的结构，就像餐厅的桌子布局

#### 第五部分：绘制图表（可视化数据）

**通俗解释**：现在文字报告已经显示出来了，但还需要画图表。图表就像把数据画成图，让人一眼就能看懂。我们用的是 ECharts 这个图表库，它就像专业的画图工具。

让我们看看第一个图表（国家分布饼图）是怎么画的：

```javascript
function renderGlobalEchart(labels, values, extraInfo) {
    // 第一步：找到要画图的地方（就像找到画布）
    const chartEl = document.getElementById('global-echart');
    if (!chartEl) return;  // 如果找不到，就不画了
    
    // 第二步：初始化图表（就像准备好画笔和画布）
    const myChart = echarts.init(chartEl);
    
    // 第三步：准备颜色（就像准备颜料）
    const COLORS = ['#B8A082', '#A0CFBA', '#899DCC', '#F2C6B4', '#DDB8A0', '#7B8FA6', '#B4A7D6', '#DBC585'];
    
    // 第四步：配置图表（就像决定画什么、怎么画）
    const option = {
        title: {
            text: 'TOP5 Country Distribution',  // 图表标题
            left: 'center',  // 标题居中
            top: 10
        },
        tooltip: {  // 鼠标悬停时显示的信息
            trigger: 'item',  // 触发方式：鼠标移到某个项目上
            formatter: '{b}: {c} views<br/>({d}%)'  // 显示格式：名称、数值、百分比
        },
        legend: {  // 图例（说明各个颜色代表什么）
            orient: 'vertical',  // 垂直排列
            left: 'left',
            top: 'middle'
        },
        series: [{  // 数据系列（要画的数据）
            type: 'pie',  // 饼图类型
            radius: ['45%', '75%'],  // 环形饼图（内半径45%，外半径75%）
            center: ['60%', '55%'],  // 图表中心位置
            data: labels.map((name, i) => ({  // 把国家名称和播放量组合成数据点
                name: name,  // 国家名称
                value: values[i],  // 播放量
                itemStyle: {
                    color: COLORS[i % COLORS.length]  // 循环使用颜色
                }
            }))
        }]
    };
    
    // 第五步：把配置应用到图表上（就像开始画图）
    myChart.setOption(option);
    
    // 第六步：监听窗口大小变化，自动调整图表大小（响应式）
    window.addEventListener('resize', function() {
        myChart.resize();
    });
}
```

**专业术语解释**：
- **ECharts**：一个 JavaScript 图表库，专门用来画各种图表，就像专业的画图工具
- **init**：初始化，就是准备好一个图表实例，就像准备好画布
- **option**：配置对象，用来设置图表的样式、数据等，就像画图的参数
- **series**：数据系列，就是要在图表上显示的数据，就像要画的内容
- **响应式**：根据窗口大小自动调整，就像画布会根据画框大小调整

`renderGlobalCategoryChart()` 函数画的是第二个图表（类别分布柱状图），原理一样，只是把 `type: 'pie'` 改成 `type: 'bar'`（柱状图）。

---

### 总结：整个流程就像餐厅点餐

1. **用户选择**（点菜）→ 前端 JavaScript 获取用户输入
2. **发送请求**（送订单）→ fetch 把数据送到后端 API
3. **接收请求**（接单）→ Flask 路由接收并解析请求
4. **查询数据**（找食材）→ 业务函数从数据库查询数据
5. **处理数据**（做菜）→ 计算指标、整理数据
6. **渲染模板**（摆盘）→ 把数据填充到模板里，生成报告文字
7. **返回结果**（上菜）→ 把结果打包成 JSON 返回
8. **显示结果**（摆桌）→ 前端显示报告文字
9. **绘制图表**（装饰）→ 用 ECharts 画出漂亮的图表

**关键概念**：
- **前端（Frontend）**：用户看到和操作的界面，用 HTML/CSS/JavaScript 实现
- **后端（Backend）**：处理业务逻辑的服务器，用 Python/Flask 实现
- **数据库（Database）**：存储数据的地方，用 SQLite 实现
- **API**：前后端通信的接口，就像餐厅的接单窗口
- **模板（Template）**：报告文字的格式，用 Jinja2 渲染
- **SQL 查询**：从数据库取数据的命令
- **JSON**：前后端传递数据的格式

其他功能模块（热门话题、发布时间分析等）的实现方式完全一样，只是：
- 查询的数据不同（不同的 SQL）
- 计算的指标不同（不同的业务逻辑）
- 显示的图表不同（不同的图表类型）

只要理解了"全球数据分析"这个例子，其他功能就都能看懂了！

---

### 9.2 其他功能模块的简要说明

其他功能模块（热门话题分析、发布时间分析、创作者表现等）的实现方式和"全球数据分析"**完全一样**，都遵循"餐厅点餐"的流程。唯一的区别在于：

#### 热门话题分析模块

**不同点**：
- **用户输入**：除了平台和时间，还需要输入"国家代码"和"最低播放量"（就像点菜时还要说明"不要太辣"）
- **查询的数据**：不是查国家分布，而是查热门标签（hashtag），比如 #美食、#旅行 这些
- **图表类型**：用的是**横向柱状图**（bar chart），标签名称在左边，播放量在右边，就像横向的条形图

**通俗理解**：就像问"在 TikTok 的美国地区，播放量超过 100 万的标签有哪些？"，然后把这些标签按播放量从高到低画成横向的条形图。

#### 发布时间分析模块

**不同点**：
- **用户输入**：可以选择三种分析方式——按小时（Hourly）、按时段（Day Parts）、按星期（Week Analysis）
- **查询的数据**：不是查国家或标签，而是查"什么时间发布的内容互动率最高"
- **图表类型**：根据选择的分析方式，画不同的柱状图，还会标记出"最佳时间"和"最差时间"

**通俗理解**：就像问"什么时候发视频效果最好？"，系统会告诉你"晚上 8 点发布互动率最高，凌晨 3 点最低"，然后用图表直观地显示出来。

#### 创作者表现模块

**不同点**：
- **用户输入**：可以选择只看某个层级的创作者（Micro/Mid/Macro/Star），或者看所有层级
- **查询的数据**：查不同层级创作者的贡献度、月度趋势等
- **图表类型**：
  - 如果只看一个层级：画**折线图**，显示这个层级每个月的播放量趋势
  - 如果看所有层级：画**饼图**，显示各层级占的比例

**通俗理解**：就像问"大V（Star）和小博主（Micro）谁贡献的播放量更多？"，系统会告诉你各占多少比例，或者某个层级每个月的变化趋势。

#### 区域广告推荐模块

**不同点**：
- **用户输入**：只需要输入区域名称（比如 "Asia"）
- **查询的数据**：查这个区域内 TikTok 和 YouTube 上各类别的表现
- **图表类型**：画两个**玫瑰图**（rose chart），一个显示 TikTok 的 top 类别，一个显示 YouTube 的 top 类别

**通俗理解**：就像问"在亚洲地区，TikTok 和 YouTube 上什么类别的内容最受欢迎？"，系统会分别列出两个平台的 top 类别，用玫瑰图展示。

#### 平台主导地位扩展模块

**不同点**：
- **用户输入**：只需要输入国家代码（比如 "US"）
- **查询的数据**：对比这个国家在 TikTok 和 YouTube 上的表现（视频数、播放量、互动率等）
- **图表类型**：画**分组柱状图**，每个指标（视频数、播放量等）都会显示两个平台的对比，还会自动切换显示不同指标

**通俗理解**：就像问"在美国，TikTok 和 YouTube 哪个更受欢迎？"，系统会从多个角度对比，用柱状图展示，还会自动轮播显示不同的对比维度。

---

### 总结：所有模块的共同点

虽然每个模块查询的数据不同、画的图表不同，但它们的**核心流程完全一样**：

1. **前端获取输入** → JavaScript 读取用户的选择
2. **发送请求** → fetch 把数据送到后端
3. **后端接收** → Flask 路由接收请求
4. **查询数据库** → 用 SQL 从数据库找数据
5. **处理数据** → 计算各种指标
6. **渲染模板** → 把数据填充到模板，生成报告文字
7. **返回结果** → 打包成 JSON 返回
8. **显示结果** → 前端显示文字和图表

**关键理解**：
- 所有模块用的都是**同一套流程**，就像所有菜都用同样的做菜步骤
- 区别只在于：**查什么数据**（不同的 SQL）、**算什么指标**（不同的计算）、**画什么图**（不同的图表类型）
- 只要理解了"全球数据分析"这个例子，其他模块就是把"查国家数据"换成"查标签数据"、"查时间数据"等，原理完全一样！

---

---

### 9.3 模板渲染机制（像填字游戏）

**通俗解释**：模板渲染就像玩填字游戏。模板里有一些"空白"（用 `{{ }}` 标记），系统会把实际数据填进去。

#### 模板是什么？

**通俗理解**：模板就像一封信的格式，信里有一些空白的地方，比如"亲爱的___"、"今天是___"、"天气是___"。每次写信时，只需要把名字、日期、天气填进去就行了。

在我们的系统里：
- **模板**：存储在数据库的 `report_templates` 表里，就像"信纸格式"
- **空白处**：用 `{{ 变量名 }}` 表示，比如 `{{ platform }}`、`{{ total_views }}`
- **数据**：从数据库查询出来，整理成 `context` 字典，就像"要填的内容"

#### 模板是怎么工作的？

**第一步：从数据库读取模板**

```python
def render_report_from_db(conn, slug, context):
    # 从"信纸库"（report_templates表）里找对应的模板
    row = conn.execute("SELECT format, content FROM report_templates WHERE slug=?", (slug,)).fetchone()
    if not row:
        return {"text": "Template not found.", ...}
    fmt, content = row[0], row[1]  # fmt是格式（html/markdown/text），content是模板内容
```

**第二步：用 Jinja2 填充数据**

```python
    # 用Jinja2引擎把数据填到模板里（就像把名字、日期填到信里）
    base_text = _render_template_text(content, context)
    # _render_template_text() 内部做的事情：
    #   1. 创建一个Jinja2环境（就像准备好填字工具）
    #   2. 解析模板（就像识别哪些地方要填）
    #   3. 把context里的数据填进去（就像把答案填到空白处）
    #   4. 返回填好的文字
```

**第三步：根据格式处理输出**

```python
    # 根据模板的格式类型，做不同的处理
    if fmt == "html":
        # 如果是HTML格式，把<strong>标签转换成<span class="highlight-data">
        html_out = convert_strong_to_span(base_text)
        text_out = html.unescape(html_out)  # 把HTML转义字符还原
        md_out = None
    elif fmt == "markdown":
        # 如果是Markdown格式，先把**加粗**转换成HTML
        md_out = base_text
        if markdown:
            temp_html = markdown.markdown(base_text, extensions=['nl2br'])
            html_out = convert_strong_to_span(temp_html)
        else:
            html_out = process_markdown_manually(base_text)
        text_out = md_out
    else:  # text格式
        text_out = base_text
        md_out = base_text
        html_out = convert_markdown_to_html(base_text)
    
    return {"text": text_out, "markdown": md_out, "html": html_out}
```

#### 实际例子

**模板内容**（存储在数据库里）：
```html
<p>In <span class="highlight-data">{{ year_month }}</span>, 
<span class="highlight-data">{{ platform }}</span> had a total of 
<span class="highlight-data">{{ total_views | format_comma }}</span> views 
across <span class="highlight-data">{{ total_content }}</span> content pieces.</p>
```

**要填的数据**（context）：
```python
context = {
    "year_month": "2025-04",
    "platform": "TikTok",
    "total_views": 1000000,
    "total_content": 500
}
```

**填好后的结果**：
```html
<p>In <span class="highlight-data">2025-04</span>, 
<span class="highlight-data">TikTok</span> had a total of 
<span class="highlight-data">1,000,000</span> views 
across <span class="highlight-data">500</span> content pieces.</p>
```

**专业术语解释**：
- **Jinja2**：Python 的模板引擎，专门用来把数据和模板结合起来，就像填字工具
- **slug**：模板的唯一标识符，就像模板的名字，比如 "global_analysis"
- **format**：模板的格式类型（html/markdown/text），就像信纸的格式
- **context**：要填到模板里的数据，是一个字典，就像填字游戏的答案
- **过滤器**：`| format_comma` 是 Jinja2 的过滤器，用来格式化数据，比如把 1000000 变成 1,000,000

---

### 9.4 数据库查询机制（像查字典）

**通俗解释**：SQL 查询就像查字典。字典里有很多词条（SQL 语句），每个词条都有个名字（slug）。当需要查某个词时，就按名字找到对应的词条，然后按照词条的内容去查。

#### SQL 查询是怎么存储的？

**通俗理解**：就像把常用的"查东西的指令"写在一本手册里，需要的时候翻手册找。

在我们的系统里：
- **手册**：`report_queries` 表，存储所有 SQL 查询语句
- **词条名**：`slug`，比如 "global_summary"、"hashtag_main"
- **词条内容**：`sql_text`，就是 SQL 查询语句

#### 怎么使用 SQL 查询？

**第一步：从手册里找指令**

```python
def get_sql(conn, slug):
    """从report_queries表获取SQL查询语句"""
    # 就像查字典：按名字（slug）找对应的SQL语句
    row = conn.execute("SELECT sql_text FROM report_queries WHERE slug=?", (slug,)).fetchone()
    if not row:
        raise ValueError(f"SQL not found for slug: {slug}")  # 如果找不到，就报错
    return row[0]  # 返回SQL语句
```

**第二步：执行这个指令**

```python
# 在业务函数里使用
sql = get_sql(conn, "global_summary")  # 从手册里找到"global_summary"对应的SQL
cursor.execute(sql, (platform, year_month))  # 执行这个SQL，传入参数
results = cursor.fetchall()  # 获取查询结果
```

#### 实际例子

**手册里的一条记录**（在 `report_queries` 表里）：
- **slug**（名字）："global_summary"
- **sql_text**（内容）：
```sql
SELECT 
    COUNT(*) as total_content,           -- 统计总内容数
    SUM(views) as total_views,            -- 统计总播放量
    SUM(likes) as total_likes,            -- 统计总点赞数
    AVG((likes + comments + shares) * 1.0 / NULLIF(views, 0)) as avg_engagement  -- 计算平均互动率
FROM Content
WHERE platform = ? AND year_month = ?    -- 条件是：平台和年月
```

**使用这个查询**：
```python
sql = get_sql(conn, "global_summary")  # 找到这个SQL
cursor.execute(sql, ("TikTok", "2025-04"))  # 执行：查TikTok在2025年4月的数据
total_content, total_views, total_likes, avg_engagement = cursor.fetchone()  # 取出结果
```

**专业术语解释**：
- **SQL**：结构化查询语言，用来从数据库里查数据的命令，就像"查字典的指令"
- **SELECT**：SQL 的关键字，表示"我要查什么"
- **WHERE**：SQL 的关键字，表示"查的条件是什么"
- **COUNT/SUM/AVG**：SQL 的聚合函数，用来统计、求和、求平均
- **参数化查询**：用 `?` 作为占位符，后面再传入实际值，这样更安全，防止 SQL 注入攻击

#### 为什么要这样设计？

**通俗理解**：就像把菜谱写在菜谱本里，而不是写在代码里。这样做的好处是：
1. **集中管理**：所有 SQL 在一个地方，好找好改
2. **不用改代码**：想改查询逻辑，直接改数据库里的 SQL，不用改 Python 代码
3. **容易扩展**：想加新的查询，直接在数据库里加一条记录就行

---

### 9.5 完整流程回顾（用生活例子）

让我们用一个完整的例子，把整个流程串起来：

**场景**：用户想知道"TikTok 在 2025年4月 的全球数据"

#### 第一步：用户点单（前端）

用户打开网页，看到：
- 一个下拉框，选择"TikTok"
- 一个输入框，输入"2025-04"
- 一个按钮"生成报告"

用户点击按钮，就像在餐厅说"我要这个！"

#### 第二步：服务员记录（JavaScript）

```javascript
// 服务员（JavaScript）看看客人选了啥
const platform = "TikTok";
const yearMonth = "2025-04";

// 服务员把订单送到厨房（发送请求到后端）
fetch('/api/global-analysis', {
    method: 'POST',
    body: JSON.stringify({ platform, year_month: yearMonth })
})
```

#### 第三步：厨房接单（Flask 路由）

```python
# 接单员（Flask路由）收到订单
@app.route('/api/global-analysis', methods=['POST'])
def global_analysis():
    data = request.json  # 打开订单
    platform = data.get('platform')  # 看到是"TikTok"
    year_month = data.get('year_month')  # 看到是"2025-04"
    
    # 把订单交给厨师
    result = generate_global_analysis(conn, platform, year_month)
    return jsonify(result)  # 把做好的菜送回
```

#### 第四步：厨师做菜（业务函数）

```python
def generate_global_analysis(conn, platform, year_month):
    # 厨师去仓库（数据库）找食材
    sql = get_sql(conn, "global_summary")  # 从"菜谱本"找SQL
    cursor.execute(sql, (platform, year_month))  # 执行查询
    total_content, total_views, ... = cursor.fetchone()  # 取出数据
    
    # 厨师处理数据（计算指标、整理数据）
    top_country = ...
    top_country_pct = ...
    
    # 厨师按照模板摆盘（渲染报告）
    context = {...}  # 把所有数据整理好
    rendered = render_report_from_db(conn, "global_analysis", context)
    
    # 打包好，准备送回
    return {
        "labels": [...],  # 图表数据
        "values": [...],
        "report_html": rendered["html"],  # 报告文字
        ...
    }
```

#### 第五步：服务员上菜（前端显示）

```javascript
.then(result => {
    // 服务员收到做好的菜
    let reportText = result.report_html;  // 报告文字
    let labels = result.labels;  // 图表数据
    
    // 把菜摆到桌子上（显示在网页上）
    resultEl.innerHTML = `<div>${reportText}</div>...`;
    
    // 画图表（装饰）
    renderGlobalEchart(labels, result.values, extraInfo);
})
```

#### 整个流程总结

```
用户选择 → JavaScript获取 → fetch发送 → Flask接收 → 
业务函数查询数据库 → 处理数据 → 渲染模板 → 
返回JSON → JavaScript接收 → 显示文字 → 绘制图表
```

**关键理解**：
- 这个流程就像**餐厅点餐**，每个步骤都有明确的分工
- 前端负责"接待客人"和"上菜"
- 后端负责"接单"和"做菜"
- 数据库负责"存储食材"
- 模板负责"摆盘格式"
- SQL 负责"找食材的指令"

只要理解了这个流程，所有功能模块就都能看懂了！它们只是"查的数据不同"、"算的指标不同"、"画的图表不同"，但流程完全一样。


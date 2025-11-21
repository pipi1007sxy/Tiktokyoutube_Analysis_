# Optimal Publish Time Analysis 实现文档

## 功能概述

Optimal Publish Time Analysis（最佳发布时间分析）功能用于分析在不同时间段发布内容时的参与度表现，帮助内容创作者找到最佳的发布时间。

## 实现逻辑

### 1. 数据查询逻辑

**SQL查询结构：**
```sql
SELECT 
    COALESCE(c.publish_hour, d.upload_hour) as hour,
    AVG(c.engagement_rate) as avg_engagement,
    MAX(c.engagement_rate) as max_engagement,
    MIN(c.engagement_rate) as min_engagement,
    AVG(c.views) as avg_views,
    AVG(c.completion_rate) as avg_completion,
    COUNT(*) as content_count
FROM Content c
LEFT JOIN Device d ON c.device_id = d.device_id
JOIN Country co ON c.country_id = co.country_id
WHERE c.platform = ? AND co.country_code = ?
[可选的日期筛选条件]
GROUP BY COALESCE(c.publish_hour, d.upload_hour)
HAVING COUNT(*) > 0
ORDER BY hour
```

**关键点：**
- 使用 `COALESCE(c.publish_hour, d.upload_hour)` 优先使用 Content 表的 publish_hour，如果为空则使用 Device 表的 upload_hour
- 支持按时间段筛选（通过 year_month 字段）
- 按小时分组统计参与度、完成率、观看数等指标

### 2. 数据处理逻辑

#### 2.1 数据清洗
- 过滤无效的小时值（只保留 0-23）
- 处理 NULL 值
- 将参与率和完成率转换为百分比（乘以100）

#### 2.2 关键指标计算

**平均参与度：**
```python
avg_eng_total = sum(engagement_rates) / len(engagement_rates)
```

**参与度差异百分比：**
```python
eng_diff_pct = [(eng - avg_eng_total) / avg_eng_total * 100 for eng in engagement_rates]
```

**峰值和谷值：**
- 峰值小时：参与度差异最大的小时
- 谷值小时：参与度差异最小的小时

#### 2.3 时间段分析

将24小时分为6个时段：
1. **Late Night (0-4)**: 深夜 0-4点
2. **Early Morning (5-8)**: 清晨 5-8点
3. **Morning (9-11)**: 上午 9-11点
4. **Afternoon (12-16)**: 下午 12-16点
5. **Evening (17-20)**: 傍晚 17-20点
6. **Night (21-23)**: 晚上 21-23点

对每个时段计算：
- 平均参与度差异百分比
- 平均参与率
- 内容数量

### 3. 报告生成逻辑

使用数据库中的报告模板（`publish_timing_analysis`）生成文本报告，包含：
- 平台和国家信息
- 分析时间段
- 平均参与度
- 最佳发布时间（峰值小时）
- 最差发布时间（谷值小时）
- 最佳时段
- 各时段的表现对比

## 函数说明

### `generate_publish_timing_analysis(conn, platform, country, period='All Time', start_month=None, end_month=None)`

**功能：** 生成发布时间分析报告

**参数：**
- `conn`: 数据库连接对象
- `platform`: 平台名称（'TikTok' 或 'YouTube'）
- `country`: 国家名称或代码
- `period`: 分析时段（'All Time' 或 'Custom'），默认为 'All Time'
- `start_month`: 开始月份（格式：'YYYY-MM'），当 period='Custom' 时必需
- `end_month`: 结束月份（格式：'YYYY-MM'），当 period='Custom' 时必需

**返回值：**
```python
{
    "platform": str,
    "country": str,
    "period_display": str,
    "report": str,              # 文本报告
    "report_markdown": str,     # Markdown格式报告
    "report_html": str,         # HTML格式报告
    "data": {
        "hours": [int],                    # 小时列表 (0-23)
        "engagement_rates": [float],       # 各小时参与率（百分比）
        "completion_rates": [float],       # 各小时完成率（百分比）
        "eng_diff_pct": [float],           # 各小时参与度差异百分比
        "content_counts": [int],           # 各小时内容数量
        "view_counts": [float],            # 各小时平均观看数
        "peak_hour": int,                  # 峰值小时
        "valley_hour": int,                # 谷值小时
        "time_slots": {
            "labels": [str],               # 时段标签
            "engagement_diff": [float],   # 各时段参与度差异
            "engagement_rates": [float],   # 各时段参与率
            "content_counts": [int]        # 各时段内容数量
        }
    },
    "error": str
}
```

### `publish_timing_analysis()` (API路由)

**功能：** 处理发布时间分析的API请求

**请求方法：** POST

**请求体：**
```json
{
    "platform": "TikTok",
    "country": "US",
    "period": "Custom",        // 可选，默认为 "All Time"
    "start_month": "2025-01",  // 当 period="Custom" 时必需
    "end_month": "2025-08"     // 当 period="Custom" 时必需
}
```

**响应：**
- 成功：返回分析结果（格式同 `generate_publish_timing_analysis` 返回值）
- 失败：返回错误信息

**错误处理：**
- 缺少必需参数：返回 `{"error": "Please provide platform and country"}`
- 自定义时段缺少日期：返回 `{"error": "For custom period, please provide both start_month and end_month..."}`
- 日期格式错误：返回 `{"error": "Invalid date format. Please use 'YYYY-MM' format..."}`
- 数据库错误：返回 `{"error": "Database query error: ..."}`

## 使用示例

### 示例1：分析所有时间的数据
```python
result = generate_publish_timing_analysis(
    conn=conn,
    platform="TikTok",
    country="US"
)
```

### 示例2：分析指定时间段的数据
```python
result = generate_publish_timing_analysis(
    conn=conn,
    platform="YouTube",
    country="CN",
    period="Custom",
    start_month="2025-01",
    end_month="2025-08"
)
```

### 示例3：API调用
```javascript
fetch('/api/publish-timing-analysis', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json'
    },
    body: JSON.stringify({
        platform: 'TikTok',
        country: 'US',
        period: 'Custom',
        start_month: '2025-01',
        end_month: '2025-08'
    })
})
.then(response => response.json())
.then(data => {
    console.log(data);
});
```

## 数据流程图

```
用户输入 (平台, 国家, 时间段)
    ↓
验证参数
    ↓
查询数据库 (按小时统计参与度)
    ↓
数据处理 (计算指标, 时段分析)
    ↓
生成报告上下文
    ↓
渲染报告模板
    ↓
返回结果 (数据 + 报告)
```

## 注意事项

1. **小时字段优先级：** 优先使用 `Content.publish_hour`，如果为空则使用 `Device.upload_hour`
2. **数据有效性：** 只处理有效的小时值（0-23）
3. **时间段筛选：** 使用 `year_month` 字段进行筛选，格式为 'YYYY-MM'
4. **错误处理：** 所有可能的错误情况都有相应的错误信息返回
5. **报告模板：** 报告内容由数据库中的 `publish_timing_analysis` 模板决定

## 相关数据库表

- **Content**: 内容主表，包含 publish_hour, engagement_rate, completion_rate 等字段
- **Device**: 设备表，包含 upload_hour 字段（备用）
- **Country**: 国家表，用于筛选特定国家的内容
- **report_templates**: 报告模板表，存储报告模板内容


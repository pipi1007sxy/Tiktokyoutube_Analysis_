from flask import Flask, render_template, request, jsonify, session, redirect
import sqlite3
from sqlite3 import Error
import matplotlib.pyplot as plt
import matplotlib
from jinja2 import Environment
import json
import html
import re
import os
try:
    import markdown  # Optional; used to render Markdown to HTML  # pyright: ignore[reportMissingModuleSource]
except Exception:
    markdown = None

# 全局字体配置 - 修复字体报错
matplotlib.rcParams['font.size'] = 9
matplotlib.rcParams['font.weight'] = 'normal'
plt.rcParams['axes.unicode_minus'] = False
plt.rcParams['figure.figsize'] = (10, 6) 
plt.rcParams['figure.dpi'] = 100
plt.rcParams['savefig.dpi'] = 100
plt.rcParams['savefig.bbox'] = 'tight'

# 关键修复：强制 Matplotlib 使用非交互式后端，避免线程警告
plt.switch_backend('Agg')

# 安全的字体配置，避免字体报错
try:
    # 尝试使用系统可用字体
    import matplotlib.font_manager as fm
    # 获取所有可用字体
    available_fonts = [f.name for f in fm.fontManager.ttflist]
    # 优先使用常见字体
    preferred_fonts = ['DejaVu Sans', 'Arial', 'Liberation Sans', 'sans-serif']
    font_found = False
    for font in preferred_fonts:
        if font in available_fonts or font == 'sans-serif':
            plt.rcParams["font.family"] = font
            font_found = True
            break
    if not font_found:
        plt.rcParams["font.family"] = "sans-serif"
except Exception as e:
    # 如果字体配置失败，使用默认字体
    plt.rcParams["font.family"] = "sans-serif"
    print(f"Font configuration warning: {e}")

# 初始化 Flask 应用
app = Flask(__name__, template_folder='.')
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here-change-in-production')

### 数据库连接函数
def create_connection():
    """Connect to SQLite database"""
    conn = None
    try:
        conn = sqlite3.connect('Tiktok_youtube.db')
        conn.row_factory = sqlite3.Row
        return conn
    except Error as e:
        print(f"Database connection error: {e}")
    return conn

### 报告模板：表初始化与种子、渲染工具
def init_report_template_table(conn):
    with conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS report_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            format TEXT NOT NULL CHECK(format IN ('text','markdown','html')),
            content TEXT NOT NULL,
            metadata TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """)

def init_report_queries_table(conn):
    with conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS report_queries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL,
            sql_text TEXT NOT NULL,
            description TEXT
        )
        """)


def get_sql(conn, slug):
    row = conn.execute("SELECT sql_text FROM report_queries WHERE slug=?", (slug,)).fetchone()
    if not row:
        raise ValueError(f"SQL not found for slug: {slug}")
    return row[0]

def upsert_report_query(conn, slug, sql_text, description):
    conn.execute(
        "INSERT OR REPLACE INTO report_queries (slug, sql_text, description) VALUES (?,?,?)",
        (slug, sql_text, description)
    )

def upsert_report_template(conn, slug, name, fmt, content, metadata_dict):
    conn.execute(
        "INSERT OR REPLACE INTO report_templates (slug, name, format, content, metadata) VALUES (?,?,?,?,?)",
        (slug, name, fmt, content, json.dumps(metadata_dict))
    )

def _format_comma(value):
    try:
        return f"{int(value):,}"
    except Exception:
        return str(value)

def _render_template_text(content, context):
    # 将常用过滤器以变量形式注入模板上下文
    context = dict(context or {})
    context.setdefault('format_comma', _format_comma)
    # 支持管道过滤器用法：{{ value | format_comma }}
    env = Environment(autoescape=False, trim_blocks=True, lstrip_blocks=True)
    env.filters['format_comma'] = _format_comma
    template = env.from_string(content)
    return template.render(**context)



def _is_missing(value):
    # None or empty-string or empty list/dict 视为缺失；数值0不算缺失
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, (list, dict)) and len(value) == 0:
        return True
    return False

def get_required_fields_from_db(conn, slug):
    row = conn.execute("SELECT metadata FROM report_templates WHERE slug=?", (slug,)).fetchone()
    if not row or not row[0]:
        return []
    try:
        meta = json.loads(row[0])
        fields = meta.get("fields", [])
        return fields if isinstance(fields, list) else []
    except Exception:
        return []

def validate_context_fields_by_db(conn, slug, context):
    required = get_required_fields_from_db(conn, slug)
    missing = [k for k in required if _is_missing(context.get(k))]
    if missing:
        return f"Missing values for: {', '.join(missing)}. Please check your inputs and try again."
    return None
def render_report_from_db(conn, slug, context):
    # Use main DB connection; ensure table and seeds exist
    row = conn.execute("SELECT format, content FROM report_templates WHERE slug=?", (slug,)).fetchone()
    if not row:
        return {
            "text": "Template not found.",
            "markdown": None,
            "html": "<p>Template not found.</p>"
        }
    fmt, content = row[0], row[1]

    base_text = _render_template_text(content, context)
    
    # 直接使用渲染后的文本，不再处理{{}}标记（现在直接在模板中使用HTML标签）
    processed_text = base_text
    
    # 统一处理函数：将所有 <strong> 标签转换为 <span class="highlight-data">（与Global模块一致）
    def convert_strong_to_span(html_text):
        """将所有 <strong> 标签转换为 <span class="highlight-data">（与Global模块一致）"""
        # 先处理已经有 class 的 <strong class="...">text</strong>，转换为 <span class="highlight-data">text</span>
        pattern_with_class = r'<strong\s+class="[^"]*">([^<]+)</strong>'
        html_text = re.sub(pattern_with_class, r'<span class="highlight-data">\1</span>', html_text)
        
        # 替换所有没有 class 的 <strong>text</strong> 为 <span class="highlight-data">text</span>
        pattern_no_class = r'<strong>([^<]+)</strong>'
        html_text = re.sub(pattern_no_class, r'<span class="highlight-data">\1</span>', html_text)
        
        return html_text

    if fmt == "html":
        html_out = convert_strong_to_span(processed_text)
        text_out = html.unescape(html_out)
        md_out = None
    elif fmt == "markdown":
        md_out = base_text  # markdown保持原始文本
        if markdown:
            # 先转换 markdown（将 **text** 转换为 <strong>text</strong>）
            # 使用extensions=['nl2br']来保留HTML标签，不转义
            temp_html = markdown.markdown(processed_text, extensions=['nl2br'])
            # 然后将所有 <strong> 标签转换为 <span class="highlight-data">
            html_out = convert_strong_to_span(temp_html)
        else:
            # 如果没有 markdown 库，处理 **text** 语法并转换为 <span class="highlight-data">
            # 匹配 **text** 并转换为 <span class="highlight-data">text</span>
            pattern = r'\*\*([^*]+)\*\*'
            def replace_bold(match):
                inner_text = match.group(1).strip()
                if inner_text:
                    return f'<span class="highlight-data">{inner_text}</span>'
                return match.group(0)
            processed_with_bold = re.sub(pattern, replace_bold, processed_text)
            # 转义HTML特殊字符，但保留span标签，文字直接装在div里，不使用br标签
            # 需要先转义，然后恢复span标签
            escaped_text = html.escape(processed_with_bold)
            # 恢复span标签（因为html.escape会把<和>转义）
            escaped_text = escaped_text.replace('&lt;span class=&quot;highlight-data&quot;&gt;', '<span class="highlight-data">')
            escaped_text = escaped_text.replace('&lt;/span&gt;', '</span>')
            html_out = f"<div>{escaped_text}</div>"
        text_out = md_out
    else:  # text
        text_out = base_text  # text格式保持原始文本
        md_out = base_text
        if markdown:
            # 先转换 markdown（将 **text** 转换为 <strong>text</strong>）
            # 使用extensions=['nl2br']来保留HTML标签，不转义
            temp_html = markdown.markdown(processed_text, extensions=['nl2br'])
            # 然后将所有 <strong> 标签转换为 <span class="highlight-data">
            html_out = convert_strong_to_span(temp_html)
        else:
            # 如果没有 markdown 库，处理 **text** 语法并转换为 <span class="highlight-data">
            pattern = r'\*\*([^*]+)\*\*'
            def replace_bold(match):
                inner_text = match.group(1).strip()
                if inner_text:
                    return f'<span class="highlight-data">{inner_text}</span>'
                return match.group(0)
            processed_with_bold = re.sub(pattern, replace_bold, processed_text)
            # 转义HTML特殊字符，但保留span标签，文字直接装在div里，不使用br标签
            # 需要先转义，然后恢复span标签
            escaped_text = html.escape(processed_with_bold)
            # 恢复span标签（因为html.escape会把<和>转义）
            escaped_text = escaped_text.replace('&lt;span class=&quot;highlight-data&quot;&gt;', '<span class="highlight-data">')
            escaped_text = escaped_text.replace('&lt;/span&gt;', '</span>')
            html_out = f"<div>{escaped_text}</div>"

    return {"text": text_out, "markdown": md_out, "html": html_out}

# (static REQUIRED_TEMPLATE_FIELDS removed; validations now read from DB metadata)

def nz(value, default=0):
    return default if value is None else value

    # (templates seeding removed by user request)

### 核心分析函数
def list_all_platforms(conn):
    """Get all platforms list"""
    with conn:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT platform FROM Content")
        return [row[0] for row in cur.fetchall()]

def list_all_countries(conn):
    """Get all countries list"""
    with conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT c.country_code, c.country_name, c.region, c.language
            FROM Country c JOIN Content ct ON c.country_id = ct.country_id
        """)
        return [{"code": row[0], "name": row[1], "region": row[2], "language": row[3]} for row in cur.fetchall()]

def list_all_year_months(conn):
    """Get all available year-month combinations"""
    with conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT year_month 
            FROM Content 
            WHERE year_month IS NOT NULL 
            ORDER BY year_month
        """)
        rows = cur.fetchall()
        result = []
        for row in rows:
            year_month = row[0]
            # Parse year-month string (e.g., "2025-01")
            if year_month and len(year_month) == 7:
                year = year_month[:4]
                month = year_month[5:7]
                month_names = {
                    "01": "January", "02": "February", "03": "March", "04": "April",
                    "05": "May", "06": "June", "07": "July", "08": "August",
                    "09": "September", "10": "October", "11": "November", "12": "December"
                }
                month_name = month_names.get(month, month)
                result.append({
                    "year_month": year_month,
                    "year": year,
                    "month": month,
                    "month_name": month_name,
                    "display": f"{month_name} {year}"
                })
        return result

def generate_global_analysis(conn, platform, year_month):
    with conn:
        cursor = conn.cursor()
        sql = get_sql(conn, "global_summary")
        cursor.execute(sql, (platform, year_month))
        total_content, total_views, total_likes, avg_engagement = cursor.fetchone()
        if not total_content:
            return {"error": f"No data found for {platform} in {year_month}"}
        # None-safe aggregation values
        total_views = nz(total_views, 0)
        total_likes = nz(total_likes, 0)
        avg_engagement = 0.0 if avg_engagement is None else float(avg_engagement)
        sql = get_sql(conn, "global_top_countries")
        cursor.execute(sql, (platform, year_month))
        top_countries = cursor.fetchall()
        country_names = [row[0] for row in top_countries]
        country_views = [nz(row[1], 0) for row in top_countries]
        sql = get_sql(conn, "global_top_hashtag")
        cursor.execute(sql, (platform, year_month))
        hashtag_result = cursor.fetchone()
        top_hashtag = hashtag_result[0] if hashtag_result else "N/A"
        
        # Category distribution data for right chart
        sql = get_sql(conn, "global_category_dist")
        cursor.execute(sql, (platform, year_month))
        category_results = cursor.fetchall()
        category_names = [row[0] for row in category_results]
        category_views = [nz(row[1], 0) for row in category_results]
        
        # report context - pass raw data only, no formatted text
        top_country = country_names[0] if country_names else "N/A"
        top_country_views = country_views[0] if country_views else 0
        top_country_pct = (top_country_views / total_views * 100) if total_views and total_views > 0 else 0
        
        # Generate country list text (only data, no full sentence)
        country_list_text = ""
        if country_names:
            country_parts = [f"{name} ({views:,} views)" for name, views in zip(country_names, country_views)]
            country_list_text = ", ".join(country_parts)
        
        context = {
            "platform": platform,
            "year_month": year_month,
            "country_list_text": country_list_text,  # Only data: "Korea (17,051,505 views), UAE (...)"
            "total_views": total_views,
            "total_content": total_content,
            "avg_engagement": avg_engagement,
            "top_country": top_country,
            "top_country_views": top_country_views,
            "top_country_pct": top_country_pct,
            "top_hashtag": top_hashtag  # Only hashtag value, template has the sentence structure
        }
        err = validate_context_fields_by_db(conn, "global_analysis", context)
        if err:
            return {
                "labels": country_names,
                "values": country_views,
                "category_labels": category_names,
                "category_values": category_views,
                "error": err
            }
        rendered = render_report_from_db(conn, "global_analysis", context)

        # 新结构输出
        return {
            "labels": country_names,
            "values": country_views,
            "category_labels": category_names,
            "category_values": category_views,
            "extra_info": {
                "platform": platform,
                "year_month": year_month,
                "total_content": total_content,
                "total_views": total_views,
                "avg_engagement": avg_engagement,
                "top_hashtag": top_hashtag,
                "top_country": top_country,
                "title": year_month + " " + platform + " Country Distribution"  # Simple concatenation for title
            },
            "report": rendered["text"],
            "report_markdown": rendered["markdown"],
            "report_html": rendered["html"],
            "error": ""
        }

# removed old platform_dominance per request

def generate_hashtag_report(conn, platform, country_code, min_views):
    """Generate hashtag report"""
    try:
        with conn:
            cur = conn.cursor()
            sql = get_sql(conn, "hashtag_country_check")
            cur.execute(sql, (country_code,))
            country_result = cur.fetchone()
            if not country_result:
                return {"error": f"Error: No data found for country code '{country_code}'"}
            country_id = country_result[0]

            sql = get_sql(conn, "hashtag_main")
            cur.execute(sql, (platform, country_id, min_views))
            results = cur.fetchall()

            if not results:
                return {"error": f"No hashtags found on {platform} in {country_code} with total views exceeding {min_views}"}

            hashtag_count = len(results)
            # Generate hashtag list text in Python
            hashtag_parts = [f"{h} ({v:,} views)" for h, v in results[:10]]
            hashtag_list_text = ", ".join(hashtag_parts)

            context = {
                "platform": platform,
                "country_code": country_code,
                "hashtag_count": hashtag_count,
                "min_views": min_views,
                "hashtag_list_text": hashtag_list_text  # Pre-generated text in Python
            }
            err = validate_context_fields_by_db(conn, "hashtag_report", context)
            if err:
                return {
                    "platform": platform,
                    "country_code": country_code,
                    "min_views": min_views,
                    "error": err
                }
            rendered = render_report_from_db(conn, "hashtag_report", context)

            hashtag_names = [row[0] for row in results][:10]
            hashtag_views = [row[1] for row in results][:10]

            return {
                "platform": platform,
                "country_code": country_code,
                "min_views": min_views,
                "hashtag_count": hashtag_count,
                "hashtags": [{"hashtag": row[0], "views": row[1]} for row in results],
                "labels": hashtag_names,
                "values": hashtag_views,
                "report": rendered["text"],
                "report_markdown": rendered["markdown"],
                "report_html": rendered["html"],
                "error": ""
            }

    except Error as e:
        return {"error": f"Database query error: {e}"}

def generate_trend_report(conn, platform, country_code, start_date, end_date):
    """Generate trend type view distribution report"""
    try:
        with conn:
            cur = conn.cursor()
            sql = get_sql(conn, "trend_country_check")
            cur.execute(sql, (country_code,))
            country_data = cur.fetchone()
            if not country_data:
                return {"error": f"Error: No records found for country code '{country_code}'"}
            country_id = country_data[0]

            sql = get_sql(conn, "trend_main")
            cur.execute(sql, (platform, country_id, start_date, end_date))
            results = cur.fetchall()

            if not results:
                return {"error": f"No trend data found on {platform} in {country_code} between {start_date} and {end_date}"}

            # Generate trend list text (only data, template has sentence structure)
            trend_parts = [f"{ttype}: {nz(views, 0):,} views" for ttype, views in results]
            trend_list_text = ", ".join(trend_parts)
            top_trend_type = results[0][0] if results else "N/A"
            trend_count = len(results)

            context = {
                "platform": platform,
                "country_code": country_code,
                "start_date": start_date,
                "end_date": end_date,
                "top_trend_type": top_trend_type,  # Only data
                "trend_list_text": trend_list_text,  # Only data: "Viral: 1000000 views, ..."
                "trend_count": trend_count  # Count for template if logic
            }
            err = validate_context_fields_by_db(conn, "trend_report", context)
            if err:
                return {
                    "platform": platform,
                    "country_code": country_code,
                    "start_date": start_date,
                    "end_date": end_date,
                    "error": err
                }
            rendered = render_report_from_db(conn, "trend_report", context)

            trend_types = [row[0] for row in results]
            trend_views = [row[1] for row in results]

            return {
                "platform": platform,
                "country_code": country_code,
                "start_date": start_date,
                "end_date": end_date,
                "trend_types": [{"trend_type": row[0], "views": row[1]} for row in results],
                "top_trend_type": top_trend_type,
                "labels": trend_types,
                "values": trend_views,
                "report": rendered["text"],
                "report_markdown": rendered["markdown"],
                "report_html": rendered["html"],
                "error": ""
            }

    except Error as e:
        return {"error": f"Database query error: {e}"}

def median_of(values):
    data = sorted([v for v in values if v is not None])
    n = len(data)
    if n == 0:
        return 0
    mid = n // 2
    if n % 2 == 1:
        return data[mid]
    return (data[mid - 1] + data[mid]) / 2

def generate_creator_performance(conn, platform, creator_scope, start_month, end_month):
    with conn:
        cursor = conn.cursor()
        # total views
        sql_total = get_sql(conn, "creator_total_views")
        total_views = cursor.execute(sql_total, (platform, start_month, end_month)).fetchone()[0] or 0
        time_frame = f"{start_month} to {end_month}"
        tier_map = {
            "All (all tiers)": ["Micro", "Mid", "Macro", "Star"],
            "Micro Only": ["Micro"],
            "Mid Only": ["Mid"],
            "Macro Only": ["Macro"],
            "Star Only": ["Star"]
        }
        target_tiers = tier_map.get(creator_scope, ["Micro", "Mid", "Macro", "Star"])
        placeholders = ", ".join(["?"] * len(target_tiers))
        sql_tpl = get_sql(conn, "creator_tier_agg")
        sql = sql_tpl.format(tier_placeholders=placeholders)
        params = [platform] + target_tiers + [start_month, end_month]
        rows = cursor.execute(sql, params).fetchall()
        
        # For single tier, query monthly trend
        monthly_data = []
        if len(target_tiers) == 1:
            # Query monthly breakdown for the single tier
            sql_monthly = """
                SELECT c.year_month, SUM(c.views) as total_views, COUNT(*) as content_count
                FROM Content c
                JOIN Author a ON c.author_id = a.author_id
                WHERE c.platform = ? AND a.creator_tier = ? AND c.year_month BETWEEN ? AND ?
                GROUP BY c.year_month
                ORDER BY c.year_month
            """
            monthly_rows = cursor.execute(sql_monthly, (platform, target_tiers[0], start_month, end_month)).fetchall()
            monthly_data = [{"month": r[0], "views": int(r[1] or 0), "count": int(r[2] or 0)} for r in monthly_rows]
        
        # Build tier details as raw data list (only data, template has sentence structure)
        tiers = []
        tier_views = []
        tier_pct = []
        tier_counts = []
        tier_avg_views = []
        tier_details_data = []
        
        if total_views > 0 and rows:
            for tier, views, content_count in rows:
                pct = round((views / total_views) * 100, 1) if total_views > 0 else 0
                avg_views = round(views / content_count) if content_count > 0 else 0
                tier_details_data.append({
                    "tier": tier,
                    "views": views,
                    "pct": pct,
                    "content_count": content_count,
                    "avg_views": avg_views
                })
                tiers.append(tier)
                tier_views.append(int(views or 0))
                tier_pct.append(float(pct))
                tier_counts.append(int(content_count or 0))
                tier_avg_views.append(int(avg_views))
        
        context = {
            "platform": platform,
            "creator_scope": creator_scope,
            "time_frame": time_frame,
            "total_views": total_views,
            "tier_details": tier_details_data,  # Raw data list, template has sentence structure
            "tier_count": len(tier_details_data)  # Count for template logic
        }
        err = validate_context_fields_by_db(conn, "creator_performance", context)
        if err:
            return {"error": err}
        rendered = render_report_from_db(conn, "creator_performance", context)
        return {
            "platform": platform,
            "creator_scope": creator_scope,
            "time_frame": time_frame,
            "report": rendered["text"],
            "report_markdown": rendered["markdown"],
            "report_html": rendered["html"],
            "data": {
                "tiers": tiers if total_views > 0 and rows else [],
                "tier_views": tier_views if total_views > 0 and rows else [],
                "tier_pct": tier_pct if total_views > 0 and rows else [],
                "tier_counts": tier_counts if total_views > 0 and rows else [],
                "tier_avg_views": tier_avg_views if total_views > 0 and rows else [],
                "monthly_trend": monthly_data  # Add monthly trend data
            },
            "error": ""
        }

def generate_region_ad_recommendation(conn, region):
    with conn:
        cursor = conn.cursor()
        sql = get_sql(conn, "region_engagement_main")
        rows = cursor.execute(sql, (region,)).fetchall()
        if not rows:
            return {"error": f"No data found for {region} region"}
        # split by platform
        tiktok = [r for r in rows if r[0] == "TikTok"]
        youtube = [r for r in rows if r[0] == "YouTube"]
        def top3(data):
            return data[:3] if data else []
        top3_tiktok = top3(tiktok)
        top3_youtube = top3(youtube)
        # Extract raw data
        category_tiktok = top3_tiktok[0][1] if top3_tiktok else ""
        engagement_tiktok = top3_tiktok[0][2] if top3_tiktok else 0
        category2_tiktok = top3_tiktok[1][1] if len(top3_tiktok) >= 2 else ""
        category3_tiktok = top3_tiktok[2][1] if len(top3_tiktok) >= 3 else ""
        category_youtube = top3_youtube[0][1] if top3_youtube else ""
        engagement_youtube = top3_youtube[0][2] if top3_youtube else 0
        category2_youtube = top3_youtube[1][1] if len(top3_youtube) >= 2 else ""
        category3_youtube = top3_youtube[2][1] if len(top3_youtube) >= 3 else ""
        
        # Determine best platform (only data, template has sentence structure)
        best_platform = ""
        best_category = ""
        best_engagement = 0
        comparison_engagement = 0
        
        if top3_tiktok and top3_youtube:
            if engagement_tiktok > engagement_youtube:
                best_platform = "TikTok"
                best_category = category_tiktok
                best_engagement = engagement_tiktok
                comparison_engagement = engagement_youtube
            else:
                best_platform = "YouTube"
                best_category = category_youtube
                best_engagement = engagement_youtube
                comparison_engagement = engagement_tiktok
        
        # Generate "followed by" text (includes "followed by" structure)
        tiktok_followed_by_text = ""
        if category2_tiktok and category3_tiktok:
            tiktok_followed_by_text = f", followed by {category2_tiktok} and {category3_tiktok}"
        elif category2_tiktok:
            tiktok_followed_by_text = f", followed by {category2_tiktok}"
        
        youtube_followed_by_text = ""
        if category2_youtube and category3_youtube:
            youtube_followed_by_text = f", followed by {category2_youtube} and {category3_youtube}"
        elif category2_youtube:
            youtube_followed_by_text = f", followed by {category2_youtube}"
        
        context = {
            "region": region,
            "category_tiktok": category_tiktok,
            "engagement_tiktok": engagement_tiktok,
            "tiktok_followed_by_text": tiktok_followed_by_text,  # Includes "followed by" but template has full sentence
            "category_youtube": category_youtube,
            "engagement_youtube": engagement_youtube,
            "youtube_followed_by_text": youtube_followed_by_text,  # Includes "followed by" but template has full sentence
            "best_platform": best_platform,  # Only data, template has full recommendation sentence
            "best_category": best_category,  # Only data
            "best_engagement": best_engagement,  # Only data
            "comparison_engagement": comparison_engagement  # Only data
        }
        err = validate_context_fields_by_db(conn, "region_ad_recommendation", context)
        if err:
            return {"error": err}
        rendered = render_report_from_db(conn, "region_ad_recommendation", context)
        return {
            "region": region,
            "report": rendered["text"],
            "report_markdown": rendered["markdown"],
            "report_html": rendered["html"],
            "data": {
                "tiktok_top": [{"category": r[1], "engagement": int(r[2] or 0)} for r in top3_tiktok],
                "youtube_top": [{"category": r[1], "engagement": int(r[2] or 0)} for r in top3_youtube]
            },
            "error": ""
        }

def generate_platform_dominance_extended(conn, country_code):
    with conn:
        cursor = conn.cursor()
        # country check
        sql = get_sql(conn, "pd_country_check")
        row = cursor.execute(sql, (country_code,)).fetchone()
        if not row:
            return {"error": f"Error: No data found for country code '{country_code}'"}
        country_id, country_name = row[0], row[1]
        # agg
        sql = get_sql(conn, "pd_agg_by_country")
        platform_data = cursor.execute(sql, (country_id,)).fetchall()
        if len(platform_data) < 2:
            available = [r[0] for r in platform_data]
            return {"error": f"Error: Only found data for {available} in {country_name}, need both platforms for comparison"}
        # details
        sql = get_sql(conn, "pd_details_by_country")
        detail_rows = cursor.execute(sql, (country_id,)).fetchall()
        # build dicts
        data = {}
        for r in platform_data:
            platform = r[0]
            data[platform] = {
                "total_videos": int(r[1] or 0),
                "total_views": int(r[2] or 0),
                "avg_engagement_rate": float(r[3] or 0),
                "avg_engagement_per_1k": float(r[4] or 0),
                "avg_likes": float(r[5] or 0),
                "avg_comments": float(r[6] or 0),
                "avg_shares": float(r[7] or 0),
                "avg_completion_rate": float(r[8] or 0),
                "median_engagement_rate": 0.0,
                "median_engagement_per_1k": 0.0,
                "median_completion_rate": 0.0
            }
        # medians
        tik_er = []
        tik_e1k = []
        tik_comp = []
        yt_er = []
        yt_e1k = []
        yt_comp = []
        for plat, er, e1k, likes, comments, shares, comp in detail_rows:
            if plat == "TikTok":
                tik_er.append(er); tik_e1k.append(e1k); tik_comp.append(comp)
            elif plat == "YouTube":
                yt_er.append(er); yt_e1k.append(e1k); yt_comp.append(comp)
        if "TikTok" in data:
            data["TikTok"]["median_engagement_rate"] = median_of(tik_er)
            data["TikTok"]["median_engagement_per_1k"] = median_of(tik_e1k)
            data["TikTok"]["median_completion_rate"] = median_of(tik_comp)
        if "YouTube" in data:
            data["YouTube"]["median_engagement_rate"] = median_of(yt_er)
            data["YouTube"]["median_engagement_per_1k"] = median_of(yt_e1k)
            data["YouTube"]["median_completion_rate"] = median_of(yt_comp)
        # extract
        t = data.get("TikTok", {})
        y = data.get("YouTube", {})
        if not t or not y:
            return {"error": "Error: Cannot get complete data for both platforms"}
        t_videos = t.get("total_videos", 0); y_videos = y.get("total_videos", 0)
        videos_diff = abs(t_videos - y_videos)
        quantity_leader = 'TikTok' if t_videos > y_videos else 'YouTube'
        t_median_er = t.get("median_engagement_rate", 0) * 100
        y_median_er = y.get("median_engagement_rate", 0) * 100
        t_e1k = t.get("avg_engagement_per_1k", 0)
        y_e1k = y.get("avg_engagement_per_1k", 0)
        quality_scores = {
            "TikTok": (t_median_er * 0.6 + t_e1k * 0.4),
            "YouTube": (y_median_er * 0.6 + y_e1k * 0.4)
        }
        quality_leader = "TikTok" if quality_scores["TikTok"] >= quality_scores["YouTube"] else "YouTube"
        final_scores = {
            "TikTok": (t_videos * 0.5 + quality_scores["TikTok"] * 0.5),
            "YouTube": (y_videos * 0.5 + quality_scores["YouTube"] * 0.5)
        }
        dominant_platform = "TikTok" if final_scores["TikTok"] >= final_scores["YouTube"] else "YouTube"
        
        # Build context for new template (no detailed table)
        context = {
            "country_name": country_name,
            "tiktok_videos": t_videos,
            "tiktok_views": int(t.get('total_views', 0)),
            "youtube_videos": y_videos,
            "youtube_views": int(y.get('total_views', 0)),
            "quantity_leader": quantity_leader,
            "videos_diff": videos_diff,
            "tiktok_median_er": f"{t_median_er:.2f}",
            "tiktok_e1k": f"{t_e1k:.1f}",
            "youtube_median_er": f"{y_median_er:.2f}",
            "youtube_e1k": f"{y_e1k:.1f}",
            "quality_leader": quality_leader,
            "dominant_platform": dominant_platform
        }
        err = validate_context_fields_by_db(conn, "platform_dominance_extended", context)
        if err:
            return {"error": err}
        rendered = render_report_from_db(conn, "platform_dominance_extended", context)
        return {
            "country_code": country_code,
            "country_name": country_name,
            "report": rendered["text"],
            "report_markdown": rendered["markdown"],
            "report_html": rendered["html"],
            "data": {
                "comparison": {
                    "metrics": ["Video Count", "Total Views", "Median Engagement Rate", "Engagement per 1k Views"],
                    "tiktok": [t_videos, int(t.get('total_views', 0)), t_median_er, t_e1k],
                    "youtube": [y_videos, int(y.get('total_views', 0)), y_median_er, y_e1k]
                },
                "radar": {
                    "indicators": [
                        {"name": "Quantity (Videos)", "max": max(t_videos, y_videos) * 1.2 + 1},
                        {"name": "Quality Score", "max": max(quality_scores['TikTok'], quality_scores['YouTube']) * 1.2 + 1},
                        {"name": "Overall Score", "max": max(final_scores['TikTok'], final_scores['YouTube']) * 1.2 + 1}
                    ],
                    "tikTok": [t_videos, quality_scores['TikTok'], final_scores['TikTok']],
                    "youTube": [y_videos, quality_scores['YouTube'], final_scores['YouTube']]
                }
            },
            "error": ""
        }

def get_country_code(conn, country):
    """Get country code by name, fall back to checking if input is already a code."""
    cur = conn.cursor()
    # Try by name or code
    cur.execute("SELECT country_code FROM Country WHERE country_name = ? OR country_code = ?", (country, country))
    row = cur.fetchone()
    return row[0] if row else None


def generate_publish_timing_analysis(conn, platform, time_analysis='Hourly', period='All Time', start_month=None, end_month=None):
    """
    Generate publish timing analysis report with support for multiple dimensions
    
    Args:
        conn: Database connection
        platform: Platform name (TikTok/YouTube)
        time_analysis: Analysis dimension ('Hourly', 'Day Parts', 'Week Analysis')
        period: Analysis period ('All Time', 'Custom')
        start_month: Start month in format 'YYYY-MM' (required if period='Custom')
        end_month: End month in format 'YYYY-MM' (required if period='Custom')
    
    Returns:
        Dictionary containing analysis results, charts data, and report
    """

    cursor = conn.cursor()
    period_display = "All Time"
    
    # Build date filter
    date_filter = ""
    params = [platform]
    if period == 'Custom' and start_month and end_month:
        date_filter = " AND c.year_month BETWEEN ? AND ?"
        params.extend([start_month, end_month])
        period_display = f"{start_month} to {end_month}"
    
    # Process based on time_analysis dimension
    if time_analysis == 'Hourly':
        return _process_hourly_analysis(cursor, conn, platform, period_display, date_filter, params)
    elif time_analysis == 'Day Parts':
        return _process_dayparts_analysis(cursor, conn, platform, period_display, date_filter, params)
    elif time_analysis == 'Week Analysis':
        return _process_week_analysis(cursor, conn, platform, period_display, date_filter, params)
    else:
        return {"error": f"Invalid time_analysis: {time_analysis}. Must be 'Hourly', 'Day Parts', or 'Week Analysis'"}


def _process_hourly_analysis(cursor, conn, platform, period_display, date_filter, params):
    """Process hourly analysis"""
    # Get SQL query from database
    try:
        sql = get_sql(conn, 'publish_timing_hourly')
        # Add date filter if needed
        if date_filter:
            sql = sql.replace('WHERE c.platform = ?', 
                            f'WHERE c.platform = ?{date_filter}')
    except ValueError as e:
        return {"error": f"SQL query not found: {e}"}

    try:
        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()
    except Error as e:
        return {"error": f"Database query error: {e}"}

    if not rows:
        return {
            "platform": platform,
            "time_analysis": "Hourly",
            "period_display": period_display,
            "report": "",
            "report_markdown": None,
            "report_html": None,
            "data": None,
            "error": "No data available for the selected criteria."
        }

    # Process data
    hours = []
    engagement_rates = []
    completion_rates = []
    content_counts = []
    eng_diff_pct = []

    for row in rows:
        hour, engagement, max_eng, min_eng, views, completion, count = row
        if hour is not None and 0 <= hour <= 23:
            hours.append(int(hour))
            eng_pct = round((engagement * 100) if engagement else 0, 2)
            comp_pct = round((completion * 100) if completion else 0, 2)
            engagement_rates.append(eng_pct)
            completion_rates.append(comp_pct)
            content_counts.append(int(count or 0))

    if not engagement_rates:
        return {
            "platform": platform,
            "time_analysis": "Hourly",
            "period_display": period_display,
            "report": "",
            "report_markdown": None,
            "report_html": None,
            "data": None,
            "error": "No valid data found."
        }
    
    # Calculate metrics
    avg_eng_total = round(sum(engagement_rates) / len(engagement_rates), 2)
    eng_diff_pct = [round((eng - avg_eng_total) / avg_eng_total * 100, 1) if avg_eng_total > 0 else 0 for eng in engagement_rates]
    peak_idx = eng_diff_pct.index(max(eng_diff_pct))
    valley_idx = eng_diff_pct.index(min(eng_diff_pct))
    max_diff = max(abs(d) for d in eng_diff_pct)

    # Time segment analysis
    time_slots = ['Late Night (0-4)', 'Early Morning (5-8)', 'Morning (9-11)',
                 'Afternoon (12-16)', 'Evening (17-20)', 'Night (21-23)']
    slot_diff = []
    slot_eng = []
    slot_counts = []

    for i, slot in enumerate(time_slots):
        if i == 0:
            slot_hours = [h for h in hours if 0 <= h <= 4]
        elif i == 1:
            slot_hours = [h for h in hours if 5 <= h <= 8]
        elif i == 2:
            slot_hours = [h for h in hours if 9 <= h <= 11]
        elif i == 3:
            slot_hours = [h for h in hours if 12 <= h <= 16]
        elif i == 4:
            slot_hours = [h for h in hours if 17 <= h <= 20]
        else:
            slot_hours = [h for h in hours if 21 <= h <= 23]

        if slot_hours:
            slot_diff_val = sum(eng_diff_pct[hours.index(h)] for h in slot_hours) / len(slot_hours)
            slot_eng_val = sum(engagement_rates[hours.index(h)] for h in slot_hours) / len(slot_hours)
            slot_count_val = sum(content_counts[hours.index(h)] for h in slot_hours)
        else:
            slot_diff_val = 0
            slot_eng_val = 0
            slot_count_val = 0

        slot_diff.append(round(slot_diff_val, 1))
        slot_eng.append(round(slot_eng_val, 2))
        slot_counts.append(slot_count_val)

    best_segment_idx = slot_diff.index(max(slot_diff)) if slot_diff else 0
    best_segment = time_slots[best_segment_idx].split(' (')[0] if slot_diff else ""
    
    # Prepare segment data for template
    segment_data = []
    for i in range(len(time_slots)):
        if slot_counts[i] > 0:
            segment_name = time_slots[i].split(' (')[0]
            segment_data.append({
                "name": segment_name,
                "diff": slot_diff[i],
                "eng": slot_eng[i]
            })
    
    # Pass raw data to template instead of pre-generated text
    context = {
        "platform": platform,
        "time_analysis": "Hourly",
        "period_display": period_display,
        "avg_eng_total": avg_eng_total,
        "peak_hour": hours[peak_idx] if hours else None,
        "peak_eng_rate": engagement_rates[peak_idx] if engagement_rates else 0,
        "peak_diff_pct": eng_diff_pct[peak_idx] if eng_diff_pct else 0,
        "valley_hour": hours[valley_idx] if hours else None,
        "valley_eng_rate": engagement_rates[valley_idx] if engagement_rates else 0,
        "valley_diff_pct": eng_diff_pct[valley_idx] if eng_diff_pct else 0,
        "best_segment": best_segment,
        "best_segment_diff": slot_diff[best_segment_idx] if slot_diff else 0,
        "segment_data": segment_data
    }
    
    err = validate_context_fields_by_db(conn, "publish_timing_analysis", context)
    if err:
        return {
            "platform": platform,
            "time_analysis": "Hourly",
            "period_display": period_display,
            "report": "",
            "report_markdown": None,
            "report_html": None,
            "data": None,
            "error": err
        }
    
    rendered = render_report_from_db(conn, "publish_timing_analysis", context)

    return {
        "platform": platform,
        "time_analysis": "Hourly",
        "period_display": period_display,
        "report": rendered["text"],
        "report_markdown": rendered["markdown"],
        "report_html": rendered["html"],
        "data": {
            "hours": hours,
            "engagement_rates": engagement_rates,
            "completion_rates": completion_rates,
            "eng_diff_pct": eng_diff_pct,
            "content_counts": content_counts,
            "peak_hour": hours[peak_idx] if hours else None,
            "valley_hour": hours[valley_idx] if hours else None
        },
        "error": ""
    }


def _process_dayparts_analysis(cursor, conn, platform, period_display, date_filter, params):
    """Process day parts analysis"""
    # Get SQL query from database
    try:
        sql = get_sql(conn, 'publish_timing_dayparts')
        # Add date filter if needed
        if date_filter:
            sql = sql.replace('WHERE c.platform = ? AND c.publish_period IS NOT NULL',
                            f'WHERE c.platform = ? AND c.publish_period IS NOT NULL{date_filter}')
    except ValueError as e:
        return {"error": f"SQL query not found: {e}"}
    
    try:
        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()
    except Error as e:
        return {"error": f"Database query error: {e}"}
    
    if not rows:
        return {
            "platform": platform,
            "time_analysis": "Day Parts",
            "period_display": period_display,
            "report": "",
            "report_markdown": None,
            "report_html": None,
            "data": None,
            "error": "No data available for the selected criteria."
        }
    
    # Process data
    periods = []
    engagement_rates = []
    content_counts = []
    
    for row in rows:
        period, engagement, count = row
        if period:
            periods.append(period)
            eng_pct = round((engagement * 100) if engagement else 0, 2)
            engagement_rates.append(eng_pct)
            content_counts.append(int(count or 0))
    
    if not engagement_rates:
        return {
            "platform": platform,
            "time_analysis": "Day Parts",
            "period_display": period_display,
            "report": "",
            "report_markdown": None,
            "report_html": None,
            "data": None,
            "error": "No valid data found."
        }
    
    # Calculate metrics
    avg_eng_total = round(sum(engagement_rates) / len(engagement_rates), 2)
    eng_diff_pct = [round((eng - avg_eng_total) / avg_eng_total * 100, 1) if avg_eng_total > 0 else 0 for eng in engagement_rates]
    max_diff = max(abs(d) for d in eng_diff_pct)
    
    # Get top 3 and best/worst
    sorted_indices = sorted(range(len(eng_diff_pct)), key=lambda i: eng_diff_pct[i], reverse=True)
    top3_indices = sorted_indices[:3]
    best_idx = sorted_indices[0]
    worst_idx = sorted_indices[-1]
    
    best_period_name = periods[best_idx]
    best_period_diff = eng_diff_pct[best_idx]
    best_period_eng = engagement_rates[best_idx]
    best_period_count = content_counts[best_idx]
    worst_period_name = periods[worst_idx]
    worst_period_diff = eng_diff_pct[worst_idx]
    worst_period_eng = engagement_rates[worst_idx]
    worst_period_count = content_counts[worst_idx]
    
    # Prepare top3 periods data for template
    top3_periods = [{"name": periods[i], "diff": eng_diff_pct[i]} for i in top3_indices]
    
    # Pass raw data to template instead of pre-generated text
    context = {
        "platform": platform,
        "time_analysis": "Day Parts",
        "period_display": period_display,
        "avg_eng_total": avg_eng_total,
        "best_period_name": best_period_name,
        "best_period_eng": best_period_eng,
        "best_period_diff": best_period_diff,
        "best_period_count": best_period_count,
        "worst_period_name": worst_period_name,
        "worst_period_eng": worst_period_eng,
        "worst_period_diff": worst_period_diff,
        "worst_period_count": worst_period_count,
        "top3_periods": top3_periods
    }
    
    err = validate_context_fields_by_db(conn, "publish_timing_analysis", context)
    if err:
        return {
            "platform": platform,
            "time_analysis": "Day Parts",
            "period_display": period_display,
            "report": "",
            "report_markdown": None,
            "report_html": None,
            "data": None,
            "error": err
        }
    
    rendered = render_report_from_db(conn, "publish_timing_analysis", context)
    
    return {
        "platform": platform,
        "time_analysis": "Day Parts",
        "period_display": period_display,
        "report": rendered["text"],
        "report_markdown": rendered["markdown"],
        "report_html": rendered["html"],
        "data": {
            "periods": periods,
            "engagement_rates": engagement_rates,
            "eng_diff_pct": eng_diff_pct,
            "content_counts": content_counts
        },
        "error": ""
    }


def _process_week_analysis(cursor, conn, platform, period_display, date_filter, params):
    """Process week analysis"""
    # Get SQL query from database
    try:
        sql = get_sql(conn, 'publish_timing_week')
        # Add date filter if needed
        if date_filter:
            sql = sql.replace('WHERE c.platform = ? AND c.publish_dayofweek IS NOT NULL',
                            f'WHERE c.platform = ? AND c.publish_dayofweek IS NOT NULL{date_filter}')
    except ValueError as e:
        return {"error": f"SQL query not found: {e}"}
    
    try:
        cursor.execute(sql, tuple(params))
        rows = cursor.fetchall()
    except Error as e:
        return {"error": f"Database query error: {e}"}
    
    if not rows:
        return {
            "platform": platform,
            "time_analysis": "Week Analysis",
            "period_display": period_display,
            "report": "",
            "report_markdown": None,
            "report_html": None,
            "data": None,
            "error": "No data available for the selected criteria."
        }
    
    # Process data
    days = []
    engagement_rates = []
    content_counts = []
    
    for row in rows:
        day, engagement, count = row
        if day:
            days.append(day)
            eng_pct = round((engagement * 100) if engagement else 0, 2)
            engagement_rates.append(eng_pct)
            content_counts.append(int(count or 0))
    
    if not engagement_rates:
        return {
            "platform": platform,
            "time_analysis": "Week Analysis",
            "period_display": period_display,
            "report": "",
            "report_markdown": None,
            "report_html": None,
            "data": None,
            "error": "No valid data found."
        }
    
    # Calculate metrics
    avg_eng_total = round(sum(engagement_rates) / len(engagement_rates), 2)
    eng_diff_pct = [round((eng - avg_eng_total) / avg_eng_total * 100, 1) if avg_eng_total > 0 else 0 for eng in engagement_rates]
    max_diff = max(abs(d) for d in eng_diff_pct)
    
    # Get top 3 and best/worst
    sorted_indices = sorted(range(len(eng_diff_pct)), key=lambda i: eng_diff_pct[i], reverse=True)
    top3_indices = sorted_indices[:3]
    best_idx = sorted_indices[0]
    worst_idx = sorted_indices[-1]
    
    best_day_name = days[best_idx]
    best_day_diff = eng_diff_pct[best_idx]
    best_day_eng = engagement_rates[best_idx]
    best_day_count = content_counts[best_idx]
    worst_day_name = days[worst_idx]
    worst_day_diff = eng_diff_pct[worst_idx]
    worst_day_eng = engagement_rates[worst_idx]
    worst_day_count = content_counts[worst_idx]
    
    # Calculate weekend vs weekday
    weekend_days = ['Saturday', 'Sunday']
    weekday_days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    
    weekend_engs = [engagement_rates[i] for i, day in enumerate(days) if day in weekend_days]
    weekday_engs = [engagement_rates[i] for i, day in enumerate(days) if day in weekday_days]
    
    weekend_eng = round(sum(weekend_engs) / len(weekend_engs), 2) if weekend_engs else 0
    weekday_eng = round(sum(weekday_engs) / len(weekday_engs), 2) if weekday_engs else 0
    weekend_lift = round((weekend_eng - weekday_eng) / weekday_eng * 100, 1) if weekday_eng > 0 else 0
    
    # Prepare top3 days data for template
    top3_days = [{"name": days[i], "diff": eng_diff_pct[i]} for i in top3_indices]
    
    # Pass raw data to template instead of pre-generated text
    context = {
        "platform": platform,
        "time_analysis": "Week Analysis",
        "period_display": period_display,
        "avg_eng_total": avg_eng_total,
        "best_day_name": best_day_name,
        "best_day_eng": best_day_eng,
        "best_day_diff": best_day_diff,
        "best_day_count": best_day_count,
        "worst_day_name": worst_day_name,
        "worst_day_eng": worst_day_eng,
        "worst_day_diff": worst_day_diff,
        "worst_day_count": worst_day_count,
        "top3_days": top3_days,
        "weekend_eng": weekend_eng,
        "weekday_eng": weekday_eng,
        "weekend_lift": weekend_lift
    }
    
    err = validate_context_fields_by_db(conn, "publish_timing_analysis", context)
    if err:
        return {
            "platform": platform,
            "time_analysis": "Week Analysis",
            "period_display": period_display,
            "report": "",
            "report_markdown": None,
            "report_html": None,
            "data": None,
            "error": err
        }
    
    rendered = render_report_from_db(conn, "publish_timing_analysis", context)
    
    return {
        "platform": platform,
        "time_analysis": "Week Analysis",
        "period_display": period_display,
        "report": rendered["text"],
        "report_markdown": rendered["markdown"],
        "report_html": rendered["html"],
        "data": {
            "days": days,
            "engagement_rates": engagement_rates,
            "eng_diff_pct": eng_diff_pct,
            "content_counts": content_counts
        },
        "error": ""
    }

### Flask routes
@app.route('/')
def index():
    """Frontend main page - Login page"""
    return render_template('index.html')

@app.route('/api/platforms', methods=['GET'])
def get_platforms():
    """API: Get all platforms"""
    conn = create_connection()
    data = list_all_platforms(conn)
    conn.close()
    return jsonify(data)

@app.route('/api/countries', methods=['GET'])
def get_countries():
    """API: Get all countries"""
    conn = create_connection()
    data = list_all_countries(conn)
    conn.close()
    return jsonify(data)

@app.route('/api/year-months', methods=['GET'])
def get_year_months():
    """API: Get all available year-month combinations"""
    conn = create_connection()
    data = list_all_year_months(conn)
    conn.close()
    return jsonify(data)

@app.route('/api/global-analysis', methods=['POST'])
def global_analysis():
    """API: Global analysis report"""
    data = request.json
    platform = data.get('platform')
    year_month = data.get('year_month')
    conn = create_connection()
    result = generate_global_analysis(conn, platform, year_month)
    conn.close()
    return jsonify(result)

# removed /api/platform-dominance endpoint per request

@app.route('/api/hashtag-report', methods=['POST'])
def hashtag_report():
    """API: Hashtag report"""
    data = request.json
    platform = data.get('platform')
    country_code = data.get('country_code')
    min_views = data.get('min_views')
    
    if not all([platform, country_code, min_views]):
        return jsonify({"error": "Please provide platform, country code and minimum views"})
    
    try:
        min_views = int(min_views)
    except ValueError:
        return jsonify({"error": "Minimum views must be an integer"})
    
    conn = create_connection()
    result = generate_hashtag_report(conn, platform, country_code, min_views)
    conn.close()
    return jsonify(result)

@app.route('/api/trend-report', methods=['POST'])
def trend_report():
    """API: Trend type analysis report"""
    data = request.json
    platform = data.get('platform')
    country_code = data.get('country_code')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    
    if not all([platform, country_code, start_date, end_date]):
        return jsonify({"error": "Please provide platform, country code, start date and end date"})
    
    conn = create_connection()
    result = generate_trend_report(conn, platform, country_code, start_date, end_date)
    conn.close()
    return jsonify(result)

@app.route('/api/publish-timing-analysis', methods=['POST'])
def publish_timing_analysis():
    """
    API: Publish timing analysis
    
    Request body:
    {
        "platform": "TikTok" or "YouTube",
        "time_analysis": "Hourly", "Day Parts", or "Week Analysis" (optional, default: "Hourly"),
        "period": "All Time" or "Custom" (optional, default: "All Time"),
        "start_month": "YYYY-MM" (required if period="Custom"),
        "end_month": "YYYY-MM" (required if period="Custom")
    }
    """
    data = request.json
    platform = data.get('platform')
    time_analysis = data.get('time_analysis', 'Hourly')
    period = data.get('period', 'All Time')
    start_month = data.get('start_month')
    end_month = data.get('end_month')
    
    # Validate required parameters
    if not all([platform]):
        return jsonify({"error": "Please provide platform"})
    
    # Validate time_analysis
    if time_analysis not in ['Hourly', 'Day Parts', 'Week Analysis']:
        return jsonify({"error": "Invalid time_analysis. Must be 'Hourly', 'Day Parts', or 'Week Analysis'"})
    
    # Validate custom period parameters
    if period == 'Custom':
        if not all([start_month, end_month]):
            return jsonify({"error": "For custom period, please provide both start_month and end_month in format 'YYYY-MM'"})
        # Validate date format
        try:
            from datetime import datetime
            datetime.strptime(start_month, '%Y-%m')
            datetime.strptime(end_month, '%Y-%m')
        except ValueError:
            return jsonify({"error": "Invalid date format. Please use 'YYYY-MM' format (e.g., '2025-01')"})
    
    conn = create_connection()
    try:
        result = generate_publish_timing_analysis(conn, platform, time_analysis, period, start_month, end_month)
        return jsonify(result)
    finally:
        conn.close()

# ====================== User Database and Login ======================
USER_DB_PATH = 'user.db'

def init_user_db():
    """Initialize user database"""
    conn = sqlite3.connect(USER_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            user_type TEXT NOT NULL CHECK(user_type IN ('user', 'admin'))
        )
    """)
    # Insert default admin if not exists
    cursor.execute("SELECT COUNT(*) FROM users WHERE user_type='admin'")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO users (username, password, user_type) 
            VALUES ('admin', 'admin123', 'admin')
        """)
    # Insert default user if not exists
    cursor.execute("SELECT COUNT(*) FROM users WHERE user_type='user'")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO users (username, password, user_type) 
            VALUES ('user', 'user123', 'user')
        """)
    conn.commit()
    conn.close()

@app.route('/login')
def login_page():
    """Login page"""
    return render_template('index.html')

@app.route('/home')
def home():
    """User home page"""
    if not session.get('user_id'):
        return redirect('/')
    return render_template('index_user.html')

@app.route('/api/login', methods=['POST'])
def login():
    """Login API"""
    data = request.json
    username = data.get('username')
    password = data.get('password')
    user_type = data.get('user_type', 'user')
    
    conn = sqlite3.connect(USER_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, username, user_type FROM users 
        WHERE username = ? AND password = ? AND user_type = ?
    """, (username, password, user_type))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        session['user_id'] = user[0]
        session['username'] = user[1]
        session['user_type'] = user[2]
        return jsonify({"success": True, "message": "Login successful"})
    else:
        return jsonify({"success": False, "message": "Invalid credentials"})

@app.route('/admin')
def admin_page():
    """Admin page"""
    if session.get('user_type') != 'admin':
        return redirect('/login')
    return render_template('index_admin.html')

@app.route('/api/admin/add-content', methods=['POST'])
def admin_add_content():
    """Admin: Add content"""
    if session.get('user_type') != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
    
    data = request.json
    conn = create_connection()
    try:
        cursor = conn.cursor()
        # Ensure country exists
        cursor.execute("INSERT OR IGNORE INTO Country (country_code, country_name) VALUES (?, ?)",
                     (data.get('country_code'), data.get('country_code')))
        cursor.execute("SELECT country_id FROM Country WHERE country_code = ?", (data.get('country_code'),))
        country_id = cursor.fetchone()[0]
        
        # Ensure author exists
        cursor.execute("INSERT OR IGNORE INTO Author (author_handle, creator_tier) VALUES (?, ?)",
                     (data.get('author_handle'), data.get('creator_tier', 'Mid')))
        cursor.execute("SELECT author_id FROM Author WHERE author_handle = ?", (data.get('author_handle'),))
        author_id = cursor.fetchone()[0]
        
        # Insert content
        cursor.execute("""
            INSERT OR REPLACE INTO Content (
                content_id, platform, category, views, likes, country_id, author_id,
                publish_date_approx, year_month
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data.get('content_id'), data.get('platform'), data.get('category'),
            data.get('views'), data.get('likes'), country_id, author_id,
            data.get('publish_date'), data.get('publish_date', '')[:7]
        ))
        conn.commit()
        return jsonify({"success": True, "message": "Content added successfully"})
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()

@app.route('/api/admin/delete-content', methods=['POST'])
def admin_delete_content():
    """Admin: Delete content"""
    if session.get('user_type') != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
    
    data = request.json
    content_id = data.get('content_id')
    conn = create_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM Content WHERE content_id = ?", (content_id,))
        conn.commit()
        if cursor.rowcount > 0:
            return jsonify({"success": True, "message": "Content deleted successfully"})
        else:
            return jsonify({"error": "Content not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()

@app.route('/api/admin/update-content', methods=['POST'])
def admin_update_content():
    """Admin: Update content"""
    if session.get('user_type') != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
    
    data = request.json
    content_id = data.get('content_id')
    conn = create_connection()
    try:
        cursor = conn.cursor()
        updates = []
        values = []
        if data.get('views') is not None:
            updates.append("views = ?")
            values.append(data.get('views'))
        if data.get('category'):
            updates.append("category = ?")
            values.append(data.get('category'))
        if data.get('likes') is not None:
            updates.append("likes = ?")
            values.append(data.get('likes'))
        
        if not updates:
            return jsonify({"error": "No fields to update"}), 400
        
        values.append(content_id)
        cursor.execute(f"UPDATE Content SET {', '.join(updates)} WHERE content_id = ?", values)
        conn.commit()
        if cursor.rowcount > 0:
            return jsonify({"success": True, "message": "Content updated successfully"})
        else:
            return jsonify({"error": "Content not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        conn.close()

@app.route('/api/admin/list-content', methods=['GET'])
def admin_list_content():
    """Admin: List content with pagination"""
    if session.get('user_type') != 'admin':
        return jsonify({"error": "Unauthorized"}), 403
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    conn = create_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT c.content_id, c.platform, c.category, c.views, c.likes, 
                   co.country_code, a.author_handle, c.publish_date_approx
            FROM Content c
            LEFT JOIN Country co ON c.country_id = co.country_id
            LEFT JOIN Author a ON c.author_id = a.author_id
            ORDER BY c.content_id
            LIMIT ? OFFSET ?
        """, (per_page, (page - 1) * per_page))
        results = cursor.fetchall()
        cursor.execute("SELECT COUNT(*) FROM Content")
        total = cursor.fetchone()[0]
        return jsonify({
            "content": [{
                "content_id": r[0],
                "platform": r[1],
                "category": r[2],
                "views": r[3],
                "likes": r[4],
                "country_code": r[5],
                "author_handle": r[6],
                "publish_date": r[7]
            } for r in results],
            "total": total,
            "page": page,
            "per_page": per_page
        })
    finally:
        conn.close()

# ====================== New Report APIs ======================
@app.route('/api/creator-performance', methods=['POST'])
def api_creator_performance():
    data = request.json
    platform = data.get('platform')
    creator_scope = data.get('creator_scope', 'All (all tiers)')
    start_month = data.get('start_month')
    end_month = data.get('end_month')
    conn = create_connection()
    try:
        result = generate_creator_performance(conn, platform, creator_scope, start_month, end_month)
        return jsonify(result)
    finally:
        conn.close()

@app.route('/api/region-ad-reco', methods=['POST'])
def api_region_ad_reco():
    data = request.json
    region = data.get('region')
    if not region:
        return jsonify({"error": "Please provide region"})
    conn = create_connection()
    try:
        result = generate_region_ad_recommendation(conn, region)
        return jsonify(result)
    finally:
        conn.close()

@app.route('/api/platform-dominance-extended', methods=['POST'])
def api_platform_dominance_extended():
    data = request.json
    country_code = data.get('country_code')
    if not country_code:
        return jsonify({"error": "Please provide country_code"})
    conn = create_connection()
    try:
        result = generate_platform_dominance_extended(conn, country_code)
        return jsonify(result)
    finally:
        conn.close()

# Initialize user database on startup
init_user_db()

# Initialize report templates on startup
try:
    _conn = create_connection()
    if _conn:
        init_report_template_table(_conn)  # optional safeguard; table exists => no-op
        init_report_queries_table(_conn)   # ensure queries table
        _conn.close()
except Exception as _e:
    print(f"Report template init warning: {_e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
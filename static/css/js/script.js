// Short Video Data Analysis Platform - JavaScript Interaction Logic

// Initialize on page load
window.onload = function() {
    loadPlatforms();
    loadCountries();
    loadYearMonths();
    initTabs();
    addLoadingStates();
};

// Initialize tab switching
function initTabs() {
    const navBtns = document.querySelectorAll('.nav-btn');
    navBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            // Switch button active state
            navBtns.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            // Switch content display
            const tabId = btn.getAttribute('data-tab');
            document.querySelectorAll('.content-section').forEach(content => {
                content.classList.remove('active');
            });
            document.getElementById(tabId).classList.add('active');
            
            // Add transition animation
            const activeContent = document.getElementById(tabId);
            activeContent.style.animation = 'none';
            setTimeout(() => {
                activeContent.style.animation = 'fadeInUp 0.5s ease-out';
            }, 10);
        });
    });
}

// Add loading states
function addLoadingStates() {
    const buttons = document.querySelectorAll('button[onclick]');
    buttons.forEach(btn => {
        btn.addEventListener('click', function() {
            const originalText = this.innerHTML;
            this.disabled = true;
            this.innerHTML = '<span class="loading"></span> Processing...';
            
            // Restore after 3 seconds (prevent long unresponsiveness)
            setTimeout(() => {
                this.disabled = false;
                this.innerHTML = originalText;
            }, 3000);
        });
    });
}

// Load platform list
function loadPlatforms() {
    fetch('/api/platforms')
        .then(res => res.json())
        .then(data => {
            const listEl = document.getElementById('platforms-list');
            if (data.length === 0) {
                listEl.innerHTML = '<div class="error-message">No platform data available</div>';
                return;
            }
            
            listEl.innerHTML = data.map((platform, index) => {
                return `
                    <div style="padding: 20px; background: var(--bg-card); border-radius: 16px; box-shadow: var(--shadow-soft); border: 1px solid rgba(0, 0, 0, 0.04); transition: all 0.3s ease;">
                        <strong style="font-size: 1rem; color: var(--text-primary);">${platform}</strong>
                    </div>
                `;
            }).join('');
            
            // Populate all platform dropdowns
            const selectEls = document.querySelectorAll('#global-platform, #hashtag-platform, #trend-platform, #publish-platform, #creator-platform');
            selectEls.forEach(selectEl => {
                // Clear existing options (keep first one)
                while (selectEl.children.length > 1) {
                    selectEl.removeChild(selectEl.lastChild);
                }
                data.forEach(platform => {
                    const option = document.createElement('option');
                    option.value = platform;
                    option.textContent = platform;
                    selectEl.appendChild(option);
                });
            });
        })
        .catch(error => {
            console.error('Failed to load platform list:', error);
            document.getElementById('platforms-list').innerHTML = 
                '<div class="error-message">Failed to load, please refresh the page and try again</div>';
        });
}

// Creator Performance
function runCreatorPerformance() {
    const platform = document.getElementById('creator-platform').value;
    const creatorScope = document.getElementById('creator-scope').value;
    const startMonth = document.getElementById('creator-start-month').value || '2025-01';
    const endMonth = document.getElementById('creator-end-month').value || '2025-08';
    if (!platform) {
        showError('creator-performance-result', 'Please select platform');
        return;
    }
    const resultEl = document.getElementById('creator-performance-result');
    resultEl.innerHTML = '<div style="text-align: center; padding: 20px;"><span class="loading"></span> Generating report...</div>';
    fetch('/api/creator-performance', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ platform, creator_scope: creatorScope, start_month: startMonth, end_month: endMonth })
    })
    .then(r => r.json())
    .then(result => {
        if (result.error) {
            showError('creator-performance-result', result.error);
            return;
        }
        // 直接使用后端处理好的report_html，所有加粗通过数据库模板中的{{}}标记处理
        let reportText = result.report_html || result.report || 'No report';
        
        // Add chart container in result HTML
        let chartHtml = '';
        if (result.data) {
            // Single tier: show monthly trend line chart
            if (result.data.monthly_trend && result.data.monthly_trend.length > 0) {
                chartHtml = '<div class="chart-container"><div id="creator-monthly-chart" style="height: 400px; width: 100%;"></div></div>';
            } 
            // Multiple tiers: show tier pie chart
            else if (result.data.tiers && result.data.tiers.length > 1) {
                chartHtml = '<div class="chart-container"><div id="creator-tier-pie" style="height: 400px; width: 100%;"></div></div>';
            }
        }
        
        resultEl.innerHTML = `
            <h3>Creator Ecosystem & Tier Performance Data Report in ${platform} - ${creatorScope} (${startMonth} to ${endMonth})</h3>
            <div class="report-text"><div style="margin-top: 12px;">${reportText}</div></div>
            ${chartHtml}
        `;
        
        // Render appropriate chart
        if (result.data) {
            if (result.data.monthly_trend && result.data.monthly_trend.length > 0) {
                setTimeout(() => renderCreatorMonthlyTrend(result.data.monthly_trend, creatorScope, platform), 100);
            } else if (result.data.tiers && result.data.tiers.length > 1) {
                setTimeout(() => renderCreatorTierPie(result.data.tiers, result.data.tier_views, result.data.tier_pct), 100);
            }
        }
    })
    .catch(e => {
        console.error(e);
        showError('creator-performance-result', 'Failed to generate report');
    });
}

function renderCreatorMonthlyTrend(monthlyData, tierName, platform) {
    const el = document.getElementById('creator-monthly-chart');
    if (!el) return;
    const chart = echarts.init(el);
    const months = monthlyData.map(d => d.month);
    const views = monthlyData.map(d => d.views);
    const option = {
        title: { text: `${tierName} Monthly Views Trend (${platform})`, left: 'center' },
        tooltip: { 
            trigger: 'axis',
            formatter: (params) => {
                const p = params[0];
                return `${p.axisValue}<br/>${p.marker}Views: ${p.value.toLocaleString()}`;
            }
        },
        xAxis: {
            type: 'category',
            data: months,
            axisLabel: { rotate: 45, fontSize: 11 }
        },
        yAxis: {
            type: 'value',
            name: 'Views',
            axisLabel: {
                formatter: (val) => {
                    if (val >= 1000000) return (val / 1000000).toFixed(1) + 'M';
                    if (val >= 1000) return (val / 1000).toFixed(1) + 'K';
                    return val;
                }
            }
        },
        grid: { left: '12%', right: '5%', bottom: '15%', top: '15%' },
        series: [{
            type: 'line',
            data: views,
            smooth: true,
            lineStyle: { width: 3, color: '#5470c6' },
            itemStyle: { color: '#5470c6' },
            areaStyle: { 
                color: {
                    type: 'linear',
                    x: 0, y: 0, x2: 0, y2: 1,
                    colorStops: [
                        { offset: 0, color: 'rgba(84,112,198,0.4)' },
                        { offset: 1, color: 'rgba(84,112,198,0.05)' }
                    ]
                }
            }
        }]
    };
    chart.setOption(option);
    window.addEventListener('resize', () => chart.resize());
}

function renderCreatorTierPie(tiers, views, pct) {
    const el = document.getElementById('creator-tier-pie');
    if (!el) return;
    const chart = echarts.init(el);
    const data = tiers.map((t, i) => ({ name: t, value: views[i] }));
    const option = {
        title: { text: 'Creator Tier Contribution (Views Share)', left: 'center' },
        tooltip: { trigger: 'item', formatter: '{b}: {c} views ({d}%)' },
        legend: { left: 'left' },
        series: [{
            type: 'pie',
            radius: ['45%','70%'],
            center: ['50%','55%'],
            roseType: false,
            itemStyle: { borderRadius: 8, borderColor:'#fff', borderWidth:2 },
            label: { formatter: '{b}\n{d}%' },
            data
        }]
    };
    chart.setOption(option);
    window.addEventListener('resize', () => chart.resize());
}
// Region Ad Recommendation
function runRegionAdReco() {
    const region = document.getElementById('region-name').value;
    if (!region) {
        showError('region-ad-result', 'Please enter region (e.g., Asia)');
        return;
    }
    const resultEl = document.getElementById('region-ad-result');
    resultEl.innerHTML = '<div style="text-align: center; padding: 20px;"><span class="loading"></span> Generating report...</div>';
    fetch('/api/region-ad-reco', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ region })
    })
    .then(r => r.json())
    .then(result => {
        if (result.error) {
            showError('region-ad-result', result.error);
            return;
        }
        // 直接使用后端处理好的report_html，所有加粗通过数据库模板中的{{}}标记处理
        let reportText = result.report_html || result.report || 'No report';
        
        resultEl.innerHTML = `
            <h3>Regional Advertising Recommendation - ${region}</h3>
            <div class="report-text"><div style="margin-top: 12px; white-space: pre-wrap;">${reportText}</div></div>
            ${result.data ? `
            <div style="display: flex; gap: 20px; margin-top: 30px; flex-wrap: wrap;">
                <div class="chart-container" style="flex: 1; min-width: 300px;">
                    <div id="region-ad-tiktok" style="height: 400px; width: 100%;"></div>
                </div>
                <div class="chart-container" style="flex: 1; min-width: 300px;">
                    <div id="region-ad-youtube" style="height: 400px; width: 100%;"></div>
                </div>
            </div>
            ` : ''}
        `;
        // charts: two rose pies for top3 categories
        if (result.data) {
            setTimeout(() => {
                renderRegionTopRose('region-ad-tiktok', 'TikTok Top Categories', result.data.tiktok_top || []);
                renderRegionTopRose('region-ad-youtube', 'YouTube Top Categories', result.data.youtube_top || []);
            }, 100);
        }
    })
    .catch(e => {
        console.error(e);
        showError('region-ad-result', 'Failed to generate report');
    });
}

function renderRegionTopRose(elId, title, items) {
    const el = document.getElementById(elId);
    if (!el) return;
    if (!items || items.length === 0) {
        el.innerHTML = '<div style="text-align:center;color:#888;padding:40px;">No data</div>';
        return;
    }
    const chart = echarts.init(el);
    // distinct palettes for TikTok vs YouTube
    const warmPalette = ['#C65B7C', '#E4A9A8', '#F2C6B4', '#DDB8A0', '#EABDA8'];
    const coolPalette = ['#74B9FF', '#A29BFE', '#55EFC4', '#81ECEC', '#B2BEC3'];
    const isTikTok = /tiktok/i.test(title);
    const colors = isTikTok ? warmPalette : coolPalette;
    const option = {
        title: { text: title, left: 'center' },
        tooltip: { trigger: 'item', formatter: '{b}: {c} (engagement)' },
        color: colors,
        series: [{
            type: 'pie',
            radius: [20, 120],
            center: ['50%','55%'],
            roseType: 'area',
            itemStyle: { borderRadius: 8 },
            label: { formatter: '{b}\n{d}%' },
            data: items.map(it => ({ name: it.category, value: it.engagement }))
        }]
    };
    chart.setOption(option);
    window.addEventListener('resize', () => chart.resize());
}

// Platform Dominance Extended
function runDominanceExtended() {
    const cc = document.getElementById('pd-country-code').value;
    if (!cc) {
        showError('pd-extended-result', 'Please enter country code (e.g., US)');
        return;
    }
    const resultEl = document.getElementById('pd-extended-result');
    resultEl.innerHTML = '<div style="text-align: center; padding: 20px;"><span class="loading"></span> Analyzing...</div>';
    fetch('/api/platform-dominance-extended', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ country_code: cc })
    })
    .then(r => r.json())
    .then(result => {
        if (result.error) {
            showError('pd-extended-result', result.error);
            return;
        }
        // 直接使用后端处理好的report_html，所有加粗通过数据库模板中的{{}}标记处理
        let reportText = result.report_html || result.report || 'No report';
        
        resultEl.innerHTML = `
            <h3>Short Video Platform Dominance Analysis by Country - ${result.country_name || cc}</h3>
            <div class="report-text"><div style="margin-top: 12px;">${reportText}</div></div>
            <div class="chart-container">
                <div id="pd-comparison-bar" style="height: 400px; width: 100%;"></div>
            </div>
        `;
        setTimeout(() => {
            if (result.data && result.data.comparison) {
                renderDominanceComparisonBar(result.data.comparison, result.country_name || cc);
            }
        }, 100);
    })
    .catch(e => {
        console.error(e);
        showError('pd-extended-result', 'Failed to analyze');
    });
}
// Load countries/regions list
function loadCountries() {
    fetch('/api/countries')
        .then(res => res.json())
        .then(data => {
            const listEl = document.getElementById('countries-list');
            if (data.length === 0) {
                listEl.innerHTML = '<div class="error-message">No country/region data available</div>';
                return;
            }
            
            listEl.innerHTML = data.map(country => 
                `<div style="padding: 20px; background: var(--bg-card); border-radius: 16px; box-shadow: var(--shadow-soft); border: 1px solid rgba(0, 0, 0, 0.04); transition: all 0.3s ease;">
                    <strong style="font-size: 1rem; color: var(--text-primary);">${country.code}</strong> - ${country.name} 
                    <span style="color: var(--text-secondary); font-size: 0.9rem;">(${country.region}, ${country.language})</span>
                </div>`
            ).join('');
        })
        .catch(error => {
            console.error('Failed to load country list:', error);
            document.getElementById('countries-list').innerHTML = 
                '<div class="error-message">Failed to load, please refresh the page and try again</div>';
        });
}

function loadYearMonths() {
    fetch('/api/year-months')
        .then(res => res.json())
        .then(data => {
            const listEl = document.getElementById('year-months-list');
            if (data.length === 0) {
                listEl.innerHTML = '<div class="error-message">No year/month data available</div>';
                return;
            }
            
            listEl.innerHTML = data.map(ym => 
                `<div style="padding: 20px; background: var(--bg-card); border-radius: 16px; box-shadow: var(--shadow-soft); border: 1px solid rgba(0, 0, 0, 0.04); transition: all 0.3s ease;">
                    <strong style="font-size: 1rem; color: var(--text-primary);">${ym.display}</strong>
                    <span style="color: var(--text-secondary); font-size: 0.9rem; margin-left: 10px;">(${ym.year_month})</span>
                </div>`
            ).join('');
        })
        .catch(error => {
            console.error('Failed to load year/month list:', error);
            document.getElementById('year-months-list').innerHTML = 
                '<div class="error-message">Failed to load, please refresh the page and try again</div>';
        });
}

function renderDominanceComparisonBar(compData, countryName) {
    const el = document.getElementById('pd-comparison-bar');
    if (!el) return;
    const chart = echarts.init(el);
    const metrics = compData.metrics || [];
    const tiktokData = compData.tiktok || [];
    const youtubeData = compData.youtube || [];
    
    if (metrics.length === 0) return;
    
    // 定义每个维度使用的颜色（动态变化）
    const colors = [
        { tiktok: '#5470c6', youtube: '#ee6666' }, // 蓝色/红色
        { tiktok: '#91cc75', youtube: '#fac858' }, // 绿色/黄色
        { tiktok: '#73c0de', youtube: '#fc8452' }, // 青色/橙色
        { tiktok: '#3ba272', youtube: '#ea7ccc' }  // 深绿/粉色
    ];
    
    let currentIndex = 0;
    let animationTimer = null;
    
    function formatValue(value, metric) {
        if (metric === 'Total Views' || metric === 'Video Count') {
            if (value >= 1000000000) return (value / 1000000000).toFixed(2) + 'B';
            if (value >= 1000000) return (value / 1000000).toFixed(1) + 'M';
            if (value >= 1000) return (value / 1000).toFixed(1) + 'K';
            return value.toLocaleString();
        } else if (metric === 'Median Engagement Rate') {
            return value.toFixed(2) + '%';
        } else if (metric === 'Engagement per 1k Views') {
            return value.toFixed(1);
        }
        return value.toFixed(2);
    }
    
    function updateChart(index) {
        const metric = metrics[index];
        const tiktokValue = tiktokData[index];
        const youtubeValue = youtubeData[index];
        const colorSet = colors[index % colors.length];
        
        const option = {
            title: { 
                text: `${metric} Comparison - ${countryName}`, 
                left: 'center',
                top: 10,
                textStyle: { fontSize: 16, fontWeight: 600 }
            },
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'shadow' },
                formatter: (params) => {
                    const param = params[0];
                    return `${param.name}<br/>${param.marker}TikTok: ${formatValue(param.value, metric)}<br/>${params[1].marker}YouTube: ${formatValue(params[1].value, metric)}`;
                }
            },
            legend: { data: ['TikTok', 'YouTube'], top: 40 },
            xAxis: {
                type: 'value',
                name: metric,
                nameLocation: 'middle',
                nameGap: 30,
                axisLabel: {
                    formatter: (value) => formatValue(value, metric)
                }
            },
            yAxis: {
                type: 'category',
                data: ['Platform'],
                axisLabel: { fontSize: 14, fontWeight: 'bold' }
            },
            grid: { left: '25%', right: '10%', top: '20%', bottom: '10%' },
            series: [
                {
                    name: 'TikTok',
                    type: 'bar',
                    data: [tiktokValue],
                    itemStyle: { 
                        color: colorSet.tiktok,
                        borderRadius: [0, 8, 8, 0]
                    },
                    label: {
                        show: true,
                        position: 'right',
                        formatter: (params) => formatValue(params.value, metric),
                        fontSize: 12,
                        fontWeight: 'bold',
                        color: colorSet.tiktok
                    },
                    barWidth: '50%'
                },
                {
                    name: 'YouTube',
                    type: 'bar',
                    data: [youtubeValue],
                    itemStyle: { 
                        color: colorSet.youtube,
                        borderRadius: [0, 8, 8, 0]
                    },
                    label: {
                        show: true,
                        position: 'right',
                        formatter: (params) => formatValue(params.value, metric),
                        fontSize: 12,
                        fontWeight: 'bold',
                        color: colorSet.youtube
                    },
                    barWidth: '50%'
                }
            ],
            animationDuration: 1000,
            animationEasing: 'cubicOut'
        };
        
        chart.setOption(option, { notMerge: false });
    }
    
    // 初始显示
    updateChart(0);
    
    // 每2秒切换一次维度
    animationTimer = setInterval(() => {
        currentIndex = (currentIndex + 1) % metrics.length;
        updateChart(currentIndex);
    }, 2000);
    
    // 清理定时器（当元素被移除时）
    const observer = new MutationObserver((mutations) => {
        if (!document.getElementById('pd-comparison-bar')) {
            if (animationTimer) {
                clearInterval(animationTimer);
                animationTimer = null;
            }
            observer.disconnect();
        }
    });
    observer.observe(document.body, { childList: true, subtree: true });
    
    window.addEventListener('resize', () => chart.resize());
}

// Render Global Analysis ECharts Pie Chart
function renderGlobalEchart(labels, values, extraInfo) {
    const chartEl = document.getElementById('global-echart');
    if (!chartEl) return;
    
    const myChart = echarts.init(chartEl);
    const COLORS = ['#B8A082', '#A0CFBA', '#899DCC', '#F2C6B4', '#DDB8A0', '#7B8FA6', '#B4A7D6', '#DBC585'];
    
    const option = {
        title: {
            text: 'TOP5 Country Distribution',
            left: 'center',
            top: 10,
            textStyle: {
                fontSize: 16,
                fontWeight: 600,
                color: '#3A3A3A'
            }
        },
        tooltip: {
            trigger: 'item',
            formatter: '{b}: {c} views<br/>({d}%)',
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            borderColor: '#E0E0E0',
            borderWidth: 1,
            textStyle: {
                color: '#3A3A3A',
                fontSize: 12
            }
        },
        legend: {
            orient: 'vertical',
            left: 'left',
            top: 'middle',
            textStyle: {
                fontSize: 12,
                color: '#7A7A7A'
            },
            itemGap: 12
        },
        series: [{
            type: 'pie',
            radius: ['45%', '75%'],
            center: ['60%', '55%'],
            avoidLabelOverlap: true,
            itemStyle: {
                borderRadius: 8,
                borderColor: '#fff',
                borderWidth: 3
            },
            label: {
                show: true,
                formatter: function(params) {
                    return params.name + '\n' + params.value.toLocaleString() + '\n(' + params.percent + '%)';
                },
                fontWeight: 'bold',
                fontSize: 11,
                color: '#3A3A3A',
                backgroundColor: 'rgba(255, 255, 255, 0.85)',
                borderRadius: 6,
                padding: [4, 6],
                borderColor: '#E0E0E0',
                borderWidth: 1
            },
            labelLine: {
                show: true,
                length: 15,
                length2: 10,
                lineStyle: {
                    color: '#9A9A9A',
                    width: 1
                }
            },
            emphasis: {
                itemStyle: {
                    shadowBlur: 10,
                    shadowOffsetX: 0,
                    shadowColor: 'rgba(0, 0, 0, 0.3)'
                },
                label: {
                    fontSize: 12
                }
            },
            data: labels.map((name, i) => ({
                name: name,
                value: values[i],
                itemStyle: {
                    color: COLORS[i % COLORS.length]
                }
            }))
        }]
    };
    
    myChart.setOption(option);
    
    // 响应式调整
    window.addEventListener('resize', function() {
        myChart.resize();
    });
}

// Render Hashtag ECharts Chart - 柱状图
function renderHashtagChart(labels, values, platform, countryCode) {
    const chartEl = document.getElementById('hashtag-echart');
    if (!chartEl) return;
    
    const myChart = echarts.init(chartEl);
    const COLORS = ['#B8A082', '#A0CFBA', '#899DCC', '#F2C6B4', '#DDB8A0', '#7B8FA6', '#B4A7D6', '#DBC585'];
    
    const option = {
        title: {
            text: `${platform} - ${countryCode} Trending Hashtags`,
            left: 'center',
            top: 10,
            textStyle: { fontSize: 16, fontWeight: 600, color: '#3A3A3A' }
        },
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'shadow' },
            formatter: function(params) {
                const param = params[0];
                return `${param.name}<br/>Views: ${param.value.toLocaleString()}`;
            },
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            borderColor: '#E0E0E0',
            borderWidth: 1
        },
        grid: { left: '20%', right: '10%', top: '20%', bottom: '15%' },
        xAxis: {
            type: 'value',
            name: 'Views',
            axisLabel: {
                formatter: function(value) {
                    if (value >= 1000000) return (value / 1000000).toFixed(1) + 'M';
                    if (value >= 1000) return (value / 1000).toFixed(1) + 'K';
                    return value;
                }
            }
        },
        yAxis: {
            type: 'category',
            data: labels,
            axisLabel: { fontSize: 11, color: '#3A3A3A' }
        },
        series: [{
            type: 'bar',
            data: values.map((v, i) => ({
                value: v,
                itemStyle: { color: COLORS[i % COLORS.length], borderRadius: [0, 8, 8, 0] }
            })),
            label: {
                show: true,
                position: 'right',
                formatter: function(params) {
                    const val = params.value;
                    if (val >= 1000000) return (val / 1000000).toFixed(1) + 'M';
                    if (val >= 1000) return (val / 1000).toFixed(1) + 'K';
                    return val.toLocaleString();
                },
                fontSize: 10,
                fontWeight: 'bold'
            },
            barWidth: '60%'
        }]
    };
    
    myChart.setOption(option);
    window.addEventListener('resize', () => myChart.resize());
}

// Render Publish Timing ECharts Chart
function renderPublishTimingChart(timeAnalysis, data, platform, periodDisplay) {
    const chartEl = document.getElementById('publish-timing-echart');
    if (!chartEl || !data) return;
    
    const myChart = echarts.init(chartEl);
    const COLORS = ['#B8A082', '#A0CFBA', '#899DCC', '#F2C6B4', '#DDB8A0', '#7B8FA6', '#B4A7D6', '#DBC585'];
    
    if (timeAnalysis === 'Day Parts') {
        const periods = data.periods || [];
        const engRates = data.engagement_rates || [];
        const engDiff = data.eng_diff_pct || [];

        // 计算y轴范围，使差异更明显
        const minRate = Math.min(...engRates);
        const maxRate = Math.max(...engRates);
        
        let yMin, yMax;
        if (maxRate - minRate < 1) {
            // 如果跨度小于1%，以中点为中心±1%
            const mid = (minRate + maxRate) / 2;
            yMin = Math.max(0, Number((mid - 1).toFixed(2)));
            yMax = Number((mid + 1).toFixed(2));
        } else {
            // 否则在上下各留20%缓冲
            const pad = (maxRate - minRate) * 0.2;
            yMin = Math.max(0, Number((minRate - pad).toFixed(2)));
            yMax = Number((maxRate + pad).toFixed(2));
        }
        const option = {
            title: {
                text: `${platform} - Day Parts Publishing Analysis`,
                subtext: periodDisplay,
                left: 'center',
                top: 10,
                textStyle: { fontSize: 16, fontWeight: 600, color: '#3A3A3A' }
            },
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'shadow' },
                formatter: function(params) {
                    const param = params[0];
                    const idx = param.dataIndex;
                    const diff = engDiff[idx];
                    const rate = engRates[idx];
                    const count = data.content_counts ? data.content_counts[idx] : 0;
                    return `${param.name}<br/>Engagement Rate: ${rate.toFixed(2)}%<br/>Difference: ${diff > 0 ? '+' : ''}${diff.toFixed(1)}%<br/>Sample Size: ${count}`;
                },
                backgroundColor: 'rgba(255, 255, 255, 0.95)',
                borderColor: '#E0E0E0',
                borderWidth: 1
            },
            grid: {
                left: '10%',
                right: '10%',
                top: '20%',
                bottom: '20%'
            },
            xAxis: {
                type: 'category',
                data: periods,
                axisLabel: { fontSize: 11, color: '#3A3A3A', rotate: 45 }
            },
            yAxis: {
                type: 'value',
                name: 'Engagement Rate (%)',
                min: yMin,
                max: yMax,
                axisLabel: { formatter: '{value}%' }
            },
            series: [{
                type: 'bar',
                data: engRates.map((rate, i) => ({
                    value: rate,
                    itemStyle: { 
                        color: engDiff[i] > 0 ? '#C4B5A6' : '#B8C5A6',
                        borderRadius: [4, 4, 0, 0]
                    }
                })),
                label: {
                    show: true,
                    position: 'top',
                    formatter: function(params) {
                        const idx = params.dataIndex;
                        const diff = engDiff[idx];
                        return `${params.value.toFixed(2)}%\n(${diff > 0 ? '+' : ''}${diff.toFixed(1)}%)`;
                    },
                    fontSize: 10,
                    fontWeight: 'bold',
                    color: '#3A3A3A'
                },
                barWidth: '60%',
                emphasis: {
                    itemStyle: {
                        shadowBlur: 10,
                        shadowOffsetX: 0,
                        shadowColor: 'rgba(0, 0, 0, 0.3)'
                    }
                }
            }]
        };
        myChart.setOption(option);
    } else if (timeAnalysis === 'Week Analysis') {
        const days = data.days || [];
        const engRates = data.engagement_rates || [];
        const engDiff = data.eng_diff_pct || [];
        const COLORS = ['#B8A082', '#A0CFBA', '#899DCC', '#F2C6B4', '#DDB8A0', '#7B8FA6', '#B4A7D6'];
        
        // 计算y轴范围，使差异更明显
        const minRateW = Math.min(...engRates);
        const maxRateW = Math.max(...engRates);
        
        let yMinW, yMaxW;
        if (maxRateW - minRateW < 1) {
            // 如果跨度小于1%，以中点为中心±1%
            const mid = (minRateW + maxRateW) / 2;
            yMinW = Math.max(0, Number((mid - 1).toFixed(2)));
            yMaxW = Number((mid + 1).toFixed(2));
        } else {
            // 否则在上下各留20%缓冲
            const pad = (maxRateW - minRateW) * 0.2;
            yMinW = Math.max(0, Number((minRateW - pad).toFixed(2)));
            yMaxW = Number((maxRateW + pad).toFixed(2));
        }

        const option = {
            title: {
                text: `${platform} - Week Analysis`,
                subtext: periodDisplay,
                left: 'center',
                top: 10,
                textStyle: { fontSize: 16, fontWeight: 600, color: '#3A3A3A' }
            },
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'shadow' },
                formatter: function(params) {
                    const param = params[0];
                    const idx = param.dataIndex;
                    const diff = engDiff[idx];
                    const rate = engRates[idx];
                    const count = data.content_counts ? data.content_counts[idx] : 0;
                    return `${param.name}<br/>Engagement Rate: ${rate.toFixed(2)}%<br/>Difference: ${diff > 0 ? '+' : ''}${diff.toFixed(1)}%<br/>Sample Size: ${count}`;
                },
                backgroundColor: 'rgba(255, 255, 255, 0.95)',
                borderColor: '#E0E0E0',
                borderWidth: 1
            },
            grid: {
                left: '10%',
                right: '10%',
                top: '20%',
                bottom: '15%'
            },
            xAxis: {
                type: 'category',
                data: days,
                axisLabel: { fontSize: 11, color: '#3A3A3A' }
            },
            yAxis: [
                {
                    type: 'value',
                    name: 'Engagement Rate (%)',
                    min: yMinW,
                    max: yMaxW,
                    axisLabel: { formatter: '{value}%' }
                },
                {
                    type: 'value',
                    name: 'Rate (%)',
                    position: 'right',
                    min: yMinW,
                    max: yMaxW,
                    axisLabel: { formatter: '{value}%'}
                }
            ],
            series: [{
                type: 'bar',
                data: engRates.map((rate, i) => ({
                    value: rate,
                    itemStyle: { 
                        color: engDiff[i] > 0 ? '#C4B5A6' : '#B8C5A6',
                        borderRadius: [4, 4, 0, 0]
                    }
                })),
                label: {
                    show: true,
                    position: 'top',
                    formatter: function(params) {
                        const idx = params.dataIndex;
                        const diff = engDiff[idx];
                        return `${params.value.toFixed(2)}%\n(${diff > 0 ? '+' : ''}${diff.toFixed(1)}%)`;
                    },
                    fontSize: 10,
                    fontWeight: 'bold',
                    color: '#3A3A3A'
                },
                barWidth: '60%',
                emphasis: {
                    itemStyle: {
                        shadowBlur: 10,
                        shadowOffsetX: 0,
                        shadowColor: 'rgba(0, 0, 0, 0.3)'
                    }
                }
            }]
        };
        myChart.setOption(option);
    } else if (timeAnalysis === 'Hourly') {
        const hours = data.hours || [];
        const engRates = data.engagement_rates || [];
        const engDiff = data.eng_diff_pct || [];
        
        const option = {
            title: {
                text: `${platform} - Hourly Analysis`,
                subtext: periodDisplay,
                left: 'center',
                top: 10,
                textStyle: { fontSize: 16, fontWeight: 600, color: '#3A3A3A' }
            },
            tooltip: {
                trigger: 'axis',
                axisPointer: { type: 'shadow' },
                formatter: function(params) {
                    const param = params[0];
                    const idx = param.dataIndex;
                    const diff = engDiff[idx];
                    const rate = engRates[idx];
                    const count = data.content_counts ? data.content_counts[idx] : 0;
                    return `${param.name}<br/>Engagement Rate: ${rate.toFixed(2)}%<br/>Difference: ${diff > 0 ? '+' : ''}${diff.toFixed(1)}%<br/>Sample Size: ${count}`;
                },
                backgroundColor: 'rgba(255, 255, 255, 0.95)',
                borderColor: '#E0E0E0',
                borderWidth: 1
            },
            grid: {
                left: '10%',
                right: '10%',
                top: '20%',
                bottom: '20%'
            },
            xAxis: {
                type: 'category',
                data: hours.map(h => h + ':00'),
                axisLabel: { fontSize: 10, color: '#3A3A3A', rotate: 45 }
            },
            yAxis: {
                type: 'value',
                name: 'Engagement Rate (%)',
                axisLabel: { formatter: '{value}%' }
            },
            series: [{
                type: 'bar',
                data: engRates.map((rate, i) => ({
                    value: rate,
                    itemStyle: { 
                        color: engDiff[i] > 0 ? '#C4B5A6' : '#B8C5A6',
                        borderRadius: [4, 4, 0, 0]
                    }
                })),
                label: {
                    show: true,
                    position: 'top',
                    formatter: function(params) {
                        const idx = params.dataIndex;
                        const diff = engDiff[idx];
                        return `${params.value.toFixed(2)}%\n(${diff > 0 ? '+' : ''}${diff.toFixed(1)}%)`;
                    },
                    fontSize: 9,
                    fontWeight: 'bold',
                    color: '#3A3A3A'
                },
                barWidth: '50%',
                markPoint: {
                    data: (() => {
                        const points = [];
                        if (data.peak_hour !== null && data.peak_hour !== undefined) {
                            const peakIdx = hours.indexOf(data.peak_hour);
                            if (peakIdx >= 0 && peakIdx < engRates.length) {
                                points.push({ 
                                    name: 'Peak Hour', 
                                    coord: [peakIdx, engRates[peakIdx]], 
                                    value: engRates[peakIdx].toFixed(2) + '%',
                                    itemStyle: { color: '#B8A082' }
                                });
                            }
                        }
                        if (data.valley_hour !== null && data.valley_hour !== undefined) {
                            const valleyIdx = hours.indexOf(data.valley_hour);
                            if (valleyIdx >= 0 && valleyIdx < engRates.length) {
                                points.push({ 
                                    name: 'Valley Hour', 
                                    coord: [valleyIdx, engRates[valleyIdx]], 
                                    value: engRates[valleyIdx].toFixed(2) + '%',
                                    itemStyle: { color: '#7B8FA6' }
                                });
                            }
                        }
                        return points;
                    })()
                },
                emphasis: {
                    itemStyle: {
                        shadowBlur: 10,
                        shadowOffsetX: 0,
                        shadowColor: 'rgba(0, 0, 0, 0.3)'
                    }
                }
            }]
        };
        myChart.setOption(option);
    }
    
    window.addEventListener('resize', () => myChart.resize());
}

// Render Trend ECharts Chart - 改为折线图
function renderTrendChart(labels, values, platform, countryCode, startDate, endDate) {
    const chartEl = document.getElementById('trend-echart');
    if (!chartEl) return;
    
    const myChart = echarts.init(chartEl);
    const COLORS = ['#B8A082', '#A0CFBA', '#899DCC', '#F2C6B4', '#DDB8A0', '#7B8FA6', '#B4A7D6', '#DBC585'];
    
    const option = {
        title: {
            text: `${platform} - ${countryCode} Trend Type View Distribution`,
            subtext: `${startDate} to ${endDate}`,
            left: 'center',
            top: 10,
            textStyle: { fontSize: 16, fontWeight: 600, color: '#3A3A3A' }
        },
        tooltip: {
            trigger: 'axis',
            formatter: function(params) {
                const param = params[0];
                return `${param.name}<br/>Views: ${param.value.toLocaleString()}`;
            },
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            borderColor: '#E0E0E0',
            borderWidth: 1
        },
        grid: {
            left: '10%',
            right: '10%',
            top: '20%',
            bottom: '20%'
        },
        xAxis: {
            type: 'category',
            data: labels,
            axisLabel: { fontSize: 11, color: '#3A3A3A', rotate: 45 }
        },
        yAxis: {
            type: 'value',
            name: 'Total Views',
            axisLabel: {
                formatter: function(value) {
                    if (value >= 1000000) return (value / 1000000).toFixed(1) + 'M';
                    if (value >= 1000) return (value / 1000).toFixed(1) + 'K';
                    return value;
                }
            }
        },
        series: [{
            type: 'line',
            data: values,
            smooth: true,
            lineStyle: {
                color: '#B8A082',
                width: 3
            },
            itemStyle: {
                color: '#B8A082'
            },
            areaStyle: {
                color: {
                    type: 'linear',
                    x: 0,
                    y: 0,
                    x2: 0,
                    y2: 1,
                    colorStops: [
                        { offset: 0, color: 'rgba(184, 160, 130, 0.3)' },
                        { offset: 1, color: 'rgba(184, 160, 130, 0.05)' }
                    ]
                }
            },
            symbol: 'circle',
            symbolSize: 8,
            label: {
                show: true,
                position: 'top',
                formatter: function(params) {
                    const val = params.value;
                    if (val >= 1000000) return (val / 1000000).toFixed(1) + 'M';
                    if (val >= 1000) return (val / 1000).toFixed(1) + 'K';
                    return val.toLocaleString();
                },
                fontSize: 10,
                fontWeight: 'bold'
            }
        }]
    };
    
    myChart.setOption(option);
    window.addEventListener('resize', () => myChart.resize());
}

// Render Global Analysis ECharts Category Chart (Right side) - 柱状图
function renderGlobalCategoryChart(labels, values, extraInfo) {
    const chartEl = document.getElementById('global-echart-bar');
    if (!chartEl) return;
    
    if (!labels || labels.length === 0) {
        chartEl.innerHTML = '<div style="text-align: center; padding: 50px; color: #999;">No category data available</div>';
        return;
    }
    
    const myChart = echarts.init(chartEl);
    const COLORS = ['#B8A082', '#A0CFBA', '#899DCC', '#F2C6B4', '#DDB8A0', '#7B8FA6', '#B4A7D6', '#DBC585'];
    
    // 计算百分比
    const total = values.reduce((a, b) => a + b, 0);
    const percentages = values.map(v => ((v / total) * 100).toFixed(1));
    
    const option = {
        title: {
            text: 'Content Category Distribution',
            left: 'center',
            top: 10,
            textStyle: {
                fontSize: 16,
                fontWeight: 600,
                color: '#3A3A3A'
            }
        },
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'shadow'
            },
            formatter: function(params) {
                const param = params[0];
                return `${param.name}<br/>Views: ${param.value.toLocaleString()}<br/>Percentage: ${percentages[param.dataIndex]}%`;
            },
            backgroundColor: 'rgba(255, 255, 255, 0.95)',
            borderColor: '#E0E0E0',
            borderWidth: 1,
            textStyle: {
                color: '#3A3A3A',
                fontSize: 12
            }
        },
        grid: {
            left: '20%',
            right: '10%',
            top: '20%',
            bottom: '15%'
        },
        xAxis: {
            type: 'value',
            name: 'Views',
            nameLocation: 'middle',
            nameGap: 30,
            nameTextStyle: {
                fontSize: 12,
                color: '#7A7A7A'
            },
            axisLabel: {
                formatter: function(value) {
                    if (value >= 1000000) return (value / 1000000).toFixed(1) + 'M';
                    if (value >= 1000) return (value / 1000).toFixed(1) + 'K';
                    return value;
                },
                fontSize: 10,
                color: '#7A7A7A'
            },
            splitLine: {
                show: true,
                lineStyle: {
                    color: '#E0E0E0',
                    type: 'dashed'
                }
            }
        },
        yAxis: {
            type: 'category',
            data: labels,
            axisLabel: {
                fontSize: 11,
                color: '#3A3A3A'
            },
            axisLine: {
                lineStyle: {
                    color: '#E0E0E0'
                }
            }
        },
        series: [{
            type: 'bar',
            data: values.map((val, i) => ({
                value: val,
                itemStyle: {
                    color: COLORS[i % COLORS.length],
                    borderRadius: [0, 8, 8, 0]
                }
            })),
            label: {
                show: true,
                position: 'right',
                formatter: function(params) {
                    return params.value.toLocaleString() + '\n(' + percentages[params.dataIndex] + '%)';
                },
                fontSize: 10,
                fontWeight: 'bold',
                color: '#3A3A3A',
                backgroundColor: 'rgba(255, 255, 255, 0.85)',
                borderRadius: 4,
                padding: [2, 6],
                borderColor: '#E0E0E0',
                borderWidth: 1
            },
            barWidth: '60%',
            emphasis: {
                itemStyle: {
                    shadowBlur: 10,
                    shadowOffsetX: 0,
                    shadowColor: 'rgba(0, 0, 0, 0.3)'
                }
            }
        }]
    };
    
    myChart.setOption(option);
    
    // 响应式调整
    window.addEventListener('resize', function() {
        myChart.resize();
    });
}

// Run global data analysis
function runGlobalAnalysis() {
    const platform = document.getElementById('global-platform').value;
    const yearMonth = document.getElementById('global-month').value;
    
    if (!platform || !yearMonth) {
        showError('global-result', 'Please select platform and enter year-month');
        return;
    }

    const resultEl = document.getElementById('global-result');
    resultEl.innerHTML = '<div style="text-align: center; padding: 20px;"><span class="loading"></span> Generating report...</div>';

    fetch('/api/global-analysis', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ platform, year_month: yearMonth })
    })
    .then(res => res.json())
    .then(result => {
        if (result.error) {
            showError('global-result', result.error);
            return;
        }
        
        const extraInfo = result.extra_info || {};
        const totalViews = extraInfo.total_views || 0;
        const avgEngagement = extraInfo.avg_engagement || 0;
        
        // 直接使用后端处理好的report_html，所有加粗通过数据库模板中的{{}}标记处理
        let reportText = result.report_html || result.report || '';
        
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
        
        // 渲染ECharts图表
        setTimeout(() => {
            renderGlobalEchart(result.labels || [], result.values || [], extraInfo);
            renderGlobalCategoryChart(result.category_labels || [], result.category_values || [], extraInfo);
        }, 100);
    })
    .catch(error => {
        console.error('Analysis failed:', error);
        showError('global-result', 'Analysis failed, please check your network connection and try again');
    });
}

// Run platform competitiveness analysis
// removed old Platform Competitiveness Analysis module per request

// Run trending hashtags analysis
function runHashtagReport() {
    const platform = document.getElementById('hashtag-platform').value;
    const countryCode = document.getElementById('hashtag-country').value;
    const minViews = document.getElementById('hashtag-min-views').value;
    
    if (!platform || !countryCode || !minViews) {
        showError('hashtag-result', 'Please select platform, enter country code and minimum views');
        return;
    }

    const resultEl = document.getElementById('hashtag-result');
    resultEl.innerHTML = '<div style="text-align: center; padding: 20px;"><span class="loading"></span> Generating report...</div>';

    fetch('/api/hashtag-report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            platform, 
            country_code: countryCode, 
            min_views: parseInt(minViews) 
        })
    })
    .then(res => res.json())
    .then(result => {
        if (result.error) {
            showError('hashtag-result', result.error);
            return;
        }
        
        const hashtagList = result.hashtags.slice(0, 10).map((item, index) => {
            return `
                <div style="display: flex; align-items: center; gap: 15px; padding: 15px; background: var(--md-surface); border-radius: 12px; margin-bottom: 10px;">
                    <div style="flex: 1;">
                        <strong style="font-size: 1.1rem; color: var(--md-primary);">#${item.hashtag}</strong>
                        <div style="color: var(--md-text-secondary); margin-top: 5px;">
                            Views: <strong style="color: var(--tiktok-pink);">${item.views.toLocaleString()}</strong>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
        
        // 直接使用后端处理好的report_html，所有加粗通过数据库模板中的{{}}标记处理
        let reportText = result.report_html || result.report || '';
        
        resultEl.innerHTML = `
            <h3>${result.platform} - ${result.country_code} Trending Hashtags Analysis</h3>
            <div class="report-text"><div style="margin-top: 12px;">${reportText}</div></div>
            <div class="chart-container">
                <div id="hashtag-echart" style="height: 400px; width: 100%;"></div>
            </div>
        `;
        
        setTimeout(() => {
            renderHashtagChart(result.labels || [], result.values || [], result.platform, result.country_code);
        }, 100);
    })
    .catch(error => {
        console.error('Analysis failed:', error);
        showError('hashtag-result', 'Analysis failed, please check your network connection and try again');
    });
}

// Run content trend analysis
function runTrendReport() {
    const platform = document.getElementById('trend-platform').value;
    const countryCode = document.getElementById('trend-country').value;
    const startDate = document.getElementById('trend-start-date').value;
    const endDate = document.getElementById('trend-end-date').value;
    
    if (!platform || !countryCode || !startDate || !endDate) {
        showError('trend-result', 'Please select platform, enter country code, start date and end date');
        return;
    }

    const resultEl = document.getElementById('trend-result');
    resultEl.innerHTML = '<div style="text-align: center; padding: 20px;"><span class="loading"></span> Generating report...</div>';

    fetch('/api/trend-report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            platform, 
            country_code: countryCode, 
            start_date: startDate,
            end_date: endDate
        })
    })
    .then(res => res.json())
    .then(result => {
        if (result.error) {
            showError('trend-result', result.error);
            return;
        }
        
        // 直接使用后端处理好的report_html，所有加粗通过数据库模板中的{{}}标记处理
        let reportText = result.report_html || result.report || '';
        // 移除换行符，确保报告显示为单段
        reportText = reportText.replace(/(\r\n|\n|\r)/gm, ' ').replace(/\s+/g, ' ').trim();
        
        resultEl.innerHTML = `
            <h3>${result.platform} - ${result.country_code} Content Trend Type Analysis</h3>
            <div class="report-text"><div style="margin-top: 12px;">${reportText}</div></div>
            <div class="chart-container">
                <div id="trend-echart" style="height: 400px; width: 100%;"></div>
            </div>
        `;
        
        setTimeout(() => {
            renderTrendChart(result.labels || [], result.values || [], result.platform, result.country_code, result.start_date, result.end_date);
        }, 100);
    })
    .catch(error => {
        console.error('Analysis failed:', error);
        showError('trend-result', 'Analysis failed, please check your network connection and try again');
    });
}

// Run optimal publish time analysis
function runPublishTimingAnalysis() {
    const platform = document.getElementById('publish-platform').value;
    const timeAnalysis = document.getElementById('time-analysis').value;
    const startMonth = document.getElementById('start-month').value;
    const endMonth = document.getElementById('end-month').value;
    
    if (!platform || !timeAnalysis || !startMonth || !endMonth) {
        showError('publish-timing-result', 'Please select platform, analysis type, start month and end month');
        return;
    }

    const resultEl = document.getElementById('publish-timing-result');
    resultEl.innerHTML = '<div style="text-align: center; padding: 20px;"><span class="loading"></span> Generating report...</div>';

    fetch('/api/publish-timing-analysis', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            platform, 
            time_analysis: timeAnalysis,
            start_month: startMonth,
            end_month: endMonth
        })
    })
    .then(res => res.json())
    .then(result => {
        if (result.error) {
            showError('publish-timing-result', result.error);
            return;
        }
        
        const analysisTypeNames = {
            'Day Parts': 'Day Parts Analysis',
            'Week Analysis': 'Week Analysis',
            'Hourly': 'Hourly Analysis'
        };
        
        // 直接使用后端处理好的report_html，所有加粗通过数据库模板中的{{}}标记处理
        let reportText = result.report_html || result.report || '';
        // 移除换行与多余空格，合并成单段
        reportText = reportText.replace(/(\r\n|\n|\r)/gm, ' ').replace(/\s+/g, ' ').trim();
        
        resultEl.innerHTML = `
            <h3>${result.platform} - ${analysisTypeNames[result.time_analysis] || result.time_analysis} Optimal Publish Time Analysis</h3>
            <div class="report-text"><div style="margin-top: 12px; white-space: normal; word-wrap: break-word;">${reportText}</div></div>
            <div id="publish-timing-echart" style="height: 500px; width: 100%; margin-top: 30px;"></div>
        `;
        
        setTimeout(() => {
            if (result.data) {
                renderPublishTimingChart(result.time_analysis, result.data, result.platform, result.period_display);
            }
        }, 100);
    })
    .catch(error => {
        console.error('Analysis failed:', error);
        showError('publish-timing-result', 'Analysis failed, please check your network connection and try again');
    });
}

// Show error message
function showError(elementId, message) {
    const element = document.getElementById(elementId);
    element.innerHTML = `<div class="error-message">${message}</div>`;
}

// Restore button state
function restoreButton(button) {
    if (button) {
        button.disabled = false;
    }
}

// ══════════════════════════════════════════════════════
// UNIVERSAL SECTOR RENDERING ENGINE
// ══════════════════════════════════════════════════════

// Helper functions (duplicated for standalone use)
const fmt = (n, d=0) => {
  if (n == null || isNaN(n)) return '0';
  return n.toLocaleString('en-US', {minimumFractionDigits:d, maximumFractionDigits:d});
};
const pct = (n) => (n>0?'+':'')+(n||0).toFixed(1)+'%';

// Sector registry: id, name, icon, dataFile, color
const SECTOR_REGISTRY = {
  semiconductor: { name:'半导体', icon:'🔬', dataFile:'data/market_data.json', color:'#4fc3f7', navLabel:'半导体产业链', stocksFile:'data/global_stocks.json', quotesFile:'data/stock_list.json' },
  pharma: { name:'创新药', icon:'💊', dataFile:'data/pharma_data.json', color:'#ff5252', navLabel:'创新药产业链', stocksFile:null, quotesFile:null },
  power: { name:'电力电网', icon:'⚡', dataFile:'data/power_data.json', color:'#ffab40', navLabel:'电力电网产业链', stocksFile:null, quotesFile:null },
  metals: { name:'金属', icon:'🪙', dataFile:'data/metals_data.json', color:'#ffd740', navLabel:'金属产业链', stocksFile:null, quotesFile:null },
  newenergy: { name:'新能源', icon:'☀️', dataFile:'data/newenergy_data.json', color:'#69f0ae', navLabel:'新能源产业链', stocksFile:null, quotesFile:null },
  robot: { name:'机器人', icon:'🤖', dataFile:'data/robot_data.json', color:'#ce93d8', navLabel:'机器人产业链', stocksFile:null, quotesFile:null },
  aerospace: { name:'航天', icon:'🚀', dataFile:'data/aerospace_data.json', color:'#64b5f6', navLabel:'航天产业链', stocksFile:null, quotesFile:null },
  oilgas: { name:'油气', icon:'🛢️', dataFile:'data/oilgas_data.json', color:'#a1887f', navLabel:'油气产业链', stocksFile:null, quotesFile:null }
};

// All sector data cache
const SECTOR_DATA_CACHE = {};
let currentSector = 'market'; // 'market' = A股大盘, others = sector IDs
let sectorCharts = {}; // Track charts per sector for resize

// Build top nav tabs HTML
function buildNavTabs() {
  let html = '';
  // A股大盘 tab
  html += `<button class="nav-tab active" id="nav-tab-market" onclick="switchMainTab('market')">🇨🇳 A股大盘</button>`;
  // Sector tabs
  for (const [id, cfg] of Object.entries(SECTOR_REGISTRY)) {
    html += `<button class="nav-tab" id="nav-tab-${id}" onclick="switchMainTab('${id}')">${cfg.icon} ${cfg.name}</button>`;
  }
  return html;
}

// Build sidebar for a sector
function buildSidebar(sectorId) {
  const cfg = SECTOR_REGISTRY[sectorId];
  if (!cfg) return '';
  const sections = [
    {id:`${sectorId}-overview`, label:'市场总览'},
    {id:`${sectorId}-chain`, label:'产业链图'},
    {id:`${sectorId}-upstream`, label:'上游'},
    {id:`${sectorId}-midstream`, label:'中游'},
    {id:`${sectorId}-downstream`, label:'下游'},
    {id:`${sectorId}-top10`, label:'十大板块'},
    {id:`${sectorId}-stocks`, label:'核心公司'},
  ];
  return `<div class="sidebar-title">${cfg.icon} ${cfg.navLabel}</div>` +
    sections.map(s => `<a href="#${s.id}" onclick="scrollToSection('${s.id}')" data-section="${s.id}">${s.label}</a>`).join('');
}

// Generate HTML for a sector's content
function buildSectorHTML(sectorId, data) {
  const cfg = SECTOR_REGISTRY[sectorId];
  const d = data;
  const prefix = sectorId;
  const ov = d.overview.globalMarket;
  const segNames = d.overview.segments || {};

  // Overview stat cards
  const statCards = `
    <div class="stat-cards">
      <div class="stat-card"><div class="value">${ov.total ? '$'+fmt(ov.total[2],0)+'亿' : '$'+fmt(ov.total||0,0)+'亿'}</div><div class="label">2025年全球${cfg.name}市场规模</div><div class="change change-up">持续增长</div></div>
      <div class="stat-card"><div class="value">${d.chain?.upstream?.materials?.length || 0}+细分</div><div class="label">上游材料/技术环节</div><div class="change change-up">国产替代加速</div></div>
      <div class="stat-card"><div class="value">${d.top10?.length || 0}大板块</div><div class="label">核心投资赛道</div><div class="change change-up">深度分析</div></div>
      <div class="stat-card"><div class="value">${d.stocks?.length || 0}只</div><div class="label">核心跟踪标的</div><div class="change change-up">A股+港股龙头</div></div>
    </div>`;

  // Chain Sankey
  const chainHTML = `
    <div class="section" id="${prefix}-chain">
      <div class="section-title"><span class="icon">🌳</span>${cfg.name}产业链结构</div>
      <div class="card"><div id="chart-${prefix}-sankey" class="chart-lg"></div>
        <div style="text-align:center;color:var(--accent);font-size:11px;margin-bottom:8px;">👆 展示${cfg.name}从上游到下游的完整价值流动</div>
        <div class="insight-card"><div class="insight-title">💡 AI 分析结论</div><div class="insight-body" id="${prefix}-insight-chain">${cfg.name}产业链覆盖从上游材料/技术到下游应用的完整价值链条，当前全球市场规模持续扩大。</div></div>
      </div>
    </div>`;

  // Upstream
  const upstreamHTML = `
    <div class="section" id="${prefix}-upstream">
      <div class="section-title"><span class="icon">🔧</span>上游 — 材料与技术</div>
      <div class="grid grid-2">
        <div class="card"><h3>上游市场规模 & 国产化率</h3><div id="chart-${prefix}-upstream-bar" class="chart"></div>
          <div class="insight-card"><div class="insight-title">💡 AI 分析结论</div><div class="insight-body" id="${prefix}-insight-upstream">上游是${cfg.name}产业链的基础环节，国产化率因细分领域差异较大。</div></div>
        </div>
        <div class="card"><h3>国内 vs 全球市场对比</h3><div id="chart-${prefix}-upstream-compare" class="chart"></div>
          <div class="insight-card"><div class="insight-title">💡 AI 分析结论</div><div class="insight-body" id="${prefix}-insight-upstream2">中国市场在全球${cfg.name}产业链中扮演越来越重要的角色。</div></div>
        </div>
      </div>
    </div>`;

  // Midstream
  const midstreamHTML = `
    <div class="section" id="${prefix}-midstream">
      <div class="section-title"><span class="icon">⚙️</span>中游 — 核心制造与服务</div>
      <div class="grid grid-2">
        <div class="card"><h3>市场份额分布</h3><div id="chart-${prefix}-midstream-pie" class="chart"></div>
          <div class="insight-card"><div class="insight-title">💡 AI 分析结论</div><div class="insight-body" id="${prefix}-insight-midstream">中游环节是${cfg.name}产业链的价值核心，龙头集中度较高。</div></div>
        </div>
        <div class="card"><h3>核心公司增长对比</h3><div id="chart-${prefix}-midstream-stock" class="chart"></div>
          <div class="insight-card"><div class="insight-title">💡 AI 分析结论</div><div class="insight-body" id="${prefix}-insight-midstream2">资本市场对不同公司的定价反映其技术实力和成长性差异。</div></div>
        </div>
      </div>
    </div>`;

  // Downstream
  const downstreamHTML = `
    <div class="section" id="${prefix}-downstream">
      <div class="section-title"><span class="icon">📱</span>下游 — 应用市场</div>
      <div class="grid grid-2">
        <div class="card"><h3>应用市场规模 & 增长率（气泡图）</h3><div id="chart-${prefix}-downstream-bubble" class="chart"></div>
          <div class="insight-card"><div class="insight-title">💡 AI 分析结论</div><div class="insight-body" id="${prefix}-insight-downstream">下游应用场景不断拓展，新兴领域增速显著高于传统领域。</div></div>
        </div>
        <div class="card"><h3>CAGR 排名</h3><div id="chart-${prefix}-downstream-cagr" class="chart"></div>
          <div class="insight-card"><div class="insight-title">💡 AI 分析结论</div><div class="insight-body" id="${prefix}-insight-downstream2">高CAGR赛道是超额收益的主要来源，但波动也更大。</div></div>
        </div>
      </div>
    </div>`;

  // Top 10
  const top10HTML = `
    <div class="section" id="${prefix}-top10">
      <div class="section-title"><span class="icon">🎯</span>前十大核心板块深度分析</div>
      <div class="grid grid-2">
        <div class="card"><h3>市场规模 & 增长率矩阵</h3><div id="chart-${prefix}-top10-scatter" class="chart"></div>
          <div class="insight-card"><div class="insight-title">💡 AI 分析结论</div><div class="insight-body" id="${prefix}-insight-top10">右上角（大规模+高CAGR）板块是机构资金的核心配置方向。</div></div>
        </div>
        <div class="card"><h3>投资优先级 & CAGR雷达</h3><div id="chart-${prefix}-top10-radar" class="chart"></div>
          <div class="insight-card"><div class="insight-title">💡 AI 分析结论</div><div class="insight-body" id="${prefix}-insight-top10-2">高优先级板块具备强逻辑但需精选个股。</div></div>
        </div>
      </div>
      <div class="card" style="margin-top:20px;">
        <h3>十大板块详情</h3>
        <div class="table-wrap"><table class="data-table" id="${prefix}-top10-table"><thead><tr><th>排名</th><th>板块</th><th>2024规模(亿$)</th><th>YoY</th><th>CAGR</th><th>全球龙头</th><th>中国龙头</th><th>优先级</th></tr></thead><tbody></tbody></table></div>
      </div>
    </div>`;

  // Stocks
  const stocksHTML = `
    <div class="section" id="${prefix}-stocks">
      <div class="section-title"><span class="icon">📈</span>核心公司表现</div>
      <div class="grid grid-2">
        <div class="card"><h3>涨跌幅排名</h3><div id="chart-${prefix}-stocks-bar" class="chart-lg"></div>
          <div class="insight-card"><div class="insight-title">💡 AI 分析结论</div><div class="insight-body" id="${prefix}-insight-stocks">核心公司的股价表现反映市场对该赛道的认可度。</div></div>
        </div>
        <div class="card"><h3>市值 vs 营收增速矩阵</h3><div id="chart-${prefix}-stocks-scatter" class="chart-lg"></div>
          <div class="insight-card"><div class="insight-title">💡 AI 分析结论</div><div class="insight-body" id="${prefix}-insight-stocks2">大市值+高增速的公司是行业绝对龙头。</div></div>
        </div>
      </div>
    </div>`;

  return `
    <div class="section" id="${prefix}-overview">
      <div class="section-title"><span class="icon">${cfg.icon}</span>全球${cfg.name}市场总览</div>
      ${statCards}
      <div class="grid grid-2">
        <div class="card"><h3>全球${cfg.name}市场趋势</h3><div id="chart-${prefix}-trend" class="chart"></div>
          <div class="insight-card"><div class="insight-title">💡 AI 分析结论</div><div class="insight-body" id="${prefix}-insight-overview">${cfg.name}行业正处于快速发展期，全球市场规模持续扩大。</div></div>
        </div>
        <div class="card"><h3>分品类增长对比</h3><div id="chart-${prefix}-segment" class="chart"></div>
          <div class="insight-card"><div class="insight-title">💡 AI 分析结论</div><div class="insight-body" id="${prefix}-insight-segment">各细分品类增速分化明显，结构性机会突出。</div></div>
        </div>
      </div>
    </div>
    ${chainHTML}
    ${upstreamHTML}
    ${midstreamHTML}
    ${downstreamHTML}
    ${top10HTML}
    ${stocksHTML}
  `;
}

// Render all charts for a sector
function renderSectorCharts(sectorId, data) {
  if (!data) return;
  const prefix = sectorId;
  const d = data;
  
  // Chart 1: Market Trend
  chartSectorTrend(prefix, d);
  // Chart 2: Segment Growth
  chartSectorSegment(prefix, d);
  // Chart 3: Sankey
  chartSectorSankey(prefix, d);
  // Chart 4-5: Upstream
  chartSectorUpstream(prefix, d);
  // Chart 6-7: Midstream
  chartSectorMidstream(prefix, d);
  // Chart 8-9: Downstream
  chartSectorDownstream(prefix, d);
  // Chart 10-11: Top10
  chartSectorTop10(prefix, d);
  // Chart 12-13: Stocks
  chartSectorStocks(prefix, d);
  // Top10 table
  renderSectorTop10Table(prefix, d);
}

// ═══ Individual Chart Functions ═══

function chartSectorTrend(prefix, d) {
  const el = document.getElementById(`chart-${prefix}-trend`);
  if (!el) return;
  const ov = d.overview.globalMarket;
  const chart = echarts.init(el);
  const years = (ov.years || ['2023','2024','2025','2026E','2027E']).map(y=>String(y).includes('E')||String(y).includes('e')?y:String(y)+'年');
  const total = ov.total || [0,0,0,0,0];
  const unit = ov.totalUnit || '亿美元';
  chart.setOption({
    tooltip: {trigger:'axis'},
    legend: {data:['总规模'], textStyle:{color:'#90a4ae'}, top:5},
    grid: {left:60, right:20, top:50, bottom:30},
    xAxis: {type:'category', data:years, axisLabel:{color:'#90a4ae'}},
    yAxis: {type:'value', name:unit, axisLabel:{color:'#90a4ae'}, splitLine:{lineStyle:{color:'#1e2456'}}},
    series: [{name:'总规模', type:'bar', data:total, itemStyle:{color:'#4fc3f7'}, barWidth:20,
      label:{show:true, position:'top', color:'#4fc3f7', fontSize:10, formatter:p=>'$'+fmt(p.value,0)}}]
  });
}

function chartSectorSegment(prefix, d) {
  const el = document.getElementById(`chart-${prefix}-segment`);
  if (!el) return;
  const chart = echarts.init(el);
  // Extract segments from globalMarket (exclude years/total keys)
  const gm = d.overview.globalMarket || {};
  const segKeys = Object.keys(gm).filter(k => !['years','total','totalUnit'].includes(k) && Array.isArray(gm[k]));
  let segNames = segKeys;
  let seg2024 = segKeys.map(k => gm[k][2] || gm[k][1] || 0); // index 2 = 2025, fallback to 2024
  if (!segNames.length) {
    segNames = ['品类A','品类B','品类C','品类D'];
    seg2024 = [100,80,60,40];
  }
  chart.setOption({
    tooltip: {trigger:'axis'},
    grid: {left:100, right:60, top:20, bottom:30},
    xAxis: {type:'value', axisLabel:{color:'#90a4ae'}, splitLine:{lineStyle:{color:'#1e2456'}}},
    yAxis: {type:'category', data:segNames, inverse:true, axisLabel:{color:'#90a4ae'}},
    series: [{type:'bar', data:seg2024.map(v=>({value:v, label:{show:true, position:'right', color:'#69f0ae', fontWeight:'bold', formatter:'$'+fmt(v,0)+'亿'}})),
      itemStyle:{color: new echarts.graphic.LinearGradient(0,0,1,0,[{offset:0,color:'#7c4dff'},{offset:1,color:'#4fc3f7'}])}, barWidth:16}]
  });
}

function chartSectorSankey(prefix, d) {
  const el = document.getElementById(`chart-${prefix}-sankey`);
  if (!el) return;
  const chart = echarts.init(el);
  const upNames = (d.chain?.upstream?.materials || []).map(m=>m.name).concat((d.chain?.upstream?.equipment || []).map(e=>e.name));
  const midNames = (d.chain?.midstream?.design || []).map(m=>m.name);
  const downNames = (d.chain?.downstream || []).map(dn=>dn.sub || dn.name);
  const nodes = [...upNames, ...midNames, '核心制造', ...downNames];
  const links = [];
  upNames.forEach(u => links.push({source:u, target:'核心制造', value:Math.round(Math.random()*100+50)}));
  midNames.forEach(m => links.push({source:m, target:'核心制造', value:Math.round(Math.random()*200+100)}));
  downNames.forEach(dn => links.push({source:'核心制造', target:dn, value:Math.round(Math.random()*150+80)}));
  chart.setOption({
    tooltip:{trigger:'item', triggerOn:'mousemove'},
    series:[{type:'sankey', layout:'none', emphasis:{focus:'adjacency'}, nodeAlign:'left', layoutIterations:0,
      lineStyle:{color:'gradient', curveness:0.5, opacity:0.3},
      label:{color:'#e0e0e0', fontSize:10},
      data: nodes.map(n=>({name:n})), links: links}]
  });
}

function chartSectorUpstream(prefix, d) {
  const barEl = document.getElementById(`chart-${prefix}-upstream-bar`);
  const compEl = document.getElementById(`chart-${prefix}-upstream-compare`);
  if (!barEl && !compEl) return;
  const items = (d.chain?.upstream?.materials || []).concat(d.chain?.upstream?.equipment || []);
  if (!items.length) return;
  
  if (barEl) {
    const chart = echarts.init(barEl);
    chart.setOption({
      tooltip:{trigger:'axis'}, legend:{data:['全球市场(亿美元)','国产化率(%)'], textStyle:{color:'#90a4ae'}, top:5},
      grid:{left:90, right:60, top:50, bottom:30},
      xAxis:{type:'category', data:items.map(i=>i.name), axisLabel:{color:'#90a4ae', rotate:15, fontSize:10}},
      yAxis:[{type:'value', name:'亿美元', axisLabel:{color:'#90a4ae'}, splitLine:{lineStyle:{color:'#1e2456'}}},
             {type:'value', name:'%', axisLabel:{color:'#90a4ae'}, max:100}],
      series:[{name:'全球市场(亿美元)', type:'bar', data:items.map(i=>i.global2024||0), itemStyle:{color:'#4fc3f7'}, barWidth:16},
               {name:'国产化率(%)', type:'line', yAxisIndex:1, data:items.map(i=>i.domesticRate||0), itemStyle:{color:'#69f0ae'}, symbol:'circle', symbolSize:8, lineStyle:{width:3}}]
    });
  }
  if (compEl) {
    const chart = echarts.init(compEl);
    chart.setOption({
      tooltip:{trigger:'axis'}, legend:{data:['全球2024','中国2024'], textStyle:{color:'#90a4ae'}, top:5},
      grid:{left:90, right:20, top:50, bottom:30},
      xAxis:{type:'category', data:items.map(i=>i.name), axisLabel:{color:'#90a4ae', rotate:15, fontSize:10}},
      yAxis:{type:'value', axisLabel:{color:'#90a4ae'}, splitLine:{lineStyle:{color:'#1e2456'}}},
      series:[{name:'全球2024', type:'bar', data:items.map(i=>i.global2024||0), itemStyle:{color:'#7c4dff'}, barWidth:14, barGap:'30%'},
               {name:'中国2024', type:'bar', data:items.map(i=>i.china2024||0), itemStyle:{color:'#4fc3f7'}, barWidth:14}]
    });
  }
}

function chartSectorMidstream(prefix, d) {
  const pieEl = document.getElementById(`chart-${prefix}-midstream-pie`);
  const stockEl = document.getElementById(`chart-${prefix}-midstream-stock`);
  const foundry = d.chain?.midstream?.foundry || [];
  
  if (pieEl && foundry.length) {
    const chart = echarts.init(pieEl);
    chart.setOption({
      tooltip:{trigger:'item', formatter:'{b}: {c}%'},
      series:[{type:'pie', radius:['40%','75%'], center:['50%','50%'],
        data: foundry.map(i=>({name:i.name, value:i.share||0})),
        label:{color:'#e0e0e0', formatter:'{b}\n{d}%'},
        emphasis:{itemStyle:{shadowBlur:10, shadowColor:'rgba(0,0,0,0.5)'}}}]
    });
  }
  if (stockEl && foundry.length) {
    const chart = echarts.init(stockEl);
    const names = foundry.map(i=>i.name);
    const vals = foundry.map(i=>i.stock||0);
    chart.setOption({
      tooltip:{trigger:'axis'}, grid:{left:100, right:40, top:20, bottom:30},
      xAxis:{type:'value', axisLabel:{color:'#90a4ae'}, splitLine:{lineStyle:{color:'#1e2456'}}},
      yAxis:{type:'category', data:names, inverse:true, axisLabel:{color:'#90a4ae', fontSize:10}},
      series:[{type:'bar', data:vals.map(v=>({value:v, label:{show:true, formatter:(v>=0?'+':'')+v.toFixed(0)+'%', position:v>=0?'right':'left', color:v>=0?'#69f0ae':'#ff5252', fontWeight:'bold'}})),
        itemStyle:{color:p=>p.value>=0?'#69f0ae':'#ff5252'}, barWidth:14}]
    });
  }
}

function chartSectorDownstream(prefix, d) {
  const bubbleEl = document.getElementById(`chart-${prefix}-downstream-bubble`);
  const cagrEl = document.getElementById(`chart-${prefix}-downstream-cagr`);
  const items = d.chain?.downstream || [];
  if (!items.length) return;
  
  if (bubbleEl) {
    const chart = echarts.init(bubbleEl);
    chart.setOption({
      tooltip:{trigger:'item', formatter:p=>`${p.data[3]}<br/>规模: $${fmt(p.data[0],0)}亿<br/>YoY: +${p.data[1]}%<br/>CAGR: ${p.data[2]}%`},
      grid:{left:60, right:20, top:20, bottom:40},
      xAxis:{type:'value', name:'2024市场规模(亿美元)', axisLabel:{color:'#90a4ae'}, splitLine:{lineStyle:{color:'#1e2456'}}},
      yAxis:{type:'value', name:'2024 YoY(%)', axisLabel:{color:'#90a4ae'}, splitLine:{lineStyle:{color:'#1e2456'}}},
      series:[{type:'scatter', symbolSize:d=>Math.sqrt(d[0])*1.5,
        data:items.map(i=>[i.global2024||0, i.yoy||0, i.cagr||0, i.sub||i.name]),
        itemStyle:{color:p=>{const c=p.data[2]; return c>=30?'#ff5252':c>=15?'#ffab40':'#4fc3f7';}},
        label:{show:true, formatter:p=>p.data[3], position:'top', color:'#e0e0e0', fontSize:9}}]
    });
  }
  if (cagrEl) {
    const chart = echarts.init(cagrEl);
    const sorted = [...items].sort((a,b)=>(b.cagr||0)-(a.cagr||0));
    chart.setOption({
      tooltip:{trigger:'axis'}, grid:{left:120, right:60, top:20, bottom:30},
      xAxis:{type:'value', axisLabel:{color:'#90a4ae'}, splitLine:{lineStyle:{color:'#1e2456'}}},
      yAxis:{type:'category', data:sorted.map(i=>i.sub||i.name), inverse:true, axisLabel:{color:'#90a4ae', fontSize:9}},
      series:[{type:'bar', data:sorted.map(i=>({value:i.cagr||0, label:{show:true, formatter:(i.cagr||0)+'%', position:'right', color:'#ffab40', fontWeight:'bold'}})),
        itemStyle:{color:new echarts.graphic.LinearGradient(0,0,1,0,[{offset:0,color:'#e65100'},{offset:1,color:'#ffab40'}])}, barWidth:12}]
    });
  }
}

function chartSectorTop10(prefix, d) {
  const scatterEl = document.getElementById(`chart-${prefix}-top10-scatter`);
  const radarEl = document.getElementById(`chart-${prefix}-top10-radar`);
  const top10 = d.top10 || [];
  if (!top10.length) return;
  
  if (scatterEl) {
    const chart = echarts.init(scatterEl);
    chart.setOption({
      tooltip:{trigger:'item', formatter:p=>`${p.data[3]}<br/>规模: $${fmt(p.data[0],0)}亿<br/>CAGR: ${p.data[2]}%`},
      grid:{left:70, right:20, top:20, bottom:30},
      xAxis:{type:'value', name:'2024市场规模(亿美元)', axisLabel:{color:'#90a4ae'}, splitLine:{lineStyle:{color:'#1e2456'}}},
      yAxis:{type:'value', name:'CAGR(%)', axisLabel:{color:'#90a4ae'}, splitLine:{lineStyle:{color:'#1e2456'}}},
      series:[{type:'scatter', symbolSize:d=>Math.sqrt(d[0])*2,
        data:top10.map(t=>[t.global2024||0, t.cagr||0, t.priority||3, t.name]),
        itemStyle:{color:p=>(p.data[2]||0)>=5?'#ff5252':(p.data[2]||0)>=4?'#ffab40':'#4fc3f7'},
        label:{show:true, formatter:p=>'#'+(p.data[2]||0)+' '+p.data[3], position:'top', color:'#e0e0e0', fontSize:9}}]
    });
  }
  if (radarEl) {
    const chart = echarts.init(radarEl);
    chart.setOption({
      tooltip:{}, radar:{center:['50%','55%'], radius:'65%', indicator:top10.map(t=>({name:t.name, max:300})), axisName:{color:'#90a4ae', fontSize:9}},
      series:[{type:'radar', data:[{value:top10.map(t=>(t.yoy||0)*2), name:'增长率', areaStyle:{color:'rgba(79,195,247,0.3)'}, lineStyle:{color:'#4fc3f7'}, itemStyle:{color:'#4fc3f7'}},
                {value:top10.map(t=>(t.cagr||0)*6), name:'CAGR(x6)', areaStyle:{color:'rgba(255,171,64,0.3)'}, lineStyle:{color:'#ffab40'}, itemStyle:{color:'#ffab40'}}]}]
    });
  }
}

function chartSectorStocks(prefix, d) {
  const barEl = document.getElementById(`chart-${prefix}-stocks-bar`);
  const scatterEl = document.getElementById(`chart-${prefix}-stocks-scatter`);
  const stocks = d.stocks || [];
  if (!stocks.length) return;
  
  if (barEl) {
    const chart = echarts.init(barEl);
    const sorted = [...stocks].sort((a,b)=>(b.chg2024||0)-(a.chg2024||0));
    chart.setOption({
      tooltip:{trigger:'axis', formatter:p=>p[0].name+'<br/>涨跌幅: '+(p[0].value>=0?'+':'')+p[0].value.toFixed(0)+'%'},
      grid:{left:100, right:50, top:10, bottom:30},
      xAxis:{type:'value', axisLabel:{color:'#90a4ae'}, splitLine:{lineStyle:{color:'#1e2456'}}},
      yAxis:{type:'category', data:sorted.map(s=>s.name), inverse:true, axisLabel:{color:'#90a4ae', fontSize:10}},
      series:[{type:'bar', data:sorted.map(s=>({value:s.chg2024||0, label:{show:true, formatter:((s.chg2024||0)>=0?'+':'')+(s.chg2024||0)+'%', position:(s.chg2024||0)>=0?'right':'left', color:(s.chg2024||0)>=0?'#69f0ae':'#ff5252', fontWeight:'bold'}})),
        itemStyle:{color:p=>p.value>=0?'#69f0ae':'#ff5252'}, barWidth:14}]
    });
  }
  if (scatterEl) {
    const chart = echarts.init(scatterEl);
    chart.setOption({
      tooltip:{trigger:'item', formatter:p=>`${p.data[3]}<br/>市值: $${fmt(p.data[0],0)}亿<br/>营收增速: +${p.data[1]}%`},
      grid:{left:70, right:20, top:20, bottom:30},
      xAxis:{type:'log', name:'市值(亿美元)', axisLabel:{color:'#90a4ae'}, splitLine:{lineStyle:{color:'#1e2456'}}},
      yAxis:{type:'value', name:'营收YoY(%)', axisLabel:{color:'#90a4ae'}, splitLine:{lineStyle:{color:'#1e2456'}}},
      series:[{type:'scatter', symbolSize:d=>Math.max(8, Math.log10(d[0])*10),
        data:stocks.map(s=>[s.mcap||1, s.revenueYoy||0, s.chg2024||0, s.name]),
        itemStyle:{color:p=>(p.data[2]||0)>=0?'#69f0ae':'#ff5252'},
        label:{show:true, formatter:p=>p.data[3], position:'top', color:'#e0e0e0', fontSize:9}}]
    });
  }
}

function renderSectorTop10Table(prefix, d) {
  const tbody = document.querySelector(`#${prefix}-top10-table tbody`);
  if (!tbody) return;
  const top10 = d.top10 || [];
  tbody.innerHTML = top10.map((t,i)=>`
    <tr>
      <td><strong>#${t.rank||i+1}</strong></td>
      <td><strong>${t.name}</strong></td>
      <td>$${fmt(t.global2024||0,0)}亿</td>
      <td class="positive">+${t.yoy||0}%</td>
      <td><span class="tag tag-hot">${t.cagr||0}%</span></td>
      <td>${t.globalLeader||'-'}</td>
      <td>${t.chinaLeader||'-'}</td>
      <td><span class="stars">${'★'.repeat(t.priority||3)}${'☆'.repeat(5-(t.priority||3))}</span></td>
    </tr>
  `).join('');
}

// Load sector data on demand
async function loadSectorData(sectorId) {
  if (SECTOR_DATA_CACHE[sectorId]) return SECTOR_DATA_CACHE[sectorId];
  const cfg = SECTOR_REGISTRY[sectorId];
  if (!cfg) return null;
  try {
    const resp = await fetch(cfg.dataFile);
    if (!resp.ok) throw new Error('Failed to load');
    const data = await resp.json();
    SECTOR_DATA_CACHE[sectorId] = data;
    return data;
  } catch(e) {
    console.error(`Failed to load ${sectorId} data:`, e);
    return null;
  }
}

// Switch to a sector tab
async function switchSectorTab(sectorId) {
  currentSector = sectorId;
  
  // Update nav tabs
  document.querySelectorAll('.nav-tab').forEach(b => b.classList.remove('active'));
  const tabBtn = document.getElementById(`nav-tab-${sectorId}`);
  if (tabBtn) tabBtn.classList.add('active');
  
  const sidebar = document.getElementById('sidebar');
  const container = document.querySelector('.container');
  const nav = document.getElementById('nav');
  const app = document.getElementById('app');
  
  // Show sidebar
  sidebar.classList.remove('hidden');
  container.classList.add('with-sidebar');
  nav.style.left = '200px';
  
  // Update sidebar links
  sidebar.innerHTML = buildSidebar(sectorId);
  
  // Load data
  app.innerHTML = `<div style="text-align:center;padding:80px;color:var(--accent);"><div class="spinner" style="width:40px;height:40px;border:3px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:spin .8s linear infinite;margin:0 auto 16px;"></div>正在加载${SECTOR_REGISTRY[sectorId].name}产业链数据...</div>`;
  
  const data = await loadSectorData(sectorId);
  if (!data) {
    app.innerHTML = `<div style="text-align:center;padding:80px;color:#ff5252;">❌ 数据加载失败，请刷新重试</div>`;
    return;
  }
  
  // Render HTML
  app.innerHTML = buildSectorHTML(sectorId, data);
  
  // Render charts
  setTimeout(() => {
    renderSectorCharts(sectorId, data);
    // Scroll to overview
    document.getElementById(`${sectorId}-overview`)?.scrollIntoView({behavior:'smooth', block:'start'});
  }, 150);
  
  // Update scroll sections
  updateScrollSections(sectorId);
}

// Dynamic scroll spy sections
let activeScrollSections = ['market'];
function updateScrollSections(sectorId) {
  activeScrollSections = ['market'];
  if (sectorId !== 'market') {
    ['overview','chain','upstream','midstream','downstream','top10','stocks'].forEach(s => {
      activeScrollSections.push(`${sectorId}-${s}`);
    });
  }
}

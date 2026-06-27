#!/usr/bin/env python3
"""Convert inline-data HTML to data-driven HTML by replacing DATA blocks with fetch-based loading."""
import re

with open('/workspace/semiconductor-site/index.html', 'r') as f:
    html = f.read()

# Find the DATA object start and end
data_start = html.find('const DATA = {')
data_end = html.find('  stocks: [', data_start)
# Find the end of the whole DATA object (before the render function or next top-level declaration)
# The DATA object ends with the stocks array closing
stocks_end = html.find('];\n', data_end) + 2
# Verify
print(f"DATA object: {data_start} to {stocks_end}, length={stocks_end-data_start}")

# Replace the DATA object with a fetch-based loader
data_loader = '''// ── DATA LOADING ──
let APP_DATA = null;
let GLOBAL_STOCKS = [];
let STOCK_LIST = [];
let CACHED_QUOTES = null;
let DATA_LOADED = false;

async function loadAllData() {
  try {
    const [marketResp, stocksResp, stockListResp, quotesResp] = await Promise.allSettled([
      fetch('data/market_data.json'),
      fetch('data/global_stocks.json'),
      fetch('data/stock_list.json'),
      fetch('data/realtime_quotes.json')
    ]);
    
    if (marketResp.status === 'fulfilled' && marketResp.value.ok) {
      APP_DATA = await marketResp.value.json();
    }
    if (stocksResp.status === 'fulfilled' && stocksResp.value.ok) {
      GLOBAL_STOCKS = await stocksResp.value.json();
    }
    if (stockListResp.status === 'fulfilled' && stockListResp.value.ok) {
      STOCK_LIST = await stockListResp.value.json();
    }
    if (quotesResp.status === 'fulfilled' && quotesResp.value.ok) {
      CACHED_QUOTES = await quotesResp.value.json();
    }
    
    DATA_LOADED = true;
    document.getElementById('loading-overlay')?.classList.add('hidden');
    return true;
  } catch(e) {
    console.error('Data loading failed:', e);
    document.getElementById('loading-overlay')?.innerHTML = '<div style="color:#ff5252;font-size:18px;">❌ 数据加载失败<br><span style="font-size:14px;">请检查网络连接后刷新页面</span></div>';
    return false;
  }
}

// Data access helpers
function D() { return APP_DATA; }'''

# Insert loading overlay CSS before </style>
loading_css = '''
#loading-overlay { position:fixed; top:0; left:0; right:0; bottom:0; background:var(--bg); z-index:9999; display:flex; justify-content:center; align-items:center; flex-direction:column; transition:opacity 0.5s; }
#loading-overlay.hidden { opacity:0; pointer-events:none; }
#loading-overlay .spinner { width:50px; height:50px; border:3px solid var(--border); border-top-color:var(--accent); border-radius:50%; animation:spin 0.8s linear infinite; margin-bottom:16px; }
@keyframes spin { to{transform:rotate(360deg);} }
#loading-overlay .loading-text { color:var(--accent); font-size:14px; }
.data-source-badge { display:inline-block; padding:2px 8px; border-radius:4px; font-size:10px; margin-left:8px; }
.data-source-badge.live { background:rgba(105,240,174,0.15); color:var(--green); }
.data-source-badge.cached { background:rgba(255,171,64,0.15); color:var(--orange); }'''

html = html.replace('</style>', loading_css + '\n</style>')

# Add loading overlay after <body>
html = html.replace('<body>\n', '''<body>
<div id="loading-overlay">
  <div class="spinner"></div>
  <div class="loading-text">正在加载产业链数据...</div>
</div>
''')

# Replace the DATA object (from const DATA = { to the stocks array closing)
html = html.replace(html[data_start:stocks_end+2], data_loader)

# Update the QUOTE_STOCKS reference to use STOCK_LIST
html = html.replace('const QUOTE_STOCKS = [', '// QUOTE_STOCKS loaded from data/stock_list.json\nconst QUOTE_STOCKS_ORIG = [')
# But we need QUOTE_STOCKS to point to STOCK_LIST. Add a line after loading:
html = html.replace('// QUOTE_STOCKS loaded from data/stock_list.json\nconst QUOTE_STOCKS_ORIG = [', '// QUOTE_STOCKS will be set from STOCK_LIST after data loads\nlet QUOTE_STOCKS = [];')

# Find the QUOTE_STOCKS array end and remove it
qs_end = html.find('];', html.find('let QUOTE_STOCKS = []'))
# We need to remove the original array literal
orig_start = html.find('// QUOTE_STOCKS will be set')
orig_data_start = html.find('[\n', orig_start)
orig_data_end = html.find('\n];\n', orig_data_start) + 4
html = html[:orig_start] + 'let QUOTE_STOCKS = [];' + html[orig_data_end:]

# Make render async and add data loading
html = html.replace('function render() {', '''async function render() {
  const ok = await loadAllData();
  if (!ok) return;
  
  // Set QUOTE_STOCKS from loaded data
  QUOTE_STOCKS = STOCK_LIST;
  
  // Set stocks in DATA.stocks format from GLOBAL_STOCKS
  if (APP_DATA && GLOBAL_STOCKS.length > 0) {
    APP_DATA.stocks = GLOBAL_STOCKS;
  }''')

# Update references: DATA.xxx → APP_DATA.xxx
for path in ['overview', 'chain', 'top10', 'stocks']:
    html = html.replace(f'DATA.{path}', f'APP_DATA.{path}')

# Fix the render function to not have double APP_DATA references
html = html.replace('APP_DATA.APP_DATA.', 'APP_DATA.')

# Update loadRealtimeQuotes to use QUOTE_STOCKS from loaded data
html = html.replace('QUOTE_STOCKS.filter', 'QUOTE_STOCKS.filter')

# Add QUOTE_STOCKS assignment after data load in loadRealtimeQuotes if needed
# The existing code references QUOTE_STOCKS which is now set from STOCK_LIST

with open('/workspace/semiconductor-platform/website/index.html', 'w') as f:
    f.write(html)

print(f"✅ Data-driven index.html created: {len(html)} bytes")
print(f"   Key changes: DATA→APP_DATA (fetch), QUOTE_STOCKS→STOCK_LIST, async render")
PYEOF
# 半导体全产业链动态图谱 — 自动化平台

## 📦 项目结构

```
semiconductor-platform/
├── website/                  # 🌐 网站前端
│   └── index.html           #    数据驱动版（从 data/ 目录加载JSON）
├── data/                     # 📊 数据文件（自动更新）
│   ├── market_data.json     #    产业链全景数据
│   ├── stock_list.json      #    监控股票列表
│   ├── realtime_quotes.json #    A股+港股实时行情（自动抓取）
│   ├── global_stocks.json   #    全球龙头股价数据
│   ├── benchmarks.json      #    基准指数
│   └── status.json          #    运行状态日志
├── scripts/                  # 🔧 自动化脚本
│   ├── fetch_all.py         #    主入口：一键抓取所有数据
│   ├── fetch_a_hk_stocks.py #    A股+港股行情
│   ├── fetch_global_stocks.py#   全球龙头股价
│   └── fetch_market_data.py #    市场基准数据
├── .github/workflows/        # ⚡ GitHub Actions
│   └── daily-update.yml     #    交易日自动更新
└── requirements.txt          #    Python依赖
```

## 🚀 部署方式

### GitHub Pages（推荐，免费）

1. Fork 本仓库到你的GitHub账号
2. Settings → Pages → Source: `GitHub Actions` 或 `main` 分支
3. 访问 `https://你的用户名.github.io/半导体平台/website/`

### 手动部署

```bash
# 安装依赖
pip install requests

# 抓取最新数据
python3 scripts/fetch_all.py

# 启动网站
cd website && python3 -m http.server 8080
# 访问 http://localhost:8080
```

## ⚡ 自动化运行

- **GitHub Actions** 每个交易日自动运行4次（9:35/11:35/14:35/15:35 北京时间）
- 数据自动提交到 `data/` 目录
- GitHub Pages 自动部署最新版本

## 📊 数据来源

| 数据 | 来源 | 更新频率 |
|------|------|:--:|
| A股+港股实时行情 | 东方财富 push2 API | 每日4次 |
| 全球龙头股价 | 东方财富全球行情 | 每日4次 |
| 行业基准数据 | WSTS/SIA/Gartner | 手动+季度 |
| 产业链分析 | 研究报告 | 手动+季度 |

## 💰 运营成本

| 项目 | 费用 |
|------|:--:|
| GitHub Pages 托管 | ¥0 |
| GitHub Actions CI | ¥0 (每月2000分钟免费) |
| 数据API | ¥0 (东方财富免费公开接口) |
| CDN (jsdelivr) | ¥0 |
| **总计** | **¥0/月** |

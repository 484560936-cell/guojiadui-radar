# 国资资金雷达

A股宽基ETF公开数据监测网站。**ETF份额变化不等于国家队交易**，也不代表中央汇金实时买卖。

## 数据
采集器通过 AKShare 获取上交所ETF公开份额和ETF行情，失败时保留旧数据并显示更新时间；不填造数据。
页面访问 GitHub Pages 后从 `data/dashboard.json` 读取数据。

## 配置
1. Settings → Pages → Build and deployment → Source: **GitHub Actions**
2. Actions → ETF数据采集与部署 → **Run workflow**
3. 在 Actions 查看采集日志及部署结果。

自动运行时间以UTC配置，约在中国交易日 09:00-16:00 每30分钟运行一次；GitHub定时任务可能延迟。首次运行若数据源不可用，仪表盘会明确显示采集失败。
项目为在连接器操作受限条件下提交的**可运行精简部署版**，不是先前ZIP的逐字节完整还原。

# NetShort 投放对比分析
固定口径对比两名投手的投放效率，输出 Markdown 结论与可视化 HTML。核心口径是 `rechargeNewRoi = rechargeNewAmount / cost`，对比一律按计划数量的比例分位，不按绝对排名。
## 目录
```
netshort-ad-analysis/
├── config.json        # 投手、主日、窗口、目标阈值（改这里）
├── fetch_data.py      # 拉取原始数据到 data/
├── analyze.py         # 计算指标 -> output/summary.json
├── render_html.py     # 生成 index.html
├── index.html         # 自包含报告，GitHub Pages 首页
├── run.sh             # analyze + render
├── data/              # 原始 JSON.gz（按投手分目录，不入库）
└── output/            # summary.json
```
## 快速开始
```bash
cd ~/netshort-ad-analysis
python3 fetch_data.py            # 拉主日 + 六日窗口 + 小时数据（需 netshort-scripts 凭据）
./run.sh                         # 生成 summary.json 与 index.html
open index.html
```
在线版：https://gar-su.github.io/netshort-ad-analysis/
只更新某一天：`python3 fetch_data.py --start 2026-11-12 --end 2026-11-12 --mode cost`。
## 口径
| 字段 | 含义 |
|---|---|
| rechargeNewAmount | 新用户充值，效率口径的分子 |
| rechargeAmount | 当日总充值，含存量复充，只看大盘 |
| rechargeNewRoi | rechargeNewAmount / cost |
| todayRoi | rechargeAmount / cost |
| 零单 | 当日 rechargeAmount = 0 且有消耗的计划 |
- `cost_list`：系列级日数据，`createBy` 为投手 empId，`today` 锚定数据日，必须翻页到 `total`，零消耗行保留。
- `hours/roi`：小时级数据，`startDate`/`endDate` 控范围，`hour` 为北京时间，`rechargeAmount` 实为新客充值。
- 参数实测：历史日 `nHour` 无效；`timezone` 请求头无效；`pageSize` 200 与 5000 结果一致。
## 分析框架
1. 校验：逐行聚合与 `cost_list/sum` 对齐。
2. 宏观：消耗、rechargeNewRoi、日波动、存量占比。
3. 中观：账户、语言、零单、有效计划数。
4. 微观：时段 ROI/CPI、首小时回收曲线。
5. 归因：三因子（付费率 × ARPPU ÷ CPI）、分位分桶、反事实分配。
## 维护
- 换对比对象：改 `config.json` 的 `users`，保持第一个人为分析对象、第二个人为对标。
- 换日期：改 `primary_day`、`daily_window`、`hourly_window`，重新 `fetch_data.py`。
- 换目标线：改 `targets`，HTML 中的优秀线与 KPI 判定会跟随。
- 展示名已匿名：分析对象显示为「agent投手」，对标投手显示为「优秀投手」，原始 empId 只保留在 config 供取数使用。
- 发布：`index.html` 提交到 main 分支根目录，GitHub Pages 自动更新。
## 已知限制
- 当日数据仍在回补，`data_snapshot` 记录快照时间，重新取数后数值会小幅变动。
- 分位分桶基于当日有消耗计划，跨日聚合会改变头部集合。
- 反事实上界未考虑头部加预算后的 CPI 抬升，实际收益低于测算值。

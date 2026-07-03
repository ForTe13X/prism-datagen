# prism-datagen

[English](README_EN.md)

确定性跨源数据包生成器。它生成带有内置标准答案的脏数据包，让规则解法和 LLM pipeline 都能被精确评分。

核心是纯 Python 标准库。生成的数据可以导出为 JSON、CSV、SQLite，也可以通过可选的本地 Web UI 浏览。

## 工作方式

生成器先写答案，再围绕答案生成观测：

1. 定义 ground truth，例如「台风事件 X 导致运单 A 和 B 延误」。
2. 把证据拆进多种来源：运单表、仓库吞吐量时序、新闻文本。
3. 加入受控噪声：别名、单位变化、缺失值、时间偏移、数值扰动和乱码文本。

答案保持不变，表面数据逐渐变难读。这样可以区分真正的跨来源推理与简单字符串匹配。

两个旋钮控制难度：

| 控制项 | 效果 |
|---|---|
| `dirtiness` 0 到 1 | 增加别名、缺失字段、单位变化、时间偏移、数值噪声和乱码 |
| `link_explicitness` 1 到 5 | 从直接 ID 线索逐步变成隐式语义线索 |

同一个 seed 会生成逐字节一致的数据包，方便跨时间、跨机器比较。

## 演示

![22 秒高光:脏度旋钮、显眼度扫描与判别力、真值链悬停联动](demo/demo-highlights.gif)

[3 分半讲解视频，中文旁白 + 中英字幕](demo/prism-datagen-demo.mp4)

![界面总览:左侧是评分与真值链,右侧是三种数据源](docs/screenshots/01_overview.png)

悬停一条真值链时，界面会同时高亮多个来源中的对应证据：

![悬停真值链,跨源联动高亮](docs/screenshots/08_truthchain_hover.png)

## 快速开始

需要 Python 3.10 或更新版本。

```bash
# 生成数据包、打印人读预览、并给内置解法评分
python -m datagen gen -d 0.6 -l 4 -s ho-0 --eval

# 导出 JSON、CSV 与 SQLite
python -m datagen gen -d 0.6 -s ho-0 -o out -f all

# 扫描一个难度旋钮
python -m datagen sweep --over dirtiness
```

可选 Web UI：

```bash
pip install fastapi uvicorn
python server.py
```

然后打开 `http://127.0.0.1:8123`。

Python API：

```python
from datagen import evaluate, generate, preview

pkg = generate("logistics_demo", dirtiness=0.6, link_explicitness=4, seed="ho-0")
print(preview(pkg))
print(evaluate(pkg))
```

## 内置难度检查

项目内置三个参考解法：

- `oracle`：读取内置答案，应始终得到 1.0。
- `naive`：主要做字面匹配和单源证据。
- `linked`：用确定性的实体、地点、时间线索做跨源对齐。

当线索变得不再显眼时，naive 解法会崩掉，而 linked 解法仍然可用：

| 显眼度 | naive F1 | linked F1 |
|---|---:|---:|
| L1，直接 ID | 1.000 | 0.800 |
| L2-L5，逐渐隐式 | 0.000 | 0.800 |

提高脏度会让 linked 的分数按多 seed 趋势下降，从而形成一条简单的鲁棒性曲线。

## 数据包内容

一次生成的数据包包含：

- `stores`：观测来源，包括关系表、时序和新闻文本。
- `ground_truth`：用于精确评分的 event-to-record 链接。
- `corruption_map`：可追踪的污染记录；能逆向的污染会记录变体与规范值。
- `manifest`：seed、难度控制、数量和边界说明。

导出格式包括完整 JSON、每张表一个 CSV、以及可查询的 SQLite 数据库。[examples/](examples/) 下有样例输出。

## 目录

```text
datagen/          生成器核心，仅标准库
  specs/          领域 spec；新增 spec 即可新增领域
server.py + web/  本地可视化界面
tests/            确定性、可恢复性、脏度、判别力、导出与 CLI 测试
docs/             技术文档、测试文档、用户手册与 PRD
demo/             讲解视频与复现脚本
examples/         JSON、CSV、SQLite 样例输出
```

```bash
python -m pytest tests/ -q
```

## 边界

- 数据分布是手工配置的合成数据，适合做受控评测，不是现实物流数据的证据。
- 内置 `linked` 解法是确定性参考基线，不是真正的语义推理模型。
- 鲁棒性曲线是多 seed 趋势；单个 seed 可能有波动。
- numeric freezing 暂未进入 `corruption_map`；其他污染类型会被记录。
- 当前判别力检查聚焦 `explain_delays`。
- 暂不包含 PDF 与 NoSQL 模态；SQLite 只物化关系表。
- 当前领域是物流，因果模式为 event -> anomaly -> delay。新增领域通过 specs 完成。
- 项目从 Prism 中抽出为独立生成器，只包含本项目自有代码。

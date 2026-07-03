# prism-datagen 产品需求文档（PRD）

> 确定性跨源数据包生成器 —— 生成"带预埋、且始终可恢复的跨源因果真值"的脏数据基准。
>
> 版本：1.0.0 · 数据域 spec：`logistics_demo` · 交付形态：Python 库 + CLI + 本地 Web UI
>
> 一句话定位：把"新闻事件 → 吞吐量异常 → 延误运单"这条跨源因果链**先建为真值**，再让所有观测 store 与之一致；两个旋钮（`dirtiness`、`link_explicitness`）只污染/隐藏观测，**永不动真值**，且相同参数逐字节可复现。

---

## 目录

1. [背景与问题](#1-背景与问题)
2. [目标与非目标](#2-目标与非目标)
3. [用户与场景](#3-用户与场景)
4. [功能需求与优先级](#4-功能需求与优先级)
5. [两个旋钮：难度产品杠杆](#5-两个旋钮难度产品杠杆)
6. [成功度量](#6-成功度量)
7. [里程碑与路线图](#7-里程碑与路线图)
8. [风险与诚实局限](#8-风险与诚实局限)
9. [优缺点（pros & cons）](#9-优缺点pros--cons)

---

## 1. 背景与问题

评测"跨源推理 / 实体消解 / 检索增强（RAG）解析器"时，长期缺一样东西：**带已知真值标注的脏数据**。现实卡在两难之间：

- **真实数据没有真值标注。** 一批真实的运单、时序、新闻放在一起，"哪条新闻解释了哪些运单延误"这个答案本身就是要人去标的，昂贵、主观、且难以规模化；没有金标准，就无法客观地给解析器打分。
- **纯合成数据又太干净。** 随手合成的数据往往结构规整、无别名冲突、无单位漂移、无缺失、时间对齐完美 —— literal（字面）匹配就能通吃，评测不出"是否真的需要跨源推理"。数据太干净，任务就没有区分度。

`prism-datagen` 的切入点：**真值先建，再让观测退化。** 先在生成器内部把跨源因果链（`news event → throughput anomaly → delayed shipments`）作为 ground-truth 直接写死，随后用两个旋钮系统地污染和隐藏观测层，而真值答案（`ground_truth.answers`）始终原样保留、始终可恢复。于是得到一份既"脏得像真实数据"、又"带金标准可判分"的基准数据。

同时，配套一个**判别力探针**：三个解法在**观测视图**（`observation_view`，只看 store、看不到真值）上跑同一个任务 ——

- `oracle`：知道真值，恒 1.0，是天花板；
- `naive`：字面精确匹配、单源，不做跨源推理；
- `linked`：跨源时空 + 实体联结（region/port/anomaly-time 多线索联结）。

当 link 隐晦或脏度升高时，`naive` 崩、`linked` 仍能部分恢复 —— 这就用可度量的 gap 证明了：**这个任务确实需要跨源推理，不是字面匹配能糊弄过去的**。

---

## 2. 目标与非目标

### 目标（In Scope）

| 目标 | 说明 | 代码依据 |
|---|---|---|
| **确定性 / 逐字节可复现** | 相同 `(seed, dirtiness, link, domain)` → 逐字节相同的数据包。基于 sha256 把种子映射到 `[0,1]`（`core._unit`）与确定性信号（`core._wiggle`），**无 `random`、无时钟、无环境态**。 | `datagen/core.py`；`tests/test_determinism.py` |
| **真值始终可恢复** | 真值**先建**（`_build_truth`），观测再向它对齐；`ground_truth.answers` 按**观测可见的 id**（新闻 id / 仓库 id）作键，使得只看 store 的解法也能被打分。 | `generator._build_truth` / `generate`；`tests/test_truth_recovery.py` |
| **两旋钮可调难度** | `dirtiness` 0–1 与 `link_explicitness` 1–5 组成难度网格；两旋钮**只动观测，不动真值**。 | `generator._apply_dirtiness` / `_news`；`tests/test_determinism.py::test_truth_invariant_to_dirtiness_and_link` |
| **多模态物化** | 一份数据包可物化为 4 种落地形态：全量 JSON、每 store 一个 CSV、**真实可查询的 SQLite**、人读 preview 文本。 | `datagen/materialize.py`、`generator.to_sqlite` |
| **判别力探针** | 内置 `naive / linked / oracle` 三解法与 F1 打分（precision/recall/f1）、gap 度量，量化"任务是否需要跨源推理"。 | `datagen/oracle.py` |
| **零依赖核心 + spec 驱动换域** | 生成器核心仅用 Python 标准库（`hashlib`/`math`/`json`/`csv`/`sqlite3`）。领域相关的 vocab/roles/regions/ports 全在 spec JSON 里；换域 = 换 spec，**零生成器代码改动**。 | `generator._cfg` / `_DEFAULT_VOCAB` / `_DEFAULT_ROLES`；`datagen/specs/logistics_demo.json` |
| **双界面** | CLI（`list` / `gen` / `sweep`）与本地 Web UI（FastAPI + 单页）两种入口，且**共用同一确定性生成器，无独立代码路径**。 | `datagen/cli.py`、`server.py`、`web/index.html` |

### 非目标（Out of Scope，如实声明）

以下能力**本包明确不做**，请勿据本文档臆想它们存在：

- **真实分布校准（no real-data calibration）。** 所有数理分布（吞吐量基线/振幅、重量区间、异常凹陷深度等）是**手设合成示意，未逆向自任何真实数据**。这一条在 spec 的 `notes.honesty` 里也明写。
- **LLM 基准跑 / agentic 解析器。** 本包不含任何 LLM 调用、不跑 LLM ablation。判别力探针里的 `linked` 是**确定性骨架解法**，是"未来 LLM/axiom 语义解法"的确定性占位替身，不是真正的语义求解器。
- **PDF / NoSQL 等更多模态。** 物化仅覆盖 JSON / CSV / SQLite / 文本 preview。没有 PDF、没有 NoSQL、没有图/向量库等模态。
- **生产级规模。** 面向教学、演示、回归测试的小规模数据（默认 3 仓 / 4 承运 / 24 运单 / 60 帧 / 8 条新闻），不追求大规模数据管线的吞吐或分布式生成。

> 上述非目标中"真实校准 / agentic 解析器 / PDF·NoSQL 多模态 / LLM-ablation"是母项目 **Prism** 的另外几条线，**不在本交付包内**。本包是那几条线要搭建其上的**确定性底座**。

---

## 3. 用户与场景

| 用户 | 场景 | 本产品提供的价值 |
|---|---|---|
| **做基准的研究者 / 工程师** | 需要一份"带金标准、可调难度"的跨源脏数据来评测自己的跨源推理 / 实体消解 / RAG 解析器。 | 一条命令生成带真值的数据包 + 现成 F1 判别力打分；用 `sweep` 一次得到整条难度曲线；`--eval` 直接对比 naive/linked/oracle。 |
| **教学 / 演示** | 想直观讲清"为什么字面匹配不够、跨源推理才行"。 | 本地 Web UI：拖动两个滑块实时重生成，悬停真值链联动高亮吞吐时序 + 运单表 + 新闻源；污染清单以 chips 呈现；判别力柱状图当场看到 `naive` 崩、`linked` 稳。 |
| **解析器回归测试** | 在 CI 里固定基准，防止解析器改动引入回归。 | 逐字节可复现意味着可作为稳定夹具（fixture）：同参数同输出，可直接断言解法在指定难度点的分数与曲线趋势（本包自带 29 个用例 / 6 个测试文件正是这样用的）。 |

---

## 4. 功能需求与优先级

优先级：**P0 = 核心不可缺**；**P1 = 交付必备**；**P2 = 增强**。（所列均为代码中真实已实现的能力。）

### 4.1 生成（Generation）· P0

- `generate(source_id, *, dirtiness=0.0, link_explicitness=4, seed=None)` 产出一个数据包 dict，含 `stores`（sql / timeseries / news）、`ground_truth`（events / answers / window）、`corruption_map`、`tasks`、`manifest`。
- 真值先建（`_build_truth`）：仓库/承运/运单行 + ground-truth 事件；每个事件落在**不同的仓库**（distinct hub），保证按仓库键的异常/答案映射不会把两条真值塌成一条。
- 吞吐时序（`_throughput`）：每仓一条序列，真值事件在其帧前后刻出异常凹陷（dip）。
- 未知域返回 `None`；旋钮越界自动 clamp 到 `[0,1]` / `[1,5]`。

### 4.2 两个旋钮（Knobs）· P0

- **`dirtiness` 0–1**（`_apply_dirtiness`）：对观测就地注入 6 类污染，并把每处以 `variant→canonical` 记入 `corruption_map`（可逆）：
  1. **身份别名 identity**：新闻正文里把 region token 改写成别名（如 华东 → 华東/华东区/HD）；
  2. **单位漂移 unit**：部分运单重量由 kg 改存 lb（`× 2.20462`）；
  3. **状态置空 missing**：部分运单 `status` 置为 `null`；
  4. **时间偏移 time**：部分新闻帧号 ±1..2 偏移；
  5. **数值冻结 numeric**：少量吞吐点被冻结为前一点（sensor glitch）；
  6. **编码乱码 encoding**：一部分新闻正文做 UTF↔latin-1 乱码（GBK↔UTF mojibake 占位）。
  - 各类污染强度随 `d` 缩放（如 lb 漂移阈值 `d*0.5`、状态置空 `d*0.3`、时移 `d*0.4`、乱码 `d*0.25`、冻结 `d*0.05`）。`d=0` 时观测完全干净。
- **`link_explicitness` 1–5**（`_news`）：控制新闻把"命中哪个仓 / 哪些运单"暴露得多显眼 —— L1 直接写 id、L5 纯语义（vocab.news 里的 `l1`..`l5` 模板）。distractor 新闻为干扰项、无真值效应。
- **不变式（P0 硬约束）**：两旋钮无论怎么调，`ground_truth.answers` 恒等（由 `test_truth_invariant_to_dirtiness_and_link` 守护）。

### 4.3 判别力探针（Discriminability）· P0

- `evaluate(package, task_id="explain_delays")` 在**观测视图**上跑 `naive` / `linked`，与 `oracle` 对比，返回 `naive_f1 / linked_f1 / oracle_f1 / gap`。
- `observation_view` 严格剔除真值元数据（`_truth_event`）与真值侧延误窗口 —— 解法看不到任何生成参数。
- `score` 输出 precision / recall / f1。`gap = linked_f1 − naive_f1`，作为"任务是否需要跨源推理"的量化信号。

### 4.4 物化（Materialize）· P1

- `to_json`：全量数据包 UTF-8 JSON。
- `to_csv`：每 SQL store 一个 CSV（`warehouses/carriers/shipments`）+ 长表 `throughput.csv`（`hub_id, frame, value`）+ `news.csv`；用 `utf-8-sig` 以便 Excel 正确读中文。
- `to_sqlite`：物化为**真实可查询的 SQLite**（一 store 一表，列由该 store schema 推断，`id` 为主键），是真正关系型的模态。
- `preview`：人读文本摘要（manifest + 真值答案 + 污染清单 + 各 store 采样），确定性、无时钟。
- **role-generic**：物化全部按包内 `roles` / store 键读取，任何域的包都能物化，不只物流。

### 4.5 CLI · P1

三个子命令（`python -m datagen ...`）：

- `list`：列出可用数据域；
- `gen`：生成并把 preview 打到 stdout，`--eval` 追加判别力 F1，`-o/--out` + `-f/--format {json,csv,sqlite,all}` 写文件；
- `sweep --over {dirtiness,link}`：扫描一个旋钮，打印判别力/鲁棒性曲线（dirtiness 扫 `0/0.3/0.6/0.9`，link 扫 `1..5`）。

### 4.6 本地 Web UI · P1

- `server.py`（FastAPI）暴露只读接口 `/api/specs`、`/api/generate`、`/api/sweep`，静态返回 `web/index.html` 单页。
- 单页 UI：两个滑块（脏度 / 显眼度）+ 种子输入 + 域选择，实时重生成；可视化判别力柱状图、跨源真值链（悬停联动高亮吞吐/运单/新闻）、污染清单 chips、吞吐时序 SVG、新闻源（★真值 / 乱码 / 时移标记）、运单表（delayed 高亮 / lb / null）。
- UI 与 CLI **共用同一生成器，无第二条代码路径**。

---

## 5. 两个旋钮：难度产品杠杆

把两个旋钮产品化为一句话："**难度不是随机的，而是两根可解释、可复现的杠杆调出来的。**"

- **`link_explicitness`（显眼度杠杆）—— 调"任务需要多强的推理"。**
  拉到 L1，新闻直接写运单 id，字面匹配即可满分，任务退化为查表；从 L2 起新闻不再给 key，只剩语义/时空线索，字面解法瞬间崩塌。它决定了"是否非跨源推理不可"。
  真实测得：`sweep --over link` → **L1：naive 1.000 / linked 0.800 / gap −0.200；L2..L5：naive 0.000 / linked 0.800 / gap +0.800**。（L1 处 gap 为负，是因为字面解法在显式 key 上反而比骨架 linked 更完整 —— 这本身就说明 L1 不构成"需要跨源"的判别区间。）

- **`dirtiness`（脏度杠杆）—— 调"线索被腐蚀到什么程度"。**
  它不改任务的答案，只腐蚀 linked 赖以联结的线索（region/port/time）。脏度越高，跨源解法越吃力，得到一条**鲁棒性曲线**。
  真实测得：`sweep --over dirtiness`（link 固定 4）→ **d0.0：linked 0.800；d0.3：linked 0.571；d0.6：linked 0.500；d0.9：linked 0.500**（naive 恒 0，gap 始终为正）。

- **组合成难度网格。** 两杠杆张成 `dirtiness × link` 的二维难度面：左下角（干净 + 显式）是热身档，右上角（脏 + 隐晦）是硬档。研究者可精确地把基准锚在任意难度点，并因确定性而随时逐字节复现该点。

> 真实 `gen -d 0.6 -l 4 -s ho-0 --eval` 输出（可原样引用）：真值 EVT-1 台风封港@WH-003 frame46→SHP-0007,SHP-0011；EVT-2 道路中断@WH-001 frame47→SHP-0023；答案 `{NEWS-001:[SHP-0007,SHP-0011], NEWS-002:[SHP-0023]}`；污染：别名5/单位漂移5/状态置空5/编码乱码1；判别力 **naive=0.000 linked=0.333 oracle=1.000 gap=+0.333**。

---

## 6. 成功度量

| 度量 | 判定标准 | 验证方式（真实） |
|---|---|---|
| **确定性可复现** | 相同 `(seed, dirtiness, link, domain)` → 逐字节相同；不同 seed 输出必不同。 | `test_determinism.py::test_same_knobs_byte_identical` / `test_seed_changes_output_but_stays_reproducible` |
| **真值不受旋钮影响** | 遍历 `d∈{0,0.3,0.6,0.9} × l∈{1..5}`，`ground_truth.answers` 恒等；oracle 恒 1.0。 | `test_truth_invariant_to_dirtiness_and_link`、`test_oracle_is_perfect` |
| **判别区间存在 gap>0** | 在隐晦 link（L≥2）下，跨 8 个 seed 的**平均 gap > 0**（linked 胜 naive）。 | `test_solvers.py::test_linked_beats_naive_in_discriminative_interval` |
| **鲁棒性曲线单调（均值）** | 跨 8 个 seed 的均值上，`linked_f1(0.0) ≥ (0.3) ≥ (0.6) ≥ (0.9)`；重污染显著劣于干净。 | `test_solvers.py::test_dirtiness_degrades_linked_on_the_mean` |
| **污染可逆、只动观测** | 每处污染都记入 `corruption_map`（variant→canonical）；脏包与净包的 `ground_truth` 完全一致。 | `test_dirtiness.py::test_unit_drift_recorded_and_reversible` / `test_dirtiness_never_touches_ground_truth` |
| **换域零代码** | 换 vocab/roles = 换领域；物化/解法均 role-generic，任何域的包都能生成、物化、打分。 | `generator._cfg`、`materialize` role-generic 实现；`to_sqlite` 注释所述"any domain materializes" |
| **物化真实可用** | SQLite 是真库、可 SQL 查询且结果与包一致；CSV 行数与 store 一致；JSON 可 round-trip。 | `test_materialize.py`（sqlite 查询 delayed 数一致 / csv 行数一致 / json round-trip） |

> **关于"单调"的诚实注脚**：鲁棒性下降是**跨多个 seed 的均值趋势**，**并非逐 seed 单调** —— 在单个 seed 上，污染偶尔会把某个边界匹配"歪打正着"地修对，导致该 seed 的分数不降反升。测试也据实只断言"均值单调"，见 `test_dirtiness_degrades_linked_on_the_mean` 的注释。

---

## 7. 里程碑与路线图

### 已交付（v1.0.0，即本包 = DP1）

确定性生成器 + 跨源真值 + `dirtiness`/`link_explicitness` 两旋钮 + `naive/linked/oracle` 判别力探针 + 四模态物化（JSON/CSV/SQLite/preview）+ CLI + 本地 Web UI + 29 个测试用例（6 个测试文件）。零依赖核心，spec 驱动换域。

### 路线图（Future，均为**尚未实现**，如实标注）

- **真实分布校准（realistic-calibration）。** 用真实数据逆向标定吞吐/重量/异常等分布，替换当前手设合成示意。这是把"看起来像真实"升级为"统计上贴近真实"的关键一步。
- **真正的语义解法。** 用 LLM / axiom 语义层替换当前确定性 `linked` 骨架，使其能真正区分 L2→L5 的细粒度梯度（尤其纯语义的 L5）—— 当前骨架对 L2–L5 打同分（~0.8）。
- **更多数据域。** 目前仅随包 `logistics_demo` 一个 spec；spec 驱动架构已就绪，可零生成器代码新增更多领域 spec。
- （更远，属母项目 Prism 另线，非本包承诺）：更多模态（PDF/NoSQL 等）、LLM-ablation 基准、agentic 解析器评测。

---

## 8. 风险与诚实局限

> 以下为**必须显著呈现**的诚实边界，不得回避。它们界定了"本产品是什么、不是什么"。

- **数理分布是手设合成示意，未逆向自真实数据。** 没有 real-data calibration；数据"看起来脏得像真实"，但分布本身并非从真实数据标定而来（spec `notes.honesty` 已明写）。用它做的结论，其外部有效性受此限制。
- **确定性 `linked` 只区分 L1 vs L≥2。** 它把多个线索（name/region/port/anomaly-time）做 OR，而 L2–L5 每一级都至少留一个线索，因此 **L2–L5 得分相同（~0.8）**。它是**未来 LLM/axiom 解法的确定性占位替身，不是真正的语义求解器**；真正的 L2→L5 细粒度梯度（尤其纯语义 L5）留给未来解法去跑。
- **`linked` 满分是 ~0.8 而非 1.0。** 这是骨架解法的上限，不是 bug；只有 `oracle`（知真值）才恒 1.0。
- **鲁棒性下降是均值趋势，非逐 seed 单调。** 单 seed 上污染可能"歪打正着"，须跨多 seed 取均值才呈现单调曲线。
- **无 PDF / NoSQL 多模态、无 LLM 基准跑。** 那是母项目 Prism 的另一条线，**不在本包**；本包只提供确定性底座。
- **规模面向教学/演示/回归**，非生产级数据管线。
- **clean-room 出处声明。** 本包从个人学习沙盒中抽取，**仅含本项目自有代码**（确定性原语 `_unit`/`_wiggle` 亦是从该沙盒逐字复制的自有代码）。

---

## 9. 优缺点（pros & cons）

围绕"这个产品定位"的取舍展开。

### 优点

- **填了一个真实空白**："带已知真值的脏数据"—— 真实数据无真值标注、纯合成又太干净，本产品用"真值先建、观测退化"同时拿到两者的好处。
- **逐字节可复现**：sha256 种子、无 random、无时钟，天然适合当 CI 夹具与可争议结论的复现底座；同参数同输出，跨机器一致。
- **难度可解释、可复现**：两个旋钮是可讲清、可断言的杠杆，能把基准精确锚在难度网格任意点，并给出量化的判别力 gap 与鲁棒性曲线。
- **判别力自证**：内置 naive/linked/oracle 三解法，用 gap>0 直接证明"任务确实需要跨源推理"，而非口头声称。
- **零依赖核心 + spec 驱动**：生成器只用标准库；换 vocab/roles 即换域，零生成器代码；物化与解法全 role-generic。
- **交付面完整**：库 + CLI + 本地 Web UI 三种入口共用同一确定性生成器（无第二代码路径），且 4 种物化模态含真实可查询 SQLite；29 个用例覆盖确定性/真值/污染/判别力/物化/CLI。

### 缺点 / 局限（如实、具体）

- **分布是手设合成，未做真实校准**（no real-data calibration）：数据"像真实"但非统计意义上"贴近真实"，基于它的结论外部有效性有限 —— 这是当前最大的诚实短板。
- **`linked` 只是确定性占位替身，不是语义求解器**：它只能区分 L1 vs L≥2，**L2–L5 同分（~0.8）**，无法体现真正的语义梯度；"linked 满分 ~0.8 而非 1.0"是骨架上限。真正的 L2→L5 求解要等未来 LLM/axiom 解法。
- **鲁棒性单调仅在均值成立**：单 seed 会因污染"歪打正着"而非单调，任何逐 seed 的强断言都不成立，必须跨多 seed 取均值。
- **模态有限**：仅 JSON/CSV/SQLite/文本，**无 PDF/NoSQL** 等；也**无 LLM 基准跑 / agentic 解析器**（属母项目 Prism 另线，不在本包）。
- **规模与领域受限**：默认小规模（3 仓/24 运单/60 帧），仅随包一个 `logistics_demo` 域；面向教学/演示/回归，非生产级。
- **单一因果模式**：目前只有"事件→异常→延误"这一条跨源因果链模式；虽 spec 可换域，但底层因果 pattern 是固定的一种。

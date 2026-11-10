# 实际运行与复算入口

## 2026-11-10 当前版本

当前运行是 `research-local/corpus-refresh/20261110/editing`，最终分析目录为 `analysis/`。454个视频的当前汇总、三部影片的新旧视频SHA与可公开查看的CSV见[版本更新与结果](../corpus_refresh/20261110/README.md)。当前入口由 `ACTIVE_EDITING_RUN.txt`记录。

本次用同一逐帧算法重新提取《买牛、扒瓜园》《永恒的友谊》《老保管、新媳妇来了》。另451个未变源继承原逐帧缓存、候选和收据。`measurement_reuse.json`绑定每个继承作业的原运行、原配置SHA、原收据SHA与视频版本。数值审计验证提取参数一致，仅允许运行范围等描述字段变化。新源均重新读取完整SHA256并解码至EOF。

建立一个新的增量运行目录与执行三部提取的命令见[明暗复算入口](../corpus_studio/REPRODUCE.md)。随后在新运行的 `editing/`目录执行以下步骤，替换为实际新目录即可。

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=analysis-python MPLCONFIGDIR=/tmp/cinematicdx-mpl OPENBLAS_NUM_THREADS=1 \
  .venv-m3/bin/python research/quantitative_exploration/scripts/analyse_corpus_editing.py \
  --run research-local/corpus-refresh/replay-20261110/editing \
  --report-directory research-local/corpus-refresh/replay-20261110/editing/report

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=analysis-python OPENBLAS_NUM_THREADS=1 \
  .venv-m3/bin/python research/quantitative_exploration/scripts/challenge_editing_edges.py \
  --run research-local/corpus-refresh/replay-20261110/editing

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=analysis-python OPENBLAS_NUM_THREADS=1 \
  .venv-m3/bin/python research/quantitative_exploration/scripts/audit_corpus_editing.py \
  --run research-local/corpus-refresh/replay-20261110/editing
```

聚合重新计算全部片厂表、时间曲线、参数与来源敏感性、条件置换参照及片中段挑战。审计独立重算标量切点规则、PTS、候选数和机构均值。输出目录必须尚未存在。重建继承结果需要父运行的逐片产物。

人工验证仍使用同一SHA的《上甘岭》02:30–12:30参考。硬切主配置为43匹配、2误报、2漏检（±80毫秒），渐变默认配置在tIoU≥0.5为0匹配、91误报、4漏检。三部源版本更新增加了实际提取证据，验证样本仍为原独立标注区间。

## 2026-10-26 历史运行说明

以下命令、数量和路径记录10月版本；当前版本与结果以上方入口为准。

当前运行指针：`research/quantitative_exploration/ACTIVE_EDITING_RUN.txt`。本次为`research-local/studio-editing/corpus-20261026T114911Z`，最终分析目录`analysis/`。453/453源已完成，数值审计、全部六张接触表的助手观察和研究解释均已完成；结论见[最终评估](ASSESSMENT.md)。`completion_receipt.json`绑定各阶段实际产物，`progress.json`仅表示原始批次进度，不能抹掉后续恢复记录。

## 输入与冻结

`plan.json`保存732影片记录、453独特源作业、原路径、key、来源SHA和继承身份映射。454个原路径中的误标重复源只计一次；279条缺有效视频仍出现在覆盖表。原始研究JSON在仓库根，影片位于外置盘`/Volumes/Extreme SSD/Video/Chinese1949-66`。没有这些实际源文件，工程测试不能替代实证复跑。

`config.json`绑定提取源码SHA、参数和原Excel SHA。全部原始视频的完整SHA在未完成作业开始前重验；每作业`run.json`保留源文件状态与产物SHA。若输入、源码或参数改变，应建立新运行目录，不能修改旧收据来强行复用。

既有`.venv-m3`含PyAV18、NumPy2.4.6、OpenCV4.13及PySceneDetect0.7.1。源码未新增重型依赖或模型下载。Matplotlib为静态科学图，中文字体使用本机STHeiti路径；不同系统可显式替换字体，不能悄改测量参数。

## 执行

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=analysis-python OPENBLAS_NUM_THREADS=1 \
  .venv-m3/bin/python research/quantitative_exploration/scripts/run_corpus_editing.py \
  --run research-local/studio-editing/corpus-20261026T114911Z --workers 4
```

上面是实际提取命令，现已完成，不需再启动。相同输入的已成功作业会检查收据后复用。未完成/失败的部分结果先另存再重试；首次失败及后续修订都应保留。要独立重提取，另建目录复制冻结plan/config及通过的preflight记录，核对原路径、代码和SHA后运行，不删除现有结果。

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=analysis-python OPENBLAS_NUM_THREADS=1 \
  .venv-m3/bin/python research/quantitative_exploration/scripts/finish_corpus_editing.py \
  --run research-local/studio-editing/corpus-20261026T114911Z --wait
```

上面是实际收尾命令，现已完成。它顺序产生分组分析、机构平衡接触表和独立数值审计。`pipeline_ready.json`只表示数值产物齐备，不能当作全库人类验证；本次额外的实际观察已另存`visual_qa/assistant_review.json`，不是独立人类真值。最终解释另见ASSESSMENT.md。

首次直接seek抽查无法精确定位部分编码帧，原部分结果保留为`visual_qa_direct_seek_failure_preserved/`。修订脚本提前解码直到精确原PTS，17片/170帧均成功；实际修订源码及SHA在`visual_qa/inspect_corpus_editing.py`和`selection_and_receipt.json`。分组时封存的旧QA源码仍保留，不冒充最后实际执行版本。

片中段挑战是观察片尾材料后新增的单独分析，不改主结果：

```sh
PYTHONDONTWRITEBYTECODE=1 .venv-m3/bin/python \
  research/quantitative_exploration/scripts/challenge_editing_edges.py \
  --run <包含相同已校验候选的新运行副本>
```

输出`edge_challenge/`必须不存在，脚本拒绝覆盖；读取原候选并检查每片全文件率与主表一致，按实际解码覆盖[10%,90%)计数。当前453片已完成，输入/脚本/结果SHA全部保存。

若只复算分组，保留原`analysis/`并在新的运行副本中执行`analyse_corpus_editing.py --run <新副本> --report-directory <独立报告目录>`。新副本可复用相同且校验通过的逐片只读产物；不要覆盖原结果或对外发布测试子集报告。

## 产物

| 路径 | 内容 |
|---|---|
| `preflight/results.json` | 硬切两种帧号/多个容差与参数、渐变多个tIoU；严格失败保留 |
| `preflight/fullfilm_execution_equivalence.json` | 前四完整影片的旧/新执行特征及切点文件SHA一致检查 |
| `preflight/hardware_probe_result.json` | 硬件解码预检不可用，最终仍为软件CPU |
| `films/<job_id>/frame_features.npz` | 每个解码帧原PTS/nextPTS、显示时间、V差、灰度小图等；没有按1Hz抽取 |
| `films/<job_id>/cut_candidates.json` | 主/宽松/严格/ROI候选，保留最短间隔抑制记录 |
| `films/<job_id>/gradual_*.json` | 渐变候选、原始候选/NMS、近黑停留及规则诊断；不是转场真值 |
| `films/<job_id>/summary.json`与`run.json` | 逐片测量、软件、端点依据、实际完整解码状态、来源及输出SHA |
| `films/<job_id>/roundoff_recovery.json` | 极小浮点超界的原值/缓存索引/修复值，原缓存不覆盖 |
| `recovery_sources/<SHA>/` | 实际使用的修复程序和helper源码快照 |
| `extraction_complete.json`与`effective_extraction_complete.json` | 初次完成/失败及保留失败后的有效完成记录分别保存 |
| `analysis/film_measurements_and_coverage.csv` | 732行，缺失和失败分别保留，不填假测量 |
| `analysis/studio_summary_*.csv` | 全机构、黑白/彩色故事片、单厂；影片等权、合拍1/k |
| `analysis/studio_year_colour_type.csv` | 年份×标签色彩×类型的构成比较 |
| `analysis/studio_source_width.csv`与`studio_frame_cadence.csv` | 数字源尺寸和实际帧节律敏感性，不冒称历史转录条件 |
| `analysis/*relative_timeline.csv`及PNG/PDF | 100相对位置箱候选率，不等于叙事阶段 |
| `analysis/conditional_*reference.json` | 单厂、构成单元内999次置换参照及实际覆盖，稀疏时BLOCKED |
| `analysis/transient-flags-*.json` | 短暂A–B–A返回警示，可能为闪光也可能是真短插镜，不删主切点 |
| `visual_qa/` | 按机构抽片的候选五帧接触表与来源；助手观察不是独立真值 |
| `numerical_audit.json` | 逐帧PTS、独立标量硬切规则、权重和组均值审计 |
| `edge_challenge/` | 事后片中段敏感性，完整453片；不替换主结果 |
| `completion_evidence/`、`completion_receipt.json` | 测试/失败日志、各阶段来源和最终产物SHA；原失败保留 |

工程测试：`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=analysis-python .venv-m3/bin/python -m unittest discover -s analysis-python/tests -v`。当前255项通过（含只允许机器精度修复、拒绝实际超界/NaN）；真实影片结论另受人工参考覆盖、源质量及方法有效性限制。

## 已知用途边界

硬切准确率仅有《上甘岭》十分钟条件内部证据；V-only对主要色相变化的切点敏感性不足，源FPS/运动/闪光也会影响。渐变严格完整区间失败，候选密度不能给出真实淡出/叠化厂间偏好。划变、虹膜等未被本轮规则覆盖。原有人工标注没有因自动结果而改写，没有要求研究者再看或重标。

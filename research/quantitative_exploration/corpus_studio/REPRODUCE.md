# 复算与产物定位

## 2026-11-10 当前版本

当前运行是 `research-local/corpus-refresh/20261110/luminance`，最终分析目录为 `analysis/`。当前结果、三部影片的新旧视频SHA与可公开查看的CSV见[版本更新与结果](../corpus_refresh/20261110/README.md)。454个视频全部成功，保留2,390,266个时间戳观察，732条元数据中278条缺本地视频。

本次仅对《买牛、扒瓜园》《永恒的友谊》《老保管、新媳妇来了》的新版本重新提取。另451个源文件核对设备、inode、大小、mtime及ctime后，继承原测量和原收据。三部变化文件重新读取完整SHA256。`measurement_reuse.json`记录继承来源、原收据SHA与视频版本，`refresh.json`记录新旧源对应。测量参数保持原协议。

从同一批本地视频复现增量更新时，使用新输出目录，并将生成的变化清单与公开版本表中的三个SHA核对。

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=analysis-python OPENBLAS_NUM_THREADS=1 \
  .venv-m3/bin/python research/quantitative_exploration/scripts/refresh_corpus_sources.py \
  --output-directory research-local/corpus-refresh/replay-20261110 \
  --luminance-parent research-local/studio-luminance/corpus-20261026T083348Z \
  --editing-parent research-local/studio-editing/corpus-20261026T114911Z

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=analysis-python OPENBLAS_NUM_THREADS=1 \
  .venv-m3/bin/python research/quantitative_exploration/scripts/refresh_corpus_sources.py \
  --output-directory research-local/corpus-refresh/replay-20261110 --extract
```

只复算当前明暗汇总时，从新版本的逐片结果生成另一分析目录。

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=analysis-python MPLCONFIGDIR=/tmp/cinematicdx-mpl OPENBLAS_NUM_THREADS=1 \
  .venv-m3/bin/python research/quantitative_exploration/scripts/analyse_studio_corpus.py \
  --run research-local/corpus-refresh/20261110/luminance \
  --output-directory research-local/corpus-refresh/20261110/luminance/analysis_replay \
  --report-directory research-local/corpus-refresh/20261110/luminance/report_replay \
  --source-diagnostic-directory research-local/corpus-refresh/20261110/luminance/colour_label_qa

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=analysis-python OPENBLAS_NUM_THREADS=1 \
  .venv-m3/bin/python research/quantitative_exploration/scripts/audit_studio_corpus.py \
  --run research-local/corpus-refresh/20261110/luminance \
  --analysis-directory research-local/corpus-refresh/20261110/luminance/analysis_replay \
  --output-file research-local/corpus-refresh/20261110/luminance/corpus_audit_replay.json
```

24段采样验证及《上甘岭》的独立人工参考仍绑定原视频版本。新版本的三部影片另有技术探测、片头核对和色度抽样记录。色度诊断按视频SHA复用未变源的帧和记录，变化源重新抽样，片厂排除敏感性完整重算。重建增量结果需要本地原视频及父运行目录中的逐片产物。

## 2026-10-26 历史运行说明

以下命令、数量和路径记录10月版本；当前版本与结果以上方入口为准。

本次运行：`research-local/studio-luminance/corpus-20261026T083348Z`。当前结果为`analysis_final/`；`analysis/`与`analysis_revision2/`是保留的先前分析。`CURRENT_ANALYSIS.txt`指向当前版。

影片文件位于外置盘`/Volumes/Extreme SSD/Video/Chinese1949-66`。研究JSON、既有M2身份映射的绝对路径及SHA见`plan.json`；原Excel的SHA见`config.json`。完整视频SHA保存在每个`films/<job_id>/summary.json`中，软件/参数/原始PTS与结果SHA见相邻的`run.json`。影片key和源字节版本分开标识；同名文件不能自动证明身份。

没有数据库、服务、模型下载或新依赖。使用现有`.venv-m3`，环境锁文件在`analysis-python/requirements-m3.lock.txt`。图表使用本机STHeiti字体；换操作系统需显式替换字体路径，只影响图的渲染。派生NPZ和图片在Git忽略目录，不提交视频。

## 只复算分厂结果

以下从完整的454份提取收据复算，输出必须为新目录；不会重新解码全库。所有命令从仓库根目录执行。

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=analysis-python MPLCONFIGDIR=/tmp/cinematicdx-mpl OPENBLAS_NUM_THREADS=1 \
  .venv-m3/bin/python research/quantitative_exploration/scripts/analyse_studio_corpus.py \
  --run research-local/studio-luminance/corpus-20261026T083348Z \
  --output-directory research-local/studio-luminance/corpus-20261026T083348Z/analysis_replay \
  --report-directory research-local/studio-luminance/corpus-20261026T083348Z/replay_report \
  --source-diagnostic-directory research-local/studio-luminance/corpus-20261026T083348Z/colour_label_qa
```

`--report-directory`将复跑报告单独保存，避免更新当前研究报告。CSV数值应相同；收据含运行时间、报告含输出目录，所以整份收据/报告不要求逐字节相同。

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=analysis-python OPENBLAS_NUM_THREADS=1 \
  .venv-m3/bin/python research/quantitative_exploration/scripts/audit_studio_corpus.py \
  --run research-local/studio-luminance/corpus-20261026T083348Z \
  --analysis-directory research-local/studio-luminance/corpus-20261026T083348Z/analysis_replay \
  --output-file research-local/studio-luminance/corpus-20261026T083348Z/corpus_audit_replay.json
```

审计检查全部文件收据、732条key覆盖、原始元数据/Excel不变、原PTS换算、逐片标量独立累加的均值/标准差、合拍权重守恒及分厂均值。它不验证历史照明、未知拷贝或独立人类身份判断。

## 从原视频复跑提取

核心源码、输入及参数被冻结，修改后拒绝复用旧检查点。`run_corpus_luminance.py --run <目录> --workers 4`会复用当前目录内已完成且匹配的逐片收据；不要通过删除现有结果强迫复跑。

如需真正独立重提取，另建运行目录，复制已存的`plan.json`、`config.json`和通过预检的`sampling_validation.json`，核实源路径及SHA后启动；保留新旧两套输出。当前配置绑定源码SHA，不能用改过的核心代码假装同方案。全库重提取约耗时136分钟，实际依赖硬件与磁盘。本次无需再次执行。

来源诊断可独立复跑`inspect_corpus_sources.py`和`check_corpus_colour_labels.py`，均显式指定`--run`、`--analysis-directory`、新的`--output-directory`。后者只抽453×3帧，旗标是色度警示，不是已验证的原始彩色工艺分类。

## 本次主要产物

| 文件 | 含义 |
|---|---|
| `analysis_final/film_measurements_and_coverage.csv` | 732条完整覆盖；453条测量，279条缺有效视频 |
| `analysis_final/studio_summary_all.csv` | 60个元数据机构全部保留，17个有实测；合拍分数权重 |
| `analysis_final/studio_relative_timeline.csv` | 全部/故事片黑白/故事片彩色的100位置箱曲线 |
| `analysis_final/studio_temporal_scale_sensitivity.csv` | 10/30/60秒与中央10–90%敏感性 |
| `analysis_final/studio_year_colour_type.csv` | 年份×色彩标签×类型分层及覆盖 |
| `analysis_final/studio_source_width_sensitivity.csv` | 编码宽度分组；宽度不等于转录来源 |
| `identity_overrides.json` | 按实际文件SHA绑定的重复片衍生修正 |
| `duplicate_identity_review/` | 《延安游击队》的片头证据与助手核对 |
| `source_qa_revision2/` | 14张源质量图、ROI、额外《刘三姐》片头及助手观察 |
| `colour_label_qa/` | 1359帧色度诊断、14旗标、排除敏感性及助手观察 |
| `rejected_keyframe_only/` | 21/24通过的失败方案及参数，不删除 |
| `sampling_validation.json` | 统一约1Hz参考帧方案24/24固定验证片段通过 |
| `corpus_audit_final.json` | 数值/来源审计 |
| `completion_receipt.json` | 最终文件路径、检查结果与SHA，不代表历史解释已验证 |

测试命令：`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=analysis-python .venv-m3/bin/python -m unittest discover -s analysis-python/tests -v`。247项通过用于工程机制；实证主张还依赖上述真实片源、预检、数值审计及明确局限。

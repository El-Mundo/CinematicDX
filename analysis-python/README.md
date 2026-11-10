# M2：视频清点、来源登记与时间轴探测

2026-11-10当前语料结果见[版本更新与结果](../research/quantitative_exploration/corpus_refresh/20261110/README.md)。454个视频中三部变化源重新提取，451部附原收据继承，全部片厂明暗、硬切与渐变候选汇总重新计算。明暗提取全部成功，保留2,390,266个时间戳观察；732条元数据中278条缺本地视频。复现入口见[明暗](../research/quantitative_exploration/corpus_studio/REPRODUCE.md)与[编辑测量](../research/quantitative_exploration/corpus_editing/REPRODUCE.md)。下方M2/M3和人工标注实验按各自日期记录。

这组命令独立于 JavaFX 和数据库运行。需要 Python 3.9 或更新版本，以及 PATH 中可用的 `ffprobe`；不需要安装 Python 第三方包。`worker.py` 仍保留原有用途，这些命令不通过它启动。

## 1. 核实视频目录

从仓库根目录执行，并把路径替换为实际目录：

```sh
python3 analysis-python/cinematicdx_cli.py inventory \
  --root "/实际视频目录" \
  --metadata ChineseSocialistFilms49-66.json \
  --expected-count 454 \
  --probe-headers \
  --output research-local/m2/inventory-001
```

`--probe-headers` 对候选文件进行有限的容器／流信息探测，不计算全库内容校验值，也不要求全片解码；省略它只做目录与权限清点。文件扩展名对应的是“视频候选文件”，不是已核实的独立影片数量。分卷、多个版本、重复内容和缺失影片需要进一步判断。

清点不跟随符号链接，排除隐藏和系统条目；目录错误、空文件、不可读文件和探测失败都保留在报告中。文件名匹配仅提供候选，不自动赋予影片身份。`readable` 是权限检查，只有成功的技术探测才提供实际打开文件的证据，两者都不证明整部影片可完整解码。

输出：

- `inventory.json`：完整清点、候选匹配、错误以及可选的原始技术探测信息。
- `inventory.csv`：便于检查的逐文件概览。
- `run.json`：参数、软件与代码标识、元数据校验值、输出校验值和限制。

`expected_count_matches` 只比较扫描到的候选文件数。必须同时检查 `scan_complete`、错误和排除项，才能判断“454”的实际含义。

## 2. 登记一部明确识别的影片

先人工核实文件与影片的对应关系，再显式指定元数据中的 `key` 或本地目录 catalog 的 `film_key`：

```sh
python3 analysis-python/cinematicdx_cli.py ingest \
  --video "/实际视频目录/桥.mp4" \
  --metadata ChineseSocialistFilms49-66.json \
  --film-id qiao \
  --source-description "填写已知下载、拷贝或转录来源；未知部分保留未知" \
  --output research-local/m2/qiao-run-001
```

同一文件内容无论复制或改名，都会得到同一个 `video_version_id=sha256:…`。它标识完整文件字节，不等于历史拷贝、修复版本或影像内容指纹；重新封装或修改文件标签也可能产生新标识。影片身份与文件版本分开记录：研究清单默认使用 `research-inventory` 命名空间，可用 `--metadata-namespace` 明确指定；本地 catalog 使用自身的 UUID。

元数据输入支持现有研究 JSON 和本地目录模式的 `catalog.json`，均为只读。此功能不把研究 JSON 导入 Java 应用，不连接数据库，也不修改全局应用设置。

输出：

- `source_manifest.json`：影片引用、完整文件 SHA-256、原路径与实际路径、元数据来源与原始记录、视频流选择、技术时间轴和质量标记。
- `probe.json`：原始 ffprobe 结果、准确参数、软件版本和诊断信息。
- `timestamp_sample.json`：有限的开头帧样本，保留原始 PTS、time_base、有理数秒数、best-effort 时间戳及分别标示的播放偏移。
- `run.json`：此次运行的 UUID、时间、参数、代码版本／源码校验值和产物校验值。

默认保留最多 12 个帧时间戳，可用 `--timestamp-sample-frames` 调整，上限 256。多视频流没有唯一默认流时，必须用 `--stream-index` 明确选择；该数字是绝对流索引。封面图片不作为电影视频流。

ffprobe 的 `-read_intervals %+#N` 限制的是包数，不是准确帧数，因此样本可能少于请求数量；探测也可能为编码识别读取额外数据，并有超时限制。[ffprobe 官方说明](https://ffmpeg.org/ffprobe.html#Main-options)

原始时间坐标不会被平均帧率换算或静默归零。播放偏移作为派生坐标另行保存。相同的头部帧率或少量均匀时间戳不能证明整片是固定帧率，`frame_rate_mode` 因此保持 `unknown`。本步骤不做全片时间戳验证、全片解码验证、镜头检测、转码或历史来源真实性判断。

每次运行使用新的输出目录；已存在的目录拒绝覆盖。成功收据最后写入，失败不会发布成功结果。检测到输入文件或元数据在运行期间变化时，登记失败并要求重新运行。把输出放在原始视频目录之外；`research-local/` 已被 Git 忽略。

## 验证

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=analysis-python \
  python3 -m unittest discover -s analysis-python/tests -v
```

测试使用临时文件、模拟探测器以及极小的人工生成视频，不需要研究影片。人工生成视频只验证工具流程，不构成真实语料试点的完成证据。

# M3：镜头候选、时长与时间轴

M3 使用可选的隔离环境。M2 本身仍不需要这些 Python 第三方依赖：

```sh
python3 -m venv .venv-m3
.venv-m3/bin/python -m pip install -r analysis-python/requirements-m3.lock.txt
```

锁文件记录本次在 macOS ARM64 / Python 3.11.3 测试的完整环境；直接依赖见 `requirements-m3.txt`。全局 Homebrew OpenCV 在本机缺少动态库，因此不借用它。PyAV 提供原始时间戳，PySceneDetect 0.7.1 提供切点建议，Matplotlib 仅用于静态图表，没有新建界面或数据库依赖。

本次《上甘岭》的默认 HSV 色差在开头校准中出现近整秒的可疑变化；对应相邻帧画面仍连续。近灰色色偏的合成测试也复现了 HSV 误报，因此此拷贝的基线显式使用 `--luma-only`。该名称来自库，实际信号是 HSV 的 V 通道差分，并不等于经过历史校准的电影亮度。它也不保证适合其他影片。

```sh
.venv-m3/bin/python analysis-python/cinematicdx_cli.py shots \
  --manifest research-local/m2/shang-gan-ling-20261025T202349Z/source_manifest.json \
  --luma-only \
  --output research-local/m3/new-shot-run
```

可用 `--start-seconds 300 --end-seconds 420` 处理局部区间。这些参数是播放偏移，不是源 PTS；实际首尾帧、原始 ticks、time_base、派生播放偏移及所请求范围分别记录。每帧均解码并参与检测，分析图像默认缩至宽320像素，不跳帧、不改写原视频。默认 Adaptive 阈值3、最低内容变化15、最短候选间隔0.12秒均写入运行记录；过滤掉的候选也保留。Content 模式的默认阈值为27。

输出 `shots.json`、`shots.csv`、`boundaries.csv`、`summary.json` 和 `run.json`。所有切点初始标为 `unreviewed_prediction`，转场类型为待分类候选。区间采用 `[start,end)`；片段两端可能只是镜头的一部分。渐变、闪光、抖动和数字拷贝噪声仍需检查，不能把这些输出直接称为镜头真值。

时间计算始终使用 PyAV 原始 PTS 及有理数 time_base。库兼容参数中的 `fps=1` 不是影片帧率，不参与源时间重建；CFR/VFR 与 H264 B帧测试均验证了非整数秒切点不会因此取整。原拷贝0.043秒的起始偏移保持原样。

```sh
.venv-m3/bin/python analysis-python/cinematicdx_cli.py shot-report \
  --shots research-local/m3/new-shot-run/shots.json \
  --output research-local/m3/new-report
```

报告包含均值、中位数、时长分布、顺序时间轴、局部候选切换率及静态PNG/PDF。默认60秒居中窗口、15秒步长；边缘窗口以实际覆盖时长为分母。镜头时长和切换率来自同一分割，不能当作相互独立的形式发现，也不识别“度量蒙太奇”。

## 镜头边界的独立验证

```sh
.venv-m3/bin/python analysis-python/cinematicdx_cli.py boundary-reference-template \
  --shots research-local/m3/new-shot-run/shots.json \
  --output research-local/m3/new-boundary-reference
```

模板不复制预测切点。研究者应在明确的覆盖区间内独立标出所有硬切，再填写标注者、方法、独立性及区间内穷尽性声明。只复核部分影片时缩小 `coverage`；不确定的渐变可列在排除区间。不要把看着预测位置逐项修正的结果称为独立参考集。

```sh
.venv-m3/bin/python analysis-python/cinematicdx_cli.py validate-shots \
  --shots research-local/m3/new-shot-run/shots.json \
  --reference /独立标注/boundary_reference.json \
  --tolerance-seconds 0.04 \
  --output research-local/m3/new-validation
```

0.04秒只是命令示例，须按标注协议和实际帧间隔预先确定。验证采用一对一匹配，报告TP/FP/FN、precision/recall/F1、时间误差和逐项匹配。真实零切点区间的比率可为未定义，不会自动变成100%。助手或合成参考会明确标示其来源，不能冒充研究者标注。片头检查、预测引导抽查和合成测试均不能替代真实留出区间的独立验证。

# M4：独立叙事标注与对齐

```sh
.venv-m3/bin/python analysis-python/cinematicdx_cli.py annotation-template \
  --shots research-local/m3/new-shot-run/shots.json \
  --output research-local/m4/new-narrative-template
```

模板的 `events` 为空，状态是待标注；它不根据切换率生成事件。影片／视频版本绑定保持固定，叙事标注不依赖特定镜头分割版本。填写者须明确 `annotator`、`annotation_method`（human/assistant/synthetic）、`independent_of_visual_measurements` 和完成状态，并为事件填写唯一ID、起止时间、描述与确定性。地点、人物配置、叙事时间和解释备注可另行记录；事件可以重叠，也可以在镜头内部开始或结束。

事件定义需要先写入独立的研究标注协议，例如行动目标或情境发生何种变化才构成新事件，以及怎样处理地点、人物或叙事时间变化。它们不是自动的新事件判据。应在查看测量曲线之前标注，并保留争议和不确定性。视觉对象／母题也不能自动当成事件或形式属性。

```sh
.venv-m3/bin/python analysis-python/cinematicdx_cli.py align-narrative \
  --shots research-local/m3/new-shot-run/shots.json \
  --annotations /独立标注/narrative_annotations.json \
  --window-seconds 30 --control-count 3 --seed 0 \
  --output research-local/m4/new-alignment
```

输出事件与镜头的区间重叠表、事件起点的前后切换率及对照比较。开始时间不会吸附到最近切点。落在切点上的事件与同一宽泛时间区域的非事件切点匹配，去掉中心切点，排除事件窗口／对照窗口重叠；镜头内部起点和其他转场另列。时间轴三等分仅用于控制影片位置，不是三幕叙事假设。匹配数量不足、边缘截断、事件不确定及窗口重叠都会明确报告。

默认比较是每个事件起点前后各30秒的切换率变化，与匹配对照变化之差；整窗口密度作为另一项描述。控制分配是按事件时间顺序、固定随机种子的贪心匹配，只有完整匹配组才占用控制窗口。分析单位是事件起点，不是帧或重叠窗口；不生成p值或历史因果结论。尚未人工复核的镜头、助手／合成事件或未声明独立性的标注都会阻止将输出标成可直接解释的研究证据。

工具初建时只生成空模板；随后收到的真实试标及本次局部实验见下节。

### 人工标注的帧号、精度与区间边缘

2026-10-25 收到《上甘岭》02:30–12:30 的首批人工试标：11条叙事事件及50条转场记录。原Excel及原始单元格另存快照。用户随后明确确认两表在该区间内完整、独立，空白确定性表示按其规则有把握；E011持续到区间外。确认版另存，原草稿和用户原表保持不变。B050在区间外，区间内保留45个硬切及4个渐变。

“真实边界”指研究者判断事件实际开始／结束的位置。“窗口截断”指事件早于观察区间开始，或晚于观察区间结束，仅可观察部分被区间端点截住。叙事时间连续／不连续是另一种判断，不能替代这两个标签。若原填写使用了不同含义，应保留原值及填写者解释，将边界性质标为待确认，不依据时间连续性自动改标。渐变转场的边缘情况同样指其是否跨越观察区间端点。

`cinematicdx.frame_times.resolve_frame_times(manifest_path, frame_numbers, frame_base=...)` 要求显式选0或1起算；`resolve_frame_base_candidates(...)` 可在一次局部顺序解码中保留两种候选。两者均重新核对源视频完整SHA-256，按选定视频流从头枚举显示顺序的帧，保留原PTS／time_base及M2播放偏移，只处理至所需最大序号，不用帧号除以名义或平均帧率。播放器的显示帧号与解码序号的对应仍须校准，不能根据哪种换算更贴近待测模型来选择起算方式。

秒级叙事时间保留为近似秒级，不能补造毫秒或用一帧容差断言事件恰落在切点。较宽窗口的探索也须限定完整标注区间，并检查时间扰动的敏感性。原 `align-narrative` 尚未处理独立的标注覆盖范围、窗口截断字段或秒级时刻不确定性；这些记录不能直接交给全片对照流程。

### 02:30–12:30 局部试验

`cinematicdx.pilot_compare.compute_pilot_comparison(annotations, shots, manual_reference)` 是这次600秒试验的纯计算接口。它显式验证影片／视频版本、局部完整性和独立性，只在150–750秒内计算；E001的区间起点不被当作真实叙事起点，E011实际终点保持为空，仅使用观察终点750秒进行区间重叠。原先被误用的边界性质字段不进入计算。

主对照固定为事件起点前后各30秒，中心±1秒从切点计数及有效曝光同时移除。对照取同一时间三分区内的非事件硬切，要求完整、互不重叠且不复用，固定种子0、每事件1个对照。另列前后各15秒／10秒及整体起点偏移−1／0／+1秒的探索敏感性，不把它们当成独立样本或置信区间。帧号两种起算方案分别计算，不按模型分数选方案。

实算中，主±30秒设计没有可识别的匹配比较，均值保留为空，不能解读为“无关系”。零扰动的±15秒仅2组、±10秒仅3组匹配，变化量相对对照的均值方向翻转，因此不支持稳定关系推断。M3在主0.08秒容差下，两种帧号情景均为43匹配／2误报／2漏检，F1约95.56%；这是同片且已参与参数探索区间的内部验证。渐变端点表示、帧号起算和容差敏感性均另存，三处人工叠化没有被现有候选切点覆盖，不应据硬切分数宣称完整镜头分割已经可靠。

本次结果根目录为 `research-local/pilot-results/shang-gan-ling-150-750-20261025T225931Z`，其中 `analysis_design.json`、输入校验和、全部敏感性、源代码快照及 `run_m4.py` 支持复算。设计是在看过标注时间分布后确定的探索方案，非预注册验证。研究数据和产物位于未纳入Git的本地目录，重新解码仍需要同一哈希的视频版本；分析无需数据库服务。

## M3/M4 测试与平台记录

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=analysis-python \
  .venv-m3/bin/python -m unittest discover -s analysis-python/tests -v
```

本机 OpenCV 与 PyAV 各自携带的 FFmpeg 库在导入时会输出 macOS AVFoundation 同名类提示。日志应保留；本任务使用文件解码而非摄像头采集，后者未验证。运行记录保存 PyAV 内嵌库版本，不能用命令行 `ffmpeg -version` 代替。

## 渐变转场：区间候选与独立评价

渐变输出为起止区间，与原 M3 的时间点切换候选并行保存，暂不自动写回最终镜头分割。新增的 Python 接口均不依赖数据库：

- `cinematicdx.transition_features.extract_transition_features(...)`：逐帧提取固定 ROI 灰度、直方图、变化与小尺寸缓存，保存原 PTS、实际帧曝光及评价覆盖范围；不读取人工标注。
- `cinematicdx.gradual.detect_gradual_candidates(features, config=...)`：近黑单调变化和多尺度端点混合规则，保留原始候选、重叠抑制、黑场及运动诊断。分数是启发式排序，不是概率。
- `cinematicdx.transition_scores.scores_to_transition_intervals(...)`：按实际 PTS 将逐帧模型分数转换为连续区间；显式设置阈值与最低时长，不填补间隙。短事件另存，不自动判为硬切。
- `cinematicdx.transition_validation.validate_gradual_transitions(...)`：在已声明完整的覆盖区间内作精确一对一匹配，分别报告区间定位、边界误差、类型及全部未匹配候选。`point_near_span_diagnostic(...)` 只描述时间点邻近覆盖，不生成渐变 F1。

当前精确匹配器针对小规模试验，每个情景最多16段渐变参考，超出会明确拒绝；本轮只有4段。扩大评价规模时应更换可扩展的匹配实现并验证等价性，不能通过只取正例附近小窗来绕开全区间误报计分。

2026-10-26 已使用原《上甘岭》150–750秒的4段人工渐变复测。实验设计和全部预设参数在对应方法推理前冻结，但区间与标注已知，因此这是内部探索，不能称为盲测或留出验证。0/1起算两种帧号情景都保留；原 Excel、人工参考及旧切点未改。

主区间交并比 `tIoU >= 0.50` 下，规则主配置为0匹配／91未匹配候选／4漏检；外部冻结的 TransNet V2 比较为0／3／4。预训练模型三个候选位于三处标注内部，但交并比只有约0.326–0.418；第四处响应分裂成短段。不能把失败解释为完全没有变化信号。预先列明的宽松 `tIoU >= 0.30` 下，预训练为3／0／1、F1≈0.857；该敏感性结果不能替代主标准的失败。

TransNet V2 比较仅使用本机既有 TensorFlow，下载并校验作者固定提交的约36.5 MB权重，没有训练、微调或更改项目依赖。其 `many_hot` 分数经本试验的 `>0.5`、连续时长 `>=0.4秒` 转换，不实施淡出／叠化类型分类；通用评价中的未知类型不能解读为类型分类性能。模型源码、许可证、权重及环境收据放在本地研究目录，不加入普通 M3 安装要求。[作者实现](https://github.com/soCzech/TransNetV2)、[论文](https://arxiv.org/abs/2008.04838)。

完整实验位于 `research-local/gradual-pilot/experiment-20261025T233231Z`：`analysis_protocol.json`、`frozen_detector_configs.json` 与 `pretrained_comparator_protocol.json` 是设计；`run_experiment.py` 和 `run_pretrained_comparator.py` 是复算入口；`build_report.py` 从已保存结果生成静态图、逐项诊断和报告。规则法的失败参数、全部敏感性及未分类短段均保留。缓存中的 `frame_delta_seconds` 原为向后差分，规则运行器显式用 `(next_pts-pts)*time_base` 适配为向前曝光，并保存适配收据，未改原缓存。

下一步应将候选发现与完整区间估计拆开，先用已知范围的合成转场和运动／曝光负例验证机制，再冻结规则作真实区间对照。不能依据这4段参考直接补齐预测范围。本轮208项 Python 测试通过只证明实现按协议工作，尚不支持自动接受渐变为最终镜头边界，亦不支持跨影片准确率或叙事关系结论。

"""Build compact evidence artifacts and update the explicitly requested research record."""
import argparse
import csv
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
import matplotlib.pyplot as plt
from run_exploration import ROOT,fonts,contact_sheet,savefig,read,write,table,clock,sha

DOC=ROOT/'research/quantitative_exploration'


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);args=p.parse_args();run=args.run.absolute();fonts()
    q1=read(run/'Q01_editing/results.json');q2=read(run/'Q02_timeline/results.json');q3=read(run/'Q03_recurrence/results.json');q4=read(run/'Q04_face_proxy/results.json');q5=read(run/'Q05_challenges/results.json');audit=read(run/'numerical_audit.json');receipt=read(run/'run.json')
    output=run/'research_delivery';output.mkdir(exist_ok=True)
    # Blank human fields remain blank; assistant judgements are in separate files.
    review=read(run/'Q04_face_proxy/unboxed_review_selection.json')['images'];rows=[]
    for i,r in enumerate(review,1):
        rows.append(dict(review_id=f'R{i:02d}',film_key='shang gan ling',video_version_id=receipt['video_version_id'],
             representative_id=r['representative_id'],source_pts=r['image_source_pts'],time_base='1/16000',playback_seconds=r['image_playback_seconds'],image_path=r['image_path'],
             human_visible_person_count='',human_face_notes='',human_shot_scale='',human_certainty='',human_annotator='',human_review_complete=''))
    table(output/'future_human_frame_review_blank.csv',rows)
    with (run/'Q03_recurrence/representatives.csv').open(encoding='utf-8-sig') as f:reps=list(csv.DictReader(f))
    middle=[r for r in reps if float(r['fraction'])==.5]
    eligible=[(i,j) for i in range(len(middle)) for j in range(i+1,len(middle)) if int(middle[j]['interval_index'])-int(middle[i]['interval_index'])>=2
              and float(middle[j]['playback_seconds'])-float(middle[i]['playback_seconds'])>=10]
    rng=np.random.default_rng(20261026);chosen=rng.choice(len(eligible),8,replace=False)
    images=[];labels=[];pairs=[]
    for k,index in enumerate(chosen,1):
        i,j=eligible[index]
        for side,n in [('A',i),('B',j)]:
            r=middle[n];images.append(run/r['image_path']);labels.append(f'Random #{k}{side} '+clock(float(r['image_playback_seconds'])))
        pairs.append(dict(pair_id=f'random-{k:02d}',first_id=middle[i]['interval_id'],second_id=middle[j]['interval_id'],first_image=middle[i]['image_path'],second_image=middle[j]['image_path'],
                          human_composition_recurrence='',human_setting_relation='',human_certainty='',human_annotator='',human_review_complete=''))
    table(output/'future_human_recurrence_review_blank.csv',pairs)
    contact_sheet(images,labels,output/'random_recurrence_control_pairs.png',cols=4)
    write(output/'review_template_policy.json',dict(human_review_requested_now=False,blank_fields_intentional=True,
           assistant_observations_are_not_human_truth=True,random_control_selection_seed=20261026,
           purpose='Compact later independent validation sample; no request to rewatch or relabel the existing 10-minute annotation.'))
    # Conditional reference distribution and actual per-event measurements.
    with np.load(run/'Q05_challenges/controls_for_inspection.npz',allow_pickle=False) as z:controls=z['decoded_ordinal_base_0__hardcut_controls']
    events=[r for r in q5['event_absolute_changes'] if r['scenario_id'].endswith('_0')]
    fig,axes=plt.subplots(1,2,figsize=(13,4.6))
    obs=np.asarray([r['absolute_gray_change'] for r in events]);x=np.arange(len(events));lo=np.quantile(controls,.025,axis=0);hi=np.quantile(controls,.975,axis=0);median=np.median(controls,axis=0)
    axes[0].plot(x,obs,'o',color='#c56835',label='人工事件起点的变化')
    axes[0].errorbar(x,median,yerr=np.stack([median-lo,hi-median]),fmt='o',color='#245a81',capsize=4,label='普通硬切条件对照范围')
    axes[0].set_xticks(x,[r['event_id'] for r in events]);axes[0].set_ylabel('|后均值−前均值|，数字灰度0–1');axes[0].legend(fontsize=9)
    axes[1].hist(controls.mean(axis=1),bins=25,color='#d4dee7',label='1999组硬切条件对照')
    axes[1].axvline(obs.mean(),color='#c56835',lw=2,label=f'六事件均值 {obs.mean():.3f}');axes[1].set_xlabel('平均绝对数字灰度变化');axes[1].set_ylabel('条件抽样次数');axes[1].legend(fontsize=9)
    for ax in axes:ax.spines[['top','right']].set_visible(False);ax.grid(alpha=.12)
    fig.suptitle('探索发现：事件附近的明暗变化较大，但E010没有同样表现')
    fig.text(.02,.01,'前后各5秒，移除中心±1秒；条件对照范围不是置信区间，不表示总体显著性。',fontsize=9)
    fig.tight_layout(rect=[0,.035,1,.95]);savefig(fig,output/'brightness_event_controls')
    # Preserve full observed lag strata, including reversals and tiny positive sets.
    ar=[r for r in q3['lag_stratified_event_proxy_auc'] if r['fraction']==.5 and r['same_event_proxy_auc'] is not None]
    fig,ax=plt.subplots(figsize=(10,4))
    for method,color in [('dct','#245a81'),('dhash','#2b916f'),('brightness','#a26874')]:
        r=[x for x in ar if x['method']==method];ax.plot([x['lag_bin_seconds'] for x in r],[x['same_event_proxy_auc'] for x in r],'o-',label=method,color=color)
    ax.axhline(.5,color='gray',ls='--',lw=.8);ax.set_ylim(0,1.05);ax.set_xlabel('镜头代表帧间隔分层下界／秒（每层20秒）');ax.set_ylabel('同事件代理AUC；不是母题检索准确率');ax.legend()
    ax.set_title('低层相似性与叙事代理的对应随时间间隔变化，未形成稳定通用优势');ax.spines[['top','right']].set_visible(False)
    fig.text(.02,.01,'较长间隔层仅有1–2个同事件配对；配对共享镜头，不能当独立样本。',fontsize=9);fig.tight_layout(rect=[0,.03,1,1]);savefig(fig,output/'recurrence_lag_controls')
    # Log and source records are small and remain outside source control.
    for source,name in [('/tmp/cinematicdx-quantitative-tests-all.log','tests_225.log'),('/tmp/cinematicdx-quantitative-exploration.log','initial_execution.log'),('/tmp/cinematicdx-quantitative-challenges.log','followup_execution.log'),('/tmp/cinematicdx-quantitative-audit.log','audit_execution.log')]:
        shutil.copy2(source,output/name)
    links='../../'+str(run.relative_to(ROOT))
    report=f'''# CinematicDX：定量证据探索报告

日期：2026-10-26。工作分支 `codex/quantitative-evidence-20261026`。本轮已完成五项新实验/挑战，评估六项候选；达到有证据的停止条件。

最有价值的新发现是：**本片现有人工事件附近的数字明暗变化，在普通硬切条件对照下仍较大，值得进一步验证。** 这不是自动叙事识别器，也没有证实电影形式与政治语境之间的因果关系。

## 材料、独立性与范围

- 《上甘岭》(1956)，`research-inventory:shang gan ling`，视频版本 `{receipt['video_version_id']}`。实际文件来自本地外置盘，已重新计算完整SHA；原始来源/转录历史仍未知。
- 唯一分析区间为播放偏移 `[150,750)`，600秒；不分析其他影片。复用此前逐帧缓存，额外只在同一范围解码144张代表图，没有扩大30分钟上限。
- 已有M2记录显示454个视频候选头部探测成功；这是此前清点，不是454部独立影片已验证、本轮也没有重新全库扫描。
- 现有独立人工参考为45处硬切、4段渐变、11条事件；10个区间内部起点。秒级叙事时间保持原精度；E001左边缘不充当新事件，E011实际终点为空、仅观察至750秒。
- QuickTime帧号与解码帧序仍未独立校准；涉及切点的主对照保留0/1起算，不能按拟合择优。图像代表帧采样用0起算情景，明确仍有该限制。
- 原视频、原Excel、既有标注与渐变失败结果未改；没有新模型/数据下载、训练、上传、数据库操作或付费服务。
- 新方案在本轮输出前冻结，但标注区间本就已知。因此全轮是内部探索，不是盲测或预注册确认。

## 六项候选的结论

| 属性 | 理论动机 | 已实现？ | 实验证据 | 可靠性 | 本轮成本 | 叙事相关性 | 建议 |
|---|---|---|---|---|---|---|---|
| 硬切时长与顺序 | 重复、反差、节奏分布，超越全片均值 | 是，Q01 | 41个完整硬切间隔；37个有效相邻关系；分块乱序1999次 | 时间表与算术已核查；顺序主张PROVISIONAL | 约0.63秒，已有参考 | 可对齐事件；不等于叙事、注意或度量蒙太奇 | 核心保留；区间/序列/截断同时存 |
| 数字灰度均值与对比度 | 明暗对比及沿时间轴的组织 | 是，Q02/Q05 | 六个硬切关联事件均值变化0.1012，对照中位0.0185；多项挑战仍存在 | 提取VERIFIED；叙事对应PROVISIONAL | 与活动/对照合计约2.9秒，复用缓存 | 本轮最强探索线索；E010反例保留 | 核心保留，限定同一数字版本 |
| 图像活动代理 | 运动/变化分布及与剪辑关系 | 是，Q02 | 1499帧对，1427有效；相关差与光流秩相关0.932；仅4/10事件窗口足够完整 | PROVISIONAL，无真实运动标签；摄像机分类未验证 | 光流约0.83秒@64×48、2.5Hz | 现有窄窗对照被缺测阻断 | 先留廉价相关和质量旗标，光流研究性保存 |
| 配置相似性 | 视觉返回、重复、对比 | 是，Q03 | 48段×3代表帧；DCT top10仅5/7对在替换代表帧后保留；存在烟雾/战场误配 | PROVISIONAL，助手定性检查不是人类真值 | 描述符轻量；144张较大代表图解码约12.93秒 | 同事件代理结果依时间间隔改变 | 保留检索工具，不升级成母题/地点识别 |
| 正脸框大小/数量 | 人物空间显著性的候选代理 | 是，Q04 | 144张图中79张零检测；31张随参数变脸数；有躯干误框和侧脸漏检 | REJECTED：当前配置不适合人数/景别代理；原框仍为预测 | 两设置合计约3.14秒；使用现有模型 | 不能从脸框得出人物配置或角色注意 | 不进入核心测量；以后须独立框/景别参考 |
| 完整渐变起止 | 编辑过渡组织 | 既有G00，本轮不重跑 | 主tIoU≥0.5：规则0/91/4，冻结预训练0/3/4 | REJECTED：当前配置的自动完整分割用途 | 本轮0次推理 | 错误会污染时长/事件边界分析 | 单列候选与人工区间，不自动合入镜头表 |

上述状态针对明确用途：数值能够复算，不等于电影理论解释已被验证。计算时间是本机缩小图像/已有缓存条件，不能直接当作原分辨率全库预算。四项初始真实材料实验整体约{receipt['elapsed_seconds']:.2f}秒；生成报告、检验与阅读另计。

## Q01：顺序比均值多告诉了什么

保守地仅取两端都是硬切、且不跨渐变的41个间隔，合计366.763秒；均值8.945秒、中位4.960秒。**它们不是完整600秒或全片的平均镜头长度。** 其余范围因渐变相邻、观察边缘等原因不进入本项完整间隔分析。

四个连续可用块的间隔数量为6/1/7/27，块内均值约1.280/29.640/6.006/10.645秒。全段一个均值明显隐藏了这些不同节奏区域，因而保留序列和位置有描述价值。

主统计量平均绝对相邻log时长差为0.7788；保持每块时长分布和总时长的乱序中位为0.8568，2.5%–97.5%条件范围0.7060–1.0017。真实值位于条件参考约14.5%位置，并不突出。相邻log时长相关0.4931，块内乱序本身中位已有0.4010；不能只报正相关就推断精细序列原则。

后续较弱的全局乱序保留总体直方图，却混合不同块的时长，主统计量中位升至1.2147，使原顺序显得非常突出。**两种对照回答不同问题：段落之间节奏有差别，不等于段落内部有额外有序规律。** 这也是本轮重要的负/边界发现。没有拟合1/f，没有测量观众注意，没有识别蒙太奇类别。

## Q02/Q05：最值得追踪的叙事线索

数字灰度按原PTS实际曝光加权。主比较为事件起点前 `[−5,−1)` 秒与后 `[+1,+5)` 秒均值之差的绝对值，不把事件起点吸附到切点。

全部10个起点的平均变化为0.1693，共同平移事件组所得469个有效配置的中位为0.0449。但这个较弱对照混合了转场与非转场，因此不能单独支撑叙事对应。

更具体的对照只取附近1秒有硬切、又不邻近人工渐变的6个事件E006–E011。与同一时间三分区的非事件硬切匹配，保留各起点到切点的偏移，每次不复用切点；允许窗口重叠并明确不作独立样本推断。结果：

- 事件平均绝对变化 **0.101233**；1999组对照中位 **0.018460**，条件2.5%–97.5%范围 **0.010977–0.037355**。
- 逐帧原PTS积分重新计算所有亚秒级对照后，中位 **0.018576**；按既定池与不复用规则计算的最大可能对照均值 **0.042148**。因此差距不是1秒分箱或随机抽样遗漏极端配置造成的。
- 逐个去掉一个事件，剩余均值 **0.086620–0.120670**，相应条件对照上界均低于它。不能归因于某一个事件。
- 3秒/5秒窗、起点整体±1秒、全画面/ROI、1Hz近似、gamma0.8/1.2、JPEG40和较窄裁切均保留方向。10秒窗的硬切匹配池不足，明确标BLOCKED，不填“无效果”。
- 灰度标准差也有条件差异，但它与均值及场景/构图变化相关，不能把它当成第二份独立叙事证据。

同时保留反例：E010在726秒附近的变化只有约 **0.0040**，并非每个事件都出现明显明暗变化；其余六事件变化分别记录在图和CSV。

**能说的：** 在这份独立事件表及固定对照下，本片局部存在可复算的明暗重组对应，值得研究其与构图、人物配置、场所转换及剪辑的关系。

**不能说的：** 变化唯一由叙事产生，能自动识别事件，或是中国政治电影的普遍规律。对照未匹配景别、人物配置、地点或所有非平稳性；事件定义本身可能借助可见转场。数字灰度不是历史摄影照明真值，条件抽样范围不是置信区间，经验秩不是可直接发表的p值。

## Q02活动代理：廉价方法已经提供大部分粗粒度信息

1499个约0.4秒帧对中1427有效，72被标为跨切点/渐变或低纹理（类别可重叠）。像素差分与光流p90秩相关0.8956，`1−像素相关`与光流为0.9323；当前粗分辨率下，光流未展示足够独立收益，尚不能归因摄像机/人物运动。

真实图像的机制扰动表明：同帧加10个灰度级会使差分中位约0.0392，而相关差接近0；一像素平移会显著抬高两者及光流。光流即使同帧也有数值底噪。**这些是受控扰动，不是电影里实际曝光变化或胶片抖动的真值。** 无法仅据全局平移判断摇镜还是拷贝不稳。

严守95%有效曝光条件后，主窗口仅4/10个事件能完整测量活动，无法对全组计算比较；保留为空，不事后放宽阈值救结果。活动对照当前BLOCKED于缺测，方法本身PROVISIONAL。

## Q03：相似性有检索价值，语义能力尚未成立

48个完整连续内容区间，各取1/4、1/2、3/4位置，共144代表图。去DC低频DCT、dHash与仅明暗距离并列比较。非相邻top10中，DCT在替换到1/4、3/4时保留5/7对；dHash各5对；仅明暗距离0/2对。说明空间配置描述符包含明暗均值以外的信息，也说明一个代表帧不稳定。

助手检查DCT前8对，看到多组相近的单人/双人构图返回，也看到明确误配：烟雾画面与多人地形画面仅低频图样相似。检查来源标为助手，无人类检索真值，不报告精确率。

以独立事件归属作代理，并按时间间隔20秒分层：在20–40秒层，DCT/dHash/仅明暗AUC约0.707/0.696/0.363；40–60秒为0.671/0.786/0.330。但0–20秒层明暗基线更高，60秒之后结果不稳定，较远层只有1–2个同事件配对。**全部层均保留，不用有利两层证明通用叙事检索，更不等同人物、地点或母题识别。** 配对共享镜头，不能当独立样本。

## Q04：拒绝当前人数/景别代理

在144张代表图上，用已安装Haar正脸模型测试两个参数。主设置79张零检测、共87个框；31/144张（21.5%）随minNeighbors变化而改变脸数。

先看固定12张无框图、记录助手观察，再看框：发现侧脸双人图零框、双人图只一框、一个人被脸/躯干各框一次、巨框覆盖躯干/背景。故当前模型输出不适合作人数、集体构图或景别数据。**没有独立人类框/景别标注，不能给出这些任务的准确率。** 原预测和反例仍保留，不因拒绝用途而删除。

未来独立复核用12图和8对随机配对的空白CSV已生成，人类字段保持空白，与助手备注分开；不要求研究者现在补看或重标。

## 最小可辩护组合与四个解释层级

1. **属性描述：** 来源版本/原PTS/质量旗标；经独立参考检查的硬切时间；保守时长序列；固定ROI数字灰度均值与标准差。它们可审计、轻量。
2. **视觉组织：** 保留逐项顺序、局部变动及跨区间对比，使用保留恰当结构的对照；低频相似性仅作辅助检索，不把数值直接叫形式原则。
3. **视觉—叙事对应：** 独立事件层加窄窗、普通切点条件对照、时间误差及缺测处理。明暗是本轮最强候选，但关联仍PROVISIONAL。
4. **语料与历史解释：** 当前无跨片/跨版本验证、无制作关系分析，不能推断年代/机构/政治规律。后续需来源分层、独立材料、抽取验证与历史研究；本轮未实施SNA。

活动相关代理可以作为第二阶段附加，但须解决转场附近有效曝光；光流、人物数量、景别分类、自动母题和完整渐变均不列入当前核心。

## 最强下一实验

冻结这次明暗操作定义，在独立材料上检验“叙事事件附近的明暗重组是否超出普通剪辑”，并把参考细分为地点改变、人物配置改变、行动目标改变等，不由图像曲线产生标签。比较更细的景别/前置明暗匹配，保留没有视觉标志的事件与有视觉变化的非事件。此任务需要新的独立参考才可成为确认性检验；本轮不要求用户补标，也不把该未执行步骤写作已完成。

## 复现、成本与停止

代码位于本目录 `scripts/` 与 `analysis-python/cinematicdx/exploration.py`；冻结协议、缓存绑定、源代码快照、全负例、分箱、逐帧对、对照和接触表位于 [{run.name}]({links}/run.json)。原片及标注校验一致，144张代表图的PTS和实际间隔已逐一核查，时间偏差最大约0.040秒。

225项Python测试通过，其中17项新测试验证实际曝光、缺测、渐变间隙、对照、描述符及机制；它们不代替电影实证。第二份数值实现核查1999次分块乱序和原始帧积分，主事件变化最大差约5.9×10⁻¹⁴。

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=analysis-python .venv-m3/bin/python -m unittest discover -s analysis-python/tests -v

PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/cinematicdx-mpl .venv-m3/bin/python research/quantitative_exploration/scripts/replay.py --from-run {run.relative_to(ROOT)} --output research-local/quantitative-exploration/replay-001
```

复算使用已有隔离环境及相同缓存/原片；`replay-001`必须是新目录，旧输出拒绝覆盖。路径可以替换，输入哈希不能随意替换；没有隐藏的数据库或模型下载步骤。主要依赖版本、代码校验和及源文件完整SHA写入收据。

已经评估六候选、完成四项真实材料实验和一轮挑战/逐帧审计、保留失败、形成排序及后续方案。继续在同一片段调参已不增加独立效度，因此在这里停止本轮，不扩至全库。

参见[候选](CANDIDATES.md)、[实验日志](EXPERIMENTS.md)、[排序](METHOD_RANKING.md)、[后续](NEXT_STEPS.md)、[核实文献](BIBLIOGRAPHY.md)。
'''
    (DOC/'REPORT.md').write_text(report)
    ranking=f'''# 证据支持的方法排序（2026-10-26）

| 排名 | 候选 | 当前状态与证据 | 决定 |
|---|---|---|---|
| 1 | C01 硬切时间、保守时长及顺序 | 时间/分布算术VERIFIED；额外细序列组织PROVISIONAL。41间隔、37相邻关系，块内乱序不突出 | 核心数据；保留时间轴与对照，不给蒙太奇标签 |
| 2 | C02 版本内数字明暗/对比度 | 提取VERIFIED；叙事对应PROVISIONAL。硬切关联六事件0.1012，对照约0.0185，逐帧/留一/源扰动仍在 | 最强新叙事候选，条件关联不等于普遍规律 |
| 3 | C04 低频配置相似检索 | PROVISIONAL。代表帧更换保留top10中5–7对，有明确误配；明暗基线优势依间隔改变 | 辅助查找视觉关系；尚非语义母题/地点工具 |
| 4 | C03 视觉活动代理 | PROVISIONAL。相关与光流秩相关0.932；事件完整曝光仅4/10 | 首选廉价相关与缺测旗标；暂不做摄像机运动/完整事件对照 |
| 5 | C05 当前Haar脸框充当人数/景别 | REJECTED用于该用途。侧脸漏检、躯干误框；21.5%代表图计数受参数影响 | 不入核心；脸框仅保留预测状态 |
| 6 | C06 当前完整渐变自动分割 | REJECTED用于该用途。既有严格区间主评分失败 | 不再围绕4例优化，不自动改镜头表 |

排序不是跨片准确率榜单。VERIFIED仅限所述计量/数值主张；人物身份、叙事功能、注意机制、政治意义均未被自动验证。

最小组合：来源版本/PTS/质量与缺测 + 有参考的硬切/保守时长序列 + 同拷贝灰度均值/对比度 + 独立叙事事件层及条件对照。活动是可选附加，相似性是探索辅助。

完整依据：[报告](REPORT.md)。本轮输出 `{run.relative_to(ROOT)}`。
'''
    (DOC/'METHOD_RANKING.md').write_text(ranking)
    next_steps='''# 本轮停止与下一步

## 已达到停止条件

评估六候选；Q01–Q04均在真实《上甘岭》600秒材料上可执行；Q05挑战强候选，另用原帧积分作数值审计；负例、排序、可复算代码及参考样本已保留。原始视频/标注未改，未新增模型下载，不扩大语料或无限调参。

## 最强下一实验（HYPOTHESIS，尚未执行）

冻结“事件附近数字明暗重组”操作定义，在独立参考材料上与普通硬切比较；增加前置明暗、景别、人物配置或场所控制。目标不是训练自动事件识别，而是区分哪些视觉重组伴随哪些独立叙事变化。

- 核心假设：部分叙事边界有超出普通切点的明暗/空间配置重组，但存在无明暗变化的事件。
- 现有E010是具体反例；不得删掉它来提高分数。
- 新参考应区分地点、人物配置、行动目标、叙事时间变化，允许重叠与无低层视觉标志；标签不能从曲线生成。
- 需要独立材料/参考才可作确认性检验；若以后新增解码，重新遵守研究者资源上限。不要求用户现在补看或重标这10分钟。
- 当前对照只匹配时间三分区和切点邻近，未控制景别、构图与全部非平稳性，这是首要替代解释。

## 次要问题

1. 配置检索：用已准备的小型空白独立复核表验证相似构图，而非人物/象征语义；比较多个代表帧是否优于单帧。当前状态PROVISIONAL。
2. 视觉活动：先改善连续有效曝光的操作定义与人工抽检；不因主比较缺测而事后降低95%门槛。无真实运动标注时不输出摄像机类别。
3. 人物/景别：当前Haar代理拒绝；更好的模型也必须验证历史材料里的侧脸、集体与遮挡。没有批准前不下载大型模型。
4. 渐变：保留原候选和负结果，完整区间定位未解决，不把它混入已验证硬切统计。
5. 跨片/历史比较：目前无证据。先做来源分层及小样本独立验证，再考虑人员/机构关系与SNA，不能从灰度等统计直接推出政治因果。

## 当前限制

QuickTime显示帧序与解码序的0/1对应、原转录历史、逐帧人物/景别真值、语义母题真值均未解决。10秒窗对照池不足、运动事件窗口缺测已明确记录。独立复核空白模板已备好，空字段不是已完成标注。
'''
    (DOC/'NEXT_STEPS.md').write_text(next_steps)
    additions=f'''
## 本轮实际执行与结果（当前状态）

运行：`{run.relative_to(ROOT)}`。输入与输出SHA见 `protocol.json`、`run.json`、`numerical_audit.json`；双帧号方案保留。

| 实验 | 当前状态 | 真实输出与限定结论 |
|---|---|---|
| Q01 | PROVISIONAL（数值核查VERIFIED） | 41完整硬切间隔，四块6/1/7/27，均值8.945秒；相邻log差0.7788对块内乱序中位0.8568，未形成突出额外序列规律。全局乱序较弱对照会夸大差异 |
| Q02 灰度/叙事 | PROVISIONAL（提取VERIFIED） | 六硬切关联事件0.1012对条件中位0.0185；十事件共同平移较弱对照0.1693对0.0449。E010仅0.0040，不能当通用事件检测 |
| Q02 视觉活动 | PROVISIONAL；全组事件对照因缺测BLOCKED | 1499帧对、1427有效；光流与相关差秩相关0.932。只有4/10事件达到完整曝光，不填零或降低门槛 |
| Q03 | PROVISIONAL | 48连续内容区间、144代表图；DCT top10换帧保留5/7对，低频误配反例保留；同事件代理优势随间隔变，不是语义真值 |
| Q04 | REJECTED用于人数/景别代理 | 79/144零检测，31/144参数变更脸数；助手先看12无框图后见侧脸漏检/躯干误框。无独立人类准确率 |
| Q05 | PROVISIONAL，初轮后明确声明的挑战 | 任去一事件均值0.0866–0.1207；gamma/JPEG/裁切保留方向；不替换主结果 |
| 数值审计 | VERIFIED仅限数值/来源主张 | 1999次分块乱序另实现核对；原帧积分事件差<6e-14；精确控制池最大均值0.04215；144代表图PTS均核对 |

初始Q01–Q04运行约{receipt['elapsed_seconds']:.2f}秒（含源校验/已有缓存/144代表图解码），光流约0.83秒，代表图解码12.93秒，脸框两个设置3.14秒。225项测试通过不代替实证。数字源敏感性、个别事件、全部窗口和不利配对均保留，详见[完整报告](REPORT.md)。
'''
    with (DOC/'EXPERIMENTS.md').open('a') as f:f.write(additions)
    with (DOC/'CANDIDATES.md').open('a') as f:f.write('''
## 本轮实测后的更新

已对C01–C05实际运行，C06引用并保留既有失败，不重复推理。当前证据排序调整为C01/C02/C04/C03/C05/C06。C01数值可审计但细序列主张尚弱；C02是最强的新叙事对照线索；C04具有视觉配置检索价值但不稳定且无语义真值；C03与廉价相关高度重复且主事件对照缺测；当前C05用于人数/景别被明确反例否定。完整八维评估见[报告](REPORT.md)，状态和用途见[排序](METHOD_RANKING.md)。
''')
    with (DOC/'RESEARCH_LOG.md').open('a') as f:f.write(f'''
## {datetime.now(timezone.utc).isoformat()}：本轮完成并停止

- 实验目录 `{run.relative_to(ROOT)}`。Q01–Q04完成，Q05挑战及第二数值实现核查完成。实际唯一影像600秒，未扩片。
- 最强新证据是本片条件明暗重组；E010反例、低层相似性误配和人物代理失败保留。
- 顺序对照显示“全局打乱”和“保留段落差异”会得出不同强度判断；不从正相关直接推出形式原则。
- 活动窗口缺测保留为空，10秒硬切对照池不足标BLOCKED；没有事后救指标。
- 工程测试中先发现常量图DCT数值残差被归一化的问题，已在产生电影实算输出前修正为缺测。初次补充审计的说明字段重名导致未发布收据，修复字段名后通过；未变更原统计输出或阈值。
- 225项Python测试通过；原片/原Excel/参考SHA一致；144图PTS核查通过。助手观察与研究者标注明确分开，未来人工表保持空白。
- 不提交或推送，不接数据库，不新增依赖/模型下载。达到任务完成条件后停止同片开发，下一确认性实验仍为HYPOTHESIS。
''')
    # Complete final package inventory, including later reviews and scripts.
    source_snapshot=output/'final_source_snapshot';source_snapshot.mkdir(exist_ok=True)
    sources=[ROOT/'analysis-python/cinematicdx/exploration.py',ROOT/'analysis-python/tests/test_exploration.py']+list((DOC/'scripts').glob('*.py'))
    for source in sources:shutil.copy2(source,source_snapshot/source.name)
    artifacts=[p for p in run.rglob('*') if p.is_file() and p.name!='research_record_receipt.json']
    write(run/'research_record_receipt.json',dict(completed_at_utc=datetime.now(timezone.utc).isoformat(),
        initial_run_sha256=sha(run/'run.json'),original_annotation_sha256=read(run/'protocol.json')['inputs']['original_excel']['sha256'],
        source_and_annotation_unchanged=True,unique_source_seconds=600,tests_passed=225,completion_conditions_met=True,
        research_documents={p.name:{'sha256':sha(p)} for p in DOC.glob('*.md')},
        sources={str(p.relative_to(ROOT)):{'sha256':sha(p)} for p in sources},
        artifacts={str(p.relative_to(run)):{'sha256':sha(p),'bytes':p.stat().st_size} for p in artifacts},
        no_push_or_commit=True,models_downloaded=False,cloud_upload=False))
    print(json.dumps({'report':str(DOC/'REPORT.md'),'artifact_count':len(artifacts),'status':'Research stopping conditions met; no generalisation claim.'},ensure_ascii=False))


if __name__=='__main__':main()

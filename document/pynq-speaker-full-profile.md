# 全链路与网络内部计时操作

2026-10-26。新完整包：`soundsight_pynq_speaker_full_profile.zip`。仍解压到 `SoundSight_PYNQ_Speaker_Live`，包含原 bit/HWH、手动标定、调参、普通声源跟随入口与全部声纹依赖。模型、登记模板、阈值、PL 和硬件接口不变。新功能是诊断，不代表身份驱动转台已实现。B 全权负责接续实施与板测安排。

## 更新与第一轮

使用原来可正常启动的 SD 卡。先结束正在运行的程序，逐行执行；解压保留 logs 和 *.local.json，旧 ZIP 不覆盖。

```sh
cd /home/xilinx
sudo unzip -o /boot/soundsight_pynq_speaker_full_profile.zip -d /home/xilinx
cd /home/xilinx/SoundSight_PYNQ_Speaker_Live
sudo sh speaker-full-profile.sh check
sudo sh speaker-full-profile.sh bench
```

check 不访问硬件。bench 使用包内已有 epoch26 PCM，不需要说话，不加载位流、不开转台。依次执行“关闭诊断→打开诊断→再次关闭”，每组处理同一份约10秒音频，1/1.5/2秒窗口各算两次。新建独立 logs/full-profile-bench-*，保存 result.json 与 profile_on/network-summary.json、network-summary.md、两份 ORT 原始 JSON。原离线 speaker-profile.sh、speaker-opt.sh 保留。

bench 完成后再测真实麦克风：

```sh
sudo sh soundsight.sh pcm-check
sudo sh speaker-full-profile.sh live 1
```

需要1.5或2秒窗口时只改最后的数字。看到 SPEAKER_CAPTURE_START 后本人正常音量说话，首轮固定位置、约10秒、不换人。还没加载工程时沿用 soundsight.sh prepare；若显示另一 overlay 已注册，先核对实际加载目录，避免覆盖其他运行。所有 speaker/profile 命令不开转台。原普通自动跟随仍按方向工作，不等于按身份跟随。

## 能看到什么

| 范围 | 输出 | 计时边界 |
|---|---|---|
| 命令与启动 | result.json、capture-chain.json | 启动检查、模型/工作进程加载、DMA缓冲准备、采集、尾部推理/trace保存、录音保存；命令总时长另列 |
| 接收链路 | 原录音 result.json 的 receiver_timing、capture_cpu_profile | DMA取包/重提交、定位快照取出/消费、IPC提交、最大轮询间隔；剩余项明确保留 |
| 软件前处理 | speaker.backend_timing.detail | PCM转换、FIR及流状态维护、去均值/预加重/加窗、FFT、功率谱、Mel投影/log、VAD Run |
| 身份计算与调度 | speaker.results、cpu_profile、backend_timing | 语音覆盖率、候选/替换/开始年龄、CMN、纯网络Run、输出复制、通信调用、归一化/余弦比较、结果发布年龄与过期原因 |
| 网络内部 | network-summary.json / .md 与原始 ORT trace | CAM++ 和 Silero VAD 各自的运行次数、逐节点/算子/模块累计和最大耗时、每次网络调用耗时 |

现场日志目录 logs/full-profile-live-* 内保留 console.log、capture-chain.json、network-summary.* 和原始 trace；capture-chain.json 指向对应 logs/pcm-*/result.json、four_mic.wav、packets.bin。两个目录一起保存才有完整声音与计时关联。离线结果不冒充实麦DMA并发结果。

## 正确读数

- ORT测的是优化后的运行节点；融合后的节点不能硬拆为原始PyTorch层。能从导出名称识别的模块按 head/layer、xvector/block/transit 等汇总，无法可靠映射者保留 UNMAPPED_OR_FUSED，并单独列原始节点名/算子名。逐节点记录仍完整；模块归属不猜测。
- Session、model_run、节点和子图可能嵌套。表中exclusive只扣除同一主线程内子节点区间并集；同时保留inclusive与区间并集。线程区间交叉异常标PARTIAL。不同进程并行执行，不能把它们累计时间相加当总延迟。
- frontend含Mel/VAD；IPC调用包含C计算；FIR项包含流状态维护；纯ORT Run仍包括运行时及诊断开销。CPU秒跨线程求和，不能用墙钟减CPU推算等待。不可读schedstat保持unknown。
- 每次进程最多记录32次声纹Run、512次VAD Run，超限仍继续算法，但trace被截断、相关网络会话报告PARTIAL，整体不会报告COMPLETE。正常约10秒诊断在界内；异常退出、落盘失败、调用数不符、无网络事件不报告COMPLETE。全程静音无声纹调用显示NO_EMBEDDING_SAMPLES，不能当作声纹性能通过。
- 诊断会增加内存、计时、记录和保存开销。开关对照包含同一输入的首次调用与后续调用；比例只是本轮观察，不能据此直接校正实麦结果。原结果过期规则仍计算这些开销，不放宽期限换PASS。
- 原始trace的线程/节点耗时不是PL周期数。PL内部采集/定位延迟没有新增硬件计数器，本包不能测到麦克风声波到采样点的精确延迟，也不测舵机机械响应。来源时间仍沿用主机采集START附近单调时钟与样本序号。

## 验证边界

本包进行软件定向测试、真实录音主机对照、ARM Cortex-A9模拟数值/ORT接口验证、模拟DMA完整回放及独立只读复核。实际PYNQ上的新诊断开销、溢出状况和热点排名仍待板测。不要把主机或模拟器耗时填入板端性能表。

官方依据：[ORT profiling说明](https://onnxruntime.ai/docs/performance/tune-performance/profiling-tools.html)；实现调用当前1.17.3 C接口EnableProfiling、SessionEndProfiling，未升级Runtime。PL评估见 [PL下放事前分析](speaker-pl-offload-preanalysis.md)。

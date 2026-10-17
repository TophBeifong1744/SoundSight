# A 独立目标说话人验证原型

**当前状态：模型已固定、本机可运行、功能自测通过；真实参与者评价及独立复核尚未完成。** 本研究对应[Issue #49](https://github.com/TophBeifong1744/Competition_fpga/issues/49)，独立于四麦工程及现行验收。当前交付是第一阶段原型，不代表整批研究验收通过。

本机目录：`E:\Users\Toph Beifong\Documents\GitHub\Competition_fpga\codex_out\speaker-verification-research-20261011`。

## 入口

- [需要怎么录音](RECORDING-GUIDE.md)：最小3人/30段，原件留在本地；你提供录音目录及记录后再做真实校准和测试。
- [模型、方法与限制](MODEL-AND-METHOD.md)：ECAPA-TDNN + Silero VAD，模型/权重/依赖身份和三态规则。
- [实际执行证据](EVIDENCE.md)：26项功能检查、9次CLI调用、冷启动与稳定推理实测、未测边界。
- [后续SoundSight接入与部署建议](INTEGRATION-NOTES.md)：离线设计，不修改总工程。
- `speaker_verify.py`：主CLI；`setup.ps1`、`setup_models.py`：独立安装入口；`requirements-lock.txt`、`model-lock.json`：准确依赖与权重锁。

## 在本机直接运行

打开PowerShell，在本目录执行；环境已准备，不需激活虚拟环境或重装依赖。

```powershell
Set-Location -LiteralPath 'E:\Users\Toph Beifong\Documents\GitHub\Competition_fpga\codex_out\speaker-verification-research-20261011'
& '.\.venv\Scripts\python.exe' -X utf8 speaker_verify.py --help
& '.\.venv\Scripts\python.exe' -X utf8 speaker_verify.py info
```

登记自己的目标（录音按说明准备好以后执行）：

```powershell
& '.\.venv\Scripts\python.exe' -X utf8 speaker_verify.py enroll --id P01 --session S1 private/recordings/enroll/P01_E01.wav private/recordings/enroll/P01_E02.wav private/recordings/enroll/P01_E03.wav
& '.\.venv\Scripts\python.exe' -X utf8 speaker_verify.py list
& '.\.venv\Scripts\python.exe' -X utf8 speaker_verify.py verify --id P01 private/recordings/dev/P01_D01.wav
```

最后一条会输出真实余弦分数；未校准前，正常结果为`THRESHOLDS_NOT_CALIBRATED / 证据不足`。没有用未经研究的阈值自动做身份判断。静音、过短、无有效语音、坏文件等输出各自原因。正常三态输出退出码0；命令配置、模板、清单或文件写入错误退出码2。

模板在 `private/templates/P01.json`，重新运行CLI会自动加载。旧ID不会被覆盖。需要主动删除自己的模板时：

```powershell
& '.\.venv\Scripts\python.exe' -X utf8 speaker_verify.py delete --id P01 --yes
```

这只删除指定声纹模板，不删除原始音频。删除功能已经在本研究临时模板上实测。

多声道文件在`enroll`或`verify`中加`--channel 0`明确选择声道；不要把声道平均混合后当作已定位的单一说话人。

## 现在就能运行的流程演示

```powershell
& '.\.venv\Scripts\python.exe' -X utf8 smoke_cli.py
```

它使用本地官方示例自动创建唯一临时目标，运行登记、跨进程加载、无校准拒判、三态演示、错误参数处理及删除，并把每次调用原始输出保存在新的 `runs/cli-smoke-*` 内。演示为了覆盖三个分支会根据示例分数构造阈值，全部标记未校准；不得把这些结果当识别准确率。只删除脚本本轮创建的临时模板。

## 开发校准和最终评价

真实录音到齐后由本聊天核对、生成两个清单，使用真实匿名ID、录制时段和授权声明，不需要你手写JSON。清单格式示例在 `examples/`；示例只展示字段，不满足真实数据数量要求。

```powershell
& '.\.venv\Scripts\python.exe' -X utf8 speaker_verify.py calibrate --id P01 --manifest private/recordings/dev-manifest.json --output private/calibration-P01-v1.json
& '.\.venv\Scripts\python.exe' -X utf8 speaker_verify.py evaluate --id P01 --manifest private/recordings/test-manifest.json --calibration private/calibration-P01-v1.json --output runs/test-P01-v1.json
& '.\.venv\Scripts\python.exe' -X utf8 speaker_verify.py verify --id P01 --calibration private/calibration-P01-v1.json private/recordings/test/P01_T01.wav
```

开发清单要求`split=dev`；最终测试清单要求`split=test`。每条需有`recording_id`、`speaker_id`、`session_id`、相对清单的`path`、`usage_authorized=true`，可带`condition`及多声道的`channel`。填写`true`必须有实际使用同意/许可。

校准文件绑定模型/预处理指纹和登记模板哈希。更改模板或模型后旧阈值拒绝使用。最终测试不修改阈值，重复的登记/开发录音、复用时段和相同内容会被拒绝。输出包括目标与非目标各自分母、误接受/误拒绝、证据不足总数及分组数量、每条记录的分数/原因。结果不足以支持总体准确率或安全认证用途。

## 在另一台电脑重建

先安装可用的Python 3.12，明确给出解释器路径；不要复制本机`.venv`当作可搬移环境。

```powershell
& '.\setup.ps1' -Python 'C:\path\to\Python312\python.exe' -SmokeAssets
```

脚本只在当前研究目录建立`.venv`与缓存，从官方PyPI/PyTorch下载精确依赖，从官方固定提交取得声纹权重；不改变全局设置。日志使用新运行目录。初次安装需要网络；准备完后推理只用本地文件。缺权重/哈希不匹配会明确失败，不偷偷改用未知来源。

`setup.ps1`已在本机现有独立环境验证复用入口；尚未在另一台干净电脑重装验证。CPU版本为本轮已测基线，GPU和嵌入式运行均未测。

## 必要自测

```powershell
& '.\.venv\Scripts\python.exe' -X utf8 test_prototype.py
& '.\.venv\Scripts\python.exe' -X utf8 test_calibration_contract.py
```

每次自测保留新的测试目录。官方示例只证明模型与程序能执行；合成信号只测试输入/决策边界；真实参与者结果仍待录音。作者自测不能代替M安排的独立R复核。

## 数据与工作区

`private/`含人声、模板、清单、校准信息，默认本地保存；`runs/`可能含匿名逐条结果，默认也不发布。公开材料只用匿名汇总；上传可识别人声或模板需要另有明确许可。

本轮仅写本研究目录，没有切换共享分支，没有修改现有RTL/固件/阈值/黄金数据，没有EDA、板测或执行器控制，也没有合并/推送。正式整批交审还需要真实评价和一次非作者复核。

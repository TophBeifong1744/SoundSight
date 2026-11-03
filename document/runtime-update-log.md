# 当前集成状态 — 2026-11-03

本轮把下列历史更新整合到当前源、公共P1更新及私人完整包，submit按新材料重建。后文“尚未集成”等为当时阶段记录，当前以[本次发布](release-20261103.md)和本PR合入状态为准。

# 运行程序与更新包维护记录

更新：2026-11-03。本文件是后续合并完整代码包的核对入口，不代表记录中的改动已经合入远端main。

## 当前维护状态

- 最近增量包：`release/output/soundsight_screen_quick_boot_update.zip`，33份payload，已包含下表此前各轮修复。安装后无需倒序逐个安装旧包。
- 当前正式完整包`soundsight_pynq_3d_speaker.zip`不能因为有更新ZIP就视为已同步；下一次更新完整包时，必须接回这些源码、测试、说明和安装器变更后重新打包核对。
- 本批开发分支：`codex/screen-speaker-capture-fix`。本机工作副本位于仓库内`simulation/work/screen-speaker-fix`（临时位置，不是发布依赖）；有效文件在该checkout的`software`、`tools`、`document`正式子目录中。主checkout另有其他聊天在途修改，尚未覆盖同步这些文件；不得清理此工作副本，直至源码和证据完成提交、集成与归档。
- 当前记录的这些修复不改RTL/BD/位流，不修改声纹模型或舵机引脚。
- 删除功能只移除指定识别档案，保留历史录音/日志和他人档案；内置P01保护不删，不宣称彻底擦除个人数据。
- 屏幕启动声纹模式当前仍未附加`--speaker-stats`：保存会话摘要和有限近期结果，但无整轮声纹次数/耗时累计。CLI显式开启仍可统计。此项没有修改，不要在后续说明中误写已支持。

## 逐轮变更与验证

### 采集协作修复

- 交付包：`release/output/soundsight_screen_speaker_fix.zip`。
- 修改：CAPTURE_COOPERATIVE_V1：DMA服务检查点、采集恢复和诊断保全。
- 结果与边界：离线证据见工作分支；不能代替联合长稳验收。
- 该包维护文件（首批）：

  - `software/screen/backend.py`
  - `software/screen/ui.py`
  - `software/screen/hardware.py`
  - `software/screen/product.py`
  - `soundsight-product.sh`
  - `document/screen-product.md`
  - `software/tests/test_screen_product.py`
  - `tools/install_product.py`
  - `software/tetra3d/linux/coherent_frontend.py`
  - `software/tetra3d/linux/speaker_capture_3d.py`
  - `software/tetra3d/linux/speaker_runtime_3d.py`
  - `software/tetra3d/linux/board_3d.py`
  - `software/tetra3d/linux/capture_recovery.py`
  - `software/tetra3d/tests/test_cf1.py`
  - `software/tetra3d/tests/test_capture_recovery.py`
  - `document/screen-speaker-capture-fix.md`

### 方向筛选修复

- 交付包：`release/output/soundsight_direction_filter_update.zip`。
- 修改：CF1_PCM_GAPS_V1：在PCM连续性证据和时间界限内允许定位快照跳号，累计实际处理帧；保留异常和质量筛选。
- 结果与边界：用户已回报53项板端离线测试通过；当前修复后的声纹双轴长稳尚待回传。
- 相对上一包新增或变化文件：

  - `software/screen/backend.py`
  - `software/screen/ui.py`
  - `software/screen/hardware.py`
  - `software/tests/test_screen_product.py`
  - `tools/install_product.py`
  - `software/tetra3d/linux/coherent_frontend.py`
  - `software/tetra3d/linux/speaker_runtime_3d.py`
  - `software/tetra3d/linux/filter_3d.py`
  - `software/tetra3d/linux/client_3d.py`
  - `software/tetra3d/linux/runtime_3d.py`
  - `software/tetra3d/linux/direction_diagnostics.py`
  - `software/tetra3d/tests/test_pcm_gap_filter.py`
  - `document/cf1-pcm-gap-filter.md`

### 屏幕旋转

- 交付包：`release/output/soundsight_screen_rotation_update.zip`。
- 修改：画面及触摸同步180度；支持独立持久方向配置。
- 结果与边界：板端发现旧Pillow无textbbox：6项中1项错误。此包已由下一包修复替代，不推荐单独安装。
- 相对上一包新增或变化文件：

  - `software/screen/ui.py`
  - `software/screen/product.py`
  - `tools/install_product.py`
  - `software/tests/test_screen_rotation.py`
  - `document/screen-rotation.md`

### 旧Pillow兼容

- 交付包：`release/output/soundsight_screen_rotation_compat_update.zip`。
- 修改：实际UI文字测量增加textsize回退，保留裁切；增加旧API绘制/导航测试。
- 结果与边界：PC 7+44项通过；用户随后确认板端7项通过，画面方向和触摸正常。
- 相对上一包新增或变化文件：

  - `software/screen/ui.py`
  - `software/tests/test_screen_rotation.py`
  - `document/screen-rotation.md`

### 触屏删除声纹档案

- 交付包：`release/output/soundsight_screen_user_delete_update.zip`。
- 修改：USERS候选用户二次确认、绑定姓名和确认时档案内容；STOP/取消不删除，运行中拒绝；删活动目标清门限和目标，禁止隐式P01回退。
- 结果与边界：PC 11+7+44=62项通过；真实ZIP升级、重复安装、保留私人资料、拒绝未知修改检查通过；板端删除待验证。
- 相对上一包新增或变化文件：

  - `software/screen/backend.py`
  - `software/screen/ui.py`
  - `tools/install_product.py`
  - `software/tetra3d/linux/board_3d.py`
  - `soundsight-3d.sh`
  - `software/ps/speaker_delete.py`
  - `software/ps/speaker_targets.py`
  - `software/tests/test_speaker_delete.py`
  - `document/screen-user-delete.md`

## 证据和下一次完整包维护

工作分支内证据：

- `document/evidence/screen-speaker-capture-fix-20261103/`
- `document/evidence/cf1-pcm-gap-filter-20261103/`
- `document/evidence/screen-rotation-20261103/`（包含原失败、兼容修复和用户板端确认）
- `document/evidence/screen-user-delete-20261103/`（测试、实际包验证、界面预览）

主checkout已归档的板端筛选自测：`document/evidence/report-measurements-20261103/direction-filter-board-offline/`。

后续维护步骤：

1. 按本记录核对分支实际diff，接回代码和必要证据；保留其他聊天的独立修改，不用旧完整包反向覆盖新修复。
2. 更新完整包打包清单，尤其新增`speaker_delete.py`、`speaker_targets.py`的未选目标处理、短命令入口、新测试与说明。
3. 用最终包验证旧版本升级、重复安装、个人参数/档案/日志保留、旧Pillow兼容；核对新包实际文件与候选源码一致。
4. 分别记录PC测试、用户板端结果、完整包生成、Git提交和远端合入状态；没做的不能标已完成。
5. 后续每次代码修复都追加目的、实际文件、包名、验证、板端状态和待集成事项，不仅在聊天里口头记录。

## 屏幕快速启动 — 2026-11-03

- 包：`release/output/soundsight_screen_quick_boot_update.zip`，33份payload，继承前5轮修复。
- 屏幕开机调用prepare --quick：跳过每次重复构建/回归；保留已有库加载和ABI、HWH、时钟复位、设备互斥、故障及旧帧、触摸初始化检查。完整check/prepare保留；变更原生源码后须重新check。
- 新增首次DISPLAY_LIT/READY计时，后续运行STOP不覆盖首次值。
- 旧原件prepare约72秒、产品BOOT至READY约90秒；不等于全可省掉。快速版板端耗时待测。
- 7+15+44=66项离线测试和实际ZIP升级/重复安装/私人资料保留验证通过。
- 证据：工作分支`document/evidence/screen-quick-boot-20261103/`；使用说明：`document/screen-quick-boot.md`。
- 仅增量包已更新，完整包和远端main尚未集成。
- 本轮相对删除包新增/变化文件：

  - `software/screen/ui.py`
  - `software/screen/product.py`
  - `software/tests/test_screen_product.py`
  - `tools/install_product.py`
  - `software/tetra3d/linux/board_3d.py`
  - `software/ps/board_tools.py`
  - `software/tests/test_screen_quick_boot.py`
  - `software/tests/test_board_tools.py`
  - `document/screen-quick-boot.md`

- 快速启动板端回报：用户确认7项测试OK、重启后屏幕明显变快；定量耗时尚未回传，不能写成具体提升倍数。

## 全量集成、实测与提交资料 — 2026-11-03

- 已将6轮侧边修复的正式源码、测试和必要证据接回当前main基线；程序路径为software/screen、software/ps、software/tetra3d/linux，入口及安装器一并维护。
- package_current_runtime.py新增P1依赖，install_current_runtime.py事务内刷新PRODUCT-INSTALL；test_current_runtime.py增加产品回执和无效依赖回归，check_current_runtime_package.py检查真实完整ZIP升级、用户状态保留和开机回执。
- 公共包soundsight_screen_product_p1.zip重建；私人完整包soundsight_pynq_3d_speaker.zip同步当前源，私有模型保持原字节。包状态和测试见runtime-release-20261103，不能把旧增量测试扩写为新板测。
- 新增用户测量表、两处更正、统计CSV/JSON、原生日志、实物照与协作TXT；analyze_measurement_workbook.py和analyze_release_session.py可重复计算。
- submit依据维护MD重建七类目录，统一写作入口与三份提示词；不修改其他聊天的Word/PPT成品。公共源码/证据/更新包及submit通过本PR同步main；私人包继续独立交付。

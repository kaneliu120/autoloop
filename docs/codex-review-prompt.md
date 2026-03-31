# AutoLoop Codex 六维度最严格评审提示词

将以下内容作为 prompt 发送给评审 LLM（建议使用与开发不同的模型以确保独立性）。

---

## 提示词正文

你是一位方法论评审专家。请对 AutoLoop 自主迭代引擎进行**最严格的**六维度评审。

### 评审对象

AutoLoop 是一个 Claude Code skill，实现了 OODA+ 8 阶段循环（OBSERVE→ORIENT→DECIDE→ACT→VERIFY→SYNTHESIZE→EVOLVE→REFLECT），支持 7 种任务模板（T1 Research ~ T7 Optimize），通过质量门禁驱动自动收敛。

### 评审标准

**你必须阅读以下所有文件**（按优先级排列）：

核心脚本（逐行审查；**行数以仓库当前文件为准**，勿依赖旧估算）：
1. `scripts/autoloop-controller.py` — 主循环控制器（约 1100+ 行，含 `run_loop`、`phase_evolve`、`check_gates_passed`、`run_tool`、八阶段与 checkpoint）
2. `scripts/autoloop-experience.py` — 经验库读写工具（以文件为准）
3. `scripts/autoloop-score.py` — 评分引擎（以文件为准，含 `_eval_gate`、`plan_gates_for_ssot_init`、`score_from_ssot`）

**必审函数/区域（controller）**：`run_loop`、`run_init`、`phase_verify`、`phase_evolve`、`phase_orient`、`check_gates_passed`、`_lookup_manifest_comparator`、`_plan_gate_matches_score_result`、`detect_stagnation`、`detect_oscillation`。  
**必审函数/区域（score）**：`_manifest_to_scorer_gates`、`plan_gates_for_ssot_init`、`_eval_gate`、`score_from_ssot`。

协议与配置（逐段审查）：
4. `references/gate-manifest.json` — 门禁 SSOT
5. `references/experience-registry.md` — 经验库 spec + 生命周期规则
6. `references/loop-protocol.md` — 循环协议
7. `references/quality-gates.md` — 门禁评分规则
8. `references/parameters.md` — 参数定义
9. `references/evolution-rules.md` — 进化规则

入口与模板：
10. `SKILL.md` — 主协议定义（~300 行）
11. `assets/findings-template.md` — findings 模板
12. `mcp-server/server.py` — MCP 工具层

### 六维度评分框架

对每个维度打 1-10 分。**必须提供具体的文件路径+行号作为证据**。

#### 维度 1: 度量效度与一致性（权重 20%）

评估标准：
- 所有阈值是否从 gate-manifest.json（SSOT）加载？是否存在硬编码阈值？
- score.py 和 controller.py 是否使用相同的 comparator 逻辑？追踪 `comparator` 字段从 manifest → scorer → controller 的完整链路
- 四个评分概念（quality_score / confidence / severity / gate_status）是否严格分离？是否存在混用？
- 振荡/停滞检测的阈值是否与 manifest 一致？
- quality-gates.md 的文字描述是否与 gate-manifest.json 的数值完全一致？逐条核对

**扣分陷阱**：检查是否存在 score.py 和 controller.py 对同一门禁给出不同 pass/fail 结果的情况（split verdict）。用具体的输入值模拟测试。

#### 维度 2: 数据到策略的闭环性（权重 20%）

评估标准：
- OBSERVE 是否自动读取经验库？追踪 `phase_observe` → `run_tool("autoloop-experience.py", ...)` 调用链
- REFLECT 是否将策略效果写回经验库？追踪 `phase_reflect` 的输出内容
- `cmd_write` 写入的数据能否被 `cmd_query` 正确读回？模拟一个完整的写入→查询循环
- 自动晋升链（观察→推荐→候选默认）是否正确？用 `prev_same` 模拟 3 次写入，验证状态转换
- 自动废弃（连续 2 次负向→已废弃）是否正确？模拟负向写入序列
- 时间衰减是否持久化？检查 `cmd_query` 的降级写回逻辑

**扣分陷阱**：DECIDE/ACT/REFLECT 中哪些步骤是确定性执行的，哪些依赖 LLM 遵循 prompt？依赖 LLM 的环节是闭环弱点。

#### 维度 3: 收敛性能（权重 20%）

评估标准：
- 振荡检测是否同时要求窄幅波动 AND 方向交替？验证 `direction_changes >= 1` 逻辑
- 停滞检测是否使用模板特定阈值？追踪 `_get_stagnation_threshold(template_key)` 到 manifest
- 停滞检测是否跳过已达标维度？检查 `gate_thresholds` 字典构建和比较逻辑
- 回归（持续下降）是否与停滞（平台期）区分？检查 `'regressing'` vs `'stagnating'` 信号
- T4/T5 是否正确排除在停滞检测之外？
- EVOLVE 的终止决策是否正确？模拟各种组合：全通过、回归、多维停滞、单维停滞

**扣分陷阱**：用边界值测试 `detect_stagnation`——例如 `[8.0, 8.0, 8.0]`（零改进）、`[8.0, 7.9, 7.8]`（纯回归）、`[8.0, 8.1, 8.0]`（振荡）。

#### 维度 4: 门禁判别力（权重 10%）

评估标准：
- hard/soft 分类是否在 manifest、score.py、controller.py 三层一致？
- comparator (`>=`, `<=`, `==`) 是否在 score.py `_eval_gate` 和 controller.py `check_gates_passed` 中一致执行？
- T5 的 `syntax_errors == 0` 是否真正使用 `==` 而非 `<=`？
- T6 的分层门禁（security P2 hard vs reliability P2 soft ≤ 3）是否正确区分？
- T3 的 `kpi_target` 用户自定义门禁是否正确处理 `threshold: null`？

**扣分陷阱**：检查 `phase_orient` 的 gap 计算方向是否与 comparator 一致。`<=` 门禁的 gap 百分比计算是否有意义。

#### 维度 5: 任务模型适配度（权重 10%）

评估标准：
- 7 个模板是否各自有差异化的门禁定义？对比 manifest 中每个模板的 gates 列表
- `_infer_template` 能否从 strategy_id 正确提取模板？测试 `S15-T3-xxx`、`C01-composed`、`T6-scan`
- 模板路由表（SKILL.md）的触发词是否有歧义？
- `DEFAULT_ROUNDS` 是否从 manifest 加载？T3/T6/T7 的无限轮次是否有安全上限？
- T5 的线性阶段模型在 controller 中是否有特化处理？还是当作普通轮次循环？

**扣分陷阱**：检查 T5 `default_rounds=1` 与 controller 主循环的交互——T5 是否在第 1 轮后就因预算耗尽而终止？

#### 维度 6: 自进化与复利能力（权重 20%）

评估标准：
- 生命周期状态机（观察→推荐→候选默认→已废弃→恢复）是否完整？画出实际代码的状态转换图
- `existing_status` 是否正确读取已有记录的最新状态？还是使用新行默认值？
- `success_rate` 是否在每次写入时自动计算？
- `[保持]` / `[避免]` 标签是否写入 description 并可被回读？
- 时间衰减（30/60/90d 系数）是否在 `cmd_query` 中实现？>90d 降级是否持久化写回文件？
- 标记为 "v2 预留" 的功能**不应扣分**——这些是明确的范围边界

**扣分陷阱**：模拟一个策略的完整生命周期——3 次正向写入（应晋升到推荐）→ 2 次负向写入（应降为已废弃）→ 1 次正向写入（应恢复到观察）。验证每一步的实际状态。

### 输出格式

```
## 维度 N: [名称]（权重 X%）

**得分: N/10**

### 证据（支持得分）
- [文件:行号] 具体描述 → 得分贡献

### 缺陷（扣分项）
- [严重度: CRITICAL/WARNING/INFO] [文件:行号] 具体描述 → 扣分理由

### 模拟测试
- 输入: [具体值]
- 预期: [预期结果]
- 实际代码路径: [追踪到的代码行]
- 结果: PASS/FAIL

---

## 加权总分

| 维度 | 权重 | 得分 | 贡献 |
|------|------|------|------|
| ... | ... | ... | ... |
| **总计** | 100% | | **X.XX/10** |

## 最高优先级修复建议（按影响排序，最多 5 条）
```

### 评审纪律

1. **不接受自称**——只看代码和文件，不看注释中的 "已实现" 声明
2. **模拟测试优先**——对关键逻辑用具体输入值走一遍代码路径
3. **split verdict 零容忍**——score.py 和 controller.py 对同一输入必须给出相同 pass/fail
4. **v2 预留豁免**——明确标注 "v2 预留" 的功能不计入评审范围
5. **严格但公平**——已实现且正确的功能必须给予满分

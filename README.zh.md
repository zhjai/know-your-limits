# know-your-limits

> **让跑长任务的便宜模型知道自己几斤几两——卡住了就找高级模型搭把手，而不是硬着头皮乱猜。**

<p align="center">
  <img src="assets/banner.svg" alt="know-your-limits——便宜的工作模型在客观触发条件下把难点升级给高级模型" width="100%">
</p>

<p align="center">
  <a href="README.md">English</a> · <strong>中文</strong>
</p>

<p align="center">
  <a href="#安装"><img src="https://img.shields.io/badge/skill-know--your--limits-blue" alt="skill"></a>
  <a href="https://github.com/zhjai/agent-arena"><img src="https://img.shields.io/badge/依赖-agent--arena-e11d48" alt="requires agent-arena"></a>
  <img src="https://img.shields.io/badge/version-0.1.1-informational" alt="version">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="MIT License"></a>
</p>

为了省 token，你让一个小模型（gpt-5-mini、Claude Haiku、GLM-4.7-Flash、deepseek-v4-flash、kimi-k2.7-code-highspeed……）当主力跑长任务。它干杂活没问题——但一旦撞上硬骨头（一个怎么都修不好的 bug、一个需要判断力的方案、一个不可逆的改动），它会**信心十足地猜错方向**，把几个小时的功夫全砸进死路里。

`know-your-limits` 管的是**「什么时候」该把难点升级给高级模型**这条策略。真正发起跨模型调用的**机制**是 [`agent-arena`](https://github.com/zhjai/agent-arena)；本 skill 只负责判断**何时**拉这根升级杆，这样你只在真正需要的关头才为贵的模型买单。

适合：大型多步重构 · 全代码库范围的改动 · 各类迁移 · 无人值守的 agent 长跑 · 任何「大量杂活 + 几个硬骨头」形态的任务。

不适合：短任务 · 通篇都很硬的任务（不如直接上高级模型）· 那些随手可撤的小步骤。

适用于 **Claude Code、OpenAI Codex、Hermes Agent、OpenClaw、OpenCode、Copilot CLI** 等支持自定义 skill 与生命周期 hook 的 AI 编码 agent。

> **重要：** 本仓库是一套策略 skill 加一个轻量触发 hook。它**不会**自己安装、鉴权或调用高级模型——那是 [`agent-arena`](https://github.com/zhjai/agent-arena) 的活，而 agent-arena 又依赖宿主具备高级模型的 CLI、凭证和 shell 权限。**没装 agent-arena 时，本 skill 会退化成「标记出这个难点、转交给人」。**

本项目与 Anthropic、OpenAI 及任何模型厂商均无隶属关系。

## 核心思路：靠客观触发条件，而不是「你慌不慌？」

陷阱在于：**越是过度自信或便宜的模型，越察觉不到自己卡住了。** 问它「你确定吗？」是自我指涉——它会说「确定」，然后继续猜。

所以升级只在**客观、可观测的事件**上触发：

| 触发条件 | 何时触发 | → 升级去做什么 |
|---|---|---|
| **PLAN_REVIEW**（强制） | 一个有分量 / 有风险的任务开始时 | 动手前先审一遍方案 |
| **IRREVERSIBLE_GUARD**（强制） | 即将做改 schema / 迁移 / 删除 / 部署 / 改权限 / 加依赖 等操作 | 在做这个不可逆动作**之前**先审 |
| **PRE_DONE_REVIEW**（强制） | 准备宣告 L2/L3 任务完成时（或 L1 上的大 / 高风险 diff） | 在「完成」之前做一次真正的审查 |
| **STALL_RESCUE** | 同一个报错扛过了 2 次不同的修法 | 别再瞎猜，找根因 |
| **OSCILLATION** | 同一个文件改了 3 次，校验都没过 | 是思路错了，不是代码错了 |
| **SCOPE_DRIFT** | 第一个验收检查通过前，已动了 ≥3 个计划外模块 | 在继续扩散前先确认范围 |
| **CHECKPOINT_DEBT** | 自阶段开始 / 上个检查点起 ≥40 个动作，没过任何检查点 | 让高级模型审一下：还在正轨上吗 |
| **GATE_BLOCK** | [`agent-completion-gate`](https://github.com/zhjai/agent-completion-gate) 检查返回 BLOCKED | 修真正的病根 |

**强制**那几条不依赖模型自己有没有察觉——它们按任务等级和动作类型触发。**响应式**那几条是**由 hook 计数的**，不归模型管（便宜模型数不清自己试了几次）。

## 它具体怎么跑——一个真实例子

**场景：** 便宜模型在修一个挂掉的接口，同一个测试反复变红。

```text
第 1 次 → POST /orders → 500 "TypeError: cannot read 'id' of undefined" → 试修法 A → 还是 500
第 2 次 → 同一个报错指纹 → 试修法 B → 还是 500
          └─ hook 计数：同一报错扛过 2 次 → STALL_RESCUE 触发
```

**工作模型停止瞎猜，发起升级**（走 agent-arena，模式 `solo_red_team`，单个高级模型——有界的 bug 诊断只需一个强模型，默认 GPT/Codex）。它只发一个**最小信息包**：触发码、目标、原始堆栈 + 它试过的两个 diff——**而不是**先抛出自己的主观臆断。

**高级模型用一个紧凑、可直接执行的 schema 回复**，便宜模型照着做就行：

```yaml
status: replan
diagnosis: "这个路由上，handler 在 auth 中间件跑之前就读了 req.user。"
next_actions:
  - 把 requireAuth 注册到 /orders 路由上，放在 handler 之前
  - req.user 缺失时返回 401，而不是 500
checks:
  - npm test -- orders.spec
risks:
  - /orders 下的其他路由可能也少了同一个中间件
```

工作模型应用修复，测试通过，hook 重置卡顿计数器——而你只在**真正要紧的那一刻**为高级模型付了**一次**钱，而不是每一步都付。

## 为什么要一个 hook，而不只是一个 skill

便宜模型没法在长会话里可靠地记住「我是不是用同样的方式失败过两次」——它会数错、会找补（「这次不一样」）、还会在上下文压缩后把计数弄丢。所以可靠的搭配是 **skill + 一个轻量 hook**：

- **hook**（[`integrations/hooks/kyl_hook.py`](integrations/hooks/kyl_hook.py)）从真实的生命周期事件里维护一份小小的**升级账本**（每个报错的尝试次数、动过的文件、模块、动作数、剩余预算），并在触发条件命中时**提示升级**。它从不亲自发起高级调用、从不阻断、从不判定完成，输入非法时也只是退出 0。
- **skill** 负责那些强制升级（开始 / 不可逆 / 完成前）——这是即便没有 hook 也兜得住的底线。

没有 hook 时它仍能以**降级模式**运行（工作模型每步自报一行状态），但强制触发条件依旧是安全网。

## 配套 skill——该一起装的东西

`know-your-limits` 刻意不去重复造跨模型调用、异步问人、或「完成」裁定权这些轮子。它和这些独立 skill 协作：

| Skill | 是否必需 | 作用 | 仓库 |
|---|---|---|---|
| **agent-arena** | **必需——升级机制** | 真正发起异构高级调用（独立作答、保留异议）。没有它，本 skill 只能「标记出来转交给人」。 | [zhjai/agent-arena](https://github.com/zhjai/agent-arena) |
| experiment-grill-feishu | 可选 | 长时间**无人值守**任务的异步问人 + 完成通知，走飞书。 | [zhjai/experiment-grill-feishu](https://github.com/zhjai/experiment-grill-feishu) |
| agent-completion-gate | 可选 | **唯一**能判定工作「真正完成」的东西——这里高级模型的审查只是参考意见。gate 返回 BLOCKED 就是一个触发条件。 | [zhjai/agent-completion-gate](https://github.com/zhjai/agent-completion-gate) |
| deliberative-analysis | 可选 | 升级前的本地选项扩展——如果难点出在思路太窄，先拓宽选项，再决定要不要花钱找高级模型。随 agent-arena 仓库一起发布。 | [zhjai/agent-arena](https://github.com/zhjai/agent-arena) |
| agent-lessonbook | 可选 | 记录策略失误（升级太晚 / 太早、某个阈值要调），方便你后续调整。 | [zhjai/agent-lessonbook](https://github.com/zhjai/agent-lessonbook) |

skill 自己也会提醒你：**项目里首次使用**时它会跑一遍软初始化（见下文），检查有没有装 `agent-arena`、并主动提议把 hook 接上；只有在检测到已装 `experiment-grill-feishu` 时，才会问你飞书通知的事。

## 安装

### 一键安装（推荐）

用 [`skills`](https://github.com/vercel-labs/skills) CLI 安装——支持 Claude Code、Codex、Cursor、OpenCode 等 50+ agent：

```bash
# 1. 安装 know-your-limits（策略本体）——全局，对所有项目可用
npx skills add zhjai/know-your-limits -g -a claude-code   # 或 -a codex 等任意宿主

# 2. 【必需】安装升级机制
npx skills add zhjai/agent-arena -g -a claude-code

# 3. 【可选】走飞书的异步问人 + 完成通知
npx skills add zhjai/experiment-grill-feishu -g -a claude-code
```

把 `-a claude-code` 换成 `-a codex`（或别的 agent），或者省略 `-a` 进入交互式选择。去掉 `-g` 则装到当前项目而非全局。

> 第 2 步在实际使用中并非可选：`know-your-limits` 是「何时升级」的策略，`agent-arena` 是「如何升级」的机制。只装第 1 步的话，每次升级都会退化成「停下来问人」。

### 接上 hook（让响应式触发可靠生效）

响应式触发（STALL / OSCILLATION / SCOPE_DRIFT / CHECKPOINT_DEBT）是**由 hook 计数的**，不靠模型。把示例合并进你宿主的 hook 配置，并改对路径：

- Claude Code：[`integrations/claude-code/settings.hooks.json`](integrations/claude-code/settings.hooks.json)
- Codex：[`integrations/codex/hooks.json`](integrations/codex/hooks.json)

首次使用时，skill 会自动检查 hook 有没有接上，没接的话主动提议帮你加。

### 便宜模型：设一个 tier 环境变量

如果上下文压缩或长时间运行让模型忘了自己是便宜模型，它可能就不再升级了。直接告诉 hook：

```bash
export KYL_WORKER_TIER=cheap
codex exec "把 orders 模块迁移到新的支付 API"
```

这会启用：L2/L3 任务首次编辑前的强 PLAN_REVIEW 提示、每 20 个动作的周期提醒、以及上下文压缩前的「你是便宜模型」提醒。

### 健康检查（可选）

```bash
cd <know-your-limits-repo>
python3 scripts/kyl_doctor.py
```

检查项：skill 是否装好（know-your-limits、agent-arena **必需**；grill-feishu 可选）、hook 是否接上、`KYL_WORKER_TIER` 是否设置、config 是否存在。

### 手动安装

可移植的 `skills/<skill-name>/SKILL.md` 布局——**整个 skill 文件夹**一起拷，让随附文件跟着走。

#### Claude Code

```bash
git clone https://github.com/zhjai/know-your-limits.git
mkdir -p ~/.claude/skills
cp -R know-your-limits/skills/know-your-limits ~/.claude/skills/
# 然后用同样方式安装 agent-arena（必需）
```

#### OpenAI Codex

```bash
git clone https://github.com/zhjai/know-your-limits.git
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
cp -R know-your-limits/skills/know-your-limits "${CODEX_HOME:-$HOME/.codex}/skills/"
```

拷完后重启或重载 agent 会话，让它重新扫描 skill。不同宿主路径可能不同，以你 agent 的官方文档为准。

## 怎么触发它

和那种「调一次审一次」的 skill 不同，`know-your-limits` 是一条**常驻策略**：你打开一次，之后它基本自己跑。没有「每个 bug 都要敲一遍」的命令。它也认简称 **`kyl`**。

**1. 为本次运行打开它**——设好档位，用一句话起头：

```bash
export KYL_WORKER_TIER=cheap
```

```text
你现在是跑长任务的便宜模型。用 kyl：
难点别瞎猜，升级给高级模型。
```

（`kyl` 和全名 `know-your-limits` 通用——「用 kyl」「应用 know-your-limits」「kyl 一下这次重构」都能激活它。）

这一句话（或者干脆就是「便宜模型 + 长任务」这个事实）会让 agent 加载这个 skill。从此之后：

- **hook** 从真实事件里给触发条件计数，命中的那一刻就提示升级（同一报错失败 2 次触发 STALL，同一文件改 3 次触发 OSCILLATION……）——这些不用你开口。
- **skill** 自己发起强制审查：L2/L3 任务一开始就审方案，任何不可逆动作之前先把关，宣告「完成」之前再审一遍。

**2. 或者直接描述任务**——只要涉及便宜模型，用自然的说法它就会自己激活：

```text
这次重构挺大，我用的是便宜模型——卡住了就找高级模型，别耗几个小时瞎猜。
```

```text
kyl 一下这个迁移：用便宜模型跑，但任何不可逆的操作之前先让高级模型审一遍。
```

**你会看到：** 触发条件命中时，工作模型会停下来，通过 agent-arena 给高级模型发一个最小证据包，再带回一个紧凑的 `status / diagnosis / next_actions / checks / risks` 回复并照着执行——就是上面那个[真实例子](#它具体怎么跑一个真实例子)。项目里首次使用时，它还会问你两个快速配置问题（见下文）。

## 配置——软初始化

**项目里首次使用**时，agent 会问你几个问题，再根据你的回答写出 `state/know-your-limits/config.yaml`——不跑脚本，不填表单：

1. **工作模型档位**（若已设 `KYL_WORKER_TIER` 则跳过）——主力是不是便宜 / 小模型？
2. **高级模型**（每次都问）——难点升级给哪个模型？（默认跨厂商：Codex 工作者 → Claude，Claude 工作者 → Codex）
3. **飞书通知**（仅当检测到 `experiment-grill-feishu` 时才问）——要不要完成 + 升级的飞书提醒？

接着它会自动检查 hook 接线、没接就提议帮你加。预算上限默认 `L1:1 / L2:3 / L3:4`。`config.yaml` 随时可改——所有选项（含每个触发条件的 arena 模式与参与者数量）见 [`examples/config.example.yaml`](examples/config.example.yaml)。

## 预算——升级是稀缺工具，不是默认动作

整件事的初衷就是省钱，所以高级调用是有上限、且事先留好名额的：

- **L1**（普通）：≤1 次升级
- **L2**（长任务）：≤3 次，留 1 次给终审
- **L3**（高风险 / 不可逆）：≤4 次，留 1 次给方案审、1 次给终审
- **去重：** 同一触发 + 同一报错 + 没有新证据 → 不再重复升级
- **自适应深度：** 判断题（方案 / 不可逆 / 完成前）用两个异构模型；有界诊断（卡顿 / 反复横跳）用一个强高级模型。可在 config 里按触发条件覆盖。
- **人类兜底：** 如果高级模型也搞不定（`status: human_required`，或同一升级触发两次仍无进展），就停下来交给**你**——别让高级模型在判断题上空转。

## 和现有方案的对比

**一句话：know-your-limits 是唯一一个在运行时用客观触发条件检测「我卡住了」的系统，而不是依赖模型自评、也不是被动等超时。**

| 能力 | LiteLLM | AutoGen | Swarm | FrugalGPT | know-your-limits |
|---------|---------|---------|-------|-----------|------------------|
| **运行时卡顿检测** | ❌ | ❌ | ❌ | ❌ | ✅ |
| **客观触发条件**（非模型自评） | ❌ | ❌ | ❌ | ❌ | ✅ |
| **细粒度失败模式**（卡顿/横跳/范围） | ❌ | ❌ | ❌ | ❌ | ✅ |
| **hook 维护账本**（模型外部计数） | ❌ | ❌ | ❌ | ❌ | ✅ |
| **强制触发**（方案/不可逆/完成前） | ❌ | ❌ | ❌ | ❌ | ✅ |
| **按目标的预算** | ✅（部分） | ❌ | ❌ | ❌ | ✅ |
| **针对长任务优化** | ❌ | ❌ | ❌ | ✅（部分） | ✅ |

- **LiteLLM：** 被动 fallback（超时 / 429 / 5xx → 重试 → 换模型）。没有「我快卡住了」这种预判。
- **AutoGen / Swarm：** 显式编排。没有运行时自省，也不会自动升级。
- **FrugalGPT（斯坦福）：** 静态路由（离线训练的分类器）。降本 98%，但不是运行中动态升级。
- **置信度校准研究：** 模型自评的置信度有约 50% 的校准误差，过度自信的便宜模型尤甚——这正好佐证了「客观触发条件」这条设计。

## 什么时候别用

- **短任务**——又小又硬的话，直接上高级模型。分档只有在「大量杂活围着几个硬骨头」时才省钱。
- **宿主调不动高级模型时**——agent-arena 需要 shell + 高级模型的 CLI + 凭证。没有这些，它会退化成「标记出难点、问人」。

## 版本

当前发布线：`v0.1.x` 预览版。打了 tag 的版本见 [Releases 页面](https://github.com/zhjai/know-your-limits/releases)——要可复现安装就 pin 到某个 tag，要最新改动就跟 `main`。变更见 [`CHANGELOG.md`](CHANGELOG.md)。

## 许可证

MIT，见 [`LICENSE`](LICENSE)。可移植的 skill 文件夹内也附了一份 MIT 许可证。

# 配置指南

本项目把所有配置分成两类：

| 类别 | 保存位置 | 是否入仓库 | 用途 |
|---|---|---|---|
| **Secrets（密钥）** | GitHub Actions Secrets | ❌ 不入 | API Key、邮箱密码 |
| **运行参数** | `config.toml` | ✅ 入仓 | 订阅源、关键词、发送时间等 |

---

## 一、GitHub Actions Secrets（必填）

在你 fork 后的仓库里：**Settings → Secrets and variables → Actions → New repository secret**，逐项添加。

| Secret 名 | 必填 | 说明 |
|---|---|---|
| `LLM_API_KEY` | ✅ | 主 LLM provider 的 API Key（必须与 `config.toml` 的 `llm.provider` 对应） |
| `LLM_FALLBACK_API_KEY` | 建议 | Fallback provider 的 API Key；主 provider 挂了会自动切换 |
| `SMTP_HOST` | ✅ | SMTP 服务器地址，例如 `smtp.gmail.com` |
| `SMTP_PORT` | ✅ | SMTP 端口：`465`（SSL）或 `587`（STARTTLS） |
| `SMTP_USER` | ✅ | 发件邮箱账号 |
| `SMTP_PASS` | ✅ | **应用专用密码**（不是邮箱登录密码） |

### 1. LLM API Key 如何获取

选一个（或多个）作主/备。推荐组合：**DeepSeek（主）+ Gemini（备）**，最便宜。

#### DeepSeek（推荐，国内可直连，价格最低）

1. 打开 <https://platform.deepseek.com/>（中国大陆可直接访问）
2. 手机号注册 → 登录
3. 左侧 **API keys** → **Create new API key** → 复制（一次性展示）
4. **Top up** 充值（赠送额度用完后才扣费；日报单次 $0.01–0.02）
5. `config.toml` 对应：`llm.provider = "deepseek"`、`llm.model = "deepseek-chat"`

#### OpenAI

1. <https://platform.openai.com/api-keys>
2. 登录 → **Create new secret key** → 复制
3. 需先绑定信用卡和充值
4. `config.toml`：`llm.provider = "openai"`、`llm.model = "gpt-5.x"`（具体看你账户可用的模型）

#### Anthropic Claude

1. <https://console.anthropic.com/settings/keys>
2. 登录 → **Create Key**
3. 需充值
4. `config.toml`：`llm.provider = "claude"`、`llm.model = "claude-4-6-sonnet"`（具体模型名看官方最新文档）

#### Google Gemini（推荐作为 fallback，有免费额度）

1. <https://aistudio.google.com/apikey>
2. 用 Google 账号登录 → **Create API key** → 选一个 GCP project（或新建）
3. 免费额度大部分场景够用
4. `config.toml`：`llm.provider = "gemini"`、`llm.model = "gemini-2.0-flash"`

### 2. SMTP 发件邮箱如何配置

⚠️ **必须用"应用专用密码"，不能用邮箱登录密码。** 原因：绝大多数邮箱服务商禁止用登录密码通过 SMTP 登录。

#### Gmail（推荐，全球通用；需科学上网或让 Actions 直连 Google）

前置条件：已开启两步验证。

1. 两步验证：<https://myaccount.google.com/security> → **2-Step Verification**
2. 应用专用密码：<https://myaccount.google.com/apppasswords>
3. **App name** 填 `ai-news-digest` → **Create** → 16 位密码（空格可忽略）
4. Secrets 填：
   - `SMTP_HOST=smtp.gmail.com`
   - `SMTP_PORT=465`
   - `SMTP_USER=你的@gmail.com`
   - `SMTP_PASS=上面生成的 16 位密码`

#### QQ 邮箱（国内推荐）

1. 登录 <https://mail.qq.com/> → **设置 → 账户**
2. 找到 **POP3/IMAP/SMTP/Exchange/CardDAV/CalDAV 服务**
3. 开启 **IMAP/SMTP 服务** → 按提示短信验证
4. 系统给出**授权码**（16 位，立即保存）
5. Secrets 填：
   - `SMTP_HOST=smtp.qq.com`
   - `SMTP_PORT=465`
   - `SMTP_USER=你的@qq.com`
   - `SMTP_PASS=授权码`

#### 163 邮箱

1. 登录 <https://mail.163.com/> → **设置 → POP3/SMTP/IMAP**
2. 开启 **SMTP 服务** → 手机验证后生成**授权码**
3. Secrets 填：
   - `SMTP_HOST=smtp.163.com`
   - `SMTP_PORT=465`
   - `SMTP_USER=你的@163.com`
   - `SMTP_PASS=授权码`

#### Outlook / Hotmail

Microsoft 已废弃基础认证，需在账号里开启"应用密码"，步骤：

1. <https://account.microsoft.com/security> → **Advanced security options**
2. 创建**应用密码**
3. Secrets 填：
   - `SMTP_HOST=smtp.office365.com`
   - `SMTP_PORT=587`
   - `SMTP_USER=你的邮箱`
   - `SMTP_PASS=应用密码`

---

## 二、`config.toml`（运行参数，必填项标 ⚠️）

路径：仓库根目录的 `config.toml`。修改后提交推送即可生效，下一次 cron 就会用新配置。

### 完整字段说明

```toml
[general]
timezone = "Asia/Shanghai"                  # 所有时间相关显示以此为准
recipient_email = "REPLACE_ME@example.com"  # ⚠️ 必改为你收件的邮箱
digest_language = "zh-CN"                   # 目前只支持 zh-CN；LLM 会输出中文
```

```toml
[llm]
provider = "deepseek"              # 主 provider: openai | deepseek | claude | gemini
model = "deepseek-chat"            # 具体 model 名，要匹配 provider 的可用模型
max_output_tokens_daily = 4000     # 日报 LLM 单次最多输出 token；调大更全但更贵
max_output_tokens_weekly = 16000   # 周报预留，本实现周报复用 daily 缓存，不走 LLM
```

```toml
[llm.fallback]                     # 可选；配齐三行会在主 provider 挂掉时自动切换
provider = "gemini"
model = "gemini-2.0-flash"
# api key 从 LLM_FALLBACK_API_KEY 环境变量读
```

```toml
[daily]
send_hour_local = 8                # 日报发送的本地时间（记录用，实际时间由 workflow cron 决定）
lookback_hours = 26                # 回溯多少小时的条目（26=1 天多 2h buffer）
pre_filter_top_n = 40              # 规则打分后留多少条喂给 LLM（控制成本）
final_max_items = 25               # 邮件中最多展示多少条
```

```toml
[weekly]
send_weekday = "monday"            # 记录用
send_hour_local = 8
weekly_candidate_threshold = 8.0   # daily 运行中 LLM 打分 ≥ 此值的条目会进入周报候选池
```

```toml
[keywords]
high     = ["claude", "gpt", "agent", ...]   # 命中 +2.0 分
medium   = ["benchmark", "eval", ...]        # 命中 +1.0 分
negative = ["crypto", "nft", ...]            # 命中 −3.0 分（筛掉噪音）
```

```toml
[[sources.items]]                  # 每个订阅源一条 [[sources.items]] 块
type = "rss"                       # "rss" 或 "github_releases"
name = "OpenAI Blog"               # 展示名，会出现在邮件里
url = "https://openai.com/blog/rss.xml"  # type=rss 必填
weight = 1.0                       # 权重 0–1，官方博客建议 1.0，论坛/聚合源建议 0.5–0.7

[[sources.items]]
type = "github_releases"
name = "claude-code"
repo = "anthropics/claude-code"    # type=github_releases 必填，格式 owner/repo
weight = 0.9
```

### 只想改三处就能跑起来

第一次跑最少只改这三个地方：

1. `general.recipient_email` → 你的邮箱
2. `llm.provider` + `llm.model` → 与你 `LLM_API_KEY` 对应的 provider
3. （可选）在 `[[sources.items]]` 列表里删除你用不上的源

---

## 三、第一次部署速查

```
1. Fork GitHub 仓库 → Settings → Secrets → 添加 6 个必填 secret
2. 仓库里改 config.toml → recipient_email + llm.provider/model
3. git commit + push
4. Actions 页面 → daily-digest → Run workflow（手动触发一次，确认邮件到达）
5. 确认后不用管；cron 会每天 08:00 北京时间自动推
```

## 四、常见问题

**Q: 我不想要日报，只要周报怎么办？**
A: 禁用 `daily.yml` workflow（Actions 页面可以禁用单个 workflow），但这样周报也没东西 —— 周报完全依赖 daily 缓存的 summary。目前设计必须先有日报才有周报。

**Q: `SMTP_PORT` 填 `465 `（末尾空格）workflow 会炸吗？**
A: 会直接抛 `RuntimeError: Env var SMTP_PORT must be an integer, got '465 '`，很明显，去 Secrets 里改掉重存即可。

**Q: 想加一个 newsletter 的订阅 URL，怎么做？**
A: 大多数 newsletter 平台（Substack、Ghost、Beehiiv）都提供 RSS，在它的站点 URL 后加 `/feed` 或 `/rss` 即可。`config.toml` 加一条 `[[sources.items]]`，`type = "rss"`，填上那个 feed URL。

**Q: 一条 item 被 LLM 打了高分，但被 category cap 踢出了 `final`，会进周报吗？**
A: 会。本项目专门修过这个点：`weekly_candidate` 判定基于所有打分后的 digest，而不仅限于实际展示的 final。

**Q: fallback provider 会触发一次邮件里挂 banner 吗？**
A: 会。邮件顶部会有一行浅黄色提示 `ℹ 本期由 fallback provider (xxx) 生成`，你就知道主 provider 这天出问题了。

**Q: 首次跑没有历史数据会不会一口气推 500 条？**
A: 不会。日报只取过去 26 小时的条目，经过 pre_filter 再砍到 40 条，最后渲染 ≤ 25 条。

**Q: 我想改成每日两次推送？**
A: 在 `.github/workflows/daily.yml` 的 cron 上加一行即可：

```yaml
on:
  schedule:
    - cron: "0 0 * * *"    # 08:00 CST
    - cron: "0 12 * * *"   # 20:00 CST
```

GitHub Actions 的 cron 用 **UTC**；北京时间减 8 小时换算。

---

## 五、本地开发时的配置

本地跑 `scripts/smoke.py`（不真发邮件，只打印 HTML）也需要 SMTP 环境变量 —— 因为 `load_config` 目前对它们做强校验。最简单的是 export 假值：

```bash
export LLM_API_KEY=你真实的key
export SMTP_HOST=smtp.example.com
export SMTP_PORT=465
export SMTP_USER=x
export SMTP_PASS=x
./.venv/bin/python scripts/smoke.py > /tmp/out.html
open /tmp/out.html
```

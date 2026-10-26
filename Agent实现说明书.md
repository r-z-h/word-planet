 # 少儿英语游戏化学习平台 — Agent 实现规格书

> **版本**：v1.7（与实现同步：按套推进 / 能力测试 / 等级回访 / 词典页 / 答错展示义项）
> **变更**：v1.2 按 40 条审查意见修订；v1.3 落地 Q1 决策（方案 A）；v1.4 修复跟读分流、卡题兜底、题量节奏；v1.5 主流程单遍制；v1.6 错题练习；v1.7 同步按套推进、能力测试、等级回访、词典与义项，见 12.6。
> **执行须知（v1.2 新增，替代 v1.1 第 3–5 行）**：本规格未覆盖的歧义，**必须停下来提问，不得自行假设、不得用注释代替决策**。

---

## 0. 决策记录（已拍板，开发时不可更改）

| 编号 | 议题 | 结论 | 影响位置 |
|---|---|---|---|
| D-01 | 进度推进方式 | **方案 A 任务驱动**（v1.7 起推进单位改为「套」，见 D-17/D-18）：当天任务 = 完成一套；连续学习只看当天是否答对 ≥1 题 | 4.3、4.4、6.3、6.4、6.5、第 8 节、第 9 节 |
| D-02 | 跟读题归属 | 独立知识点（`question_type=pronunciation`），只做**单词**，不做句子 | 3、4.8、5.2、6.9、7 |
| D-03 | 错题复习范围 | 当前知识点优先，**其次跨知识点**；跟读答错**也入错题本** | 4.3、4.5、6.7 |
| D-04 | 阶段小测验 | **本期不做**，`is_quiz` 仅建列；需求侧标注 v2 | 3、5、9 |
| D-05 | 图片支持 | **本期不做**。听力、拼写只用文字/中文题干 | 3、6.8 |
| D-06 | 跨级 | **锁定等级，不跨级**。学完本级最后一个知识点即停住 | 6.3、6.10 |
| D-07 | 水平测试形态 | **整页**（`/test`），**不可重测** | 5.1、5.2 |
| D-08 | 家长报告 | 不做角色隔离，孩子账号可直接查看 | 4.7 |
| D-09 | 每日提醒 | 固定 19:00，走浏览器 Web Push，不做自定义时间 | 第 8 节 |
| D-10 | 徽章 | 保持 4 个，不按知识点批量生成 | 6.6 |
| D-11 | 等级升级 | 只能通过水平测试决定，学习过程不改变等级 | 6.2、6.10 |
| D-12 | 卡题兜底 | ~~某题累计答错 ≥ 5 次视为"已练习"~~（v1.5 已删除，见 V5-6） | 4.3、6.3 |
| D-13 | 知识点题量 | 每个知识点 **≥ 15 题**，让"一天一个知识点"成为真实节奏 | 第 7 节 |
| D-14 | 跟读出题通道 | `/question/next` 排除 `pronunciation`；当前知识点是跟读时改调 `/pronunciation/next` | 4.3、4.8、5.2 |
| D-15 | 主流程单遍制 | 答过的题不再出现（对错都算），答错只进错题本；**v1.7 起完成单位改为「套」**（见 D-17） | 4.3、4.4、6.3、6.7 |
| D-16 | 错题练习 | 本期只收集，练习入口放 v2 | 6.7 |
| D-17 | 学习推进单位 | **套**。知识点下每 15 题为一套；一套内所有题都作答过（对错不论）即完成该套，写入 `set_progress` | 3、4.3、4.11、6.3 |
| D-18 | 达标与升级门槛 | 一个知识点完成 **≥3 套**为达标；本级所有 `counts_for_gate` 的知识点都达标，才解锁能力测试 | 6.3、6.11 |
| D-19 | 不计门槛的知识点 | `counts_for_gate=false`：L1 字母表、L3 听力理解（题量固定，凑不满 3 套） | 3、7 |
| D-20 | 能力测试 | 门槛达成后开测；本级题库随机 10 题，对 8 题通过；**通过只解锁 `max_level`**，由用户选择升级或留级 | 4.12、6.12 |
| D-21 | 等级回访 | 可切回 `max_level` 以内的任意等级，`users.level` 随之改变，越级返回 409 | 4.11、6.12 |
| D-22 | 词典页 | 只查当前等级；未学优先 → 教材册序；搜索英文/中文均可；英文释义只给 L3；“已学”= 该词对应题目答对过至少一次 | 4.13、6.13 |
| D-23 | 答错展示义项 | 答错停住，展示正确答案+音标+全部义项（L3 加英文）+「下一题」；答对保持自动跳；不自动朗读；不强制停留 | 4.3、5.2、6.14 |
| D-24 | 义项来源与清洗 | 课本义取人教版词表 `data/sources/pep-words`，机械清洗后置顶并标 `source=textbook`；人工清洗清单 `data/sense_cleanup.json` 整词覆盖 | 3、7、6.13 |

---

## 1. 项目范围

前后端分离 Web 应用。用户通过链接访问，登录/注册；初次登录进入水平测试，自动分 L1/L2/L3；按等级和知识点从本地题库抽题，以不同题型呈现；持久化进度、每日任务、连续学习、错题、徽章；提供家长报告与每日提醒。

**硬约束：**

- 题目全部来自本地题库，不调用 LLM、不调用外部 AI API。
- **"不接 API"的范围（v1.2 明确）**：指不接题库 API、不接 LLM/生成式 AI API。浏览器原生的 `SpeechRecognition` / `SpeechSynthesis` / Web Push 允许使用，**但需知悉其数据流向见 1.1**。
- 密码只存哈希，不存明文。
- 语音识别/合成使用浏览器 Web Speech API。
- 前端必须可在手机与电脑浏览器访问。
- **部署必须使用 HTTPS**（v1.2 新增）。`getUserMedia`、`SpeechRecognition`、Service Worker、Web Push 均要求安全上下文，`http://` + 局域网 IP 直接不可用。
- **单 worker 部署**（v1.2 新增）：`uvicorn` 不得加 `--workers`，原因见 4.2 与第 8 节。

### 1.1 数据流向声明（v1.2 新增，需使用者知情）

| 功能 | 数据去哪 | 是否可关闭 |
|---|---|---|
| 水平测试 / 答题 / 进度 | 仅本服务数据库 | — |
| 跟读识别 | Chrome 等浏览器会将音频发送至浏览器厂商的云端识别服务 | 不支持时隐藏入口，见 5.2 |
| 每日提醒推送 | 经浏览器厂商的推送服务投递 | 用户不授权即不启用 |

---

## 2. 技术栈（固定，不得替换）

| 层 | 技术 |
|---|---|
| 前端框架 | Vue 3 |
| 构建 | Vite |
| 路由 | Vue Router |
| 状态 | Pinia |
| UI | Element Plus |
| HTTP | Axios |
| 图表 | ECharts |
| 后端框架 | FastAPI |
| 校验 | Pydantic |
| 数据库 | PostgreSQL |
| ORM | SQLAlchemy |
| 迁移 | Alembic |
| 认证 | JWT + OAuth2PasswordBearer + python-jose + passlib[bcrypt] |
| 跨域 | CORS 中间件 |
| 语音识别 | Web Speech API `SpeechRecognition` + `getUserMedia` |
| 语音合成 | Web Speech API `SpeechSynthesis` |
| 推送 | Notification API + Service Worker + Web Push + pywebpush |
| 定时 | APScheduler |
| 测试 | pytest + httpx |
| 文档 | Swagger UI / OpenAPI |

**v1.2 新增配置项**：`APP_TIMEZONE`（IANA 名称，如 `Asia/Shanghai`）、`ENABLE_SCHEDULER`（`1`/`0`），均写入 `.env.example`。

---

## 3. 数据库表结构

```sql
CREATE TABLE users (
  id UUID PRIMARY KEY,
  account VARCHAR(64) UNIQUE NOT NULL,      -- 存库前必须 strip().lower()
  password_hash VARCHAR(255) NOT NULL,
  nickname VARCHAR(64) NOT NULL,
  level VARCHAR(2) CHECK (level IN ('L1','L2','L3')),
  max_level VARCHAR(2) CHECK (max_level IN ('L1','L2','L3')),  -- v1.7：能力测试解锁到的最高等级
  has_tested BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE knowledge_points (
  id UUID PRIMARY KEY,
  level VARCHAR(2) NOT NULL CHECK (level IN ('L1','L2','L3')),
  name VARCHAR(128) NOT NULL,
  sort_order INT NOT NULL,
  question_type VARCHAR(32) NOT NULL,
  counts_for_gate BOOLEAN NOT NULL DEFAULT TRUE,   -- v1.7：是否计入本级能力测试门槛
  UNIQUE (level, sort_order)
);

CREATE TABLE questions (
  id UUID PRIMARY KEY,
  knowledge_point_id UUID NOT NULL REFERENCES knowledge_points(id),
  question_type VARCHAR(32) NOT NULL,
  stem TEXT NOT NULL,
  options JSONB,
  answer TEXT NOT NULL,
  explanation TEXT,                                  -- v1.6：答错展示的解析
  set_no INT NOT NULL DEFAULT 1,                     -- v1.7：属于第几套（15 题一套）
  difficulty INT NOT NULL DEFAULT 1 CHECK (difficulty BETWEEN 1 AND 3),
  is_quiz BOOLEAN NOT NULL DEFAULT FALSE,
  UNIQUE (knowledge_point_id, stem)
);

CREATE TABLE progress (
  user_id UUID PRIMARY KEY REFERENCES users(id),
  current_knowledge_point_id UUID REFERENCES knowledge_points(id),
  completed_knowledge_points JSONB NOT NULL DEFAULT '[]',   -- UUID 字符串数组，必须去重
  last_question_id UUID REFERENCES questions(id),            -- v1.5：未作答、下次进 /play 要恢复的题
  test_seen_question_ids JSONB NOT NULL DEFAULT '[]',        -- v1.5：水平测试出过的题，学习阶段优先避开
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE attempts (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  question_id UUID NOT NULL REFERENCES questions(id),       -- v1.2：改为 NOT NULL
  question_type VARCHAR(32) NOT NULL DEFAULT 'question',
  idempotency_key VARCHAR(64),                              -- v1.2 新增，见 4.3
  is_correct BOOLEAN NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (user_id, idempotency_key)
);

CREATE TABLE streaks (
  user_id UUID PRIMARY KEY REFERENCES users(id),
  current_streak INT NOT NULL DEFAULT 0,
  longest_streak INT NOT NULL DEFAULT 0,
  last_study_date DATE
);

CREATE TABLE wrong_questions (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  question_id UUID NOT NULL REFERENCES questions(id),
  error_count INT NOT NULL DEFAULT 1,
  consecutive_correct INT NOT NULL DEFAULT 0,
  last_wrong_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (user_id, question_id)
);

CREATE TABLE badges (
  id UUID PRIMARY KEY,
  code VARCHAR(32) UNIQUE NOT NULL,
  name VARCHAR(64) NOT NULL,
  condition_type VARCHAR(32) NOT NULL,
  condition_value INT NOT NULL
);

CREATE TABLE achievements (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  badge_id UUID NOT NULL REFERENCES badges(id),
  earned_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (user_id, badge_id)
);

CREATE TABLE daily_tasks (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  task_date DATE NOT NULL,
  is_completed BOOLEAN NOT NULL DEFAULT FALSE,
  UNIQUE (user_id, task_date)
);

CREATE TABLE push_subscriptions (
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  endpoint VARCHAR(512) UNIQUE NOT NULL,                    -- v1.2：从 JSONB 提为独立列
  subscription JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE set_progress (                                 -- v1.7：按套推进的完成记录
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  knowledge_point_id UUID NOT NULL REFERENCES knowledge_points(id),
  set_no INT NOT NULL,
  correct_count INT NOT NULL DEFAULT 0,
  total_count INT NOT NULL DEFAULT 15,
  completed_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (user_id, knowledge_point_id, set_no)
);

CREATE TABLE level_tests (                                  -- v1.7：本级能力测试结果
  id UUID PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES users(id),
  level VARCHAR(2) NOT NULL,                                -- 被测试的等级（测的是本级内容）
  score INT NOT NULL DEFAULT 0,
  total INT NOT NULL DEFAULT 10,
  passed BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE words (                                        -- v1.7：词典页
  id UUID PRIMARY KEY,
  word VARCHAR(128) UNIQUE NOT NULL,                        -- 小写，唯一
  display VARCHAR(128) NOT NULL,                            -- 展示形式（保留原大小写）
  level VARCHAR(2) NOT NULL,
  grade VARCHAR(32) NOT NULL DEFAULT '',
  order_index INT NOT NULL DEFAULT 0,                       -- 教材册序 × 10000 + 册内序号
  phonetic VARCHAR(128),
  senses JSONB NOT NULL DEFAULT '[]',                       -- [{"text": ..., "source": "textbook"|"dict"}]
  definition_en TEXT,                                       -- 英文释义（只给 L3 下发）
  is_phrase BOOLEAN NOT NULL DEFAULT FALSE
);
```

**字段口径（v1.2）：**

- `attempts.question_type`：普通答题写 `'question'`；跟读写 `'pronunciation'`。**连续学习与每日提醒的统计**只算 `is_correct=true`，不区分类型（v1.3：每日任务已不是计数制，不再适用此句）。
- `attempts.idempotency_key`：前端为每次答题生成一个 UUID，重试复用同一个值。服务端遇重复键**直接返回首次结果，不再计数**（见 4.3）。
- `wrong_questions.consecutive_correct`：连续答对次数。答错重置为 0，答对 +1；**达到 2 视为已掌握**，退出错题优先队列与默认错题本。
- `questions.options`：**结构固定（v1.2 定义）**。选择题为对象 `{"A": "文本", "B": "文本", "C": "文本", "D": "文本"}`，key 固定大写 A–D；非选择题（`spelling`、`pronunciation`）为 `NULL`。
- `questions.answer`：**选择题存选项 key 单个大写字母**（如 `"A"`）；`spelling` 存标准英文拼写；`pronunciation` 存目标单词的英文拼写；`listening` 同选择题。
- `questions.difficulty`：1/2/3 分别对应 L1/L2/L3 难度，**水平测试按此字段分层抽题**（见 4.2）。学习路径不使用此字段。
- `knowledge_points.question_type` 必须与其下所有 `questions.question_type` 一致。种子脚本与运行时抽题均需校验，不一致按数据错误处理。
- `questions.is_quiz`：**预留字段，本期不实现任何 `/quiz/*` 接口与前端页面**。只建列、默认 `FALSE`。
- `badges.condition_value`：`streak` 类型为天数，`answer_correct` 类型为题目数；**`complete_kp` 类型忽略此字段**（固定填 `1` 占位），判定逻辑见 6.6。

**v1.7 补充口径：**

- `questions.set_no`：题所属的套号，从 1 起；同一知识点的题按题干顺序每 15 题一套。抽题与完成判定都按 `(knowledge_point_id, set_no)` 定位。
- `questions.explanation`：答错时展示的解析文本，所有题必须填写（种子脚本会检查）。
- `knowledge_points.counts_for_gate=false` 的知识点不计入本级能力测试门槛，但照样能学、照样记 `set_progress`。
- `users.max_level`：初始等于水平测试定的 `level`；能力测试通过后上调。`/api/lesson/switch-level` 与 `/api/level-test/choose` 都以它为上限。
- `progress.last_question_id`：每次 `/question/next`、`/pronunciation/next` 写入；答完即清空。它的作用是中途退出后回到同一道题。
- `attempts.question_type`：`question`（主流程）/ `pronunciation`（跟读）/ `practice`（错题练习）。**`practice` 不计入套完成、知识点达标与每日任务**。
- `words.senses`：数组，元素为 `{"text": str, "source": "textbook"|"dict"}`；**第一条必须是课本义**（`source=textbook`），人工清洗清单可以整体替换某词的义项列表。

---

## 4. API 接口规格

所有接口前缀 `/api`。除注册、登录外，均需 `Authorization: Bearer <token>`。

**统一鉴权语义（v1.2 新增）：**

- 缺少或无效 token → `401`，响应体 `{ "detail": "未登录" }`。
- token 过期 → `401`，响应体 `{ "detail": "登录已过期", "code": "TOKEN_EXPIRED" }`，前端据此跳转 `/login?expired=1` 并提示。
- 已登录但 `has_tested=false`，访问除 `/api/me`、`/api/test/*`、`/api/progress`（只读）以外的业务接口 → `409`，响应体 `{ "detail": "尚未完成水平测试", "code": "NOT_TESTED" }`。**前端守卫不能替代后端校验。**

### 4.1 认证

**POST /api/register**

- 请求：`{ "account": str, "password": str, "nickname": str }`
- 响应：`{ "user_id": str, "access_token": str, "token_type": "bearer", "has_tested": false, "level": null }`
- 规则：
  - `account` 先 `strip().lower()` 再查重与存库；长度 3–64；`password` 长度 6–72（bcrypt 上限）。
  - bcrypt 哈希存储。
  - 同一事务内插入：`users`、`progress`（`current_knowledge_point_id` 为 `NULL`，`completed_knowledge_points` 为 `[]`）。
  - **v1.2**：注册直接返回 token，前端无需再调一次登录。

**POST /api/login**

- 请求：`{ "account": str, "password": str }`（account 同样归一化）
- 响应：`{ "access_token": str, "token_type": "bearer", "has_tested": bool, "level": str|null }`
- 规则：校验哈希；签发 JWT，有效期 7 天。

**GET /api/me**

- 响应：`{ "user_id", "nickname", "level", "has_tested" }`

### 4.2 水平测试

**POST /api/test/start**

- 响应：`{ "question": { "id", "question_type", "stem", "options" }, "question_index": int }`
- 规则（v1.2 重写抽题规则）：
  - 起始估计等级 `L2`（对应 `difficulty=2`）。
  - 抽题池：`questions.question_type IN ('letter','word','spelling','listening')`，**排除 `pronunciation`**。
  - **按 `difficulty` 分层抽题**：优先从 `difficulty = 当前估计等级对应值` 的题池抽取；该档题池耗尽时，依次放宽到相邻档。
  - 单次测试最多 10 题；题池不足 10 题时以题池容量为上限。
  - 同一次测试内不重复抽题。
  - 无 `difficulty` 分层时，低龄用户会被随机抽到高难度题并一路掉级——这是 v1.1 的实际缺陷，不得回退。

**【v1.1 保留】测试会话状态**

- 存放在进程内字典 `test_sessions: dict[user_id, TestState]`，`TestState = {level: str, answered: int, used_question_ids: set[str], last_level: str, unchanged_streak: int}`。
- 进程重启即丢失：用户重新登录时 `has_tested=false`，重新开始测试。
- **仅支持单 worker 部署**（`uvicorn` 不加 `--workers`）。
- 同一用户重复调用 `/test/start` 时覆盖重置会话。

**POST /api/test/answer**

- 请求（v1.2：删除 `question_index`）：`{ "question_id": str, "answer": str }`
- 响应：`{ "is_finished": bool, "next_question": {...}|null, "level": str|null }`
- 规则：
  - 答对：当前估计等级 +1（上限 L3）；答错：−1（下限 L1）。
  - 答满 10 题，或等级连续 3 题不变，测试结束。`unchanged_streak` 判定见 6.2。
  - 结束时：写 `users.level`、`has_tested=true`；同时把 `progress.current_knowledge_point_id` 设为**该等级下 `sort_order` 最小**的知识点，`completed_knowledge_points` 保持 `[]`。
  - 判题：后端按 4.3 的归一化规则比对 `questions.answer` 与提交值。
  - **不写 `attempts`**（水平测试不计入学习数据、任务、错题、徽章）。
  - 测试不可重测：`has_tested=true` 的用户调用 `/test/start` 返回 `409`，`code = "ALREADY_TESTED"`。

### 4.3 题库与答题

**GET /api/question/next**

- 查询参数：`?exclude_id=<逗号分隔的题目 id>`（可选，前端「跳过」用；被排除的题本次不再返回）。
- 当前知识点取自 `progress.current_knowledge_point_id`，出题范围是**当前未完成的套**。
- 响应：`{ "question": { "id", "question_type", "stem", "options", "knowledge_point_id" }, "set_no", "set_total", "set_done", "knowledge_point_name" }`
- 规则：
  1. 前置校验：`has_tested=false` → `409 NOT_TESTED`；`current_knowledge_point_id` 为 `NULL` → `409 NO_CURRENT_KNOWLEDGE_POINT`。
  2. **恢复未答完的题**（v1.5）：若 `progress.last_question_id` 指向当前知识点、且该题尚未作答，直接返回它。中途退出后重新进入应看到同一道题。
  3. 否则取该知识点**没做过**的题（`attempts` 中无记录），优先避开水平测试出过的题（`progress.test_seen_question_ids`）。
  4. 被"测试题"挤空时，允许出测试出过但没做过的题，否则知识点会因凑不满题目数而永远无法完成（v1.5）。
  5. 仍无则取该知识点任意题（兜底，正常不会走到）。
  6. **不再重复出答过的题**：答错的题只进错题本，不回主流程（v1.5，D-15）。
  7. **该知识点下无任何题目时，返回 `409`，`code = "EMPTY_KNOWLEDGE_POINT"`，并记录错误日志。禁止静默推进知识点**。
  8. 返回的 `question.question_type` 必须等于该知识点的 `question_type`，否则按数据错误返回 500 并记日志。
  9. **排除跟读（v1.4，D-14）**：抽题池必须排除 `question_type = 'pronunciation'`。若当前知识点的 `question_type` 为 `pronunciation`，本接口返回 `409`，`code = "USE_PRONUNCIATION_ENDPOINT"`，前端改调 4.8 的 `/api/pronunciation/next`。
     - 原因：本接口的响应**不包含 `answer`**，而跟读判题在前端，必须拿到标准答案，只能走 4.8。

**POST /api/answer/submit**

- 请求：`{ "question_id": str, "answer": str, "idempotency_key": str }`
- 响应：`{ "is_correct": bool, "correct_answer": str, "progress_advanced": bool, "current_knowledge_point": {...}, "new_badges": [...], "duplicated": bool, "answer_text": str|null, "word": {...}|null }`
- **v1.7 新增字段（答错展示义项，D-23）**：
  - `progress_advanced`：**表示"完成了一套"**（v1.7 起不再是"完成知识点"）。
  - `answer_text`：正确答案的展示文本（选择题取正确选项内容，拼写/跟读取 `answer`）。
  - `word`：`{ "word", "phonetic", "senses": [{"text","source"}], "definition_en" }`；`definition_en` **只对 L3 单词下发**。字母题查不到单词时 `word = null`，但 `answer_text` 仍有值。
  - 幂等重放（`duplicated=true`）同样返回 `answer_text` 与 `word`。
- **判题规则（归一化，唯一实现处）**：
  - 取 `questions.answer` 与提交的 `answer` 各自 `strip().lower()` 后比较。
  - 选择题（`letter`/`word`/`listening`）提交选项 key（`"A"`/`"B"`/`"C"`/`"D"`），服务端转大写后比较。
  - 拼写题（`spelling`）提交原始输入。
  - 响应 `correct_answer` 返回标准答案（选择题返回 key，同时可用 `options` 回显文本）。
- **幂等（v1.2 新增）**：先按 `(user_id, idempotency_key)` 查 `attempts`；已存在则**直接返回上次结果**并置 `duplicated=true`，不重复写任何表。`idempotency_key` 缺失 → `422`。
- 规则（下列步骤必须在**同一数据库事务**内完成）：
  1. 写入 `attempts`（`question_type` 记 `'question'`）。
  2. 答错：写/更新 `wrong_questions`（`error_count += 1`，`consecutive_correct = 0`）。答对且该题在错题本中：`consecutive_correct += 1`。
  3. **创建当日 `daily_tasks` 行**（`INSERT ... ON CONFLICT (user_id, task_date) DO NOTHING`）。缺行会导致任务永远无法完成（v1.2 修复 A1）。
  4. **判断当前套是否完成**（v1.7，D-17）：当前套下的题，该用户**做过的不同题目数**（`COUNT(DISTINCT question_id)`，对错都算，排除 `practice`）≥ 该套题目数时，该套完成。
     - 理由：主流程只过一遍、答错不回头，若仍要求"全部答对"，套将永远无法完成。
     - 掌握度不由完成判定承担，改由错题本练习承担（4.10）。
  5. **套完成后**（v1.7）：
     - 写入 `set_progress`（`UNIQUE (user_id, knowledge_point_id, set_no)`，重复不再新增）；
     - 当日 `daily_tasks.is_completed` 置 `true`；
     - 该知识点累计完成套数 ≥ 3 时，把知识点加入 `completed_knowledge_points`（**先判重再追加**，v1.2 修复 A4）；
     - **不自动切换知识点**：下一套仍属于当前知识点，全部套答完后 `/question/next` 返回 409 `KNOWLEDGE_POINT_FINISHED`，由用户在 `/modules` 里选下一个模块（见 6.3）。
  6. 套未完成时：`daily_tasks.is_completed` 保持不变，`current_knowledge_point_id` 不变，下一次出题继续在当前套内取没做过的题。
  7. 检查徽章，满足则 `INSERT ... ON CONFLICT DO NOTHING`。
  8. 连续学习：**当天首次答对即触发**，与是否完成套无关（见 6.5）。
  9. **上述逻辑抽成公共函数 `apply_attempt()`，4.8 跟读与 4.10 错题练习必须复用同一函数**（v1.2 修复 A3）。

### 4.4 进度与每日任务

**GET /api/progress**

- 响应：`{ "level", "max_level", "current_knowledge_point", "completed_knowledge_points", "today_task": { "is_completed", "correct_count", "target_count" }, "kp_total", "kp_done", "set_no", "completed_sets", "total_sets" }`
- 口径：
  - `correct_count`：今日 `attempts` 中 `is_correct=true` 的**记录数**（含跟读，含重复答对）。
  - `target_count`（v1.7）：**当前套还没做过的题数**；当前知识点全部套完成、或未测时返回 `0`。
  - `is_completed`：**表示"今天是否完成过至少一套"**；套完成那一刻置 `true`，当天不回退。
  - `kp_total` / `kp_done`：当前套的总题数 / 已做题数，供「第 X / Y 题」与进度条使用。
  - `set_no` / `completed_sets` / `total_sets`：当前套号 / 该知识点已完成套数 / 总套数（`set_no` 为 `null` 表示该知识点已全部学完）。
  - `max_level`：能力测试解锁到的最高等级。
  - 日期口径见 6.4，**必须使用 `APP_TIMEZONE`**。

**GET /api/streak**

- 响应：`{ "current_streak", "longest_streak", "last_study_date" }`

### 4.5 错题

**GET /api/wrong-questions**

- 查询参数：`?scope=current|all`（默认 `current`）、`?include_mastered=true`。
- 响应：`{ "items": [ { "question_id", "stem", "knowledge_point_name", "error_count", "is_mastered" } ] }`
- 规则：
  - 默认只返回**未掌握**（`consecutive_correct < 2`）的错题。
  - `scope=current`：仅当前知识点，按 `error_count DESC`。
  - `scope=all`：**当前知识点的错题排在前面**，其余知识点按 `error_count DESC` 紧随其后（v1.2 决策 D-03）。
  - `include_mastered=true` 时返回全部，附 `is_mastered`，供家长报告使用。

### 4.6 徽章

**GET /api/achievements**

- 响应：`{ "items": [ { "badge_id", "code", "name", "earned_at" } ] }`

### 4.7 家长报告

**GET /api/report**

- 响应：

```json
{
  "level": "L2",
  "completed_knowledge_points": 5,
  "total_knowledge_points": 12,
  "last_7_days_completed": 4,
  "daily_attempts": [ { "date": "2026-10-20", "count": 12 } ],
  "wrong_questions": [ { "stem": "...", "error_count": 3, "is_mastered": false } ]
}
```

- 口径：
  - `completed_knowledge_points`：`progress.completed_knowledge_points` **去重后的长度**。
  - `total_knowledge_points`：**用户当前等级下**的知识点总数。
  - `last_7_days_completed`：近 7 天（含今天）`daily_tasks.is_completed=true` 的天数，即"**当天完成过至少一套**"的天数（v1.7 口径；v1.3 时的"学完一个知识点"已随按套推进失效）。
  - `daily_attempts[].count`：该日 `attempts` 总条数。
  - `wrong_questions`：调用 4.5 的 `include_mastered=true`，包含已掌握项（v1.2：修复"死条款"，4.5 的参数确有使用者）。
  - 日期一律按 `APP_TIMEZONE` 计算。

### 4.8 语音跟读

**GET /api/pronunciation/next**（v1.2 新增）

- 响应：`{ "question": { "id", "stem", "answer" } }`
- 规则：取当前知识点下 `question_type='pronunciation'` 且用户未答对过的题；无题返回 `409 EMPTY_KNOWLEDGE_POINT`。**若当前知识点的 `question_type` 不是 `pronunciation`，返回 `409`，`code = "WRONG_ENDPOINT"`**（v1.4，D-14，与 4.3 的分流互为约束）。

**POST /api/pronunciation/result**

- 请求：`{ "word_id": str, "is_correct": bool, "idempotency_key": str }`
- 响应：`{ "recorded": true, "progress_advanced": bool, "new_badges": [...], "duplicated": bool }`
- 规则：
  - `word_id` 即 `questions.id`，`question_type` 必须为 `'pronunciation'`。
  - 写入 `attempts`（`question_type = 'pronunciation'`），**并调用与 4.3 相同的 `apply_attempt()`**：含错题本、每日任务、套完成判定、徽章、连续学习（v1.2 修复 A3）。
  - **判题权例外**：`SpeechRecognition` 的识别文本只存在于浏览器，后端无法取得，因此 `is_correct` 由前端比对后上报。这是全项目**唯一**的前端判题点。
  - **已知风险（v1.2 记录）**：前端上报意味着该字段可被伪造。接受此风险的前提是"使用者是自己孩子"；若将来多租户上线，必须改为上传识别文本由后端比对。

### 4.9 推送

**POST /api/push/subscribe**

- 请求：`{ "subscription": {...} }`
- 响应：`{ "ok": true }`
- 规则：按 `subscription.endpoint` 去重（写入 `push_subscriptions.endpoint` 列，`UNIQUE` 约束兜底），已存在则更新 `subscription`。

**DELETE /api/push/unsubscribe**

- 响应：`{ "ok": true }`
- 规则：无请求体，删除当前登录用户的**全部**推送订阅。

### 4.10 错题本练习（v1.6 新增，P1）

> 错题从主流程移出后，必须有一个专门的地方去练，否则"收集"没有意义。

**GET /api/practice/next**

- 查询参数：`?knowledge_point_id=<uuid>`（可选，按知识点筛选）
- 响应：`{ "question": { "id", "question_type", "stem", "options", "explanation", "error_count", "consecutive_correct", "knowledge_point_name" }, "remaining": int }`
- 规则：
  - 只出 `wrong_questions.consecutive_correct < 2` 的题，按 `error_count DESC`。
  - **排除 `pronunciation` 题**：本地识别未落地前，练习里无法判分（见 4.8 已知问题）。
  - 没有可练的题时返回 `409`，`code = "NO_WRONG_QUESTIONS"`。

**POST /api/practice/result**

- 请求：`{ "question_id": str, "answer": str, "idempotency_key": str }`
- 响应：`{ "is_correct", "correct_answer", "explanation", "consecutive_correct", "mastered", "duplicated" }`
- 规则：
  - 判题复用 4.3 的归一化规则。
  - 写 `attempts`，`question_type = 'practice'`。
  - 更新 `wrong_questions`：答对 `consecutive_correct += 1`，答错清零；达 2 视为掌握。
  - **不影响** `progress`、`current_knowledge_point_id`、`daily_tasks.is_completed`；`is_kp_complete` 统计时排除 `practice`。
  - 计入连续学习（当天首次答对）与徽章。

**GET /api/practice/summary**

- 响应：`{ "pending": int, "mastered": int, "by_knowledge_point": [ { "knowledge_point_id", "knowledge_point_name", "level", "pending", "mastered", "is_current" } ] }`

### 4.11 学习模块（v1.7）

**GET /api/lesson/overview**

- 响应：`{ "level", "max_level", "required_sets", "knowledge_points": [ { "id", "name", "question_type", "counts_for_gate", "total_sets", "completed_sets", "current_set", "meets_gate" } ], "gate_ready", "can_test", "next_level", "switchable_levels" }`
- 口径：
  - `current_set`：该知识点还没完成的最小套号；全部学完为 `null`。
  - `meets_gate`：该知识点已完成套数 ≥ `required_sets`（固定 3）。
  - `gate_ready`：所有 `counts_for_gate=true` 的知识点都 `meets_gate`。
  - `can_test`：`gate_ready` 且存在下一级。
  - `switchable_levels`：`max_level` 及以下的所有等级。

**POST /api/lesson/select**

- 请求：`{ "knowledge_point_id": str }`
- 规则：知识点必须属于 `users.level`，否则 `409 LEVEL_MISMATCH`；切换后清空 `progress.last_question_id`。
- 响应：`{ "ok": true, "knowledge_point": {...} }`

**POST /api/lesson/switch-level**

- 请求：`{ "level": "L1"|"L2"|"L3" }`
- 规则：只能切到 `max_level` 以内，越级 `409 LEVEL_LOCKED`；切换后 `users.level` 改变，当前知识点落到该级第一个。
- 响应：`{ "ok": true, "level", "max_level", "knowledge_point": {...} }`

### 4.12 能力测试（v1.7）

**GET /api/level-test/status**

- 响应：`{ "level", "next_level", "required_sets", "gate_ready", "can_test", "attempt_count", "last_result": { "score", "total", "passed", "at" }|null }`

**POST /api/level-test/start**

- 前置：门槛未达成 `409 GATE_NOT_READY`；已是最高级 `409 MAX_LEVEL`；本级题库不足 10 题 `409 NOT_ENOUGH_QUESTIONS`。
- 规则：从本级题库**随机抽 10 题**，排除 `pronunciation`；会话存进程内 `_sessions`（单 worker 限制同 4.2）。
- 响应：`{ "question": { "id", "question_type", "stem", "options" }, "index": 1 }`

**POST /api/level-test/answer**

- 请求：`{ "question_id": str, "answer": str }`
- 响应：`{ "is_finished": bool, "score": int, "total": 10, "passed": bool|null, "next_level": str|null }`
- 规则：
  - 答满 10 题结算；**对 8 题及以上为通过**。
  - 通过时把 `users.max_level` 上调到下一级，**但不改 `users.level`**——由用户在 `/api/level-test/choose` 决定升级还是留级（D-20）。
  - 结果写 `level_tests`（`score`/`total`/`passed`）。

**GET /api/level-test/next**

- 响应：`{ "question": {...}, "index": int }`；未开始 `409 TEST_NOT_STARTED`，已结束 `409 TEST_FINISHED`。

**POST /api/level-test/choose**

- 请求：`{ "go_next": bool }`
- 规则：`go_next=true` 且已解锁时，`users.level` 升到下一级、当前知识点落到该级第一个；`go_next=false` 留在原级。未通过就 `go_next=true` → `409 NOT_UNLOCKED`。
- 响应：`{ "level", "max_level", "knowledge_point"|null }`

### 4.13 词典（v1.7）

**GET /api/words**

- 查询参数：`?q=&offset=0&limit=30`（`limit` 上限 100）。
- 范围：**只查当前等级** `users.level` 的词。
- 排序：**未学优先**（该词对应题目没答对过），同组内按 `order_index`（教材册序）。
- 搜索：`q` 同时匹配英文单词（大小写不敏感）与中文释义/音标；空 `q` 返回全部。
- 响应：`{ "level", "total", "items": [ { "id", "word", "phonetic", "level", "grade", "is_phrase", "senses": [{"text","source"}], "definition_en", "learned", "has_wrong" } ], "has_more" }`
- 口径：
  - `learned`：该词对应题目**至少答对过一次**（D-22）。
  - `has_wrong`：该词对应题目进过错题本，不论是否已掌握。
  - 词与题目的对应：拼写/跟读取 `questions.answer`；选择题取正确选项（`options[answer]`）的文本；字母题不参与。
  - `definition_en` **只对 L3 返回**，其余等级为 `null`。

---

## 5. 前端页面与组件

### 5.1 路由

| 路径 | 页面 | 守卫 |
|---|---|---|
| `/` | 重定向到 `/home`，再由守卫按登录/水平测试状态分流 | 无 |
| `/login` | 登录页 | 无 |
| `/register` | 注册页 | 无 |
| `/home` | 首页（今日课程、能力测试、等级切换、错题/词典/徽章/报告入口） | 需登录 |
| `/test` | 初次水平测试页（**整页，非弹窗**） | 需登录且 `has_tested=false`；已测 → 重定向 `/home` |
| `/modules` | 知识点（模块）列表，显示套进度与门槛 | 需登录 |
| `/play` | 答题页（按套出题） | 需登录，`has_tested=true` |
| `/level-test` | 本级能力测试 | 需登录 |
| `/result` | 一套学完后的结算页 | 需登录 |
| `/practice` | 错题练习 | 需登录 |
| `/words` | 词典 | 需登录 |
| `/wrong` | 错题本 | 需登录 |
| `/achievements` | 徽章墙 | 需登录 |
| `/report` | 家长报告 | 需登录 |

### 5.2 组件

| 组件 | 职责 |
|---|---|
| `LoginForm.vue` | 账号密码登录 |
| `RegisterForm.vue` | 账号密码昵称注册 |
| `TestPage.vue` | 水平测试整页，调 `/test/*`（v1.1 的 `TestDialog.vue` 删除） |
| `LetterChoice.vue` | 字母选择题，提交选项 key |
| `WordChoice.vue` | 单词选择题，提交选项 key |
| `SpellingGame.vue` | 拼写题，输入框；**只收集输入并提交原始字符串，不做对错判定** |
| `ListeningChoice.vue` | 听力题，`SpeechSynthesis` 朗读 + 选项，提交选项 key |
| `PronunciationGame.vue` | 跟读，`getUserMedia` + `SpeechRecognition` + 编辑距离比对（唯一前端判题处） |
| `QuestionRenderer.vue` | 按 `question_type` 用 `<component :is>` 渲染 |
| `StreakBadge.vue` | 首页连续天数展示 |
| `AchievementWall.vue` | 徽章墙 |
| `WrongList.vue` | 错题表格 |
| `ReportCharts.vue` | ECharts 柱状图/折线图 |
| `ModulesView.vue` | 知识点列表：套进度、门槛状态、进入学习（v1.7） |
| `LevelTestView.vue` | 能力测试：开始、答题、结果、选择升级/留级（v1.7） |
| `ResultView.vue` | 一套完成后的结算页（v1.7） |
| `PracticeView.vue` | 错题练习：出题、判题、解析（v1.6） |
| `WordsView.vue` | 词典：搜索、滚动加载、默认 2 条义项+展开、状态标签、L3 英文释义（v1.7） |
| `SpeakButton.vue` | 英文点读按钮，所有英文选项/单词可点（v1.6） |

**前端约束（v1.2 新增）：**

- **浏览器能力检测**：`SpeechRecognition` 不存在（Firefox、部分 iOS Safari）时，隐藏 `/play` 中的跟读入口，并显示"当前浏览器不支持跟读"，**不得阻塞其他题型**。
- **跟读出题分流（v1.4，D-14）**：`/play` 加载题目时，先看当前知识点的 `question_type`。等于 `pronunciation` → 调 `/api/pronunciation/next`、渲染 `PronunciationGame`；否则调 `/api/question/next`。**不得依赖 `/question/next` 返回跟读题。**
- **通知权限必须在用户点击时请求**，不得在 `/home` 加载时自动调用（浏览器会静默拒绝）。
- **幂等键**：每次进入一题时生成 UUID 作为 `idempotency_key`，提交失败重试复用同一值。
- **提交按钮防抖**：请求发出后禁用，避免重复提交（幂等键是兜底，防抖是一线）。
- **按套出题（v1.7）**：`/play` 用 `/question/next` 返回的 `set_no/set_total/set_done` 显示「第 X / Y 题」；一套完成（`progress_advanced=true`）跳 `/result`；模块全部学完时后端返回 `409 KNOWLEDGE_POINT_FINISHED`，前端提示后回 `/modules`。
- **答错展示义项（v1.7，D-23）**：答错后作答组件置灰、**不自动跳**，用响应里的 `word` 渲染「正确答案 + 音标 + 全部义项（L3 加英文）」，点「下一题」才继续；答对保持 250ms 后自动跳；**不自动朗读**（只提供手动点读）。
- **词典页（v1.7）**：进入 `/words` 先拉 30 条，滚动到底自动加载，搜索 300ms 防抖；只显示当前等级的词。

### 5.3 Pinia Store

**useUserStore**

- state：`token`、`userId`、`nickname`、`level`、`hasTested`
- actions：`login()`、`logout()`、`fetchMe()`、`setLevel()`

**useProgressStore**

- state：`currentKnowledgePoint`、`completedKnowledgePoints`、`todayTask`
- actions：`fetchProgress()`、`submitAnswer()`

---

## 6. 业务规则

### 6.1 水平分级

- L1：刚入门，什么都不懂。
- L2：学过字母表，单词量很少。
- L3：约初二学生水平。
- 知识点必须归属 L1/L2/L3，同等级内按 `sort_order` 顺序推进。

### 6.2 测试分级

- 起始估计等级 L2。
- 答对 +1，答错 −1，限制在 L1–L3。
- 10 题结束，或等级连续 3 题不变结束。
- `unchanged_streak` 判定：本次答完后 `level == last_level` 则 +1，否则重置为 0；`unchanged_streak >= 3` 即结束。
- 结果写 `users.level`，`has_tested=true`。
- **等级一经确定不再变化**（D-11）：学习过程不改变 `users.level`，也不提供重测入口。

### 6.3 套与知识点完成判定（v1.7 重写）

**推进单位是「套」，不是知识点。**

- 一个知识点下的题按 15 题一套切分（`questions.set_no`）。
- **一套完成**：该套下的题，该用户**做过的不同题目数** ≥ 该套题目数（对错都算，排除 `practice`）。
  - 实现：`SELECT COUNT(DISTINCT question_id) FROM attempts WHERE user_id = :uid AND question_id IN (该套全部题 id) AND question_type != 'practice'`，与该套题数比较。
- 一套完成即写入 `set_progress`（唯一约束兜底，重复不新增），同时把当日 `daily_tasks.is_completed` 置 `true`。
- **知识点达标**：该知识点已完成套数 ≥ **3**（`SETS_REQUIRED`）。达标时才把知识点 id 追加进 `progress.completed_knowledge_points`（去重）。
- **跟读题计入套完成**（它属于某个套的题目）。
- **不自动推进知识点**：当前套答完自动进入当前知识点的下一套；该知识点全部套答完后 `/question/next` 返回 `409 KNOWLEDGE_POINT_FINISHED`，由孩子到 `/modules` 选下一个模块。

### 6.4 每日任务

**任务定义（v1.7）：当天的任务是「完成一套（15 题）」。**

- 完成条件：当前套的每道题都作答过（对错都算，排除 `practice`）——即 6.3 的"一套完成"。
- 一套完成的那一刻，`daily_tasks.is_completed` 置 `true`；当天再完成新的一套不改变该字段（不回退）。
- **不存在"答对 10 题"这个固定目标**；`target_count` 表示当前套还剩多少题没做（见 4.4）。
- 未完成时：`is_completed` 保持 `false`，下一次出题继续在当前套内取没做过的题（4.3 不会重复出答过的题）。
- **`daily_tasks` 行由每次答题时懒创建**（`ON CONFLICT (user_id, task_date) DO NOTHING`），不在注册时预建。
- **时区（v1.2 修复 A7）**：所有"今天"的判定必须显式写成 `(created_at AT TIME ZONE :tz)::date`，`:tz` 取 `APP_TIMEZONE`。**禁止依赖数据库 session 时区**，否则 UTC 服务器上早 8 点前的答题会被算到前一天。
- **跨天行为**：一天没学完的一套，第二天继续，不重置、不回退。
- **同一天完成多套**：允许。`is_completed` 在第一套完成时置 `true`，之后不再变化。

### 6.5 连续学习

**触发条件（v1.3 定稿，方案 A）：当天第一次答对题目即触发**，与"是否学完知识点"无关。

- 判断依据：本次答题**之前**，当天是否已存在 `is_correct = true` 的 `attempts` 记录。没有 → 触发；有 → 跳过。
- `last_study_date` 为昨天：`current_streak += 1`。
- `last_study_date` 为今天：不变。
- 其他（`NULL` 或更早）：`current_streak = 1`。
- `longest_streak = MAX(longest_streak, current_streak)`（v1.2 明确，v1.1 未定义更新条件）。
- 更新 `last_study_date = 今天`。
- **代价说明**：连续天数现在只反映"有没有来学"，不反映"学得好不好"。每天只答对 1 题也能保持连续；若将来要改成"完成知识点才算"，必须同步修改第 8 节的提醒口径。

### 6.6 徽章条件

预置 4 个（`badges.code` 为稳定标识，`name` 存中文展示名）：

| code | name | condition_type | condition_value |
|---|---|---|---|
| `streak_3` | 连续三天 | `streak` | 3 |
| `streak_7` | 连续七天 | `streak` | 7 |
| `complete_l1_first` | 初学有成 | `complete_kp` | 1（占位，逻辑不使用） |
| `answer_100` | 百题达成 | `answer_correct` | 100 |

- `streak`：比较 `streaks.current_streak`。
- `answer_correct`：`COUNT(*) FROM attempts WHERE user_id = :uid AND is_correct = true`（含跟读与重复）。
- `complete_kp`：动态查 `knowledge_points WHERE level='L1' AND counts_for_gate = true ORDER BY sort_order LIMIT 1` 得到 id（v1.7：字母表不计门槛，所以取「基础问候词」），判断该 id 是否在 `progress.completed_knowledge_points` 中。**不得硬编码 UUID。**
- 检查时机：`answer/submit`、`pronunciation/result`、`practice/result` 共用的 `apply_attempt()` 内（套完成事件也在该函数中处理）。
- 写入用 `ON CONFLICT (user_id, badge_id) DO NOTHING`。

### 6.7 错题处理（v1.5 重写，v1.6 补练习入口）

**主流程不再复现错题。** 一道题在知识点内被作答一次后，无论对错都不再出现在 `/question/next` 里；答错的只写入 `wrong_questions`。

- 写入时机：`answer/submit`、`pronunciation/result`、`practice/result` 共用的 `apply_attempt()`。
- 答错：`error_count += 1`，`consecutive_correct = 0`。
- 答对且已在错题本：`consecutive_correct += 1`；**连续答对 2 次（`MASTERY_STREAK`）视为掌握**，移出默认错题列表。
- `GET /wrong-questions` 默认只列 `consecutive_correct < 2` 的题；`include_mastered=true` 返回全部；`scope=current|all`，前端默认 `all`，可按 `knowledge_point_id` 筛选。
- **错题练习（v1.6）已实现**：入口在 `/wrong` 的「开始练习错题」，走 `/api/practice/*`（见 4.10）；练习答对 2 次即掌握，不影响学习进度。

### 6.8 听力题

- 前端用 `SpeechSynthesis` 朗读 `stem`，`lang="en-US"`。
- 选项来自 `options`，**仅文字，不支持图片**（D-05）。
- `listening` 题的 `stem` 必须是**英文**（它同时是朗读内容）；中文题干会被读成乱码，不得出现。

### 6.9 跟读题

- `question_type = 'pronunciation'` 的题**归属独立知识点**（D-02），该知识点的 `question_type` 同样为 `pronunciation`。
- 题目结构：`stem` 与 `answer` 均为目标**单词**（本期不做句子），`options` 为 `NULL`。
- 流程：请求麦克风权限 → `SpeechRecognition` 识别 → 与 `answer` 做 `strip().lower()` 比较，或编辑距离 ≤ 1 判对 → 提交 `/pronunciation/result`。
- 结果写入 `attempts`，并走 `apply_attempt()`。
- 全前端比对是**明确例外**，原因与风险见 4.8。

### 6.10 知识点与等级边界（v1.7 重写）

- **不自动推进知识点**：当前套答完自动进入同一知识点的下一套；该知识点全部套答完后，出题接口返回 `409 KNOWLEDGE_POINT_FINISHED`，不会静默换模块。
- 换模块由孩子在 `/modules` 里主动选择（`POST /api/lesson/select`）。
- `users.level` 只由水平测试（初次）与能力测试后的 `/level-test/choose`（升级或回访切级）改变；学习过程本身不改等级。
- `users.max_level` 是能力测试解锁的上限；`/api/lesson/switch-level` 只能切到该等级以内。
- 因此学完一个模块不会自动跑到下一个等级，也不会跨级出题。**这是产品边界，不是缺陷**；若需改变，另立需求。

### 6.11 升级门槛（v1.7）

- 本级每个 `counts_for_gate=true` 的知识点都要 **完成 ≥ 3 套**，才 `gate_ready=true`。
- `counts_for_gate=false` 的知识点（L1 字母表、L3 听力理解）不参与门槛判定，但可以正常学习、正常记 `set_progress`。
- 门槛状态由 `GET /api/lesson/overview` 与 `GET /api/level-test/status` 返回。

### 6.12 能力测试与等级回访（v1.7）

- **入口**：`/level-test`。门槛未达成时按钮置灰，接口返回 `409 GATE_NOT_READY`。
- **形式**：本级题库随机抽 10 题（排除跟读），一题一题答。
- **通过线**：对 **8 题**及以上通过。
- **通过后**：`users.max_level` 上调到下一级，**`users.level` 不变**；结果页让用户选「升级」或「留在本级」。
- **升级**：`POST /api/level-test/choose {go_next:true}` → `users.level` 变为下一级，当前知识点落到该级第一个。
- **留级**：`{go_next:false}` → 留在原级，仍可随时用 `/api/lesson/switch-level` 切到已解锁的等级。
- **回访**：`POST /api/lesson/switch-level` 可切到 `max_level` 以内任意等级；越级返回 `409 LEVEL_LOCKED`。
- 每次测试结果写 `level_tests`，可重复测（每次都要重新达标），历史保留。

### 6.13 词典与义项（v1.7）

- **数据来源**：`words` 表由 `backend/import_dictionary.py` 生成，输入是 `data/build/words.json`（词表）、`data/build/word_senses.json`（ECDICT 释义）、`data/sources/pep-words/*.json`（课本义）与 `data/sense_cleanup.json`（人工清洗清单）。
- **课本义**：取 pep 词表（L1/L2 用小学册、L3 用初中册），做机械清洗（去语法注记、尾部标点、相邻重复、`um`/`num` 残字、统一分隔符）后置顶，标 `source=textbook`。**每个词的第一条必须是课本义。**
- **词典义**：ECDICT 部分按逗号拆项，删领域标签、俚语脏话、技术义、与课本义重复项；每行最多留 2 项、每词最多留 3 行。
- **人工清洗**：`data/sense_cleanup.json` 按等级分桶，命中即整词覆盖；`textbook_fixes` 记录课本义纠错。洗过一批就跑一次 `import_dictionary.py`，可重复执行（先删后插）。
- **展示规则**：只显示当前等级；未学优先 → 教材册序；每条默认 2 条义项、可展开全部；英文释义只给 L3；「已学」= 该词对应题目答对过至少一次，「有错题」= 进过错题本。

### 6.14 答错展示义项（v1.7）

- **触发**：`/play` 答题页答错（含跟读判错）。
- **内容**：正确答案、音标、该词全部义项（第一条标「课本」），L3 再显示英文释义。
- **行为**：停住不自动跳，点「下一题」才继续；不自动朗读（只提供手动点读）；不强制停留（随时可点返回）。
- **答对**：保持自动跳（约 250ms）。
- **数据来源**：`/api/answer/submit` 与 `/api/pronunciation/result` 的 `word` 字段（见 4.3）。
- **边界**：字母题查不到单词，只显示 `answer_text`；查不到词时面板降级为只显示正确答案。

---

## 7. 种子数据

必须提供初始化脚本 `seed.py`，**幂等**（按 `code` / `account` / `knowledge_point_id + stem` 判重）：

**知识点与题目：**

| 等级 | 知识点 | question_type | sort_order | 计入升级门槛 | 套数 | 题量（当前值） |
|---|---|---|---|---|---|---|
| L1 | 字母表 | `letter` | 1 | **否** | 1 | 15 |
| L1 | 基础问候词 | `word` | 2 | 是 | 22 | 330 |
| L2 | 常用单词 | `word` | 1 | 是 | 32 | 480 |
| L2 | 简单拼写 | `spelling` | 2 | 是 | 27 | 405 |
| L2 | 单词跟读 | `pronunciation` | 3 | 是 | 29 | 435 |
| L3 | 听力理解 | `listening` | 1 | **否** | 1 | 15 |
| L3 | 拼写进阶 | `spelling` | 2 | 是 | 95 | 1425 |

合计 **3105 题 / 207 套**，每套 15 题。

> **v1.7 说明**：第 1 套是手写题（`seed.py`，含解析）；第 2 套起由 `seed_words.py` 按 15 个词切分生成（题干用词表释义、选项用同套其它单词）。字母表与听力理解题量固定、凑不满 3 套，`counts_for_gate=false`，不影响能力测试解锁（D-19）。
>
> 内容量已从 v1.4 规划的 105 题扩到 3105 题，全部来自现成数据源生成 + 人工抽检，不由 agent 凭空编写。

**词典数据（v1.7 新增）：**

- `words` 表 **1972 词**：L1 319 / L2 493 / L3 1160，由 `backend/import_dictionary.py` 生成。
- 输入：`data/build/words.json` + `data/build/word_senses.json`（ECDICT）+ `data/sources/pep-words/*.json`（课本义）+ `data/sense_cleanup.json`（人工清洗清单）。
- 义项口径见 6.13；脚本**可重复执行**（先 `DELETE` 再批量插入，业务表无外键引用 `words`）。

**其他要求：**

- 每题的 `difficulty` 取值与其所属等级一致（L1→1、L2→2、L3→3）。
- 选择题 `options` 为 `{"A":..., "B":..., "C":..., "D":...}`，`answer` 为单个大写字母。
- `listening` 题的 `stem` 为英文，且与朗读内容一致。
- `pronunciation` 题的 `stem` 与 `answer` 均为单词，`options` 为 `NULL`。
- 预置 4 个徽章（见 6.6）。
- **每个知识点的题量必须 ≥ 该知识点完成判定所需的最小题数**：计入升级门槛的知识点至少需要 **3 套（45 题）**，否则永远达不成门槛；不计门槛的至少 1 套（15 题）。不得出现 0 题知识点。
- 种子脚本运行后必须校验：`knowledge_points.question_type` 与其下 `questions.question_type` 全一致，不一致则报错退出。

---

## 8. 每日提醒

- 前端在 `/home` 提供**显式的"开启提醒"按钮**，点击后才请求通知权限并注册 Service Worker（D-09、v1.2 修复 C3）。
- 用户授权后 `pushManager.subscribe()`，订阅信息 POST `/api/push/subscribe`。
- 后端 APScheduler 每日 **19:00**（`APP_TIMEZONE`）执行任务：
  - 目标用户 = **有推送订阅、且当日没有任何 `is_correct = true` 的 `attempts` 记录**的用户（v1.3 修改：连续学习改为"当天答对 ≥1 题"，提醒口径随之对齐，**不再看 `daily_tasks.is_completed`**，否则学了一半的孩子不会被提醒）。
  - 用 `pywebpush` 发送，`endpoint` 返回 404/410 时删除该订阅。
- VAPID 密钥从环境变量读取。
- `APScheduler` 用 `BackgroundScheduler`，在 FastAPI `startup` 启动、`shutdown` 停止；设 `misfire_grace_time`。
- **`ENABLE_SCHEDULER=0` 时不启动调度器**（v1.2 修复 D11：`--reload` 开发模式下会启动两次导致重复推送）。
- 推送失败只记日志，不影响主流程。

---

## 9. 验收标准

**基础项：**

1. 注册、登录、JWT 鉴权可用；库中密码为哈希；`Tom` 与 `tom` 视为同一账号。
2. 初次登录进入 `/test`，10 题内完成并写入 L1/L2/L3；已测用户再访问 `/test` 返回 409。
3. `GET /question/next` 按当前知识点返回题，题型与知识点绑定一致。
4. 答错进入 `wrong_questions`，**不回主流程**；在错题本里连续答对 2 次后退出默认列表（v1.5）。
5. 一套完成时写入 `set_progress`、`daily_tasks.is_completed` 同步置 `true`，重新登录不回到起点（`progress.last_question_id` 会恢复未答完的那道题）。
6. 一套未做完时，`daily_tasks.is_completed` 保持 `false`；但当天只要答对 ≥1 题，`streaks` 已更新。
7. 徽章条件满足时写入 `achievements`，不重复。
8. `/report` 返回等级、达标模块数、近 7 天完成套数的天数、每日答题数、错题列表。
9. 听力题可朗读；跟读题可识别并记录结果。
10. 推送订阅可保存，定时任务可发送（浏览器支持范围内）。
11. `pytest` 覆盖注册、登录、测试分级、答题推进、错题、每日任务、徽章。
12. **无 LLM 依赖**：`requirements.txt` / `package.json` 中不得出现任何 LLM SDK（可用脚本校验依赖清单，v1.2 改为可自动验证）。

**v1.1 补充项：**

13. 注册后立即 `GET /api/progress` 返回 200（`progress` 行已创建），测试完成后 `current_knowledge_point` 非空。
14. 同一道题连续答对两次，不计入两次"不同题目数"。
15. 错题连续答对 2 次后，不再出现在 `/question/next` 的首选位置，也不再出现在 `/wrong-questions` 默认列表。
16. 篡改 `answer` 字段不影响判题；`is_correct` 由后端决定。

**v1.2 新增项（对应本轮修复）：**

17. 注册后、首次答题前 `daily_tasks` 无行；首次答题后行存在，且 `correct_count` 正确（A1）。
18. 当日未学习的用户也能收到 19:00 提醒（A2）。
19. 跟读答对后，知识点完成判定与徽章检查**确实执行**（A3）。
20. 反复完成同一知识点，`completed_knowledge_points` 长度不增长（A4）。
21. L1 用户做水平测试，不会因抽到 L3 题而全部掉级（A5）。
22. 同一 `idempotency_key` 提交两次，`attempts` 只增 1 条，`daily_attempts` 不重复计数（A6）。
23. 服务器时区设为 UTC 时，北京时间 00:30 的答题计入当天（A7）。
24. 未测试用户直接调 `/api/question/next` 返回 409 `NOT_TESTED`，不是 500（A8）。
25. 空知识点不触发静默跳级，返回 409 `EMPTY_KNOWLEDGE_POINT`（A9）。
26. 不支持 `SpeechRecognition` 的浏览器上，跟读入口隐藏，其他题型可正常作答（C1）。
27. 通知权限只在点击按钮后请求（C3）。

**v1.3 新增项（Q1 定稿）：**

28. 当天只答对 1 题、知识点未学完时，`streaks.current_streak` 仍然 +1。
29. 当天一道题都没答对时 19:00 能收到提醒；答对过 1 题但知识点没学完时**不再**收到提醒。
30. `GET /api/progress` 的 `target_count` 随**当前套**剩余题数变化，**不等于固定 10**。
31. 同一套跨两天完成时，`is_completed` 只在第二天那一次置 `true`（当天完成后继续做新的一套不重置该字段）。

**v1.5 新增项（主流程单遍制）：**

36. 一道题答错后，主流程不再返回同一题；该题出现在错题本里。
37. 一套 15 题全部答错，该套仍然判定完成并进入下一套（不会卡死）。
38. 答错后 `target_count` 同样递减（按"做过"计数，不按"答对"计数）。
39. 水平测试出过的题在正常够用的情况下不会在学习阶段重复出现；当当前套只剩测试题时允许出现，以保证能凑满 15 题。
40. 未答完就离开答题页，下次进入 `/play` 返回同一道题（`progress.last_question_id`）。

**v1.4 新增项：**

32. 【已废止】v1.5 删除了"某题累计答错 5 次视为已练习"的规则（V5-6），现在一套内做过一次即算学过。
33. 当前知识点为「单词跟读」时，`/api/question/next` 返回 409 `USE_PRONUNCIATION_ENDPOINT`，前端改调 `/api/pronunciation/next` 后能正常出题并判分（D-14）。
34. 当前知识点不是跟读时，`/api/pronunciation/next` 返回 409 `WRONG_ENDPOINT`（D-14）。
35. 每个知识点的 `questions` 数量 ≥ 15，且不存在 0 题知识点（D-13）。

**v1.7 新增项（按套推进 / 能力测试 / 词典 / 答错义项）：**

45. 一套 15 题全部作答过（对错不论）才算完成，完成写入 `set_progress`，重复完成不新增行。
46. 同一知识点完成 ≥3 套算达标；本级所有计门槛知识点达标后 `/api/lesson/overview` 的 `gate_ready=true`。
47. 字母表、听力理解 `counts_for_gate=false`，它们没达标也不影响能力测试解锁。
48. 能力测试 10 题对 8 过；通过后 `max_level` 提升、`level` 不变；`/level-test/choose` 才决定升级或留级。
49. `/lesson/switch-level` 只能切到 `max_level` 以内，越级返回 409 `LEVEL_LOCKED`。
50. 模块全部套学完后 `/question/next` 返回 409 `KNOWLEDGE_POINT_FINISHED`，不会静默换模块。
51. `/api/words` 只返回当前等级的词；`total` 等于该等级词数；分页不重叠、可翻全。
52. 词典排序未学优先、同组按教材册序；搜索中英文都能命中；跨等级搜不到。
53. 词表每条至少 1 条义项且**第一条是课本义**；L1/L2 的 `definition_en` 为 `null`，L3 有值。
54. 「已学」= 该词对应题目答对过至少一次；「有错题」= 进过错题本；已学的词排在未学之后。
55. 答错时 `/answer/submit` 返回 `word`（单词/音标/全部义项/L3 英文）与 `answer_text`；字母题 `word=null` 但 `answer_text` 有值；幂等重放同样带这些字段。
56. 答题页答错停住并展示义项，点「下一题」才继续；答对自动跳下一题；答错后不能重复提交。

---

## 10. 交付物

- 后端：FastAPI 应用、Alembic 迁移、`seed.py`、`pytest` 测试。
- 前端：Vue 3 应用、路由、Pinia、组件、Service Worker。
- `README.md`：环境变量、启动命令、种子数据命令、测试命令。
- `.env.example`：数据库连接、JWT 密钥、VAPID 密钥、`APP_TIMEZONE`、`ENABLE_SCHEDULER`。
- **`.gitignore`**（v1.2 新增）：至少覆盖 `.env`、`node_modules/`、`dist/`、`__pycache__/`、`.venv/`、`*.pyc`、本地数据库文件。
- **`scripts/create_db.sql`**（v1.2 新增）：建库与建角色，不含业务表（业务表由 Alembic 管）。

**README 必须写明：**

- 本机开发用 `localhost` 访问（`getUserMedia`/`SpeechRecognition` 要求安全上下文，局域网 IP 走 http 直接不可用）。
- **正式部署必须 HTTPS**，否则跟读、Service Worker、Web Push 全部失效。
- 后端 `uvicorn --host 0.0.0.0` 以便手机访问。
- **APScheduler 依赖单 worker，不得加 `--workers`**；开发 `--reload` 时设 `ENABLE_SCHEDULER=0` 避免重复推送。

---

## 11. 已决事项（原 Q1，v1.3 定稿）

**决议：进度推进采用「方案 A 任务驱动」。**

> **v1.7 说明**：本节是历史决策记录。其中"当天任务 = 学完当前知识点""任务完成条件 = 答对的不同题目数 ≥ 题目总数""推进时机 = 知识点完成的那一刻"三行已被 **6.3 / 6.4** 取代——现在的推进单位是「套」，当天任务 = 完成一套（15 题，对错都算）。其余（连续学习、提醒口径）仍然有效。

| 项 | 定稿 |
|---|---|
| 当天任务是什么 | 学完**当前知识点** |
| 任务完成条件 | 当前知识点下已答对的不同题目数 ≥ 该知识点题目总数 |
| 任务量 | 动态，等于当前知识点剩余未答对的题目数；**不存在固定 10 题** |
| 推进时机 | 知识点完成的那一刻，立即推进 |
| 未完成时 | 不推进，继续出复习内容（错题 → 未做过 → 任意），进度不回退 |
| 连续学习 | 当天答对 ≥ 1 题即算，与是否完成知识点脱钩 |
| 每日提醒 | 当天未答对任何题才提醒 |
| 报告「近 7 天完成天数」 | 语义变为"学完知识点的天数"，字段名不变 |

**已废弃的方案：**

- ~~B 内容驱动~~（答对全部题目立即推进、日任务固定 10 题）：与需求不符，未采用。
- ~~C 双门槛~~（额外引入"待推进"状态）：未采用，无 pending 字段。

**连带改动清单（已全部落到正文）：** 4.3 步骤 3–9、4.4、4.7、6.3、6.4、6.5、第 8 节、第 9 节验收 5/6/28–31。

---

## 12. 修订记录

### 12.1 v1.3（Q1 定稿）

| # | 位置 | 变更 |
|---|---|---|
| Q1-1 | 4.3 步骤 3–9 | 删除"待定"标记；完成知识点后立即推进，同时置 `daily_tasks.is_completed=true`；未完成则两者都不变 |
| Q1-2 | 4.4 | `target_count` 由常量 10 改为动态值（当前知识点剩余未答对的不同题目数） |
| Q1-3 | 4.7 | `last_7_days_completed` 语义改为"学完知识点的天数"，字段名不变 |
| Q1-4 | 6.3 / 6.4 | 每日任务重新定义为"学完当前知识点"，删除固定 10 题目标 |
| Q1-5 | 6.5 | 连续学习触发条件改为"当天首次答对"，与知识点是否完成脱钩 |
| Q1-6 | 8 | 提醒目标改为"当天没有任何答对记录的用户" |
| Q1-7 | 9 | 验收 5/6 重写，新增 28–31 项 |

### 12.2 v1.2（40 条审查）

| # | 位置 | 问题 | 处理 |
| A1 | 3 / 4.3 / 6.4 | `daily_tasks` 行无任何创建时机，任务永远完不成 | 答题时 `ON CONFLICT DO NOTHING` 懒创建 |
| A2 | 8 | 推送只查 `is_completed=false`，没学习的人收不到 | v1.2 先改为"无记录或未完成"；v1.3 按方案 A 再改为"当天无答对记录" |
| A3 | 4.8 | 跟读不触发完成判定与徽章，知识点可能卡死 | 抽出 `after_attempt()` 共用 |
| A4 | 4.3 / 4.7 | `completed_knowledge_points` 追加无去重 | 追加前判重；报告取去重长度 |
| A5 | 4.2 | 跨等级随机抽题，`difficulty` 从未使用，全员掉 L1 | 按 `difficulty` 分层抽题 |
| A6 | 4.3 | 提交无幂等，双击可刷任务与徽章 | 增加 `idempotency_key` + 唯一约束 |
| A7 | 6.4 | `created_at::date` 依赖 DB session 时区 | 显式 `AT TIME ZONE :tz` |
| A8 | 4.3 | 未测用户调接口无定义，后端无校验 | 增加 `NOT_TESTED` 409 与统一鉴权语义 |
| A9 | 4.3 | 空知识点静默跳级 | 改为 409 报错 |
| B1/B2 | 4.3 / 6.3 / 6.4 | 推进时机与需求冲突 | **v1.3 定稿为方案 A**，见第 11 节 |
| B3/B4 | 3 / 6.9 / 7 | 跟读挂在 word 知识点，违反一知识点一题型 | 独立 `pronunciation` 知识点，只做单词 |
| B5 | 4.5 / 6.7 | 错题仅限当前知识点；跟读错题不入本 | 增加 `scope=all` 跨知识点；跟读同样入本 |
| B6 | 3 / 5 / 9 | 小测验需求有、规格无 | 明确本期不做，需求标 v2 |
| B7 | 3 / 6.8 | 需求要图片，表结构无图片能力 | 明确不做图片 |
| B8 | 6.6 | 徽章覆盖与需求描述不符 | 保持 4 个，需求措辞收窄 |
| B9 | 4.7 | 无家长角色隔离 | 明确不隔离 |
| B10 | 8 | 提醒时间不可配 | 固定 19:00 |
| B11 | 5.1 / 5.2 | 弹窗与整页并存 | 统一为整页 `TestPage.vue`，不可重测 |
| B12 | 6.10 | 学完一级进不去下一级 | 明确为产品边界，不跨级 |
| B13 | 3 | `options` JSON 结构未定义 | 固定为 `{"A":...}`，`answer` 存 key |
| B14 | 3 / 6.8 | 各题型题干语言未定义 | 逐题型定义（见"字段口径"） |
| C1 | 5.2 | 移动端浏览器不支持语音识别 | 能力检测 + 隐藏入口 |
| C2 | 1 / 10 | 部署未要求 HTTPS | 写入硬约束与 README |
| C3 | 5.2 / 8 | 通知权限在页面加载时请求会被拒 | 改为按钮触发 |
| C4 | 4 | token 过期无处理 | 增加 `TOKEN_EXPIRED` 码与前端跳转 |
| C5 | 4.1 | 账号大小写未归一 | 存库前 `strip().lower()` |
| C6 | 3 | 两处 `question_type` 可能不一致 | 加唯一约束与运行时校验 |
| C7 | 3 / 4.9 | `endpoint` 在 JSONB 中无法建唯一索引 | 提为独立列 + `UNIQUE` |
| D1 | 3 | `attempts.question_id` 可空且理由自相矛盾 | 改 `NOT NULL` |
| D2 | 3 | `difficulty` 死字段 | 随 A5 启用 |
| D3 | 3 | `condition_value` 对 `complete_kp` 无意义 | 注明为占位 |
| D4 | 4.2 | `question_index` 冗余 | 删除 |
| D5 | 4.5 / 4.7 | `include_mastered` 无使用者 | 报告接口实际使用 |
| D6 | 6.5 | `longest_streak` 更新条件未定义 | 明确取 `MAX` |
| D7 | 4.1 | 注册后还要再登录一次 | 注册直接返回 token |
| D8 | 10 | 缺 `.gitignore` 与建库脚本 | 补入交付物 |
| D9 | 9 | "无 LLM 调用"无法自动验证 | 改为校验依赖清单 |
| D10 | 5.1 | `has_tested=true` 访问 `/test` 去向未定义 | 重定向 `/home` |
| D11 | 8 | `--reload` 下调度器启动两次 | 增加 `ENABLE_SCHEDULER` |

**未改动、但已明确为"已知边界"的两处：**

- **跟读判题在前端**（4.8 / 6.9）：识别文本只在浏览器，无替代方案。已记录伪造风险。
- **测试会话存进程内**（4.2）：单 worker 限制，重启丢失。MVP 可接受。

### 12.3 v1.4（5 项收尾）

| # | 位置 | 问题 | 处理 |
|---|---|---|---|
| V4-1 | 4.3 / 4.8 / 5.2 | `/question/next` 不含 `answer`，跟读知识点无法判题；两条出题路径并存 | `/question/next` 排除 `pronunciation` 并返回 409；前端按知识点类型分流；两个接口互相约束 |
| V4-2 | 4.3 / 6.3 | 一道题反复答错会让知识点永久卡死 | 累计答错 ≥5 次视为"已练习"，计入完成判定，仍保留在错题本 |
| V4-3 | 第 7 节 | 每知识点 5 题导致"每日任务"3 分钟就完成 | 题量提到 ≥15 题 |
| V4-4 | 需求 50 行 | "或下一学习环节"无定义 | 删除该措辞，只保留"下一个知识点" |
| V4-5 | 需求 59/65/67/69/71 行 | 需求仍写着句子跟读、设定时间、阶段小测验、图片 | 需求文档同步收窄，标注 v2 |

### 12.4 v1.5（主流程单遍制）

| # | 位置 | 变更 |
|---|---|---|
| V5-1 | 4.3 | `/question/next` 删除"错题优先"，改为：恢复未答完的题 → 没做过的题（优先避开测试题）→ 测试题兜底 → 任意题 |
| V5-2 | 6.3 / 4.3 步骤 4 | 知识点完成改为「做过即算」：`COUNT(DISTINCT question_id)`，不再要求答对 |
| V5-3 | 6.7 | 重写为"错题只进错题本，不回主流程"；错题练习列入 v2 |
| V5-4 | 4.4 | `target_count` 改为"还没做过的题数" |
| V5-5 | 验收 | 新增 36–40 |
| V5-6 | 全篇 | 删除 v1.4 的"答错 5 次视为已练习"规则 |

### 12.5 v1.6（P1：学习闭环）

| # | 位置 | 变更 |
|---|---|---|
| P1-1 | 4.10（新增） | 错题本练习三个接口：出题 / 判题 / 汇总 |
| P1-2 | 3 | `questions` 增加 `explanation`，105 题全部补写解析 |
| P1-3 | 4.4 | `/progress` 增加 `kp_total`、`kp_done`，供进度条与题号使用 |
| P1-4 | 4.5 | 错题列表返回 `explanation`；支持 `knowledge_point_id` 筛选 |
| P1-5 | 5.1 | 新增路由 `/practice`、`/result` |
| P1-6 | 5.2 | 新增 `SpeakButton.vue`：所有英文选项可点读；选择题渲染带发音按钮 |
| P1-7 | 6.3 | `is_kp_complete` 排除 `question_type='practice'`，练习不推进学习进度 |
| P1-8 | 9 | 新增验收 41–44（见下） |

**v1.6 验收：**

41. 错题本显示"待练习 / 已掌握"数量，可按知识点筛选。
42. 练习页答错展示解析；同一题连续答对 2 次后从默认列表移出。
43. 练习不改变 `current_knowledge_point_id`、不推进知识点、不影响每日任务完成态。
44. 答题页显示"第 X / Y 题"与进度条；一套完成后跳转结算页。

### 12.6 v1.7（与实现同步）

> 本版只补齐规格与实现之间的差距，**不改已实现行为**（除 6.x 中被明确重写的口径）。

| # | 位置 | 变更 |
|---|---|---|
| V7-1 | 0 | 新增决策 D-17～D-24（按套推进、门槛、不计门槛、能力测试、等级回访、词典、答错义项、义项来源） |
| V7-2 | 3 | 补 `users.max_level`、`knowledge_points.counts_for_gate`、`questions.explanation`/`set_no`、`progress.last_question_id`/`test_seen_question_ids`；新增 `set_progress`、`level_tests`、`words` 三张表 |
| V7-3 | 3 | 补 v1.7 字段口径（套号、解析、max_level、恢复指针、practice 不计进度、senses 结构） |
| V7-4 | 4.3 | `/question/next` 增加 `exclude_id` 参数与 `set_no/set_total/set_done` 响应；`/answer/submit` 增加 `answer_text`、`word`（答错展示义项），`progress_advanced` 语义改为"完成一套" |
| V7-5 | 4.4 | `/progress` 增加 `max_level/kp_total/kp_done/set_no/completed_sets/total_sets`；`target_count` 改为"当前套剩余题数" |
| V7-6 | 4.11～4.13（新增） | 学习模块三个接口、能力测试五个接口、词典接口 |
| V7-7 | 5.1 / 5.2 | 补 `/modules`、`/level-test`、`/result`、`/practice`、`/words` 路由与对应组件；补 v1.7 前端约束 |
| V7-8 | 6.3 / 6.4 | 完成判定从"知识点"改为"套"，每日任务定义为"完成一套" |
| V7-9 | 6.7 | 错题练习从"v2 计划"改为已实现（4.10） |
| V7-10 | 6.10 | 改为"不自动推进知识点，模块由用户选择" |
| V7-11 | 6.11～6.14（新增） | 升级门槛、能力测试与等级回访、词典与义项、答错展示义项 |
| V7-12 | 7 | 种子数据表补 `counts_for_gate`、真实套数/题量（3105 题 / 207 套）、词典 1972 词 |
| V7-13 | 9 | 修正验收 4/5/6/30/31/32/37/39，新增 45–56 |
| V7-14 | 全文 | 统一 `after_attempt()` 的函数名为实现中的 `apply_attempt()` |

**v1.7 验收：** 见第 9 节 45–56。

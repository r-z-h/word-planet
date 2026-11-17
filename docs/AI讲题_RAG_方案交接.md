# AI 讲题 / 错题 AI 讲解（RAG）· 方案交接

> 用途：新会话接手这个需求时，先读本文件 + `AGENTS.md` + `需求说明书.md` + `Agent实现说明书.md`。
> 状态：**方案阶段，未动代码**。上次结论：先保留、以后谈；现决定推进，需先确认下方"待拍板"。

---

## 1. 背景与硬约束

- 项目：Word Planet 少儿英语学习平台（Vue3 + FastAPI + PostgreSQL）。
- **现有需求明确禁止 LLM**：
  - `需求说明书.md:46`：题目来自本地题库，不接题库 API、**不调大模型（LLM）**。
  - `Agent实现说明书.md:46-47`：不调用 LLM、不调用外部 AI API（浏览器原生语音/推送除外）。
- 因此第一步必须做：**需求变更**（改这两处口径 + 隐私说明），否则实现即违规。

## 2. 目标（先做小、做对）

在**错题本**里给已作答的题加一个入口：**「AI 讲解这道题」**。
- 只针对**当前这道题 + 孩子的作答**讲解，**不开放自由闲聊**。
- 讲解必须**基于检索到的项目自有内容**，带来源；检索不到就**不瞎编**，退回模板式讲解。
- 儿童向语气、中文、短句、鼓励式。

## 3. 总体架构（RAG）

1. **知识源（全部来自现有资产，尽量不新造内容）**
   - 题库：3315 题（题干/选项/答案/解析 `explanation`）。
   - 词典表 `words` 1972 词（课本义、音标、英文释义 ECDICT）。
   - 各知识点/模块说明（字母表/问候/单词/拼写/跟读/听力/拼写进阶）。
   - 可补充：教材例句（`data/sources/pep-words`、听力语料 `data/sources/manythings`）。
2. **入库/分块**
   - 题目级：`question_id` + 题干 + 答案 + 现有解析。
   - 词级：word + 音标 + 义项（标 `source=textbook` 优先）。
   - 每条 chunk 带 metadata：`level`、`knowledge_point_id`、`question_type`、`source_type`、`source_id`。
3. **向量化 + 向量库**
   - 新增 PostgreSQL 扩展 **pgvector**；表 `rag_chunks(id, source_type, source_id, level, kp_id, content, embedding vector(N), meta jsonb)`。
   - embedding 模型走外部 API（需 key）；维度按所选模型定。
4. **检索**
   - 查询 = 题干 + 选项 + 用户错答 + 正确答案。
   - 向量 top-k（先按 level / kp 过滤，避免跨级串题）；可加关键词混合检索。
5. **生成**
   - LLM 只允许使用检索到的 chunk；Prompt 要求：
     - 输出固定结构：①这道题考什么 ②你为什么会错（针对孩子作答）③正确思路 ④一个同类小例子。
     - **每条结论标注来源 chunk id**；无依据则写"资料不足"。
     - 禁止超纲、禁止编造词义、禁止输出不适龄内容。
   - 低置信度/无检索结果 → 返回**模板讲解**（由题目现有 `explanation` + 词义拼装），不调用 LLM 或调用但强约束。
6. **接口**
   - `POST /api/ai/explain`：`{question_id, user_answer?}` → `{explanation, citations[], mode: 'rag'|'template', cached: bool}`。
   - 仅登录用户；按 `question_id + 答案` 做缓存（表 `ai_explain_cache`）。
   - 限流/配额：每用户每日 N 次（可配置），全局成本上限。
7. **前端**
   - `WrongView.vue` 每行加「AI 讲解」按钮 → 弹窗显示结构化讲解 + 来源 + 免责声明。
   - 缓存命中直接显示；失败降级模板讲解。
8. **运营/安全**
   - 记录 prompt/response 日志（脱敏），人工抽检；一键 kill switch（环境变量关闭 AI）。
   - 儿童隐私：只发送题目与作答，不发用户名/手机号；在隐私政策写明。

## 4. 分两期落地（强烈建议）

- **Phase 1（先做，风险低）：离线讲解库**
  - 用 LLM **离线批量生成**每题讲解 → **人工审核** → 存 `ai_explanations` 表。
  - 前端只读库里的审核版讲解，**不实时调 LLM**。
  - 优点：正确性可控、无实时成本与延迟；缺点：覆盖需人工。
- **Phase 2（再做）：在线 RAG**
  - 接 LLM API + pgvector，实时检索生成，带引用；保留 Phase 1 库作为兜底。
- 建议：**先 Phase 1 跑通 100 道高频错题**，评估质量后再决定 Phase 2。

## 5. 涉及文件（预估）

- 后端：`app/models.py`（新增 `rag_chunks`/`ai_explanations`/`ai_explain_cache`）、`alembic/versions/*`、`app/routers/ai.py`、`app/services/rag.py`、`app/services/llm.py`、`app/config.py`（API key/env）、`app/schemas.py`。
- 前端：`views/WrongView.vue`、新组件 `components/AIExplainDialog.vue`、`api/http` 调用。
- 文档：更新 `需求说明书.md`、`Agent实现说明书.md`、`AGENTS.md`。
- 环境：`backend/.env` 配 `LLM_API_KEY`/`LLM_BASE_URL`/`LLM_MODEL`、`EMBEDDING_MODEL`；PostgreSQL 安装 pgvector。

## 6. 待拍板（新会话先问用户）

1. **Phase 1 还是直接 Phase 2**？（建议 Phase 1）
2. LLM/Embedding 用哪家（火山方舟/通义/OpenAI/其它）？有无 API key 与预算？
3. 是否允许把**题目与孩子作答**发到外部 API？（隐私）
4. 每日免费额度多少？是否家长可见/可关？
5. 讲解范围：只错题本？还是也覆盖"答错即时讲解"？

## 7. 验收标准（建议）

- 抽 50 道题人工核对：讲解不出现错误词义/错误语法；引用可追溯。
- 无检索命中时**100% 走模板**，不出现编造。
- 接口 P95 延迟 < 3s（缓存 < 200ms）；每日成本不超预算。
- 关闭 AI 开关后全站无报错（优雅降级）。

## 8. 给新会话的开场提示（可直接复制）

> 读 `docs/AI讲题_RAG_方案交接.md`、`AGENTS.md`、`需求说明书.md`、`Agent实现说明书.md`。
> 按该文件的 Phase 1 先做"离线讲解库"最小闭环：新增表+接口+错题本弹窗，内容先覆盖 100 道高频错题；不要接实时 LLM，先把审核流程跑通。动手前先复述需求与不确定项，等我确认。

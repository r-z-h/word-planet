# Word Planet · Agent 交接说明

> 新会话请先读本文件，再读 `Agent实现说明书.md` 与 `需求说明书.md`。
> 本文件记录**当前真实进度**与**已拍板但尚未写进说明书**的决策，避免重复讨论。

---

## 1. 项目是什么

少儿英语学习平台。Vue 3 + FastAPI + PostgreSQL，题库来自人教版词表（KyleBing，BSD-3）+ ECDICT 释义（MIT）。

- 需求：`需求说明书.md`
- 规格：`Agent实现说明书.md`（v1.7，已同步"按套推进/能力测试/词典/答错义项"）
- 操作规则：`agents操作规则.md`（**动手前先复述、有歧义先问、超出范围先报备**）
- **第二版游戏设计：`docs/游戏设计.md`（v2.0，三层奖励/徽记/解锁条件）——做第二版必须先读**

## 2. 怎么跑起来

```powershell
.\dev.ps1 start      # PostgreSQL + 后端(8000) + 前端(5173 HTTP / 5174 HTTPS)
.\dev.ps1 stop
.\dev.ps1 status
```

也可双击 `start.bat` / `stop.bat` / `status.bat`（`.ps1` 在本机没有文件关联）。

- PostgreSQL 是**便携版**（`D:\PostgreSQL`），**不会开机自启**，重启电脑后必须先 `dev.ps1 start`
- 数据库连接、JWT、VAPID 都在 `backend/.env`（不入库）
- 前端电脑用 `http://localhost:5173`；手机用 `https://<局域网IP>:5174`（自签证书）

## 3. 常用验证命令

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests -q          # 16 项
.\.venv\Scripts\python.exe smoke.py                    # 24 项真实 HTTP
.\.venv\Scripts\python.exe verify_p1.py                # 12 项：错题练习/解析
.\.venv\Scripts\python.exe verify_sets.py              # 18 项：按套推进/能力测试/回访
.\.venv\Scripts\python.exe verify_words.py             # 23 项：词典接口
.\.venv\Scripts\python.exe verify_feedback.py          # 15 项：答错展示义项
.\.venv\Scripts\python.exe audit_content.py            # 3105 题内容审计
```

改题库后必须重跑 `audit_content.py`；改义项后必须重跑 `import_dictionary.py`。

## 4. 已完成

- 认证、水平测试分级、答题、错题本、错题练习、解析、徽章、连续学习、家长报告、推送、每日提醒
- **按套推进**：知识点 → 套（每套 15 题）→ 题目；`set_progress` 记录完成；
  知识点"达标" = 完成 ≥3 套；字母表/听力不计入门槛（`knowledge_points.counts_for_gate=false`）
- **能力测试**：本级门槛知识点各满 3 套 → `POST /api/level-test/start` → 10 题对 8 过 →
  解锁下一级（`users.max_level`）→ `POST /api/level-test/choose` 让用户选升级/留级
- **等级回访**：`POST /api/lesson/switch-level`，只能切到 `max_level` 以内的等级
- **义项清洗（L1+L2+L3 全量）**：课本义改用 `data/sources/pep-words`（分学段），机械清洗后置顶；
  `data/sense_cleanup.json` 人工清单覆盖 1109 个词（L1 103 / L2 258 / L3 748）+ 35 条课本义纠错；
  `backend/import_dictionary.py` 可重复执行（`--preview` 只出预览不写库）
- **词典页 `/words`**：只查当前等级、未学优先→教材册序、搜索中英文、默认 2 条义项+展开、
  状态标签（未学/已学/有错题）、英文释义只给 L3
- **答错展示义项**：`/answer/submit` 与 `/pronunciation/result` 返回 `answer_text` + `word`
  （单词/音标/全部义项/L3 英文）；答题页答错停住，点「下一题」才继续，答对保持自动跳
- 题库 3105 题 / 207 套；词典表 `words` 1972 词

## 5. 进行中 / 待办

| 事项 | 状态 |
|---|---|
| 题库题干清洗 | **未做，且已定"题干保持不动"**。全库 273 道题的题干是 `“男孩, 儿子, 孩子气的人, 男仆”用英语怎么说？` 这种（`data/build/words.json` 的 `meaning` 来自 kylebing 而非 pep）。要修得重建题目，`seed_words.py` 遇到已有作答记录会跳过 |
| 跟读 | 暂不修：本地访问不了 Google 语音服务，等部署服务器再说 |

## 6. 已拍板的关键决策（不要再重新讨论）

- 题库**不由 agent 生成**，必须来自现成数据源
- 义项：课本义置顶并标 `source=textbook`；带领域标签的专业义项**直接删**；俚语、需要特定语境才有意义的义项**直接删**；课本外但通用常用的保留
- **课本义统一取 `data/sources/pep-words`**（L1/L2 小学册、L3 初中册），不再用 kylebing 的 `meaning`
- **义项只能改 `data/sense_cleanup.json`**，再跑 `import_dictionary.py`；直接改库会被下次导入覆盖
- 词典页排序：未学优先 → 教材册顺序；搜索只搜当前等级；英文释义只对 L3 显示
- 词典「已学」= 该词对应题目**答对过至少一次**（不是"做过"）
- 答错才展示义项，答对保持自动跳
- 跟读功能因本地无法访问 Google 语音服务而不可用，**暂不修**，等部署服务器再说

## 7. 已知坑

- **Edge 朗读**：必须本地声音优先（`frontend/src/utils/speech.js` 有打分逻辑），否则会选到在线声音导致延迟和错误发音
- **跟读**：`SpeechRecognition` 依赖 Google 服务，当前网络不可用；手机端还受自签证书限制
- **seed.py 的 prune**：只清理第 1 套，第 2 套起由 `seed_words.py` 生成，不要误删
- **义项清洗**：只改 `data/sense_cleanup.json`（键必须**小写**，`China`/`English` 这类用 `china`/`english`），
  再跑 `import_dictionary.py`；它是 `DELETE` 后重建整表，别只改库
- **词典英文释义**：ECDICT 里是字面量 `\n`，`import_dictionary.py` 导入时会转成真换行，别在库里手改
- **测试库**：pytest 用 `word_planet_test`，会自动跑 `seed.py` + `seed_words.py`，需要 `data/build/words.json` 存在
- 本机无 WSL、无 Docker；PostgreSQL 用便携版

## 8. 改代码前的规矩

1. 先复述需求 + 列出不确定项
2. 有歧义用选择题问，给推荐项
3. 改规则/改需求/加功能，**先给方案等确认**；只有修用户报的 bug 才直接动手
4. 改完必须跑上面第 3 节的验证命令，贴真实输出

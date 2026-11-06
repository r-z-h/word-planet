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
.\dev.ps1 start      # PostgreSQL + 后端(8000) + 前端(5273 HTTP / 5274 HTTPS)
.\dev.ps1 stop
.\dev.ps1 status
```

日常用**双击根目录 `服务管理.bat`**（统一菜单：1启动 2停止 3重启 4状态 5打开网页 6查看报错 7环境检查 0退出）；命令行仍可用 `dev.ps1 start|stop|restart|status`。旧的 `start.bat`/`stop.bat`/`status.bat` 已移除。

- PostgreSQL 是**便携版**（`D:\PostgreSQL`），**不会开机自启**，重启电脑后必须先 `dev.ps1 start`
- 数据库连接、JWT、VAPID 都在 `backend/.env`（不入库）
- 前端电脑用 `http://localhost:5273`；手机用 `https://<局域网IP>:5274`（自签证书）

### 公网演示（临时隧道 + 口令门，方案②）

给家人/朋友临时演示时，把本机 5273 发布到公网：

```powershell
.\tools\tunnel.ps1 start     # 启动口令门(8080)+cloudflared，打印 公网 URL / 用户名 / 密码
.\tools\tunnel.ps1 status    # 查看前端/后端/口令门/隧道状态、当前 URL、登录口令
.\tools\tunnel.ps1 stop      # 关闭公网入口（开发栈不动）
```

- **只暴露口令门 8080（自带登录页 + 签名 Cookie）**，后端 8000 与数据库不出网；前端经 Vite `/api` 代理访问后端。
- 临时隧道**每次 start 公网 URL 都会变、无 SLA**；口令存 `.run\tunnel-credentials.json`（git-ignored，**明文，勿外发/勿截图**）。
- 排查未授权隧道：`status` 会告警第三方 cloudflared；遗留直连隧道常用指标端口 20241（本脚本用 20242）。
- 完整说明见 `docs/公网演示使用与安全说明.md`。

## 3. 常用验证命令

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests -q          # 16 项
.\.venv\Scripts\python.exe smoke.py                    # 24 项真实 HTTP
.\.venv\Scripts\python.exe verify_p1.py                # 12 项：错题练习/解析
.\.venv\Scripts\python.exe verify_sets.py              # 18 项：按套推进/能力测试/回访
.\.venv\Scripts\python.exe verify_words.py             # 23 项：词典接口
.\.venv\Scripts\python.exe verify_feedback.py          # 15 项：答错展示义项
.\.venv\Scripts\python.exe audit_content.py            # 3315 题内容审计
```

改题库后必须重跑 `audit_content.py`；改义项后必须重跑 `import_dictionary.py`。

## 4. 已完成

- 认证、水平测试分级、答题、错题本、错题练习、解析、徽章、连续学习、家长报告、推送、每日提醒
- **游客体验 `/guest`**：登录页有「游客体验」入口，免注册；后端 `/api/guest/*`（`backend/app/routers/guest.py`）按模块随机取 3 题、判题返回义项，**不写库、不记进度/错题**；排除跟读（依赖麦克风+Google 语音）。模块列表来自 6 个知识点。
- **按套推进**：知识点 → 套（每套 15 题）→ 题目；`set_progress` 记录完成
- **星球徽记 & 解锁（2026-11-05 落地）**：每个星球各自一种"星球徽记"（字母表无徽记、只判完成）；门槛按星球各自数量、读"已兑换徽记数"：
  - L1→L2：字母表「已完成（15 题全对）」+ 基础问候词 5 枚
  - L2→L3：常用单词 3 + 简单拼写 5 + 单词跟读 7
  - 字母表=纯练（不发花/徽记，只判完成）；听力已改为**正常星球**（徽记：卡通戴耳机头像 `/medals/listening.svg`，产花、可兑徽记）
- **成就徽章（2026-11-06 落地）**：`badges` 表新增 `icon`（emoji 或图片路径，迁移 `e5f6a7b8c9d0`）。**共 18 个（17 普通 + 最高成就）**：连续三天🔥、连续七天、半月里程碑(streak≥14)、持之以恒(累计学习30天)、百题达成💯、五百题、千题斩、一日猛练(单日≥50)、初学有成🎓、学有所成🏫、三星连珠(单星球3徽记)、完美一套、全场最佳(10套全对)、能力初试🎖️、错题清零🧹、补花达人🌼、连击高手🎇；最高成就 **「寰宇圆满·万物生花」**(`ultimate_all`，徽章 `/badges/ultimate.svg`)：判定=**所有星球都拿到过花 + 字母表已完成**（即所有产花题目都拿到花）。解锁动效：`frontend/src/utils/achievementFx.js` 右下角滑入"成就解锁卡"（徽章弹跳+金光+星光，1.6s，排队播放），答题接口 `new_badges` 触发；最高成就全屏大片特效**待做**。徽章墙 A2 版式：「成长徽章」=已得荣誉墙；下方「待解锁成就」只列**未得**（置灰+🔒，按 ORDER 排序），最高成就**单独放大一张放最后**（未得置灰）；接口 `/api/achievements` 返回 `badges: BadgeDef[]{code,name,icon,earned,condition}`。
- **错题补花**：主流程答错进错题本；错题本里**连续答对 3 次**（`MASTERY_STREAK=3`，同一题两次答对需间隔 ≥10 分钟防抢记）→ 补该题 1 朵花并移出错题本；"满套"=该套 15 题**都拿到过花**（含补花）
- **兑换入口**：首页「🧾 进入兑换」跳转**独立兑换页 `/exchange`**，列出当前星球**全部套**（已完成/进行中/未开始分组），有花没花都能进、不足置灰+差额；接口 `GET /api/lesson/planet-sets`（含未开始套）
- **能力测试**：本级每个计入门槛星球达标（各自数量/完成）→ `POST /api/level-test/start` → 10 题对 8 过 → 解锁 `max_level` → `/choose` 选升级/留级
- **错题本单题练习**：错题列表每行「练这一题」→ `/practice?qid=` 单题练习（`GET /api/practice/one`）；保留 抽查/强化/复测
- **等级回访**：`POST /api/lesson/switch-level`，只能切到 `max_level` 以内的等级
- **义项清洗（L1+L2+L3 全量）**：课本义改用 `data/sources/pep-words`（分学段），机械清洗后置顶；
  `data/sense_cleanup.json` 人工清单覆盖 1109 个词（L1 103 / L2 258 / L3 748）+ 35 条课本义纠错；
  `backend/import_dictionary.py` 可重复执行（`--preview` 只出预览不写库）
- **词典页 `/words`**：只查当前等级、未学优先→教材册序、搜索中英文、默认 2 条义项+展开、
  状态标签（未学/已学/有错题）、英文释义只给 L3
- **答错展示义项**：`/answer/submit` 与 `/pronunciation/result` 返回 `answer_text` + `word`
  （单词/音标/全部义项/L3 英文）；答题页答错停住，点「下一题」才继续，答对保持自动跳
- 题库 3315 题 / 221 套；词典表 `words` 1972 词。**听力理解 15 套 / 225 题**（第 1 套 `seed.py` 手写；第 2–15 套由 `seed_listening.py` 从现成句对语料 `data/sources/manythings/cmn.txt`（Tatoeba/ManyThings，CC BY 2.0，署名见文件）筛出；规则：句中出现的 L3 词为答案、干扰项整词/子串都不在句中、每套 15、幂等）。

## 5. 进行中 / 待办

| 事项     | 状态                                                                                                                                                           |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 题库题干清洗 | **未做，且已定"题干保持不动"**。全库 273 道题的题干是 `“男孩, 儿子, 孩子气的人, 男仆”用英语怎么说？` 这种（`data/build/words.json` 的 `meaning` 来自 kylebing 而非 pep）。要修得重建题目，`seed_words.py` 遇到已有作答记录会跳过 |
| 跟读     | 已接入讯飞语音评测（提交于 `00dd990`），可用；部署需在 `.env` 配 `IFLYTEK_*` |

## 6. 已拍板的关键决策（不要再重新讨论）

- 题库**不由 agent 生成**，必须来自现成数据源（听力英文句来自 `data/sources/manythings/cmn.txt`，Tatoeba/ManyThings CC BY 2.0）
- 义项：课本义置顶并标 `source=textbook`；带领域标签的专业义项**直接删**；俚语、需要特定语境才有意义的义项**直接删**；课本外但通用常用的保留
- **课本义统一取 `data/sources/pep-words`**（L1/L2 小学册、L3 初中册），不再用 kylebing 的 `meaning`
- **义项只能改 `data/sense_cleanup.json`**，再跑 `import_dictionary.py`；直接改库会被下次导入覆盖
- 词典页排序：未学优先 → 教材册顺序；搜索只搜当前等级；英文释义只对 L3 显示
- 词典「已学」= 该词对应题目**答对过至少一次**（不是"做过"）
- 答错才展示义项，答对保持自动跳
- **命名**：v2 奖励体系的"星球徽章/徽记"统一叫**星球徽记**；需求的"学习成就徽章"叫**成就徽章**（两者不是一回事）
- 跟读已接入讯飞（`services/iflytek.py`），本地可用；部署需配置 `IFLYTEK_*` key

## 7. 已知坑

- **Edge 朗读**：必须本地声音优先（`frontend/src/utils/speech.js` 有打分逻辑），否则会选到在线声音导致延迟和错误发音
- **跟读**：已改为讯飞语音评测（PCM→后端评分）；未配 key 时 `/pronunciation/score` 返回 503；旧浏览器 SpeechRecognition 为历史回退
- **seed.py 的 prune**：只清理第 1 套，第 2 套起由 `seed_words.py` 生成，不要误删
- **义项清洗**：只改 `data/sense_cleanup.json`（键必须**小写**，`China`/`English` 这类用 `china`/`english`），
  再跑 `import_dictionary.py`；它是 `DELETE` 后重建整表，别只改库
- **词典英文释义**：ECDICT 里是字面量 `\n`，`import_dictionary.py` 导入时会转成真换行，别在库里手改
- **测试库**：pytest 用 `word_planet_test`，会自动跑 `seed.py` + `seed_words.py`，需要 `data/build/words.json` 存在
- **页面空白只剩标题（浏览器标签是项目名）**：多为前端 Vite 依赖预构建缓存坏了（控制台 `504 Outdated Optimize Dep`）。电脑 5273 与手机 5274 两个 dev 实例曾共用 `node_modules/.vite` 互相抢占，导致 `deps` 只留下 `deps_temp_*`；已在 `frontend/vite.config.js` 按模式分 `cacheDir`（`.vite-desktop` / `.vite-mobile`）。再遇空白：删 `frontend/node_modules/.vite*` 后重启前端。
- 本机无 WSL、无 Docker；PostgreSQL 用便携版
- **改后端/改表后必须重启后端并 `alembic upgrade head`**：否则前端新页面会拿到旧接口（曾导致兑换页"暂无套"空白）。后端代码改了不重启 = 新前端配旧接口。
- **星球徽记图标/名称一律取 `knowledge_points.medal_icon / medal_name`**（地图、首页、兑换页、结算页、徽章墙统一），不要在前端写死映射。
- **星球徽记图标可以是 emoji 或图片路径**：图片型（如听力的 `/medals/listening.svg`）必须用 `frontend/src/components/MedalIcon.vue` 渲染（`<MedalIcon :icon="..." />`），不要当文本插值；`knowledge_points.medal_icon` 已加长到 VARCHAR(128)（迁移 `b2c3d4e5f6a7`）。
- **成就徽章图标同理**：`badges.icon` 可为 emoji 或图片路径；徽章墙用 `MedalIcon` 渲染（迁移 `e5f6a7b8c9d0` 给 `badges` 加 `icon`）。
- **判定成就**在 `app/services/attempts.py::award_badges`：条件类型 `streak/answer_correct/complete_kp/complete_level/perfect_set/level_test_pass/active_days/daily_correct/planet_medals/perfect_sets/wrong_cleared/refill/consecutive_correct/ultimate`；`ultimate` 每次判定要数"产花题总数 vs 用户拿到花的题数"，较重但可接受。

## 8. 改代码前的规矩

1. 先复述需求 + 列出不确定项
2. 有歧义用选择题问，给推荐项
3. 改规则/改需求/加功能，**先给方案等确认**；只有修用户报的 bug 才直接动手
4. 改完必须跑上面第 3 节的验证命令，贴真实输出

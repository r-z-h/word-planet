# Word Planet · 少儿英语游戏化学习平台

按《[Agent实现说明书](./Agent实现说明书.md) v1.4》实现，需求见《[需求说明书](./需求说明书.md)》。

- 后端：FastAPI + SQLAlchemy + Alembic + PostgreSQL
- 前端：Vue 3 + Vite + Vue Router + Pinia + Element Plus + ECharts

---

## 一、本机环境

| 组件 | 位置 | 说明 |
|---|---|---|
| PostgreSQL 17.2 | `D:\PostgreSQL` | 免安装便携版，非 Windows 服务，用 `pg_ctl` 手动启停 |
| Python 3.13 | 已装 | 虚拟环境在 `backend/.venv` |
| Node.js 24 | 已装 | 前端依赖在 `frontend/node_modules` |

### 启动 / 停止数据库

```powershell
# 启动
& "D:\PostgreSQL\bin\pg_ctl.exe" -D "D:\PostgreSQL\data" -l "D:\PostgreSQL\log\server.log" -o "-p 5432" -w start

# 停止
& "D:\PostgreSQL\bin\pg_ctl.exe" -D "D:\PostgreSQL\data" -m fast stop
```

数据库：`word_planet`（业务）、`word_planet_test`（测试）。超级用户 `postgres`，密码见 `backend/.env`。

> 便携版**不会开机自启**，重启电脑后需要手动拉起，否则后端连接失败。

---

## 二、启动后端

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- 接口文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/api/health
- **不要加 `--workers`**：水平测试会话与定时任务都依赖单进程。

### 数据库迁移与种子

```powershell
cd backend
.\.venv\Scripts\alembic.exe upgrade head
.\.venv\Scripts\python.exe seed.py     # 幂等，可重复执行
```

种子数据：7 个知识点、105 道题（每点 15 题）、4 个徽章。

---

## 三、启动前端

```powershell
cd frontend
npm run dev
```

- 本机：https://localhost:5173 （**自签证书，浏览器会提示不安全，点"继续访问"**）
- 手机：https://<本机局域网IP>:5173

### 为什么是 HTTPS

跟读要用麦克风（`getUserMedia`）、提醒要用 Service Worker，浏览器只在**安全上下文**（HTTPS 或 localhost）下允许。用 http + 局域网 IP 访问，这两个功能直接不可用。

### 手机第一次访问

1. 手机和电脑连同一个 Wi-Fi。
2. 手机浏览器打开 `https://<电脑局域网IP>:5173`。
3. 出现证书警告 → 选择"高级" → "继续前往"。
4. **注意**：证书不受信任时，部分安卓机型的跟读会被禁用；iOS 需要在"设置 → 通用 → 关于本机 → 证书信任设置"里手动信任后才能用。

查本机 IP：

```powershell
Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' } | Select-Object IPAddress, InterfaceAlias
```

---

## 四、测试

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest tests -q      # 16 项
.\.venv\Scripts\python.exe smoke.py                # 24 项真实 HTTP 链路（需先启动后端）
```

`tests` 用独立的 `word_planet_test` 库，不会碰业务数据。

---

## 五、关键规则（详见规格书）

- 当天任务 = **学完当前知识点**；学完即推进到下一个知识点。
- 一道题累计答错 5 次视为"已练习"，不再阻塞知识点完成。
- 连续学习：当天答对 ≥1 题即 +1 天。
- 等级由水平测试一次决定，学习过程不升级、不跨级。
- 跟读题走独立知识点，接口是 `/api/pronunciation/*`，不能走 `/api/question/next`。

---

## 六、常见问题

| 现象 | 原因 / 处理 |
|---|---|
| 后端启动报连不上数据库 | PostgreSQL 没启动，见第一节 |
| 手机打不开页面 | 电脑防火墙拦了 5173；或不在同一网段 |
| 手机能看页面但跟读没反应 | 证书未被信任，或浏览器不是 Chromium 系（Firefox 不支持语音识别） |
| 提醒收不到 | `VAPID` 未配置 / 未点"开启提醒" / 浏览器通知权限被拒 |
| 定时任务没跑 | `.env` 里 `ENABLE_SCHEDULER=0` |

---

## 七、已知边界

- 跟读的对错由前端判定后上报，可被伪造（自用场景接受）。
- 水平测试会话存进程内，重启后未完成的测试会丢失。
- 便携版 PostgreSQL 不做开机自启，也不做备份策略。

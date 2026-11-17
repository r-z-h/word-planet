# 看图猜词 · 补图文生图 Prompt（15 个）

## 统一规格（重要）
- **尺寸**：1024×1024，正方形 1:1
- **格式**：PNG，**透明背景**（不行就纯白 #FFFFFF）
- **画风**：扁平矢量 emoji 风格、可爱、圆润、少量柔和光影、纯色、无描边过重
- **构图**：单一主体、居中、四周留 ~12% 边距、不要文字/水印
- **一致性**：15 张用同一句"风格后缀"，保证像一套

**统一风格后缀（每条 prompt 都拼在末尾）：**
`flat vector emoji style, cute, soft rounded shapes, minimal soft shading, single subject centered, plain white background, no text, no watermark, 1024x1024, consistent icon set`

**统一负向词：**
`text, watermark, letters, logo, photo, realistic, 3d render, busy background, multiple subjects, ugly`

---

## 15 个词（主体 + 英文 prompt 主体，后面拼统一风格后缀）

1. **football player 足球运动员** — a cute kid in a soccer uniform kicking a soccer ball, full body
2. **driver 司机** — a cute person driving a car holding the steering wheel, simple flat car
3. **nurse 护士** — a friendly cute nurse wearing a nurse cap and white uniform, standing
4. **head 头** — a simple flat side view of a human head
5. **hair 头发** — a neat hairstyle of hair (no face), flat cartoon
6. **pencil box 铅笔盒** — an open pencil case with a few pencils inside
7. **blackboard 黑板** — a green classroom blackboard with a piece of chalk
8. **fan 风扇** — an electric desk fan with blades
9. **wall 墙壁** — a section of brick wall
10. **desk 书桌** — a student desk (school desk)
11. **table 桌子** — a simple wooden table
12. **floor 地板** — a section of wooden floorboards
13. **fridge 冰箱** — a refrigerator with two doors
14. **fork 餐叉** — a single dining fork
15. **study 书房** — a cozy study room scene with a bookshelf and desk

> 其余已配好的类别不动；动物用 3D、衣物/食物/身体/文具/物品/人物/天气用 fluent-emoji-flat。
> 生成好后按 `英文单词.png` 命名发我（如 football_player.png、pencil_box.png），我统一接入。

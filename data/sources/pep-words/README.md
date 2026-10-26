# pep-words（人教版课本释义）

本目录是词典页「课本义」的来源，按课标分为两册：

| 文件 | 条数 | 用于 |
|---|---|---|
| `primary_school.json` | 1331 | L1 / L2（小学） |
| `middle_school.json` | 2895 | L3（初中） |

字段：`id` / `word` / `phonetic` / `pos` / `meaning` / `letter`。

## ⚠️ 来源说明（务必先读）

- **本目录的来源尚未考证**。数据由项目早期阶段引入，未记录原始仓库地址、作者与许可证。
- 其字段结构与 `KyleBing/english-vocabulary`（BSD-3，见 `../kylebing/`）不同，不是从该仓库导出。
- 因此：**本目录不作为对外数据分发**，仅作为本项目的内部参考数据随仓库保存，以便 `backend/import_dictionary.py` 可重复执行。
- 如需转载或二次分发，请先自行确认上游授权，或改用可考证的替代数据源。
- 已知的数据质量问题（已在导入脚本里做机械修补，见 `backend/import_dictionary.py`）：
  - 少量词条粘连相邻词（如 `store` → `商店buy /bai/购买；买`）
  - `num` 被截成 `um`（如 `zero` → `um & n零`）
  - 尾部残留句点、相邻重复（如 `zoo` → `动物园动物园`）

## 来源考证待办

- [ ] 找到原始仓库 / 数据集页面
- [ ] 确认许可证
- [ ] 补 LICENSE 文件
- [ ] 若上游不可考证，评估替换为可考证的人教词表

## 相关脚本

- `tools/import_words.py`：把人教版分册 jsonl 清洗成 `data/build/words.json`（题库用）
- `backend/import_dictionary.py`：合并词表 + ECDICT + 本目录，生成 `words` 表（词典用）

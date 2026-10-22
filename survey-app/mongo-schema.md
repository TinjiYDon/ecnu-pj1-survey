# MongoDB Schema（规则）

库名：`survey_app`（可用 `SURVEY_DB_NAME` 改）。  
四个集合。程序不在 Mongo 里挂 JSON Schema 校验器，约束由本文件规定，`app/logic.py` / `app/services.py` 执行，索引在 `app/db.py`。

记号：必填 = insert 时必须有；可空 = 允许 `null` 或省略后由程序补默认值。

---

## 1. users

| 字段 | 类型 | 必填 | 约束 | 含义 |
|---|---|---|---|---|
| `_id` | ObjectId | 是 | 主键，自动生成 | 用户 id |
| `username` | string | 是 | 非空；全库唯一 | 登录名 |
| `password_hash` | string | 是 | `salt:digest`，PBKDF2-HMAC-SHA256 | 密码摘要，不存明文 |
| `created_at` | Date | 是 | UTC | 注册时间 |

索引：`username` unique。

---

## 2. questions（一版一文档）

同一道逻辑题的每个版本是**独立文档**。改题 = insert 新文档，旧文档字段不再改内容。

| 字段 | 类型 | 必填 | 约束 | 含义 |
|---|---|---|---|---|
| `_id` | ObjectId | 是 | 主键；**这一版**的 id | 问卷 `items.question_id` 引用的就是它 |
| `logical_id` | ObjectId | 是 | 同一题家族共用；v1 新建时生成 | 串版本历史 |
| `version` | int | 是 | ≥ 1；同一 `logical_id` 内递增 | 版本号 |
| `derived_from` | ObjectId \| null | 是 | v1 为 null；其后指向被改的那一版 `_id` | 从哪一版改来 |
| `owner_id` | ObjectId | 是 | → `users._id` | 出题人 |
| `visibility` | string | 是 | `private` \| `shared` | 是否已分享给他人 |
| `shared_with` | ObjectId[] | 是 | 元素 → `users._id`；可空数组 | 被分享者；不能改原版，只能引用 |
| `category` | string | 是 | 可空字符串 | 分类标签，不是单独集合 |
| `in_bank` | bool | 是 | | 是否出现在题库选题列表 |
| `type` | string | 是 | `single` \| `multi` \| `text` \| `number` | 题型，创建后版本间应保持一致 |
| `stem` | string | 是 | 非空 | 题干 |
| `options` | string[] | 是 | `single`/`multi`：至少 2 项；`text`/`number`：必须 `[]` | 选项文案 |
| `required_default` | bool | 是 | | 被放进问卷时「必答」的默认值 |
| `validation` | object | 是 | 键随 `type` 变，见下表；无规则用 `{}` | 填写时的校验规则 |
| `created_at` | Date | 是 | UTC | 这一版创建时间 |
| `deprecated` | bool | 是 | 默认 false | 预留；当前未强制过滤 |

索引：`(logical_id, version)`、`owner_id`、`category`、`in_bank`、`shared_with`。

### 2.1 `validation`（按 `type`）

未出现的键表示「不做这项限制」。程序只认下表字段，不写死某一道题。

| type | 允许的键 | 值类型 | 规则 |
|---|---|---|---|
| `single` | （无） | — | 答案必须是 `options` 中恰好一项 |
| `multi` | `min_select` | int ≥ 0 | 至少选几项 |
| | `max_select` | int ≥ 0 | 至多选几项 |
| | `exact_select` | int ≥ 0 | 必须恰好几项；与 min/max 同时出现时都要满足 |
| `text` | `min_len` | int ≥ 0 | 最短字数 |
| | `max_len` | int ≥ 0 | 最长字数 |
| `number` | `min` | number | 下限（含） |
| | `max` | number | 上限（含） |
| | `integer` | bool | true 则必须是整数 |

答案取值（写入 `responses.answers.value` 之前）：

| type | value 类型 |
|---|---|
| `single` | string，且 ∈ `options` |
| `multi` | string[]，每项 ∈ `options` |
| `text` | string |
| `number` | number（integer=true 时为 int） |

---

## 3. surveys

问卷元数据 + 对本卷题目的引用 + 本卷跳转规则。不嵌套题目全文。

| 字段 | 类型 | 必填 | 约束 | 含义 |
|---|---|---|---|---|
| `_id` | ObjectId | 是 | 主键 | 问卷 id |
| `owner_id` | ObjectId | 是 | → `users._id` | 出卷人 |
| `title` | string | 是 | 非空 | 标题 |
| `description` | string | 是 | 可空字符串 | 说明 |
| `allow_anonymous` | bool | 是 | | 是否允许答卷打匿名标记（仍须登录） |
| `allow_multiple` | bool | 是 | | 同一用户是否可交多份 |
| `deadline` | Date \| null | 是 | null = 无截止 | 截止后不可填 |
| `status` | string | 是 | `draft` \| `published` \| `closed` | 草稿可改 items/跳转；发布后锁定 |
| `slug` | string | 是 | 非空；唯一（sparse） | 填写 URL：`/survey/{slug}` |
| `created_at` | Date | 是 | UTC | 创建时间 |
| `published_at` | Date \| null | 是 | 未发布为 null | 最近发布时间 |
| `items` | object[] | 是 | 可空数组；结构见 3.1 | 卷内题目，有序 |
| `jump_rules` | object[] | 是 | 可空数组；结构见 3.2 | 跳转规则，按数组顺序匹配 |

索引：`owner_id`、`slug` unique sparse、`status`。

### 3.1 `items[]`

| 字段 | 类型 | 必填 | 约束 | 含义 |
|---|---|---|---|---|
| `item_id` | string | 是 | 本卷内唯一 | 卷内题号，跳转用这个，不是 question `_id` |
| `question_id` | ObjectId | 是 | → `questions._id`（某一版） | 钉死版本；改题出新版不会改这里 |
| `required` | bool | 是 | | 本卷是否必答 |

发布后禁止改 `items`。引用的题目必须是所有者自己的，或 `shared_with` 含当前用户。

### 3.2 `jump_rules[]`

规则存在数据里。代码只解释，不针对某份问卷写 if。

| 字段 | 类型 | 必填 | 约束 | 含义 |
|---|---|---|---|---|
| `from_item` | string | 是 | 必须是本卷某个 `items.item_id` | 从哪题出发 |
| `when` | object | 是 | 见 3.3 | 匹配条件 |
| `to_item` | string | 是 | 本卷某个 `item_id`，或字面量 `"end"` | 跳到哪；`end` = 结束填写 |

未命中任何规则：按 `items` 数组的下一题。匹配时按 `jump_rules` 从上到下第一条成功的。

### 3.3 `when`

| `op` | 适用题型 | 其它键 | 匹配含义 |
|---|---|---|---|
| `eq` | single | `option`: string | 答案等于该选项 |
| `includes` | multi | `option`: string | 答案数组包含该选项 |
| `eq_number` | number | `value`: number | 数值相等 |
| `between` | number | `min` / `max`：number，可只写一侧 | 落在闭区间 |

其它 `op` 视为不匹配。

---

## 4. responses

一次提交一份文档。`answers` 只含**跳转路径上实际问过的题**，被跳过的题不出现。

| 字段 | 类型 | 必填 | 约束 | 含义 |
|---|---|---|---|---|
| `_id` | ObjectId | 是 | 主键 | 答卷 id |
| `survey_id` | ObjectId | 是 | → `surveys._id` | 填的哪份卷 |
| `respondent_id` | ObjectId | 是 | → `users._id` | 填写人（匿名也有） |
| `anonymous` | bool | 是 | 仅当问卷 `allow_anonymous=true` 才可为 true | 统计展示时隐藏用户名 |
| `submitted_at` | Date | 是 | UTC | 提交时间 |
| `answers` | object[] | 是 | 非空；结构见 4.1 | 路径上的作答 |

索引：`survey_id`、`answers.question_id`、`(survey_id, respondent_id)`。

`allow_multiple=false` 时，同一 `(survey_id, respondent_id)` 只允许一份（程序检查，不是 unique 索引）。

### 4.1 `answers[]`

| 字段 | 类型 | 必填 | 约束 | 含义 |
|---|---|---|---|---|
| `item_id` | string | 是 | 对应本卷 `items.item_id` | 卷内题号 |
| `question_id` | ObjectId | 是 | 提交时从 item 拷贝的那一版 | 跨卷统计用这个字段 |
| `value` | string \| string[] \| number | 是 | 类型必须符合该题 `type`（见 2.1） | 校验通过后的值 |

---

## 5. 集合之间的引用（规则，不是某一份数据）

- `questions.owner_id`、`surveys.owner_id`、`responses.respondent_id`、`questions.shared_with[]` → `users._id`
- `surveys.items[].question_id` → `questions._id`（版本钉死）
- `responses.survey_id` → `surveys._id`
- `responses.answers[].question_id` → `questions._id`
- `jump_rules.from_item` / `to_item` → 本卷 `items.item_id`（或 `to_item="end"`）

没有把题目全文嵌进问卷，也没有单独的 versions / categories 集合。

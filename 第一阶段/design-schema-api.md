# 阶段一（含需求变更）字段设计 + API 列表

> 技术栈：Python · FastAPI · Jinja2 模板 · Session Cookie · pymongo · 本地 MongoDB  
> 数据模型：`users` / `questions` / `surveys` / `responses`  
> 版本策略：一版一文档，内容不可变；保存=新版本并提示；问卷只引用 `question_id`（不做 snapshot）  
> 状态：待你确认「方案 OK」后再实现

数据库名建议：`survey_app`

---

## 一、集合与字段

### 1. `users`

| 字段 | 类型 | 说明 |
|---|---|---|
| `_id` | ObjectId | |
| `username` | string | 唯一 |
| `password_hash` | string | 不可存明文 |
| `created_at` | datetime | 注册时间 |

索引：`username` 唯一。

---

### 2. `questions`（题库：一版一文档）

| 字段 | 类型 | 说明 |
|---|---|---|
| `_id` | ObjectId | **版本实例 id**；问卷引用的就是它 |
| `logical_id` | string/ObjectId | 同一题家族共用，串 v1→v2→v3 |
| `version` | int | 从 1 递增 |
| `derived_from` | ObjectId \| null | 从哪版 `_id` 改来 |
| `owner_id` | ObjectId | 创建者 → users |
| `visibility` | string | `private` \| `shared` |
| `shared_with` | ObjectId[] | 被分享用户（visibility=shared 时用；也可空表示「公开到题库」——实现时取：仅 shared_with 列表可见） |
| `category` | string | 分类标签，如「人口统计」 |
| `in_bank` | bool | 是否在题库中可被选题（常用题） |
| `type` | string | `single` \| `multi` \| `text` \| `number` |
| `stem` | string | 题干 |
| `options` | string[] | 单选/多选的选项；填空为空数组 |
| `required_default` | bool | 题库默认是否必答（卷内可覆盖） |
| `validation` | object | 见下表 |
| `created_at` | datetime | |
| `deprecated` | bool | 软下架，不物理删 |

`validation` **按题型：**

| type | validation 字段 |
|---|---|
| `single` | `{}` 或无需 |
| `multi` | `min_select`, `max_select`（可选；或 `exact_select`） |
| `text` | `min_len`, `max_len` |
| `number` | `min`, `max`, `integer` (bool) |

索引建议：

- `(logical_id, version)`  
- `owner_id`  
- `category`  
- `in_bank`  
- `shared_with`（多键）

**改题流程：** 读旧版 → 用户改 → insert 新文档（version+1, derived_from=旧_id, 同 logical_id）→ 返回提示「已保存为 vN」。

---

### 3. `surveys`（问卷）

| 字段 | 类型 | 说明 |
|---|---|---|
| `_id` | ObjectId | |
| `owner_id` | ObjectId | 创建者 |
| `title` | string | |
| `description` | string | |
| `allow_anonymous` | bool | 是否允许匿名填写（仍可能要求登录，见需求；实现：登录用户可匿名标记身份） |
| `allow_multiple` | bool | 同一人是否可填多次 |
| `deadline` | datetime \| null | |
| `status` | string | `draft` \| `published` \| `closed` |
| `slug` | string | 公开链接键，`/survey/{slug}` |
| `created_at` | datetime | |
| `published_at` | datetime \| null | |
| `items` | array | 本卷题目编排，见下 |
| `jump_rules` | array | 跳转规则，见下 |

`items[]`**：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `item_id` | string | 本卷内稳定 id，如 `q1` |
| `question_id` | ObjectId | → questions._id（某一版） |
| `required` | bool | 本卷是否必答 |

`jump_rules[]`**：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `from_item` | string | 源 item_id |
| `when` | object | 条件，见下 |
| `to_item` | string \| `"end"` | 目标题或结束 |

`when` **示例：**

```json
{ "op": "eq", "option": "男" }                    // 单选
{ "op": "includes", "option": "苹果" }            // 多选含某项
{ "op": "between", "min": 18, "max": 60 }         // 数字
{ "op": "eq_number", "value": 1 }
```

无匹配的规则则默认「下一题」（按 items 顺序）。

索引：`owner_id`；`slug` 唯一；`status`。

---

### 4. `responses`（答卷）

| 字段 | 类型 | 说明 |
|---|---|---|
| `_id` | ObjectId | |
| `survey_id` | ObjectId | |
| `respondent_id` | ObjectId \| null | 登录用户；匿名策略下可仍存 user 但标记 anonymous |
| `anonymous` | bool | |
| `submitted_at` | datetime | |
| `answers` | array | 见下 |

`answers[]`**：**

| 字段 | 类型 | 说明 |
|---|---|---|
| `item_id` | string | |
| `question_id` | ObjectId | **必带**，支撑跨卷单题统计 |
| `value` | any | 单选 string；多选 string[]；文本 string；数字 number |

索引：`survey_id`；`answers.question_id`；`(survey_id, respondent_id)`（多次填写策略用）。

---

### 5. Session（Cookie）

不单独强调「业务集合」也可：

- 使用 Starlette/FastAPI **SessionMiddleware**（签名 Cookie 存 `user_id`），或  
- 可选集合 `sessions`：`{ session_id, user_id, expires_at }`

作业推荐：**SessionMiddleware + 签名 Cookie**，少一个集合。

---

## 二、页面路由

| 方法 | 路径 | 说明 | 登录 |
|---|---|---|---|
| GET | `/` | 首页 | 否 |
| GET/POST | `/register` | 注册 | 否 |
| GET/POST | `/login` | 登录 | 否 |
| POST | `/logout` | 注销 | 是 |
| GET | `/surveys` | 我的问卷列表 | 是 |
| GET/POST | `/surveys/new` | 创建问卷 | 是 |
| GET | `/surveys/{id}` | 问卷详情/编辑草稿 | 是（所有者） |
| POST | `/surveys/{id}/publish` | 发布 | 是 |
| POST | `/surveys/{id}/close` | 关闭 | 是 |
| GET/POST | `/surveys/{id}/items` | 从题库选题/加题编排 | 是 |
| GET/POST | `/surveys/{id}/jumps` | 配置跳转 | 是 |
| GET | `/survey/{slug}` | 填写入口 | 是（需求：填写需登录） |
| POST | `/survey/{slug}/answer` | 提交一题或整卷（实现可选分步） | 是 |
| GET | `/surveys/{id}/stats` | 整卷统计 | 是（所有者） |
| GET | `/surveys/{id}/stats/{item_id}` | 单题（本卷）统计 | 是 |
| GET | `/questions` | 我的题库/可选题 | 是 |
| GET/POST | `/questions/new` | 新建题（v1） | 是 |
| GET | `/questions/{id}` | 查看某版 | 是 |
| POST | `/questions/{id}/save` | **另存为新版本**并 flash 提示 | 是（所有者） |
| POST | `/questions/{id}/share` | 分享给用户 | 是 |
| GET | `/questions/{id}/usage` | 被哪些问卷使用 | 是 |
| GET | `/questions/by-logical/{logical_id}` | 版本历史 | 是 |
| GET | `/questions/{id}/stats-cross` | **跨卷**该题统计 | 是（所有者/有权） |

（也可用「页面 + 同路径 JSON API」双轨；下列 REST 便于测试与文档。）

---

## 三、JSON API 列表

统一前缀建议：`/api`。未登录返回 401。

### 认证

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/auth/register` | body: username, password |
| POST | `/api/auth/login` | 设置 session cookie |
| POST | `/api/auth/logout` | 清 session |
| GET | `/api/auth/me` | 当前用户 |

### 题库

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/questions` | 查询：own / bank / shared；支持 category |
| POST | `/api/questions` | 创建 v1 |
| GET | `/api/questions/{id}` | 某版详情 |
| POST | `/api/questions/{id}/versions` | 基于该版保存为新版本（body 为修改后字段） |
| GET | `/api/questions/logical/{logical_id}/versions` | 历史版本列表 |
| POST | `/api/questions/{id}/share` | body: user_ids[] 或 username |
| GET | `/api/questions/{id}/usage` | 引用该 `question_id` 的 surveys |
| GET | `/api/questions/{id}/stats` | 跨卷统计 |

### 问卷

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/surveys` | 我创建的列表 |
| POST | `/api/surveys` | 创建（title, description, allow_anonymous, allow_multiple, deadline） |
| GET | `/api/surveys/{id}` | 详情（含 items 解析出的题面） |
| PATCH | `/api/surveys/{id}` | 改元数据（仅 draft 或未影响已发布策略：仅 draft 可改 items） |
| POST | `/api/surveys/{id}/items` | 添加/重排 items（body: question_ids + required） |
| PUT | `/api/surveys/{id}/jump_rules` | 整表替换跳转规则 |
| POST | `/api/surveys/{id}/publish` | 生成/确认 slug，status=published |
| POST | `/api/surveys/{id}/close` | status=closed |
| GET | `/api/surveys/{id}/stats` | 本卷统计 |
| GET | `/api/surveys/{id}/stats/items/{item_id}` | 本卷单题统计 |

### 填写

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/fill/{slug}` | 问卷结构（按登录态；检查 deadline/status） |
| POST | `/api/fill/{slug}/next` | body: 当前 item 作答 → 返回下一 item（服务端跑跳转+校验） |
| POST | `/api/fill/{slug}/submit` | 提交完整 answers[]（再次校验） |

### 统计结果形状（约定）

- 单选：`{ options: [{label, count}], total_answers }`  
- 多选：`{ options: [{label, count}], total_responses }`  
- 文本：`{ values: [...] }`  
- 数字：`{ values: [...], avg }`

跨卷统计与本卷类似，但 match 条件为 `answers.question_id`。

---

## 四、权限与业务规则

1. 用户只能管理自己的 survey；题库：所有者可改版；`shared_with` 可只读引用到卷中。
2. `published` 后：**禁止改 items 的 question_id 列表**（或整卷锁定）；关闭用 `closed`。
3. 改题只走「新版本」；旧 survey 仍指向旧 `question_id`。
4. 填写：需登录；校验 required / multi 数量 / text 长度 / number 范围与整数；跑 jump_rules。
5. `allow_multiple=false` 时同一 `respondent_id` 仅一条 response。

---

## 五、与需求覆盖对照

| 需求 | 靠什么 |
|---|---|
| 注册登录、我的问卷 | users + surveys.owner_id |
| 发布/截止/关闭/链接 | status, deadline, slug |
| 三种题型+校验 | questions.type + validation |
| 可配置跳转 | surveys.jump_rules |
| 填写保存 | responses |
| 本卷统计 | responses + survey_id |
| 题库存题、复用 | questions.in_bank + items.question_id |
| 分享 | visibility + shared_with |
| 改题不影响旧卷 | 不可变版本 + 引用 id |
| 版本历史 / 多版本并存 | logical_id + version + derived_from |
| 题被哪些卷用 | usage 查询 surveys.items.question_id |
| 跨卷单题统计 | answers.question_id |


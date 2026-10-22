# AI 使用日志（阶段一）

工具：Cursor Agent

---

## 1. 读题、范围

Prompt:
```
@homework/04 大作业的内容是什么，涉及什么知识点，要完成什么
```

Result:
- 说明项目是「类问卷星」的 MongoDB 问卷系统，分两阶段，阶段一按初始需求实现。

修改：无代码。后来用户补充「需求变更一里的也要实现」，范围改为初始需求 + 需求变更一起设计。

---

## 2. 用户提出的数据想法

Prompt:
```
需求变更一里的也要实现。我想的说设计一个存储题目的数据库，
然后版本要不要设计一个嵌套库呢，感觉可能库太多了，你怎么看，
然后题目库嵌套在问卷库当中，再涉及问卷库和用户库，题目分类，
同时包含时间，版本等等信息
```

Result:
- AI 建议不要把题库嵌进问卷；版本不要再单独开一个集合。
- 推荐 4 个集合：users / questions / surveys / responses。
- 版本用「一版一文档 + logical_id」，问卷只引用某一版的 question_id。

修改：
- 采纳「不把题目库嵌套在问卷里」。
- 未采用「版本再开嵌套库」。
- 分类做成 questions 上的 category 字段，没有单独分类集合。

---

## 3. snapshot 是否需要

Prompt）:
```
不能直接嵌套我理解了，snapshot怎么实现的，要存储什么东西呢，
题库里要备份一份吗还是什么，如果分了版本的话，修改之后不就是产生新的版本吗，
嵌套引用前版本的题目不存在修改题目产生新版本后影响问卷中的题目啊
```

Result:
- AI 同意：版本不可变 + 问卷引用旧版 id 时，改题出新版不会影响旧问卷。
- snapshot 只是可选双保险，不是题库再备份一份。

修改：
- 最终方案不做 snapshot。
- 用户补充：「没有要求一定要可以改变旧版本，修改后保存自动变成新版本然后告知就行」→ 实现为保存=insert 新版并提示。

---

## 4. 技术栈取舍

Prompt:
```
需求ok，先确定技术栈，再确定字段和api
```
随后:
```
前端fastapi，vue以及认证的JWT（session cookie）怎么取舍，各有什么优劣，现在普遍生产使用什么
```

Result:
- 作业推荐 FastAPI + Jinja 模板 + Session Cookie。
- 生产里浏览器应用常用 HttpOnly Cookie（session 或 JWT）；SPA/App 常用 Bearer JWT。作业不因此改成 Vue。

修改：
- 用户拍板：「模板 + Session Cookie，然后开始字段设计＋api列表」
- 未使用 Vue，未使用 JWT。

---

## 5. 字段含义、分享、填写身份

Prompt:
```
这些都对应什么
（users / questions / surveys / responses 字段表）
```
随后:
```
分享相关谁可以借去用（同事/同学）怎么设计呢，
填写问卷肯定需要填写的id，那是让用户自己填信息还是注册呢，
我觉得可以注册，这样子可以实现后续已答问题的统计和溯源
```

Result:
- 用生活例子解释四集合。
- 填写：题面要求登录；采用注册账号，答卷写 respondent_id。
- 匿名：仍登录，只在答卷上打 anonymous 标记。
- 分享：questions.shared_with 存对方用户 id，所有者输入用户名添加；被分享者可引用进自己的卷，不能改原版。

修改：按上述实现，没有做「不登录临时填姓名」。

---

## 6. 实现

Prompt:
```
ok
```
（确认方案后开始写代码）

Result:
- 生成 `homework/04/survey-app/`：FastAPI、模板页、pymongo、API、pytest。

修改（实现时相对「理想依赖」做的调整）：
- 密码哈希用标准库 PBKDF2，没有装 passlib。
- 测试用 mongomock，避免测试必须连正在跑的 mongod。
- 跳转/校验写在 `app/logic.py`，规则存在 surveys.jump_rules / questions.validation，没有写死某一份问卷。

---

## 7. 本条日志本身

Prompt:
```
ai使用日志选用真实对话
```

Result:
- 把原先「摘要式」日志改成上面这种 Prompt / Result / 修改 格式，便于作业评分查看。

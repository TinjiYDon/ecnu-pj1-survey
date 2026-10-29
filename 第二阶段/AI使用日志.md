# AI 使用日志（阶段一 + 阶段二）

工具：Cursor Agent

***

## 1. 读题、范围

Prompt:

```
@homework/04 大作业的内容是什么，涉及什么知识点，要完成什么
```

Result:

- 说明项目是「类问卷星」的 MongoDB 问卷系统，分两阶段，阶段一按初始需求实现。

修改：无代码。后来用户补充「需求变更一里的也要实现」，范围改为初始需求 + 需求变更一起设计。

***

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
- 版本用「一版一文档 + logical\_id」，问卷只引用某一版的 question\_id。

修改：

- 采纳「不把题目库嵌套在问卷里」。
- 未采用「版本再开嵌套库」。
- 分类做成 questions 上的 category 字段，没有单独分类集合。

***

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

***

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

***

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
- 填写：题面要求登录；采用注册账号，答卷写 respondent\_id。
- 匿名：仍登录，只在答卷上打 anonymous 标记。
- 分享：questions.shared\_with 存对方用户 id，所有者输入用户名添加；被分享者可引用进自己的卷，不能改原版。

修改：按上述实现，没有做「不登录临时填姓名」。

***

## 6. 实现

Prompt:

```
ok
```

（确认方案后开始写代码）

Result:

- 生成 `homework/04/第一阶段/survey-app/`：FastAPI、模板页、pymongo、API、pytest。
  （阶段二代码为 `homework/04/第二阶段/survey-app/`，是在它基础上修改的）

修改（实现时相对「理想依赖」做的调整）：

- 密码哈希用标准库 PBKDF2，没有装 passlib。
- 测试用 mongomock，避免测试必须连正在跑的 mongod。
- 跳转/校验写在 `app/logic.py`，规则存在 surveys.jump\_rules / questions.validation，没有写死某一份问卷。

***

# 阶段二

工具：Trae Agent（Kimi）

## 1. 梳理阶段二目标和差距

Prompt:

```
大作业目前已经完成了第一阶段和部分需求，在 homework/04 里，
现在要继续完成第二阶段，先梳理第二阶段目标，再整理出框架和方案，我确定后再进行改进
```

Result:

- AI 读了阶段一/需求变更 docx、全部代码和文档，把 8 条变更逐条对照实现：
  已完成 4 条（复用、分享、改题不影响旧卷、多版本共存），
  有缺口 4 条：恢复旧版本缺失；usage 只查单版本；题库把 v1/v2/v3 全列出且无加入/移出操作；跨卷统计只算单版本。
- 另指出版本号「查最新+1」并发会撞号，建议 (logical\_id, version) 唯一索引。
- 给出阶段二方案：补齐 4 缺口 + 唯一索引 + 5 个新测试 + 文档和阶段二报告。

修改：

- 用户确认范围「补齐+深化」、报告「新建阶段二报告」后才开始改代码。

## 9. 恢复旧版本的语义

Prompt:

```
（讨论恢复语义）恢复 = 创建内容拷贝自旧版的新版本，还是直接回滚？
```

Result:

- AI 建议不允许回滚删历史：恢复 = 以旧版内容为蓝本 insert 最新版，
  derived\_from 指向原最新版保持链连续，新增 restored\_from 记内容来源；
  分享/分类/题库标记沿用家族现状，不从旧版带回。

修改：采纳。restore 最新版本身会报 400。

## 10. 族级口径的兼容做法

Result:

- usage / 跨卷统计都加 `scope=version|family` 参数，默认 version 保持旧行为；
  family 用 `$in 族内全部版本_id` 查询，选择题选项骨架取各版本并集防漏计。
- 题库列表 scope=bank 按 logical\_id 去重只出最新版。
- (logical\_id, version) 升唯一索引，启动时自动替换旧非唯一索引；写入撞号重取版本号重试。

修改：

- 用户要求旧功能必须可用，确认默认口径不变这条底线。

## 11. 验证

Result:

- `python -m pytest -q` → 9 passed（旧 4 个回归 + 新 5 个：恢复、族级 usage、族级统计、题库最新版/开关、唯一索引）。
- 另跑模板页冒烟脚本时发现所有网页 500：starlette 1.x 移除了 `TemplateResponse(name, context)` 旧参数顺序，
  12 处调用统一改成 `TemplateResponse(request, name, context)` 后页面全部 200。
  这是阶段一遗留问题（旧环境能跑、pytest 只测 JSON API 所以没暴露）。

修改：修复模板调用签名后重跑 pytest 9 passed、冒烟全过。

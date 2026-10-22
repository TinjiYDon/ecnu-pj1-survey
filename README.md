# 基于 MongoDB 的问卷系统

华东师范大学《当代数据管理系统》大作业一（阶段一，含需求变更）。

学号 10245501470，姓名唐竟涵。

技术栈：FastAPI + Jinja2 模板页 + Session Cookie + MongoDB（pymongo）。网页和 JSON 接口都有。

## 目录

| 路径 | 内容 |
|---|---|
| `survey-app/` | 可运行代码、自动测试、字段规则 `mongo-schema.md` |
| `项目文档.md` | 系统说明、数据库设计、API、关键逻辑 |
| `测试用例.md` | 测试步骤 / 输入 / 输出 / 结果 |
| `项目完成报告.md` | 水杉提交的报告正文（另导出 PDF） |
| `AI使用日志.md` / `AI使用说明.md` | AI 使用记录 |

## 运行

需要本机已启动 `mongod`（与课程 Lab 相同即可）。

```powershell
cd survey-app
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

浏览器打开 http://127.0.0.1:8000 。先注册登录，再创建题目 / 问卷。填写地址形如 `/survey/{slug}`，必须登录。

可选环境变量：`SURVEY_MONGO_URI`（默认 `mongodb://127.0.0.1:27017/`）、`SURVEY_DB_NAME`（默认 `survey_app`）、`SURVEY_SECRET`。

## 测试

不依赖正在跑的 mongod（用 mongomock）：

```powershell
cd survey-app
python -m pytest -q
```

应看到 `4 passed`。

## 数据模型

四个集合：`users`、`questions`、`surveys`、`responses`。题目一版一文档，问卷只引用某一版的 `question_id`。字段规则见 `survey-app/mongo-schema.md`。

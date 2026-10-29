# 大作业一 · 第一阶段

华东师范大学《当代数据管理系统》大作业一（阶段一提交物）。
学号 10245501470　姓名 唐竟涵　GitHub：https://github.com/TinjiYDon/ecnu-pj1-survey

本阶段完成基础问卷系统，并提前实现了《需求变更说明》的主体部分（题目独立、版本化、分享、按版本的跨卷统计）；
尚未实现「恢复旧版本」「族级统计口径」「题库管理入口」，这些是第二阶段的任务。

## 提交内容对照

| 要求 | 本目录文件 |
|---|---|
| 1. 代码（后端 / MongoDB schema / 配置说明，可运行） | [`survey-app/`](survey-app/)（`README.md` 为配置说明，`mongo-schema.md` 为 schema） |
| 2. 文档（系统说明 / 数据库设计 / API说明 / 关键逻辑） | [`项目文档.md`](项目文档.md)（四节对应四类） |
| 3. 测试用例（步骤 / 输入 / 输出 / 结果） | [`测试用例.md`](测试用例.md)（用例 A–G + 手工测试表） |
| 4. 项目完成报告（9 项齐全） | [`项目完成报告.md`](项目完成报告.md) |

附：[`AI使用日志.md`](AI使用日志.md)、[`AI使用说明.md`](AI使用说明.md)、[`design-schema-api.md`](design-schema-api.md)（本阶段字段与 API 设计草稿）。

## 运行

```powershell
cd survey-app
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

浏览器 http://127.0.0.1:8000 。**需要本机 `mongod` 已启动**；配置项与常见问题见
[`survey-app/README.md`](survey-app/README.md)。

## 测试

```powershell
cd survey-app
python -m pytest -q
```

期望 `4 passed`（不依赖 mongod，使用 mongomock）。

## 运行兼容性修订说明（不影响功能）

阶段一的原始代码在本机新版依赖下网页会报错。为保证「必须可运行」，提交时做了两处**非功能性修订**，
业务逻辑与数据结构未变：

1. 12 处模板渲染由旧签名 `TemplateResponse(name, context)` 改为 `TemplateResponse(request, name, context)`
   （starlette 1.x 移除了旧参数顺序，旧写法在 1.x 下所有页面 500）。
2. `stats.html` 的 `stats.items` 改为 `stats['items']`：Jinja 中 `stats.items` 会取到字典的 `items` 方法
   而不是同名键，导致问卷统计页报错。

修订后已逐页冒烟（首页、注册登录、问卷列表/新建/详情/统计、题库、题目详情、跨卷统计、填写页），均返回 200；
`pytest` 仍为 4 passed。

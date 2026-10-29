# 大作业一 · 提交总目录

华东师范大学《当代数据管理系统》大作业一。
学号 10245501470　姓名 唐竟涵　GitHub：https://github.com/TinjiYDon/ecnu-pj1-survey

代码按阶段拆成两个**自包含、可运行**的版本，每个目录都齐备课程要求的四类提交物。

## 目录

```
04/
├── 第一阶段/     # 阶段一提交物（基础问卷系统 + 需求变更主体）
└── 第二阶段/     # 阶段二提交物（按需求变更补齐与深化）
```

## 两阶段对照

| 内容 | 第一阶段 | 第二阶段 |
|---|---|---|
| 代码 | [`第一阶段/survey-app/`](第一阶段/survey-app/) | [`第二阶段/survey-app/`](第二阶段/survey-app/) |
| 配置说明 | [`第一阶段/survey-app/README.md`](第一阶段/survey-app/README.md) | [`第二阶段/survey-app/README.md`](第二阶段/survey-app/README.md) |
| MongoDB schema | [`第一阶段/survey-app/mongo-schema.md`](第一阶段/survey-app/mongo-schema.md) | [`第二阶段/survey-app/mongo-schema.md`](第二阶段/survey-app/mongo-schema.md) |
| 文档（系统/数据库/API/关键逻辑） | [`项目文档.md`](第一阶段/项目文档.md) | [`项目文档.md`](第二阶段/项目文档.md) |
| 测试用例（步骤/输入/输出/结果） | [`测试用例.md`](第一阶段/测试用例.md) | [`测试用例.md`](第二阶段/测试用例.md) |
| 项目完成报告 | [`项目完成报告.md`](第一阶段/项目完成报告.md) | [`项目完成报告.md`](第二阶段/项目完成报告.md) |
| 自动测试 | 4 passed | 9 passed |

阶段一：基础问卷系统，并提前实现需求变更的主体（题目独立/版本化/分享/按版本跨卷统计）。
阶段二：在同一套代码上补齐「恢复旧版本、族级使用查询、题库管理、族级跨卷统计」，
升级版本号唯一索引，并修复 starlette 1.x 的模板兼容问题；旧功能与旧数据全部保留。

## 各阶段运行

两个阶段的启动方式相同（均需本机 `mongod` 已启动）：

```powershell
cd 第一阶段/survey-app      # 或 第二阶段/survey-app
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

浏览器打开 http://127.0.0.1:8000 。

## 各阶段测试

```powershell
cd 第一阶段/survey-app      # 或 第二阶段/survey-app
python -m pytest -q
```

不依赖正在运行的 mongod（使用 mongomock）。第一阶段应为 `4 passed`，第二阶段应为 `9 passed`。

## 课程材料

- `大作业一第一阶段.docx`：第一阶段作业要求
- `大作业一：需求变更.docx`：需求变更说明（第二阶段任务来源）
- `2026_ECNU_PJ1_1_唐竟涵.pdf`：第一阶段报告 PDF 版

# 大作业一 · 第二阶段

华东师范大学《当代数据管理系统》大作业一（阶段二提交物）。
学号 10245501470　姓名 唐竟涵　GitHub：https://github.com/TinjiYDon/ecnu-pj1-survey

第二阶段按《需求变更说明》在阶段一代码上**修改扩展**（不推倒重做），补齐四处缺口并加固数据一致性：

1. **恢复旧版本**：以旧版内容生成最新版，历史版本不删不改（新增字段 `restored_from`）
2. **族级使用查询**：`usage?scope=family` 按 `logical_id` 聚合，标注各问卷钉在哪一版
3. **题库管理**：题目详情页加入/移出题库，整族生效；选题列表按族只显示最新版
4. **族级跨卷统计**：`stats?scope=family` 聚合全族作答，并给 `by_version` 细分
5. **并发加固**：`(logical_id, version)` 升级为唯一索引，版本号撞号自动重取重试
6. **兼容修复**：模板渲染统一为 `TemplateResponse(request, name, context)`，适配 starlette 1.x

## 提交内容对照

| 要求 | 本目录文件 |
|---|---|
| 1. 代码（后端 / MongoDB schema / 配置说明，可运行） | [`survey-app/`](survey-app/)（`README.md` 为配置说明，`mongo-schema.md` 为 schema） |
| 2. 文档（系统说明 / 数据库设计 / API说明 / 关键逻辑） | [`项目文档.md`](项目文档.md) |
| 3. 测试用例（步骤 / 输入 / 输出 / 结果） | [`测试用例.md`](测试用例.md)（用例 A–L + 手工测试表） |
| 4. 项目完成报告（9 项齐全 + 修改过程） | [`项目完成报告.md`](项目完成报告.md) |

附：[`AI使用日志.md`](AI使用日志.md)、[`AI使用说明.md`](AI使用说明.md)。

## 运行

```powershell
cd survey-app
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

浏览器 http://127.0.0.1:8000 。**需要本机 `mongod` 已启动**；配置项、从阶段一升级时的索引替换、
常见问题见 [`survey-app/README.md`](survey-app/README.md)。

## 测试

```powershell
cd survey-app
python -m pytest -q
```

期望 `9 passed`（阶段一 4 个回归 + 阶段二新增 5 个，不依赖 mongod）。

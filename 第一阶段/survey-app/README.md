# 问卷系统 · 运行与配置说明（阶段一）

本目录是阶段一的可运行代码。字段规则见 [`mongo-schema.md`](mongo-schema.md)。

## 1. 环境要求

| 项 | 要求 |
|---|---|
| Python | 3.10 及以上（开发环境 3.12） |
| MongoDB | 5.0 及以上，本机 `mongod` 已启动 |
| 依赖 | 见 `requirements.txt`（FastAPI / uvicorn / pymongo / jinja2 / python-multipart / itsdangerous / pytest / httpx / mongomock） |

## 2. 安装与启动

```powershell
cd survey-app
pip install -r requirements.txt
# 另开一个终端确认 MongoDB 已启动（默认 127.0.0.1:27017）
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

浏览器打开 http://127.0.0.1:8000 ，先注册再登录。

## 3. 配置项（环境变量）

| 变量 | 默认值 | 说明 |
|---|---|---|
| `SURVEY_MONGO_URI` | `mongodb://127.0.0.1:27017/` | MongoDB 连接串 |
| `SURVEY_DB_NAME` | `survey_app` | 数据库名 |
| `SURVEY_SECRET` | `dev-secret-change-me` | Session Cookie 签名密钥，部署时应更换 |

见 [`app/config.py`](app/config.py)。会话有效期 7 天（`SESSION_MAX_AGE`）。

## 4. 数据库初始化

无需手工建库建集合：首次写入时 MongoDB 自动创建 `users` / `questions` / `surveys` / `responses`；
应用启动时 `ensure_indexes()` 自动补索引（`app/db.py`）。集合与索引规则见 `mongo-schema.md`。

## 5. 自动测试

不依赖正在运行的 `mongod`（用 mongomock）：

```powershell
cd survey-app
python -m pytest -q
```

期望 `4 passed`。

## 6. 目录结构

```
survey-app/
├── app/
│   ├── main.py          # 路由：网页 + JSON API
│   ├── services.py      # 业务逻辑（题目/问卷/答卷/统计）
│   ├── logic.py         # 跳转与校验
│   ├── db.py            # 连接与索引
│   ├── security.py      # 密码哈希
│   ├── config.py        # 环境变量
│   └── templates/       # Jinja2 页面
├── tests/test_api.py    # 自动测试
├── mongo-schema.md      # MongoDB schema
└── requirements.txt
```

## 7. 常见问题

- **启动报连接失败**：先确认 `mongod` 已运行，或改 `SURVEY_MONGO_URI`。
- **表单提交 422**：缺 `python-multipart`，重装依赖。
- **网页报 `unhashable type: 'dict'`**：starlette 1.x 的模板参数顺序变化，本阶段代码已统一为
  `TemplateResponse(request, name, context)`，新旧版本都可用。

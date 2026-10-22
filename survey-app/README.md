# 问卷系统（运行说明）

仓库根目录的 `README.md` 是总说明。这里只写本目录怎么启动。

```powershell
cd survey-app
pip install -r requirements.txt
# 本机 mongod 需已启动
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
python -m pytest -q
```

浏览器：http://127.0.0.1:8000

环境变量：`SURVEY_MONGO_URI`、`SURVEY_DB_NAME`、`SURVEY_SECRET`。  
字段规则：`mongo-schema.md`。

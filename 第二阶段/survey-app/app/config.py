# -*- coding: utf-8 -*-
import os

MONGO_URI = os.environ.get("SURVEY_MONGO_URI", "mongodb://127.0.0.1:27017/")
DB_NAME = os.environ.get("SURVEY_DB_NAME", "survey_app")
SECRET_KEY = os.environ.get("SURVEY_SECRET", "dev-secret-change-me")
SESSION_MAX_AGE = 60 * 60 * 24 * 7

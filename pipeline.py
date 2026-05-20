import os
from sqlalchemy import create_engine
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

engine = create_engine(
    os.getenv("DB_URL"),
    connect_args={"sslmode": "require"}
)

print(pd.read_sql("SELECT 1", engine))
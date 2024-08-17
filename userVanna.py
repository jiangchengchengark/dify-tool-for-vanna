import pandas as pd
import docx2txt
from vanna.ZhipuAI import ZhipuAI_Chat
from vanna.vannadb import VannaDB_VectorStore
from dotenv import load_dotenv
import os
from vanna.flask import VannaFlaskApp
import threading
from vanna.ZhipuAI import ZhipuAI_Chat
from vanna.chromadb import ChromaDB_VectorStore
from vanna.ZhipuAI import ZhipuAIEmbeddingFunction
import uuid
import pandas as pd
# 创建zhipuembedding实例
load_dotenv()
local_ip = os.getenv("LOCAL_IP")
api_key = os.getenv("API_KEY")
zhipu_ai_embedding_function = ZhipuAIEmbeddingFunction(
    config={"api_key": api_key,"model_name":"embedding-2"}
)

# 基本不变，系统设定的llm和向量数据库装置
# 初始化系统
# 重写VannaFlaskApp类中的run方法，实现自定义的flask启动方式
class CustomFlaskApp(VannaFlaskApp):
    def run(self, port):
        try:
            from google.colab import output
            output.serve_kernel_port_as_window(port)
            from google.colab.output import eval_js
            print("Your app is running at:")
            print(eval_js(f"google.colab.kernel.proxyPort({port})"))
        except:
            print("Your app is running at:")
            print(f"{local_ip}:{port}")
        self.flask_app.run(host="0.0.0.0", port=port, use_reloader=False, debug=True)

class init_Vanna(ChromaDB_VectorStore, ZhipuAI_Chat):
    def __init__(self, config=None, vsconfig=None):
        ChromaDB_VectorStore.__init__(self, config=vsconfig)
        ZhipuAI_Chat.__init__(self, config=config)

# 全局字典存储每个用户的向量数据库路径
user_vsconfig_paths = {}

class userVanna:
    def __init__(self, sql_name, user_id, init_Vanna=init_Vanna, customflaskapp=CustomFlaskApp):
        self.sql_name = sql_name
        self.user_id = user_id
        self.vsconfig = self.get_or_create_vsconfig_path()
        self.user_Vanna = init_Vanna(config={"api_key": api_key, "model": "glm-4-flash"}, vsconfig=self.vsconfig)
        self.port = None
        self.customflaskapp = customflaskapp
        self.port_event = threading.Event()

    def get_or_create_vsconfig_path(self):
        if self.user_id in user_vsconfig_paths:
            path = user_vsconfig_paths[self.user_id]
        else:
            path = self.generate_unique_path()
            user_vsconfig_paths[self.user_id] = path
        return {
            "embedding_function": zhipu_ai_embedding_function,
            "n_results_sql": 5,
            "n_results_documentation": 5,
            "n_results_ddl": 3,
            "path": path
        }

    def generate_unique_path(self):
        # 生成一个唯一的向量数据库路径
        unique_id = uuid.uuid4().hex
        directory="./embedding_db"
        if not os.path.exists(directory):
            os.makedirs(directory)
        path=f"{directory}/{unique_id}.chroma"
        return path


    def connect(self, **kwargs):
        if self.sql_name == "mysql":
            self.get_Mysql_connect(**kwargs)
        elif self.sql_name == "sqlite":
            self.get_SQLite_connect(**kwargs)
        elif self.sql_name == "snowflake":
            self.get_snowflake_content(**kwargs)
        else:
            raise ValueError("Unsupported database type")

    def get_Mysql_connect(self, host=None, dbname=None, user=None, password=None, port=None,sql_name=None,role=None):
        self.user_Vanna.connect_to_mysql(host=host, dbname=dbname, user=user, password=password, port=port)

    def get_SQLite_connect(self, host=None, port=None, dbname=None,sql_name=None,role=None,user=None,passward=None):
        self.user_Vanna.connect_to_sqlite(f"{host}:{port}/{dbname}")

    def get_snowflake_content(self, host=None, user=None, password=None, dbname=None, role=None,sql_name=None,port=None):
        self.user_Vanna.connect_to_snowflake(account=host, username=user, password=password, database=dbname, role=role)

    # 其他方法...

    def pre_train(self, log_callback=None):
        if log_callback:
            log_callback("开始预训练...")
        
        df_information_schema = self.user_Vanna.run_sql("SELECT * FROM INFORMATION_SCHEMA.COLUMNS")
        if log_callback:
            log_callback("获取到数据库元数据。")
        
        plan = self.user_Vanna.get_training_plan_generic(df_information_schema)
        if log_callback:
            log_callback("训练计划创建完毕。")
        
        self.user_Vanna.train(plan=plan)
        if log_callback:
            log_callback("正在训练...")
        
        self.user_Vanna.train(
            ddl="""
CREATE TABLE IF NOT EXISTS my-table (
    id INT PRIMARY KEY,
    name VARCHAR(100),
    age INT
)
"""
        )
        if log_callback:
            log_callback("正在使用DDL语句训练，注意，这并不会在您的数据库上进行任何操作")
        
        if log_callback:
            log_callback("预训练已完毕。")
        
        return 0

    def documentation_train(self, file_path):
        if file_path.endswith('.docx'):
            file_path = docx2txt.process(file_path)
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        f.close()
        self.user_Vanna.train(documentation=content)

    def sql_train(self, sql_list):
        for sql in sql_list:
            self.user_Vanna.train(sql=sql)

    def sql_question_train(self, file_path):
        df = pd.read_excel(file_path)
        for index, row in df.iterrows():
            question = row['question']
            sql = row['sql']
            self.user_Vanna.train(question=question, sql=sql)

    def inference(self, question):
        return self.user_Vanna.ask(question)

    def web_server(self):
        app = self.customflaskapp(self.user_Vanna, allow_llm_to_see_data=True)
        self.port = self.find_free_port()
        self.port_event.set()
        app.run(port=self.port)

    def find_free_port(self):
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            return s.getsockname()[1]

    def start_web_server(self):
        thread = threading.Thread(target=self.web_server)
        thread.start()
        self.port_event.wait()
        return self.port
    def generate_sql_code(self,question):

        return self.user_Vanna.generate_sql(question)
    def ask(self,question):
        sql=self.user_Vanna.generate_sql(question)
        df=self.user_Vanna.run_sql(sql)
        if type(df) != str:
            df=df.to_string()
        return df



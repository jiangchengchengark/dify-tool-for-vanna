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
from vanna.qianfan import Qianfan_Chat 
from vanna.qianfan import Qianfan_embeddings
from vanna.vllm import Vllm 
from vanna.ollama import Ollama 
import json
# 加载环境变量
import socket
import requests
from flask import request
import textract
load_dotenv()
# 本地地址
local_adress = os.getenv("LOCAL_ADRESS")
key = os.getenv("KEY")
# 基本不变，系统设定的llm和向量数据库装置
# 初始化系统
# 重写VannaFlaskApp类中的run方法，实现自定义的flask启动方式
from flask import Flask, request
from flask_sock import Sock
from flask import jsonify
import signal
class CustomFlaskApp(VannaFlaskApp):
    #接收任意参数
    #def shutdown_server(self):
        #pid = os.getpid()
        #os.kill(pid, signal.SIGINT)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        @self.flask_app.route('/shutdown',methods=['POST'])
        def shutdown():
            self.stop_event.set()
            return "Server shutting down..."
    def run(self, port=None):
        try:
            from google.colab import output
            output.serve_kernel_port_as_window(port)
            from google.colab.output import eval_js
            print("Your app is running at:")
            print(eval_js(f"google.colab.kernel.proxyPort({port})"))
        except:
            print("Your app is running at:")
            print(f"http://10.0.1.38:{port}")
            self.flask_app.run(host="0.0.0.0", port=port, use_reloader=False, debug=True)
    
class zhipu_Vanna(ChromaDB_VectorStore, ZhipuAI_Chat):
    def __init__(self, config=None, vsconfig=None):
        ChromaDB_VectorStore.__init__(self, config=vsconfig)
        ZhipuAI_Chat.__init__(self, config=config)

class qianfan_Vanna(ChromaDB_VectorStore, Qianfan_Chat):
    def __init__(self, config=None, vsconfig=None):
        ChromaDB_VectorStore.__init__(self, config=vsconfig)
        Qianfan_Chat.__init__(self, config=config)

class vllm_Vanna(ChromaDB_VectorStore, Vllm):
    def __init__(self, config=None, vsconfig=None):
        ChromaDB_VectorStore.__init__(self, config=vsconfig)
        Vllm.__init__(self, config=config)

class ollama_Vanna(ChromaDB_VectorStore, Ollama):
    def __init__(self, config=None, vsconfig=None):
        ChromaDB_VectorStore.__init__(self, config=vsconfig)
        Ollama.__init__(self, config=config)

# 全局字典存储每个用户的向量数据库路径
user_vsconfig_paths = {}

class init_Vanna:
    CLASS_MAP = {
        "zhipu": zhipu_Vanna,
        "qianfan": qianfan_Vanna,
        "vllm": vllm_Vanna,
        "ollama": ollama_Vanna
    }
    EMBEDDING_MAP = {
        "zhipu": ZhipuAIEmbeddingFunction,
        "qianfan": Qianfan_embeddings,
        "vllm": None,
        "ollama": None
    }

    def __init__(self, key=None, user_id=None):
        self.key = key
        self.vsconfig = None
        self.user_id = user_id
    def generate_unique_path(self):
        # 生成一个唯一的向量数据库路径
        unique_id = uuid.uuid4().hex
        directory = "./embedding_db"
        if not os.path.exists(directory):
            os.makedirs(directory)
        path = f"{directory}/{unique_id}.chroma"
        return path

    def get_or_create_vsconfig_path(self,):
        if self.user_id in user_vsconfig_paths:
            path = user_vsconfig_paths[self.user_id]
        else:
            path = self.generate_unique_path()
            user_vsconfig_paths[self.user_id] = path
        total_config = self.load_config_for_class(self.key)
        try:
            vsconfig = total_config.get("vsconfig")
        except:
            vsconfig = None
        if vsconfig is not None:
            embeddingmodel = self.EMBEDDING_MAP[self.key]
            return {
                "embedding_function": embeddingmodel(config=vsconfig),
                "n_results_sql": 5,
                "n_results_documentation": 5,
                "n_results_ddl": 3,
                "path": path
            }
        else:
            return {
                "embedding_function": None,
                "n_results_sql": 5,
                "n_results_documentation": 5,
                "n_results_ddl": 3,
                "path": path
            }

    def load_config_for_class(self, key):
        with open("config.json", "r") as f:
            config_data = json.load(f)
            return config_data.get(key, {})

    def get_instance(self):
        config_data = self.load_config_for_class(self.key)
        cls = self.CLASS_MAP.get(self.key)
        if cls is not None:
            return cls(config=config_data.get('config'), vsconfig=self.get_or_create_vsconfig_path())
        else:
            raise ValueError(f"未知的类类型：{self.key}")

class userVanna:
    def __init__(self, sql_name, user_id,init_Vanna=init_Vanna, customflaskapp=CustomFlaskApp, key=key):
        self.sql_name = sql_name
        self.user_id=user_id
        self.user_Vanna = init_Vanna(key=key,user_id=self.user_id).get_instance()
        self.port = None
        self.customflaskapp = customflaskapp
        self.port_event = threading.Event()
        self.stop_event=threading.Event()
        self.server_thread = None
        self.app = None
    def connect(self, **kwargs):
        if self.sql_name == "mysql":
            self.get_Mysql_connect(**kwargs)
        elif self.sql_name == "sqlite":
            self.get_SQLite_connect(**kwargs)
        elif self.sql_name == "snowflake":
            self.get_snowflake_content(**kwargs)
        else:
            raise ValueError("Unsupported database type")

    def get_Mysql_connect(self, host=None, dbname=None, user=None, password=None, port=None):
        self.user_Vanna.connect_to_mysql(host=host, dbname=dbname, user=user, password=password, port=port)

    def get_SQLite_connect(self, adress=None, port=None, dbname=None):
        self.user_Vanna.connect_to_sqlite(f"{adress}:{port}/{dbname}")

    def get_snowflake_content(self, account, username, password, database, role):
        self.user_Vanna.connect_to_snowflake(account=account, username=username, password=password, database=database, role=role)

    def pre_train(self, log_callback=None):
        if log_callback:
            log_callback("开始预训练...")

        df_information_schema = self.user_Vanna.run_sql("SELECT * FROM INFORMATION_SCHEMA.COLUMNS")
        if log_callback:
            log_callback("获取到数据库元数据。")

        plan = self.user_Vanna.get_training_plan_generic(df_information_schema)
        if log_callback:
            log_callback("训练计划创建完毕。")
        if log_callback:
            log_callback("正在训练，训练结束前不会开启客户端，请耐心等待...")

        self.user_Vanna.train(plan=plan)
        
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

    def documentation_train(self, file_path,log_callback=None):
        if file_path.endswith('.docx'):
            content= docx2txt.process(file_path)
        elif file_path.endswith('.doc'):
            content=textract.process(file_path).decode('utf-8')
        else:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            f.close()
        if log_callback:
            log_callback("解析完毕...")
        if log_callback:
            log_callback("开始训练...")
        self.user_Vanna.train(documentation=content)
        if log_callback:
            log_callback("训练完成...")
    def sql_train(self, sql_list,log_callback=None):
        if log_callback:
            log_callback("开始训练...")
        for sql in sql_list:
            self.user_Vanna.train(sql=sql)
        if log_callback:
            log_callback("训练完成...")

    def sql_question_train(self, file_path,log_callback=None):
        df = pd.read_excel(file_path)
        for index, row in df.iterrows():
            question = row['question']
            sql = row['sql']
            if log_callback:
                log_callback(f"训练问题：{question}，SQL：{sql}")
            self.user_Vanna.train(question=question, sql=sql)
            if log_callback:
                log_callback(f"训练完成。")

    def inference(self, question):
        return self.user_Vanna.generate_sql(question)

    def web_server(self):
        self.app = self.customflaskapp(self.user_Vanna, allow_llm_to_see_data=True)
        self.port = self.find_free_port()
        self.port_event.set()
        print(f"Your app is running at: http://{local_adress}:{self.port}")
        #启动flask服务
        self.server_thread = threading.Thread(target=self.app.run,kwargs={"port":self.port})
        self.server_thread.start()
    def find_free_port(self):
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            return s.getsockname()[1]

    def start_web_server(self):
        self.web_server()
        #等待端口开启
        self.port_event.wait()
        print("Web server started.")
        #返回端口号
        if self.port is not None:
            return self.port
        else:
            return "开启失败，请检查端口是否被占用"
    def stop_web_server(self):
       if self.app is not None:
           self.app.stop_event.set()
    def generate_sql_code(self,question):

        return self.user_Vanna.generate_sql(question)
    def ask(self,question):
        sql=self.user_Vanna.generate_sql(question)
        df=self.user_Vanna.run_sql(sql)
        if type(df) != str:
            df=df.to_string()
        text=f"sql查询语句为:\n{sql}\n查询结果(含索引)：\n{df}"
        return text


        
            

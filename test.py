from flask import Flask, request, render_template, redirect, url_for, session, jsonify,make_response
from userVanna import userVanna
import uuid
import logging
import threading
import json
import os
# 导入环境变量
from dotenv import load_dotenv
load_dotenv()
local_adress = os.getenv('LOCAL_ADRESS')
app = Flask(__name__)
app.config["SERVER_NAME"]=f"{local_adress}:5000"
app.secret_key = '1345456'  # 设置一个秘密密钥用于会话加密
import time
import os
import json
import logging
import shutil
from  werkzeug.utils import secure_filename
# 配置日志记录
logging.basicConfig(level=logging.DEBUG)

# 配置上传文件夹路径
app.config['UPLOAD_FOLDER'] = 'uploads'
# 存储实例的字典
instances = {}

# 存储预训练日志的字典
pre_training_logs = {}

# 预训练信息文件路径
PRE_TRAINED_FILE = 'pre_trained.json'

# 初始化 embedding_db 目录
EMBEDDING_DB_DIR = 'embedding_db'

def initialize_files():
    # 清空 embedding_db 目录
    if os.path.exists(EMBEDDING_DB_DIR):
        shutil.rmtree(EMBEDDING_DB_DIR)
        logging.info(f"Removed directory: {EMBEDDING_DB_DIR}")
    os.makedirs(EMBEDDING_DB_DIR)
    logging.info(f"Created directory: {EMBEDDING_DB_DIR}")

    # 清空 pre_trained.json 文件
    if os.path.exists(PRE_TRAINED_FILE):
        os.remove(PRE_TRAINED_FILE)
        logging.info(f"Removed file: {PRE_TRAINED_FILE}")
    with open(PRE_TRAINED_FILE, 'w') as f:
        json.dump({}, f)
    logging.info(f"Created and initialized file: {PRE_TRAINED_FILE}")

# 在应用启动时调用初始化函数
initialize_files()
# 确保上传文件夹存在
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])
def load_pre_trained_info():
    if os.path.exists(PRE_TRAINED_FILE):
        with open(PRE_TRAINED_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_pre_trained_info(info):
    with open(PRE_TRAINED_FILE, 'w') as f:
        json.dump(info, f)


@app.before_request
def before_request():
    session['ip'] = request.remote_addr

@app.route('/')
def welcome():
    return render_template('welcome.html')

@app.route('/select_db', methods=['POST'])
def select_db():
    sql_name = request.form['sql_name']
    session['sql_name'] = sql_name
    return render_template(f'select_db_{sql_name}.html')


@app.route('/generate', methods=['POST'])
def generate():
    sql_name = session.get('sql_name')
    ip = session.get('ip')
    pre_trained_info = load_pre_trained_info()
    port = None
    instance = None
    session['port']=None
    # 检查是否已经有预训练好的实例
    db_name = session.get('db_name')
    if ip in pre_trained_info and sql_name in pre_trained_info[ip] and db_name in pre_trained_info[ip][sql_name] and pre_trained_info[ip][sql_name][db_name]:
        instance_id = pre_trained_info[ip][sql_name][db_name]['instance_id']
        instance = instances.get(instance_id)
        if instance:
            session['instance_id'] = instance_id
            session["pre_trained"] = True
            #启动 Web 服务并等待完成
            port_old=session.get('port')
            session["port"]= instance.start_web_server()
            while port_old==session.get('port'):
                time.sleep(1)
            return redirect(url_for('view_instance'))
    # 创建数据库实例
    try:
        if sql_name == 'mysql':
            # 数据库连接参数
            host = request.form['host']
            dbname = request.form['dbname']
            user = request.form['user']
            password = request.form['password']
            port = request.form['port']
            instance = userVanna(sql_name, user_id=ip)
            port = int(port)
            instance.connect(host=host, dbname=dbname, user=user, password=password, port=port)
            session['db_name'] = dbname
        elif sql_name == 'sqlite':
            # SQLite 参数
            adress = request.form['adress']
            port = request.form['port']
            port = int(port)
            dbname = request.form['dbname']
            instance = userVanna(sql_name, user_id=ip)
            instance.connect(adress=adress, port=port, dbname=dbname)
            session['db_name'] = dbname
        elif sql_name == 'snowflake':
            # Snowflake 参数
            account = request.form['account']
            username = request.form['username']
            password = request.form['password']
            database = request.form['database']
            role = request.form['role']
            instance = userVanna(sql_name, user_id=ip)
            instance.connect(account=account, username=username, password=password, database=database, role=role)
            session['db_name'] = database
        else:
            return "Unsupported database type"
    except ValueError:
        return "端口应为 int 类型"
    except Exception as e:
        logging.error(f"创建数据库实例时发生错误: {e}")
        return "创建数据库实例失败"

    # 存储实例的唯一标识符
    instance_id = str(uuid.uuid4())
    instances[instance_id] = instance
    session['instance_id'] = instance_id
    session["pre_trained"]=False
    # 检查预训练状态
    db_name = session.get('db_name')
    if not pre_trained_info.get(ip, {}).get(sql_name, {}).get(db_name, False):
        pre_training_logs[ip] = []
        # 启动预训练线程
        threading.Thread(target=pre_train_async, args=(instance, ip, sql_name, db_name)).start()
        #不用等待预训练完成，直接返回
        return redirect(url_for('view_instance'))
    else:
     #启动 Web 服务并等待完成
     port_old=session.get('port')
     session["port"]= instance.start_web_server()     
     while port_old==session.get('port'):
          time.sleep(1)
     return redirect(url_for('view_instance'))

@app.route('/connect', methods=['POST'])
def connect():
    ip = session.get('ip')
    pre_trained_info = load_pre_trained_info()
    port = None
    instance = None
    sql_name=request.form["sql_name"]
    session['sql_name'] = sql_name
    # 检查是否已经有预训练好的实例
    db_name = session.get('db_name')
    if ip in pre_trained_info and sql_name in pre_trained_info[ip] and db_name in pre_trained_info[ip][sql_name] and pre_trained_info[ip][sql_name][db_name]:
        instance_id = pre_trained_info[ip][sql_name][db_name]['instance_id']
        instance = instances.get(instance_id)
        print("存在预训练实例",instance_id)
        if instance:
            session['instance_id'] = instance_id
            session["pre_trained"] = True
            return  make_response(instance_id, 200)

    # 创建数据库实例
    try:
        if sql_name == 'mysql':
            # 数据库连接参数
            host = request.form['host']
            dbname = request.form['dbname']
            user = request.form['user']
            password = request.form['password']
            port = request.form['port']
            instance = userVanna(sql_name, user_id=ip)
            port = int(port)
            instance.connect(host=host, dbname=dbname, user=user, password=password, port=port)
            session['db_name'] = dbname
        elif sql_name == 'sqlite':
            # SQLite 参数
            adress = request.form['host']
            port = request.form['port']
            port = int(port)
            dbname = request.form['dbname']
            instance = userVanna(sql_name, user_id=ip)
            instance.connect(adress=adress, port=port, dbname=dbname)
            session['db_name'] = dbname
        elif sql_name == 'snowflake':
            # Snowflake 参数
            account = request.form['host']
            username = request.form['user']
            password = request.form['password']
            database = request.form['dbname']
            role = request.form['role']
            instance = userVanna(sql_name, user_id=ip)
            instance.connect(account=account, username=username, password=password, database=database, role=role)
            session['db_name'] = database
        else:
            return make_response("Unsupported database type", 400)
    except ValueError:
        return make_response("端口应为 int 类型", 400)
    except Exception as e:
        logging.error(f"创建数据库实例时发生错误: {e}")
        return make_response("创建数据库实例失败", 500)
    # 存储实例的唯一标识符
    instance_id = str(uuid.uuid4())
    instances[instance_id] = instance
    session['instance_id'] = instance_id
    session["pre_trained"]=False
     # 检查预训练状态
    db_name = session.get('db_name')
    if not pre_trained_info.get(ip, {}).get(sql_name, {}).get(db_name, False):
        try:
            pre_training_logs[ip] = []
            # 启动预训练线程
            threading.Thread(target=pre_train_async, args=(instance, ip, sql_name, db_name, instance_id)).start()
            # 不用等待预训练完成，直接返回
            return make_response(instance_id, 200)
        except Exception as e:
            logging.error(f"预训练线程启动失败: {e}")
            return make_response("预训练线程启动失败", 500)

    return make_response(instance_id, 200)
    
def pre_train_async(instance, ip, sql_name, db_name,instance_id):
    print("开始预训练")
    try:
            instance.pre_train(log_callback=lambda log: pre_training_logs[ip].append(log))
            print("预训练完毕")
            # 存储预训练状态
            pre_trained_info = load_pre_trained_info()
            if not pre_trained_info:
                if ip not in pre_trained_info:
                    pre_trained_info[ip] = {}
                    if sql_name not in pre_trained_info[ip]:
                        pre_trained_info[ip][sql_name] = {}
                    pre_trained_info[ip][sql_name][db_name]={
                        "instance_id":instance_id,
                        "pre_trained":True
                    }
            save_pre_trained_info(pre_trained_info)
            print("存储预训练状态完毕")

    except Exception as e:
            logging.error(f"预训练过程中发生错误: {e}")
    return  0
@app.route('/current_port')
def current_port():
    port = session.get('port')
    return jsonify({'port': port})

@app.route('/view')
def view_instance():
    instance_id = session.get('instance_id')
    port = session.get('port')
    if instance_id:
        url = f"{local_adress}:{port}"
        print("your app is running on: ", url)
        return render_template('view_instance.html', instance_id=instance_id, port=port, local_adress=local_adress, url=url)
    else:
        print("No instance generated")
        return "No instance generated", 404

@app.route('/check_pre_training')
def check_pre_training():
    #检查tran info中是否有预训练记录
    ip = session.get('ip')
    sql_name = session.get('sql_name')
    db_name = session.get('db_name')
    pre_trained_info = load_pre_trained_info()
    if  pre_trained_info.get(ip, {}).get(sql_name, {}).get(db_name, False):
        if session["pre_trained"]==False:
            session["pre_trained"]=True
        return jsonify({'pre_trained': True, 'port': session.get('port')})
    else:
        return jsonify({'pre_trained': False})

@app.route('/get_pre_training_log')
def get_pre_training_log():
    ip = session.get('ip')
    if ip:
        return jsonify({'log': pre_training_logs.get(ip, [])})
    return jsonify({'log': []})

@app.route('/train_documentation', methods=['POST'])
def train_documentation():
    instance_id = session.get('instance_id')
    if instance_id:
        instance = instances.get(instance_id)
        if instance:
            try:
                if "file" not in request.files:
                    return jsonify({'status': 'error', 'message': 'No file part in the request'})
                file = request.files["file"]
                if file.filename == "":
                    return jsonify({'status': 'error', 'message': 'No selected file'})
                if file and allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    #训练同时记录log_callback
                    instance.documentation_train(file_path, log_callback=lambda log: pre_training_logs[session.get('ip')].append(log))
                    print("训练完毕") 
                    return jsonify({'status': 'success', 'message': 'Documentation training completed'})
                else:
                    return jsonify({'status': 'error', 'message': 'File type not allowed'})
            except Exception as e:
                logging.error(f"训练文档时发生错误: {e}")
                return jsonify({'status': 'error', 'message': '训练文档时发生错误'})
    else:
        return jsonify({'status': 'error', 'message': 'Instance not found'})

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'txt', 'doc','docx'}

@app.route('/train_sql', methods=['POST'])
def train_sql():
    instance_id = session.get('instance_id')
    if instance_id:
        instance = instances.get(instance_id)
        if instance:
            try:
                sql_list = request.json.get('sql_list', [])
                #训练同时记录log_callback
                instance.sql_train(sql_list, log_callback=lambda log: pre_training_logs[session.get('ip')].append(log))
                return jsonify({'status': 'success', 'message': 'SQL training completed'})
            except Exception as e:
                logging.error(f"训练SQL时发生错误: {e}")
                return jsonify({'status': 'error', 'message': '训练SQL时发生错误'})
    return jsonify({'status': 'error', 'message': 'Instance not found'})

@app.route('/train_sql_question', methods=['POST'])
def train_sql_question():
    instance_id = session.get('instance_id')
    if instance_id:
        instance = instances.get(instance_id)
        if instance:
            try:
                file_path = request.form['file_path']
                #训练同时记录log_callback
                instance.sql_question_train(file_path, log_callback=lambda log: pre_training_logs[session.get('ip')].append(log))
                render_template('view_instance.html', instance_id=instance_id, local_adress=local_adress)
                return jsonify({'status': 'success', 'message': 'SQL question training completed'})
            except Exception as e:
                logging.error(f"训练SQL问题时发生错误: {e}")
                return jsonify({'status': 'error', 'message': '训练SQL问题时发生错误'})
    return jsonify({'status': 'error', 'message': 'Instance not found'})

@app.route('/inference', methods=['POST'])
def inference():
    instance_id = session.get('instance_id')
    if instance_id:
        instance = instances.get(instance_id)
        if instance:
            try:
                question = request.json.get('question')
                result =instance.inference(question)
                return jsonify({'status': 'success', 'result': result})
            except Exception as e:
                logging.error(f"推理时发生错误: {e}")
                return jsonify({'status': 'error', 'message': '推理时发生错误'})
    return jsonify({'status': 'error', 'message': 'Instance not found'})
@app.route('/get_sql_code', methods=['POST'])
def get_sql_code():
    data = request.json
    question = data['question']
    instance_id = data['instance_id']
    if instance_id:
        instance = instances.get(instance_id)
        if instance:
            try:
                return instance.generate_sql_code(question)
            except Exception as e:
                logging.error(f"生成SQL代码时发生错误: {e}")
                return '生成SQL代码时发生错误'
    return '未找到实例，请重新连接数据库'

@app.route('/get_answer', methods=['POST'])
def get_answer():
    data = request.json
    question = data['question']
    instance_id = data['instance_id']
    if instance_id:
        instance = instances.get(instance_id)
        if instance:
            try:
                return instance.ask(question)
            except Exception as e:
                logging.error(f"获取答案时发生错误: {e}")
                return  '发生错误，数据库查询失败'
    return  '未找到实例，请重新连接数据库'
if __name__ == '__main__':
    app.run(use_reloader=False, threaded=True, debug=True, host='0.0.0.0')

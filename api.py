from flask import Flask, request, jsonify
from userVanna import userVanna
import uuid
import logging
import threading
import json
import os

app = Flask(__name__)
app.secret_key = '1345456'  # 设置一个秘密密钥用于会话加密

# 配置日志记录
logging.basicConfig(level=logging.DEBUG)

# 存储实例的字典
instances = {}

# 存储预训练日志的字典
pre_training_logs = {}

# 预训练信息文件路径
PRE_TRAINED_FILE = 'pre_trained.json'

def load_pre_trained_info():
    if os.path.exists(PRE_TRAINED_FILE):
        with open(PRE_TRAINED_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_pre_trained_info(info):
    with open(PRE_TRAINED_FILE, 'w') as f:
        json.dump(info, f)

@app.route('/connect', methods=['POST'])
def connect():
    data = request.json
    sql_name = data['sql_name']
    ip = request.remote_addr
    pre_trained_info = load_pre_trained_info()

    # 检查是否已经有预训练好的实例
    if ip in pre_trained_info and sql_name in pre_trained_info[ip]:
        dbname = data.get('dbname', '')
        if dbname in pre_trained_info[ip][sql_name] and pre_trained_info[ip][sql_name][dbname]:
            # 使用预训练好的实例
            instance = userVanna(sql_name, user_id=ip)
            instance.connect(**data)
            instance_id = str(uuid.uuid4())
            instances[instance_id] = instance
            return   instance_id

    # 如果没有预训练好的实例，则创建新的实例并进行预训练
    if sql_name == 'mysql':
        host = data['host']
        dbname = data['dbname']
        user = data['user']
        password = data['password']
        port = data['port']
        role = data['role']
        instance = userVanna(sql_name, user_id=ip)
        instance.connect(host=host, dbname=dbname, user=user, password=password, port=port)
    elif sql_name == 'sqlite':
        host = data['host']
        port = data['port']
        dbname = data['dbname']
        role = data['role']
        instance = userVanna(sql_name, user_id=ip)
        instance.connect(host=host, port=port, dbname=dbname)
    elif sql_name == 'snowflake':
        host = data['host']
        user = data['user']
        password = data['password']
        dbname = data['dbname']
        role = data['role']
        instance = userVanna(sql_name, user_id=ip)
        instance.connect(host=host, user=user, password=password, dbname=dbname, role=role)

    instance_id = str(uuid.uuid4())  # 使用UUID作为实例的唯一标识
    instances[instance_id] = instance

    # 检查预训练状态
    if not pre_trained_info.get(ip, {}).get(sql_name, {}).get(dbname, False):
        pre_training_logs[ip] = []
        # 在单独的线程中启动预训练
        threading.Thread(target=pre_train_async, args=(instance, ip, sql_name, dbname)).start()

    return instance_id

def pre_train_async(instance, ip, sql_name, db_name):
    try:
        instance.pre_train(log_callback=lambda log: pre_training_logs[ip].append(log))
        pre_trained_info = load_pre_trained_info()
        if ip not in pre_trained_info:
            pre_trained_info[ip] = {}
        if sql_name not in pre_trained_info[ip]:
            pre_trained_info[ip][sql_name] = {}
        pre_trained_info[ip][sql_name][db_name] = True
        save_pre_trained_info(pre_trained_info)
    except Exception as e:
        logging.error(f"预训练过程中发生错误: {e}")

@app.route('/get_sql_code', methods=['POST'])
def get_sql_code():
    data = request.json
    question = data['question']
    instance_id = data['instance_id']
    if instance_id:
        instance = instances.get(instance_id)
        if instance:
            return instance.generate_sql_code(question)
    return jsonify({'error': 'Instance not found'}), 404

@app.route('/get_answer', methods=['POST'])
def get_answer():
    data = request.json
    question = data['question']
    instance_id = data['instance_id']
    if instance_id:
        instance = instances.get(instance_id)
        if instance:
            return instance.ask(question)
    return jsonify({'error': 'Instance not found'}), 404

if __name__ == '__main__':
    app.run(use_reloader=False, threaded=True, debug=True, host='0.0.0.0', port=5600)


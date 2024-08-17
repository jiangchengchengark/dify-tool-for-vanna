

# Local Vanna for Dify

## 简介

Local Vanna for Dify 是一个基于 Vanna 框架的 API，用于连接和交互数据库。它支持多种数据库类型，如 MySQL、SQLite 和 Snowflake，并提供了生成 SQL 代码和获取数据库查询结果的功能。该项目旨在与 Dify 平台集成，以便用户可以轻松地创建自定义工具。

## 功能特性

- **连接数据库**：支持多种数据库类型，包括 MySQL、SQLite 和 Snowflake。
- **生成 SQL 代码**：根据用户提供的问题生成相应的 SQL 代码。
- **获取数据库查询结果**：根据用户提供的问题从数据库中获取查询结果。

## 部署指南

### 前提条件

在部署之前，请确保您已经安装了以下软件：

- Python 3.7 或更高版本
- Flask
- Vanna 框架
- 其他依赖库（请参考 `requirements.txt`）

### 安装步骤

1. **克隆仓库**

   ```bash
   git clone https://github.com/jiangchengchenggark/dify-tool-for-vanna.git
   cd local-vanna-for-dify
   ```

2. **创建虚拟环境**

   ```bash
   python -m venv venv
   source venv/bin/activate  # 在 Windows 上使用 `venv\Scripts\activate`
   conda create -n vanna python==3.10
   ```

3. **安装依赖**

   ```bash
   pip install -r requirements.txt
   ```

4. **配置环境变量**

   您可以在项目根目录下创建一个 `.env` 文件，并添加必要的配置，例如：

   ```env
   LOCAL_IP=输入dify部署的主机地址
   API_KEY=输入智谱平台的API_KEY
   ```

5. **启动应用**

   ```bash
   flask run
   or
   python api.py
   ```

   默认情况下，应用会在 `http://127.0.0.1:5600` 上运行。

### 与 Dify 集成

1. **配置 Dify**

   在 Dify 平台上，创建一个新的自定义工具，并将openapi文件中的url地址改为 `http://127.0.0.1:5600`，或者你部署dify的主机地址

2. **导入 OpenAPI 规范**

   将 `openapi.txt` 中的内容复制到 Dify 自定义工具的 schema 中，即可创建成功。



## 贡献

我们欢迎任何形式的贡献，包括但不限于代码提交、问题反馈和功能建议。请参阅我们的 [贡献指南](CONTRIBUTING.md) 了解更多信息。

## 许可证

本项目采用 [MIT 许可证](LICENSE)。

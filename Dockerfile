FROM python:3.11-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制代码
COPY . .

# 创建 session 目录
RUN mkdir -p /app/sessions

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV SESSION_NAME=/app/sessions/forwarder_session

# 运行程序
CMD ["python", "main.py"]
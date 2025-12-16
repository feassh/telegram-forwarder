# Telegram 消息转发器

一个用于转发 Telegram 消息到第三方平台的 Python 程序，专为中国大陆用户设计，解决因网络封锁导致的消息接收延迟问题。

## ✨ 特性

- 🚀 实时转发 Telegram 消息到企业微信、飞书或自定义 HTTP API
  - 支持企业微信群机器人
  - 支持企业微信自建应用（推送到指定用户）
- 🔕 智能过滤：自动识别并跳过已静音的对话
- 📋 灵活配置：支持白名单/黑名单模式
- 🐳 Docker 部署：一键启动，轻松维护
- 🔐 安全可靠：使用官方 Telethon 库，Session 持久化

## 📋 前置要求

### 获取 Telegram API 凭证

1. 访问 [https://my.telegram.org](https://my.telegram.org)
2. 使用你的手机号登录
3. 选择 "API development tools"
4. 创建一个新应用，获取 `api_id` 和 `api_hash`

### 获取 Webhook URL

**企业微信群机器人：**
1. 在企业微信群中添加机器人
2. 获取 Webhook 地址

**企业微信自建应用：**
1. 登录[企业微信管理后台](https://work.weixin.qq.com/)
2. 进入"应用管理" → "自建" → "创建应用"
3. 创建应用后，获取以下信息：
   - `CorpID`：在"我的企业" → "企业信息"中查看
   - `AgentId`：应用详情页中的 AgentId
   - `Secret`：应用详情页中的 Secret
4. 配置应用可见范围（添加需要接收消息的成员）

**飞书机器人：**
1. 在飞书群中添加自定义机器人
2. 获取 Webhook 地址

## 🚀 快速开始

### 使用 Docker Compose（推荐）

1. **克隆项目**
```bash
git clone https://github.com/yourusername/telegram-forwarder.git
cd telegram-forwarder
```

2. **配置环境变量**
```bash
cp .env.example .env
# 编辑 .env 文件，填入你的配置
```

3. **首次运行（登录 Telegram）**
```bash
docker compose run --rm telegram-forwarder
# 按提示输入手机号和验证码完成登录
```

4. **后台运行**
```bash
docker compose up -d
```

5. **查看日志**
```bash
docker compose logs -f
```

### 直接使用 Python

1. **安装依赖**
```bash
pip install -r requirements.txt
```

2. **配置环境变量**
```bash
cp .env.example .env
# 编辑 .env 文件
```

3. **运行程序**
```bash
python main.py
```

## ⚙️ 配置说明

### 必需配置

```bash
# Telegram 配置
TELEGRAM_API_ID=your_api_id          # 从 my.telegram.org 获取
TELEGRAM_API_HASH=your_api_hash      # 从 my.telegram.org 获取
TELEGRAM_PHONE=+8613800138000        # 你的手机号（国际格式）

# 转发器类型：
# - wecom: 企业微信群机器人
# - wecom-app: 企业微信自建应用
# - feishu: 飞书机器人
# - custom: 自定义 HTTP API
FORWARDER_TYPE=wecom
```

### 转发器配置

**企业微信群机器人：**
```bash
WECOM_WEBHOOK_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=your_key
```

**企业微信自建应用：**
```bash
WECOM_CORPID=wwxxx                                 # 企业 ID
WECOM_CORPSECRET=xxx                               # 应用 Secret
WECOM_AGENTID=100000                               # 应用 AgentId
WECOM_TOUSER=@all                                  # 接收用户，@all=所有人，或指定: user1|user2
```

> **注意**：企业微信应用方式会自动管理 access_token 的获取和刷新，token 会缓存并在过期前 5 分钟自动刷新。

**飞书：**
```bash
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/your_hook_id
```

**自定义 API：**
```bash
CUSTOM_API_URL=https://your-api.com/webhook
CUSTOM_API_METHOD=POST
CUSTOM_API_HEADERS=Authorization:Bearer token,X-Custom-Header:value
```

自定义 API 将收到以下格式的 JSON：
```json
{
  "chat_title": "群组名称",
  "sender": "发送者名字",
  "message": "消息内容",
  "chat_id": 123456789,
  "message_id": 987654321
}
```

### 过滤配置

```bash
# 是否过滤静音对话（推荐开启）
FILTER_MUTED=true

# 白名单：仅转发这些对话（逗号分隔的 chat_id）
WHITELIST_CHATS=123456789,987654321

# 黑名单：不转发这些对话（逗号分隔的 chat_id）
BLACKLIST_CHATS=111111111,222222222
```

**获取 chat_id：**
- 运行程序后，查看日志即可看到每个对话的 chat_id
- 或者使用 Telegram 机器人如 [@userinfobot](https://t.me/userinfobot)

## 🔧 高级功能

### 获取对话 ID

运行程序后，每条消息的日志都会显示 chat_id，你可以据此配置白名单或黑名单。

### Session 持久化

Session 文件保存在 `./sessions` 目录，确保该目录已挂载到容器中，避免重启后重新登录。

### 日志管理

Docker Compose 默认配置了日志轮转：
- 单个日志文件最大 10MB
- 最多保留 3 个文件

## 📦 构建和发布

### 本地构建

```bash
docker build -t telegram-forwarder:latest .
```

### 自动构建和发布

项目配置了 GitHub Actions，当你推送新 tag 时会自动构建并发布到 Docker Hub。

**配置步骤：**

1. 在 GitHub 仓库中添加 Secrets：
   - `DOCKER_HUB_USERNAME`: Docker Hub 用户名
   - `DOCKER_HUB_TOKEN`: Docker Hub 访问令牌

2. 创建并推送 tag：
```bash
git tag v1.0.0
git push origin v1.0.0
```

3. GitHub Actions 会自动构建并推送镜像：
   - `yourusername/telegram-forwarder:1.0.0`
   - `yourusername/telegram-forwarder:latest`

## 🛠️ 故障排除

### 无法登录 Telegram

- 确保 API_ID 和 API_HASH 正确
- 检查手机号格式（必须包含国家代码，如 +86）
- 首次登录需要交互式输入验证码

### 消息未转发

- 检查对话是否被静音（如果启用了 `FILTER_MUTED`）
- 检查白名单/黑名单配置
- 查看日志确认是否收到消息事件

### Session 文件丢失

- 确保 `./sessions` 目录已正确挂载
- 检查目录权限

## 📝 项目结构

```
telegram-forwarder/
├── main.py                 # 主程序
├── forwarders.py          # 转发器实现
├── requirements.txt       # Python 依赖
├── Dockerfile            # Docker 镜像定义
├── docker-compose.yml    # Docker Compose 配置
├── .env.example         # 环境变量示例
├── .github/
│   └── workflows/
│       └── docker-publish.yml  # GitHub Actions
└── README.md            # 项目文档
```

## 📄 许可证

MIT License

## ⚠️ 免责声明

本项目仅供学习和个人使用。请遵守相关法律法规和服务条款。
# 阿里云简单部署文档

## 1. 目标

本文档用于把当前项目快速部署到阿里云，目标是：

- 前端和后端都先部署到阿里云
- 适合 `测试 / 内测 / 自用`
- 部署复杂度尽量低
- 先把服务跑通，后面再逐步拆分

当前推荐方案：

- `1 台阿里云 ECS`
- `1 个 Spring Boot 后端`
- `1 个 React/Vite 前端静态站点`
- `1 个 PostgreSQL`
- `1 个 Redis`
- `1 个 Nginx`

如果你现在只是要验证服务可用性，这个方案最省事。

## 2. 推荐部署拓扑

```mermaid
flowchart LR
    U["Browser"] --> N["Nginx :80/:443"]
    N --> F["Frontend static files"]
    N --> B["Spring Boot API :8092"]
    B --> P["PostgreSQL :5432"]
    B --> R["Redis :6379"]
```

说明：

- `Nginx` 负责统一入口
- 前端由 `Nginx` 直接托管静态文件
- 后端以 `jar` 方式运行
- PostgreSQL 和 Redis 先部署在同一台 ECS 上

后面如果访问量起来了，再拆成：

- ECS 跑 Nginx + 后端
- RDS 跑 PostgreSQL
- 阿里云 Redis 跑缓存
- OSS 托管前端静态文件

## 3. 服务器建议

测试环境建议：

- `ECS`
- `2 vCPU / 4 GB` 起步
- `Ubuntu 22.04`
- `40 GB` 系统盘起

说明：

- 如果只是控制平面和前端测试，`2C4G` 基本够
- 如果你还要在这台机子上临时跑额外服务，建议 `4C8G`
- 音频处理、训练、推理仍然不要放在这台机器上，继续用 `AutoDL`

## 4. 域名与端口建议

建议对外只暴露：

- `80`
- `443`

如果只是临时测试，也可以先只开：

- `80`

内部服务端口：

- 前端静态文件：Nginx 本地目录
- 后端：`8092`
- PostgreSQL：`5432`
- Redis：`6379`

安全组建议：

- 对公网开放 `22/80/443`
- `5432/6379/8092` 不对公网开放

## 5. 服务器初始化

登录 ECS 后执行：

```bash
sudo apt update
sudo apt install -y nginx redis-server postgresql postgresql-contrib unzip curl git
```

安装 Java 21：

```bash
curl -fsSL -o /tmp/jdk21.tar.gz 'https://api.adoptium.net/v3/binary/latest/21/ga/linux/x64/jdk/hotspot/normal/eclipse'
sudo mkdir -p /opt/jdk-21
sudo tar -xzf /tmp/jdk21.tar.gz -C /opt/jdk-21 --strip-components=1
echo 'export JAVA_HOME=/opt/jdk-21' | sudo tee /etc/profile.d/java21.sh
echo 'export PATH=$JAVA_HOME/bin:$PATH' | sudo tee -a /etc/profile.d/java21.sh
source /etc/profile.d/java21.sh
java -version
```

安装 Node 22：

```bash
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs
node -v
npm -v
```

## 6. 创建部署目录

建议统一放在：

```bash
sudo mkdir -p /srv/ai-music
sudo mkdir -p /srv/ai-music/backend
sudo mkdir -p /srv/ai-music/frontend
sudo mkdir -p /srv/ai-music/logs
sudo chown -R $USER:$USER /srv/ai-music
```

## 7. PostgreSQL 初始化

切换 postgres 用户：

```bash
sudo -u postgres psql
```

执行：

```sql
CREATE USER pgvector WITH PASSWORD 'change-me';
CREATE DATABASE aimusic OWNER pgvector;
\q
```

验证连接：

```bash
psql postgresql://pgvector:change-me@localhost:5432/aimusic -c '\l'
```

## 8. Redis 初始化

编辑配置：

```bash
sudo nano /etc/redis/redis.conf
```

建议至少调整：

- `supervised systemd`
- 如果要密码，设置 `requirepass`

重启：

```bash
sudo systemctl restart redis-server
sudo systemctl enable redis-server
```

验证：

```bash
redis-cli ping
```

如果设置了密码：

```bash
redis-cli -a 'your-password' ping
```

## 9. 上传项目代码

最简单方式：

```bash
cd /srv/ai-music
git clone git@github.com:xiaosenho/ai-music.git .
```

如果 ECS 没配 GitHub SSH，也可以在本地打包上传。

## 10. 后端部署

## 10.1 准备环境变量

在服务器上创建：

```bash
mkdir -p /srv/ai-music/backend/config
nano /srv/ai-music/backend/config/app.env
```

写入示例：

```bash
SERVER_PORT=8092
SPRING_PROFILES_ACTIVE=postgres

SPRING_DATASOURCE_URL=jdbc:postgresql://127.0.0.1:5432/aimusic
SPRING_DATASOURCE_USERNAME=pgvector
SPRING_DATASOURCE_PASSWORD=change-me
SPRING_DATASOURCE_HIKARI_MAXIMUM_POOL_SIZE=16
SPRING_DATASOURCE_HIKARI_MINIMUM_IDLE=4
SPRING_DATASOURCE_HIKARI_IDLE_TIMEOUT=300000
SPRING_DATASOURCE_HIKARI_CONNECTION_TIMEOUT=10000
SPRING_DATASOURCE_HIKARI_MAX_LIFETIME=1800000

SPRING_DATA_REDIS_HOST=127.0.0.1
SPRING_DATA_REDIS_PORT=6379
SPRING_DATA_REDIS_PASSWORD=

AIMUSIC_DB_MIGRATION_ENABLED=true

JWT_SECRET=change-me
JWT_ACCESS_TTL_MS=86400000
JWT_REFRESH_TTL_MS=604800000

COS_REGION=ap-guangzhou
COS_BUCKET=change-me
COS_SECRET_ID=change-me
COS_SECRET_KEY=change-me
COS_PUBLIC_BASE_URL=https://change-me.cos.ap-guangzhou.myqcloud.com
COS_UPLOAD_TOKEN_TTL_SECONDS=300
MEDIA_MAX_IMAGE_BYTES=10485760

AIMUSIC_AI_MOCK_ENABLED=false
AIMUSIC_AI_MAX_TOOL_ROUNDS=3
AI_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
AI_CHAT_COMPLETIONS_PATH=/chat/completions
AI_API_KEY=change-me
AI_CHAT_MODEL=doubao-seed-2-0-mini-260428

AIMUSIC_WORKER_HEARTBEAT_INTERVAL_SECONDS=30
AIMUSIC_WORKER_PULL_INTERVAL_SECONDS=10
AIMUSIC_WORKER_JOB_LEASE_SECONDS=300

AIMUSIC_CORS_ALLOWED_ORIGINS=https://your-domain.com,http://your-server-ip
```

## 10.2 打包后端

在服务器或本地打包都可以。

服务器上直接打包：

```bash
cd /srv/ai-music
source scripts/use-local-toolchain.sh
cd apps/api
mvn -DskipTests package
```

产物会在：

```bash
apps/api/target/control-plane-0.0.1-SNAPSHOT.jar
```

## 10.3 创建 systemd 服务

创建：

```bash
sudo nano /etc/systemd/system/ai-music-api.service
```

内容如下：

```ini
[Unit]
Description=AI Music Control Plane API
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/srv/ai-music/apps/api
EnvironmentFile=/srv/ai-music/backend/config/app.env
ExecStart=/opt/jdk-21/bin/java -jar /srv/ai-music/apps/api/target/control-plane-0.0.1-SNAPSHOT.jar
Restart=always
RestartSec=5
StandardOutput=append:/srv/ai-music/logs/api.out.log
StandardError=append:/srv/ai-music/logs/api.err.log

[Install]
WantedBy=multi-user.target
```

启动：

```bash
sudo systemctl daemon-reload
sudo systemctl enable ai-music-api
sudo systemctl start ai-music-api
sudo systemctl status ai-music-api
```

查看日志：

```bash
tail -f /srv/ai-music/logs/api.out.log
tail -f /srv/ai-music/logs/api.err.log
```

## 10.4 后端验证

先本机测：

```bash
curl http://127.0.0.1:8092/actuator/health
```

期望返回 `UP`。

再测 summary：

```bash
curl http://127.0.0.1:8092/api/v1/dashboard/summary
```

## 11. 前端部署

## 11.1 准备前端环境变量

创建：

```bash
cd /srv/ai-music/apps/web
cp .env.example .env
nano .env
```

内容示例：

```bash
VITE_API_BASE_URL=https://your-domain.com
```

如果你暂时还没有域名，也可以先写：

```bash
VITE_API_BASE_URL=http://your-server-ip
```

## 11.2 打包前端

```bash
cd /srv/ai-music
source scripts/use-local-toolchain.sh
cd apps/web
npm install
npm run build
```

产物目录：

```bash
apps/web/dist
```

## 11.3 部署到 Nginx 目录

```bash
rm -rf /srv/ai-music/frontend/*
cp -r /srv/ai-music/apps/web/dist/* /srv/ai-music/frontend/
```

## 12. Nginx 配置

创建站点配置：

```bash
sudo nano /etc/nginx/sites-available/ai-music
```

内容如下：

```nginx
server {
    listen 80;
    server_name your-domain.com _;

    root /srv/ai-music/frontend;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:8092;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /actuator/ {
        proxy_pass http://127.0.0.1:8092;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

启用：

```bash
sudo ln -sf /etc/nginx/sites-available/ai-music /etc/nginx/sites-enabled/ai-music
sudo nginx -t
sudo systemctl reload nginx
```

## 13. HTTPS

如果你有域名，建议立刻上 HTTPS。

安装 certbot：

```bash
sudo apt install -y certbot python3-certbot-nginx
```

申请证书：

```bash
sudo certbot --nginx -d your-domain.com
```

## 14. 部署后测试清单

## 14.1 基础测试

访问：

- `http://your-domain.com`
- `http://your-domain.com/api/v1/dashboard/summary`
- `http://your-domain.com/actuator/health`

确认：

- 前端页面能打开
- summary 接口有返回
- health 是 `UP`

## 14.2 后端接口测试

创建任务示例：

```bash
curl -X POST http://your-domain.com/api/v1/jobs \
  -H 'Content-Type: application/json' \
  -d '{
    "jobType":"PROCESS",
    "executionMode":"CLOUD",
    "priority":1,
    "inputAssetIds":["asset-001"],
    "note":"deploy smoke test"
  }'
```

查看任务：

```bash
curl http://your-domain.com/api/v1/jobs
```

## 14.3 worker 测试

注册一个测试 worker：

```bash
curl -X POST http://your-domain.com/api/v1/workers/register \
  -H 'Content-Type: application/json' \
  -d '{
    "nodeType":"AUTODL",
    "hostname":"autodl-test-01",
    "provider":"autodl",
    "gpuName":"RTX 4090",
    "gpuCount":1,
    "vramMb":24576,
    "supportedJobTypes":["PROCESS","TRAIN","INFER"],
    "workerVersion":"0.0.1",
    "status":"IDLE"
  }'
```

然后查看节点：

```bash
curl http://your-domain.com/api/v1/workers
```

## 15. 更新流程

后端更新：

```bash
cd /srv/ai-music
git pull
source scripts/use-local-toolchain.sh
cd apps/api
mvn -DskipTests package
sudo systemctl restart ai-music-api
sudo systemctl status ai-music-api
```

前端更新：

```bash
cd /srv/ai-music
git pull
source scripts/use-local-toolchain.sh
cd apps/web
npm install
npm run build
rm -rf /srv/ai-music/frontend/*
cp -r dist/* /srv/ai-music/frontend/
sudo systemctl reload nginx
```

## 16. 常见问题

### 16.1 前端打开但接口 404

通常是：

- `VITE_API_BASE_URL` 配错
- Nginx 没代理 `/api/`
- 后端没启动成功

### 16.2 后端启动失败

检查：

- PostgreSQL 用户名密码
- Redis 配置
- Java 版本是否是 `21`
- Flyway 是否执行失败

命令：

```bash
sudo systemctl status ai-music-api
tail -f /srv/ai-music/logs/api.err.log
```

### 16.3 页面刷新 404

说明 Nginx 没正确配置：

```nginx
try_files $uri $uri/ /index.html;
```

### 16.4 CORS 报错

检查：

- `AIMUSIC_CORS_ALLOWED_ORIGINS`
- 前端访问域名和后端允许域名是否一致

## 17. 后续升级建议

等你测试跑稳后，建议升级到下面结构：

1. PostgreSQL 迁移到 `阿里云 RDS`
2. Redis 迁移到 `阿里云 Redis`
3. 前端静态文件迁移到 `OSS + CDN`
4. 后端改为 `CI 打包 + ECS 拉包发布`
5. 接入域名、HTTPS、监控和告警

## 18. 当前最推荐的执行顺序

如果你要今天先跑通，我建议按这个顺序：

1. 买一台 `Ubuntu 22.04` 的 `2C4G ECS`
2. 安装 Java 21 / Node / PostgreSQL / Redis / Nginx
3. 克隆项目
4. 配后端环境变量
5. 启动后端 systemd 服务
6. 构建前端并交给 Nginx
7. 用 `dashboard/summary` 做 smoke test
8. 手动注册一个测试 worker

这样最容易一次打通。

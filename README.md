# BitaHubHelper

BitaHub 平台命令行工具，用于登录、管理项目和任务、查询 GPU 资源。

## 安装

```bash
pip install -e .
```

## 依赖

- Python >= 3.8
- requests >= 2.28.0
- click >= 8.0.0

## 使用方法

### 账户

```bash
bitahub login <邮箱> <密码>           # 登录
bitahub status                        # 查看登录状态（含当前项目）
bitahub logout                        # 退出登录
```

### 项目管理

```bash
bitahub list-project                  # 查看项目列表
bitahub list-project -p 2 -s 10      # 分页查看
bitahub use <项目ID/项目名称>          # 切换到指定项目
```

### 任务管理

```bash
bitahub list-task                     # 查看任务列表（含标签）
bitahub list-task -p 2 -s 10         # 分页查看
bitahub status -t <ID或codeNo>       # 查看任务详情（参数/日志/SSH）
bitahub tail -t <ID> -l 100          # 查看日志末尾
bitahub full-log -t <ID>             # 查看完整日志

# 启动任务
bitahub run -i <镜像> -g rtx3090 -c 1 -x "python train.py"
bitahub run -i <镜像> -g rtx3090 -c 1 -x "python train.py" --tag mytag

# 创建调试机并获取 SSH 连接
bitahub create-debug -i <镜像> -c 1
bitahub create-debug -i <镜像> -c 1 -x "sleep 3h"

# 停止任务
bitahub stop-task -t <ID或codeNo>
bitahub stop-task -t <ID或codeNo> -f   # 跳过确认

# 删除任务
bitahub delete-task -t <ID或codeNo>
bitahub delete-task -t <ID或codeNo> -f # 跳过确认
```

### 资源与镜像

```bash
bitahub list-gpu                      # 查看 GPU 资源
bitahub list-gpu -g rtx3090          # 按类型筛选
bitahub list-image                    # 查看平台镜像（缓存）
bitahub list-image --update           # 刷新缓存
bitahub list-image --user             # 用户自定义镜像
```

### 支付

```bash
bitahub payment                       # 查看算力余额
bitahub payment -s <团队ID>           # 设置默认支付
```

## 配置

配置存储在 `~/.bitahub/config.json`，镜像缓存存储在 `~/.bitahub/images_cache.json`。

## License

MIT

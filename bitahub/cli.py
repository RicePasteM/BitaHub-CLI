"""BitaHub CLI interface."""

import click
import json
import random
import re
import string
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

import requests as http_requests
from .client import BitaHubClient
from .config import load_config, clear_config, save_config


def _format_time(value):
    """将时间戳或字符串统一格式化为字符串."""
    if not value:
        return ""
    if isinstance(value, (int, float)):
        ts = value / 1000 if value > 1e12 else value
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    return str(value)[:19].replace("T", " ")


def get_client() -> BitaHubClient:
    """获取BitaHub客户端实例."""
    config = load_config()
    return BitaHubClient(base_url=config.get("base_url", "https://bitahub.ustc.edu.cn"))


@click.group()
@click.version_option(version="0.1.0")
def main():
    """BitaHub CLI - 用于与BitaHub平台交互的命令行工具."""
    pass


@main.command()
@click.argument("username")
@click.argument("password")
def login(username: str, password: str):
    """登录BitaHub平台.

    USERNAME: 用户名（邮箱）
    PASSWORD: 密码
    """
    client = get_client()

    click.echo(f"正在登录 {username}...")

    try:
        result = client.login(username, password)

        if result.get("message", {}).get("code") == 0:
            click.echo("登录成功！")
            click.echo(f"欢迎, {username}")
        else:
            error_msg = result.get("message", {}).get("message", "未知错误")
            click.echo(f"登录失败: {error_msg}", err=True)
            sys.exit(1)
    except Exception as e:
        click.echo(f"登录出错: {e}", err=True)
        sys.exit(1)


@main.command("list-project")
@click.option("--page", "-p", default=1, help="页码")
@click.option("--page-size", "-s", default=18, help="每页数量")
def list_project(page: int, page_size: int):
    """列出项目."""
    client = get_client()

    # 检查是否已登录
    if not client.check_login():
        click.echo("未登录，请先使用 'bitahub login' 命令登录", err=True)
        sys.exit(1)

    try:
        result = client.get_projects(page=page, page_size=page_size)

        if result.get("message", {}).get("code") == 0:
            data = result.get("data", {})
            projects = data.get("list", [])
            total = data.get("total", 0)

            click.echo(f"项目列表 (共 {total} 个项目)")
            click.echo("=" * 80)
            click.echo(f"{'ID':<30} {'名称':<20} {'描述':<30} {'创建者'}")
            click.echo("-" * 80)

            for project in projects:
                project_id = project.get("id")
                name = project.get("projectName", "未命名")
                profile = project.get("profile", "")
                user = project.get("userName", "未知")

                click.echo(f"{project_id:<30} {name:<20} {profile:<30} {user}")
        else:
            error_msg = result.get("message", {}).get("message", "未知错误")
            click.echo(f"获取项目列表失败: {error_msg}", err=True)
            sys.exit(1)
    except Exception as e:
        click.echo(f"获取项目列表出错: {e}", err=True)
        sys.exit(1)


@main.command("use")
@click.argument("identifier")
def use_project(identifier: str):
    """切换到指定项目.

    IDENTIFIER: 项目ID或项目名称
    """
    client = get_client()

    if not client.check_login():
        click.echo("未登录，请先使用 'bitahub login' 命令登录", err=True)
        sys.exit(1)

    try:
        result = client.get_projects(page=1, page_size=100)

        if result.get("message", {}).get("code") != 0:
            error_msg = result.get("message", {}).get("message", "未知错误")
            click.echo(f"获取项目列表失败: {error_msg}", err=True)
            sys.exit(1)

        projects = result.get("data", {}).get("list", [])
        matched = None

        for p in projects:
            pid = str(p.get("id", ""))
            pname = p.get("projectName", "")
            if pid == identifier or pname == identifier:
                matched = p
                break

        if not matched:
            click.echo(f"未找到项目: {identifier}", err=True)
            sys.exit(1)

        config = load_config()
        config["current_project_id"] = matched.get("id")
        config["current_project_name"] = matched.get("projectName")
        save_config(config)
        click.echo(f"已切换到项目: {matched.get('projectName')} (ID: {matched.get('id')})")

    except Exception as e:
        click.echo(f"切换项目出错: {e}", err=True)
        sys.exit(1)


@main.command("list-task")
@click.option("--page", "-p", default=1, help="页码")
@click.option("--page-size", "-s", default=20, help="每页数量")
def list_task(page: int, page_size: int):
    """列出当前项目的所有任务."""
    client = get_client()
    config = load_config()

    if not client.check_login():
        click.echo("未登录，请先使用 'bitahub login' 命令登录", err=True)
        sys.exit(1)

    project_id = config.get("current_project_id")
    if not project_id:
        click.echo("未指定项目，请先使用 'bitahub use <项目ID>' 命令切换项目", err=True)
        sys.exit(1)

    try:
        result = client.get_task_list(
            project_id=str(project_id), page=page, page_size=page_size
        )

        if result.get("message", {}).get("code") == 0:
            data = result.get("data", {})
            tasks = data.get("list", [])
            total = data.get("total", 0)

            project_name = config.get("current_project_name", "未知项目")
            click.echo(f"任务列表 - {project_name} (共 {total} 个任务)")
            click.echo("=" * 130)
            click.echo(f"{'任务ID':<38} {'代号':<6} {'标签':<12} {'名称':<24} {'状态':<10} {'用时':<12} {'创建时间'}")
            click.echo("-" * 130)

            state_map = {
                "CREATED": "已创建",
                "TAGING": "提交中",
                "TAGFAILED": "提交失败",
                "TAGSUCCESS": "提交成功",
                "UNDERPOWERED": "算力不足",
                "PRERUNNING": "等待",
                "WAITING": "等待",
                "STOPPING": "停止中",
                "STOPING": "停止中",
                "STOPPED": "停止",
                "RUNNING": "运行中",
                "SUCCEEDED": "成功",
                "FAILED": "失败",
                "RESTARTING": "重启",
            }

            for task in tasks:
                task_id = str(task.get("id", "-"))
                code_no = task.get("codeNo", "-")
                job_tag = task.get("jobTag", "") or "-"
                job_name = task.get("jobName", "未命名")
                state = task.get("state", "UNKNOWN")
                status_text = state_map.get(state, "N/A")
                time_consuming = task.get("timeConsuming", 0)
                created_time = task.get("createdTime") or task.get("createTime", "")
                created_time = _format_time(created_time)

                if time_consuming:
                    duration_seconds = time_consuming
                    d = duration_seconds // 86400
                    h = (duration_seconds % 86400) // 3600
                    m = (duration_seconds % 3600) // 60
                    s = duration_seconds % 60
                    if d > 0:
                        duration = f"{d}d{h}h{m}m{s}s"
                    elif h > 0:
                        duration = f"{h}h{m}m{s}s"
                    elif m > 0:
                        duration = f"{m}m{s}s"
                    else:
                        duration = f"{s}s"
                else:
                    duration = "--"

                click.echo(f"{task_id:<38} {code_no:<6} {job_tag:<12} {job_name:<24} {status_text:<10} {duration:<12} {created_time}")
        else:
            error_msg = result.get("message", {}).get("message", "未知错误")
            click.echo(f"获取任务列表失败: {error_msg}", err=True)
            sys.exit(1)
    except Exception as e:
        click.echo(f"获取任务列表出错: {e}", err=True)
        sys.exit(1)


@main.command("stop-task")
@click.option("--task-id", "-t", required=True, help="任务ID或codeNo")
@click.option("--force", "-f", is_flag=True, help="跳过确认")
def stop_task(task_id: str, force: bool):
    """停止指定任务."""
    client = get_client()

    if not client.check_login():
        click.echo("未登录，请先使用 'bitahub login' 命令登录", err=True)
        sys.exit(1)

    task_id = _resolve_task_id(client, task_id)

    if not force:
        click.confirm(f"确认要停止任务 {task_id}?", abort=True)

    try:
        result = client.stop_job(task_id)
        if result.get("message", {}).get("code") == 0:
            click.echo("任务已停止")
        else:
            error_msg = result.get("message", {}).get("message", "未知错误")
            click.echo(f"停止失败: {error_msg}", err=True)
            sys.exit(1)
    except Exception as e:
        click.echo(f"停止任务出错: {e}", err=True)
        sys.exit(1)


@main.command("delete-task")
@click.option("--task-id", "-t", required=True, help="任务ID或codeNo")
@click.option("--force", "-f", is_flag=True, help="跳过确认")
def delete_task(task_id: str, force: bool):
    """删除指定任务."""
    client = get_client()

    if not client.check_login():
        click.echo("未登录，请先使用 'bitahub login' 命令登录", err=True)
        sys.exit(1)

    task_id = _resolve_task_id(client, task_id)

    if not force:
        click.confirm(f"确认要删除任务 {task_id}? 此操作不可恢复!", abort=True)

    try:
        result = client.delete_task(task_id)
        if result.get("message", {}).get("code") == 0:
            click.echo("任务已删除")
        else:
            error_msg = result.get("message", {}).get("message", "未知错误")
            click.echo(f"删除失败: {error_msg}", err=True)
            sys.exit(1)
    except Exception as e:
        click.echo(f"删除任务出错: {e}", err=True)
        sys.exit(1)


def _resolve_task_id(client, identifier):
    """将 codeNo 或任务ID 解析为真实任务ID."""
    if re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-', identifier, re.IGNORECASE):
        return identifier

    config = load_config()
    project_id = config.get("current_project_id")
    if not project_id:
        return identifier
    if not re.match(r'^\d+$', identifier):
        return identifier

    task_list_result = client.get_task_list(
        project_id=str(project_id), page=1, page_size=200
    )
    if task_list_result.get("message", {}).get("code") == 0:
        for t in task_list_result.get("data", {}).get("list", []):
            if str(t.get("codeNo", "")) == identifier:
                return str(t.get("id", ""))
    return identifier


@main.command("tail")
@click.option("--task-id", "-t", required=True, help="任务ID或codeNo")
@click.option("--lines", "-l", default=50, help="显示末尾行数 (默认50)")
def tail_log(task_id: str, lines: int):
    """查看任务日志末尾行数."""
    client = get_client()

    if not client.check_login():
        click.echo("未登录，请先使用 'bitahub login' 命令登录", err=True)
        sys.exit(1)

    task_id = _resolve_task_id(client, task_id)

    try:
        urls = client.get_container_log_urls(task_id)
        if not urls:
            click.echo("未找到容器日志URL", err=True)
            sys.exit(1)

        for name, url in urls:
            click.echo(f"[{name}] (最后 {lines} 行)")
            click.echo("-" * 80)
            text = client.get_task_tail_log(url, lines=lines)
            click.echo(text)
            click.echo()
    except Exception as e:
        click.echo(f"获取日志出错: {e}", err=True)
        sys.exit(1)


@main.command("full-log")
@click.option("--task-id", "-t", required=True, help="任务ID或codeNo")
def full_log(task_id: str):
    """获取任务完整日志."""
    client = get_client()

    if not client.check_login():
        click.echo("未登录，请先使用 'bitahub login' 命令登录", err=True)
        sys.exit(1)

    task_id = _resolve_task_id(client, task_id)

    try:
        urls = client.get_container_log_urls(task_id)
        if not urls:
            click.echo("未找到容器日志URL", err=True)
            sys.exit(1)

        for name, url in urls:
            click.echo(f"[{name}] (完整日志)")
            click.echo("=" * 80)
            text = client.get_task_full_log(url)
            click.echo(text)
    except Exception as e:
        click.echo(f"获取日志出错: {e}", err=True)
        sys.exit(1)


@main.command("list-gpu")
@click.option("--gpu", "-g", default=None, help="按GPU类型筛选，如: rtx3090")
def list_gpu(gpu: str):
    """列出GPU资源."""
    client = get_client()

    if not client.check_login():
        click.echo("未登录，请先使用 'bitahub login' 命令登录", err=True)
        sys.exit(1)

    try:
        result = client.get_gpu_resources(gpu_type=gpu or "")

        if result.get("message", {}).get("code") == 0:
            data = result.get("data", [])

            click.echo("GPU资源列表")
            click.echo("=" * 80)
            click.echo(f"{'GPU类型':<20} {'GPU空闲/总数':<20} {'CPU空闲/总数':<20} {'内存空闲/总数(MB)'}")
            click.echo("-" * 80)

            for gpu in data:
                gpu_type = gpu.get("sourceInfo", "未知")
                gpu_left = gpu.get("gpuLeft", 0)
                gpu_total = gpu.get("gpuTotal", 0)
                cpu_left = gpu.get("cpuLeft", 0)
                cpu_total = gpu.get("cpuTotal", 0)
                mem_left = gpu.get("memLeft", 0)
                mem_total = gpu.get("memTotal", 0)

                click.echo(f"{gpu_type:<20} {gpu_left}/{gpu_total:<17} {cpu_left}/{cpu_total:<17} {mem_left}/{mem_total}")
        else:
            error_msg = result.get("message", {}).get("message", "未知错误")
            click.echo(f"获取GPU资源失败: {error_msg}", err=True)
            sys.exit(1)
    except Exception as e:
        click.echo(f"获取GPU资源出错: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option("--task-id", "-t", default=None, help="任务ID，用于查看任务详情")
def status(task_id: str):
    """查看登录状态或任务详情."""
    client = get_client()
    config = load_config()

    if task_id:
        if not client.check_login():
            click.echo("未登录，请先使用 'bitahub login' 命令登录", err=True)
            sys.exit(1)

        # 将 codeNo 解析为真实任务ID
        actual_task_id = _resolve_task_id(client, task_id)
        if actual_task_id != task_id:
            click.echo(f"解析 codeNo [{task_id}] -> 任务ID: {actual_task_id}")

        try:
            result = client.get_task_detail(actual_task_id)

            if result.get("message", {}).get("code") == 0:
                detail = result.get("data", {})

                state_map = {
                    "CREATED": "已创建",
                    "TAGING": "提交中",
                    "TAGFAILED": "提交失败",
                    "TAGSUCCESS": "提交成功",
                    "UNDERPOWERED": "算力不足",
                    "PRERUNNING": "等待",
                    "WAITING": "等待",
                    "STOPPING": "停止中",
                    "STOPING": "停止中",
                    "STOPPED": "停止",
                    "RUNNING": "运行中",
                    "SUCCEEDED": "成功",
                    "FAILED": "失败",
                    "RESTARTING": "重启",
                }
                state = detail.get("state", "UNKNOWN")
                status_text = state_map.get(state, "N/A")

                click.echo("=" * 60)
                click.echo("  任务详情")
                click.echo("=" * 60)
                click.echo(f"  任务名称: {detail.get('jobName', '-')}")
                click.echo(f"  代号:     #{detail.get('codeNo', '-')}")
                click.echo(f"  项目:     {detail.get('projectName', '-')}")
                click.echo(f"  状态:     {status_text}")
                click.echo(f"  环境:     {detail.get('language', '-')} / {detail.get('algorithm', '-')}")

                created = detail.get("createTime", "") or detail.get("createdTime", "")
                if created:
                    click.echo(f"  创建时间: {_format_time(created)}")

                completed = detail.get("completedTime", "")
                if completed and state not in ("WAITING", "RUNNING", "CREATED", "TAGING"):
                    click.echo(f"  结束时间: {_format_time(completed)}")

                remark = detail.get("remark", "")
                if remark:
                    remark_clean = re.sub(r"<[^>]+>", "", remark)
                    click.echo(f"  备注:     {remark_clean}")

                config_str = detail.get("config", "")
                if config_str:
                    try:
                        task_config = json.loads(config_str)
                        click.echo("-" * 60)
                        click.echo("  任务参数:")
                        click.echo("-" * 60)

                        task_roles = task_config.get("taskRoles", [])
                        for idx, role in enumerate(task_roles):
                            if len(task_roles) > 1:
                                click.echo(f"  [子任务 {idx + 1}]: {role.get('taskName', '-')}")
                            click.echo(f"    镜像:       {role.get('image', '-')}")
                            click.echo(f"    GPU类型:    {role.get('gpuType', '-')}")
                            click.echo(f"    GPU数量:    {role.get('gpuNumber', 0)}")
                            click.echo(f"    CPU核心:    {role.get('cpuNumber', '-')}")
                            click.echo(f"    内存:       {role.get('memoryMB', '-')}MB")
                            click.echo(f"    子任务数:   {role.get('taskNumber', 1)}")
                            if role.get('minSucceededTaskCount'):
                                click.echo(f"    最少成功数: {role.get('minSucceededTaskCount')}")
                            if role.get('minFailedTaskCount'):
                                click.echo(f"    最少失败数: {role.get('minFailedTaskCount')}")
                            click.echo(f"    启动命令:   {role.get('command', '-')}")
                    except (json.JSONDecodeError, ValueError):
                        pass

                try:
                    job_name = detail.get("jobName", "")
                    if job_name:
                        retry_result = client.get_task_retry_log(job_name)
                        retry_data = retry_result.get("data", {}).get("data", [])
                        if retry_data:
                            click.echo("-" * 60)
                            click.echo("  重启日志:")
                            click.echo("-" * 60)
                            for entry in retry_data:
                                log = entry.get("retrylog", "")
                                log_clean = re.sub(r"<[^>]+>", "", log)
                                click.echo(log_clean)
                except Exception:
                    pass

                # 调试任务始终尝试获取 SSH 信息，普通任务仅在 RUNNING 时显示
                is_debug_task = False
                if config_str:
                    try:
                        task_config = json.loads(config_str)
                        if task_config.get("kind") == "debug":
                            is_debug_task = True
                    except (json.JSONDecodeError, ValueError):
                        pass

                if is_debug_task:
                    try:
                        ssh_result = client.get_task_ssh_info(job_name)
                        containers = ssh_result.get("containers", [])
                        if containers:
                            click.echo("-" * 60)
                            click.echo("  SSH 连接信息:")
                            click.echo("-" * 60)
                            key_pair = ssh_result.get("keyPair", {})
                            for c in containers:
                                click.echo(f"    容器:     {c.get('id', '-')}")
                                click.echo(f"    IP:       {c.get('sshIp', '-')}:{c.get('sshPort', '-')}")
                            if key_pair.get("privateKey"):
                                key = key_pair.get("privateKey", "")
                                key_file = key_pair.get("privateKeyFileName", "key")
                                click.echo(f"    密钥文件: {key_file}")
                                click.echo(f"    密钥内容:")
                                click.echo(key)
                                if containers:
                                    c0 = containers[0]
                                    click.echo(f"    连接命令: ssh -i {key_file} -p {c0.get('sshPort','')} root@{c0.get('sshIp','')}")
                        elif is_debug_task and state != "RUNNING":
                            click.echo("-" * 60)
                            click.echo("  SSH: 调试机尚未就绪，SSH 信息暂不可用")
                            click.echo("-" * 60)
                    except Exception:
                        pass

                try:
                    urls = client.get_container_log_urls(actual_task_id)
                    if urls:
                        click.echo("-" * 60)
                        click.echo("  运行日志:")
                        click.echo("-" * 60)

                        for name, url in urls:
                            click.echo(f"  [{name}]")
                            try:
                                log_text = client.get_task_log(url)
                                if log_text:
                                    lines = log_text.strip().split("\n")
                                    for line in lines[-30:]:
                                        click.echo(f"    {line}")
                            except Exception:
                                click.echo(f"    (无法获取日志)")
                except Exception:
                    pass

            else:
                error_msg = result.get("message", {}).get("message", "未知错误")
                click.echo(f"获取任务详情失败: {error_msg}", err=True)
                sys.exit(1)
        except Exception as e:
            click.echo(f"获取任务详情出错: {e}", err=True)
            sys.exit(1)
        return

    username = config.get("username")
    if not username:
        click.echo("未登录")
        return

    if client.check_login():
        project_id = config.get("current_project_id")
        project_name = config.get("current_project_name")
        click.echo(f"已登录: {username}")
        if project_id:
            click.echo(f"当前项目: {project_name} (ID: {project_id})")
    else:
        click.echo(f"登录已过期: {username}")
        click.echo("请重新使用 'bitahub login' 命令登录")


@main.command()
def logout():
    """退出登录."""
    clear_config()
    click.echo("已退出登录")


@main.command("list-image")
@click.option("--user", "show_user", is_flag=True, help="显示用户自定义镜像")
@click.option("--update", is_flag=True, help="强制刷新缓存")
def list_image(show_user: bool, update: bool):
    """列出所有可用镜像（首次自动缓存到本地，用 --update 刷新）."""

    cache_dir = Path.home() / ".bitahub"
    cache_file = cache_dir / "images_cache.json"
    cache_dir.mkdir(parents=True, exist_ok=True)

    client = get_client()

    if not client.check_login():
        click.echo("未登录，请先使用 'bitahub login' 命令登录", err=True)
        sys.exit(1)

    try:
        if show_user:
            result = client.get_user_images_list()
            if result.get("message", {}).get("code") == 0:
                data = result.get("data", {})
                images = data.get("list", [])
                click.echo("用户自定义镜像")
                click.echo("=" * 80)
                click.echo(f"{'ID':<38} {'名称':<30} {'创建时间'}")
                click.echo("-" * 80)
                for img in images:
                    click.echo(f"{str(img.get('id', '-')):<38} {img.get('name', '-'):<30} {_format_time(img.get('createTime', ''))}")
            else:
                error_msg = result.get("message", {}).get("message", "未知错误")
                click.echo(f"获取用户镜像失败: {error_msg}", err=True)
            return

        # 缓存命中
        if not update and cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                click.echo("=" * 120)
                click.echo(f"{'镜像名称':<40} {'路径':<60} {'语言/框架'}")
                click.echo("=" * 120)
                for item in cached:
                    click.echo(f"{item['name']:<40} {item['path']:<60} {item['tag']}")
                click.echo()
                click.echo(f"共 {len(cached)} 个镜像 (缓存，用 --update 刷新)")
                return
            except (json.JSONDecodeError, IOError):
                pass

        # 从 API 拉取
        lang_result = client.get_language_list()
        fw_result = client.get_framework_list()

        if lang_result.get("message", {}).get("code") != 0:
            click.echo("获取语言列表失败", err=True)
            sys.exit(1)

        langs = lang_result.get("data", [])
        fw_list = fw_result.get("data", []) if fw_result.get("message", {}).get("code") == 0 else []

        if not langs:
            click.echo("未获取到语言列表", err=True)
            sys.exit(1)
        if not fw_list:
            click.echo("未获取到框架列表", err=True)
            sys.exit(1)

        all_images = []
        first = True
        for lang in langs:
            lang_name = lang.get("name", "") if isinstance(lang, dict) else str(lang)
            for fw in fw_list:
                fw_name = fw.get("name", "") if isinstance(fw, dict) else str(fw)
                try:
                    img_result = client.get_images_list(lang_name, fw_name)
                    if img_result.get("message", {}).get("code") == 0:
                        images = img_result.get("data", [])
                        if images and first:
                            click.echo("=" * 120)
                            click.echo(f"{'镜像名称':<40} {'路径':<60} {'语言/框架'}")
                            click.echo("=" * 120)
                            first = False
                        for img in images:
                            name = img.get("name", "-")
                            path = img.get("path", "-")
                            tag = f"{lang_name} / {fw_name}"
                            click.echo(f"{name:<40} {path:<60} {tag}")
                            all_images.append({"name": name, "path": path, "tag": tag})
                except Exception as ex:
                    click.echo(f"  获取 {lang_name}/{fw_name} 镜像出错: {ex}", err=True)

        if all_images:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(all_images, f, ensure_ascii=False, indent=2)
            click.echo()
            click.echo(f"共 {len(all_images)} 个镜像 (已缓存，下次直接使用)")
    except Exception as e:
        click.echo(f"获取镜像列表出错: {e}", err=True)
        sys.exit(1)


@main.command("payment")
@click.option("--set", "-s", "team_id", default=None, help="设置默认支付团队ID")
def payment(team_id: str):
    """查看或设置默认支付方式."""
    client = get_client()
    config = load_config()

    if not client.check_login():
        click.echo("未登录，请先使用 'bitahub login' 命令登录", err=True)
        sys.exit(1)

    if team_id:
        config["default_team_id"] = team_id
        save_config(config)
        click.echo(f"默认支付方式已设置为团队ID: {team_id}")
        return

    try:
        power_result = client.get_user_calculation_power()
        team_result = client.get_team_list_with_power()

        click.echo("支付方式")
        click.echo("=" * 80)
        click.echo(f"{'类型':<8} {'ID':<38} {'名称':<24} {'剩余算力'}")
        click.echo("-" * 80)

        current_team = config.get("default_team_id")

        if power_result.get("code") == 0:
            power = float(power_result.get("result", {}).get("surplusCalculationPower", 0))
            marker = " *" if current_team is None else ""
            click.echo(f"{'个人':<8} {'-':<38} {'个人账户':<24} {power:.1f}{marker}")

        if team_result.get("message", {}).get("code") == 0:
            for team in team_result.get("data", []):
                tid = str(team.get("teamId", ""))
                tname = team.get("teamName", "-")
                tpower = float(team.get("power", 0))
                marker = " *" if current_team and str(current_team) == tid else ""
                click.echo(f"{'团队':<8} {tid:<38} {tname:<24} {tpower:.1f}{marker}")

        click.echo()
        click.echo("* 表示当前默认支付方式")
        click.echo("使用 'bitahub payment -s <ID>' 设置默认支付方式")
    except Exception as e:
        click.echo(f"获取支付方式出错: {e}", err=True)
        sys.exit(1)


def _resolve_image(image: str):
    """将镜像名称或路径解析为完整路径。优先从缓存查找，缓存不存在则原样返回路径."""
    cache_file = Path.home() / ".bitahub" / "images_cache.json"
    if not cache_file.exists():
        return image
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            cached = json.load(f)
        for item in cached:
            if item["name"] == image or item["path"] == image:
                return item["path"]
    except (json.JSONDecodeError, IOError):
        pass
    return image


@main.command("run")
@click.option("--image", "-i", required=True, help="镜像名称或路径")
@click.option("--gpu-type", "-g", default="rtx3090", help="节点类型")
@click.option("--gpu-count", "-c", default=1, type=int, help="GPU数量 (0=仅CPU)")
@click.option("--command", "-x", required=True, help="启动命令")
@click.option("--tag", "-t", default=None, help="任务标签")
@click.option("--debug", "is_debug", is_flag=True, help="调试模式 (debug)")
def run_task(image: str, gpu_type: str, gpu_count: int, command: str, tag: str, is_debug: bool):
    """在当前项目中启动任务."""
    client = get_client()
    config = load_config()

    if not client.check_login():
        click.echo("未登录，请先使用 'bitahub login' 命令登录", err=True)
        sys.exit(1)

    image_path = _resolve_image(image)

    project_id = config.get("current_project_id")
    project_name = config.get("current_project_name")
    if not project_id:
        click.echo("未指定项目，请先使用 'bitahub use <项目ID>' 命令切换项目", err=True)
        sys.exit(1)

    try:
        charge_result = client.get_task_charge_config()
        if charge_result.get("message", {}).get("code") != 0:
            click.echo("获取计费配置失败", err=True)
            sys.exit(1)

        gpu_configs = charge_result.get("data", [])
        gpu_config = None
        for gc in gpu_configs:
            if gc.get("gpu_type") == gpu_type:
                gpu_config = gc
                break

        if not gpu_config:
            available = [g.get("gpu_type") for g in gpu_configs if g.get("gpu_type")]
            click.echo(f"无效的节点类型: {gpu_type}", err=True)
            click.echo(f"可用类型: {', '.join(available)}")
            sys.exit(1)

        if gpu_count == 0:
            cpu_num = gpu_config.get("cpuRange", "4").split(",")[0]
            cpu_num = int(cpu_num)
            memory_mb = cpu_num * int(gpu_config.get("memoryScale", 4)) * 1024
            shm_mb = int(cpu_num * int(gpu_config.get("memoryScale", 4)) / int(gpu_config.get("memory_num", 16)) * int(gpu_config.get("shared_memory_num", 4096)))
        else:
            cpu_num = int(gpu_config.get("cpu_num", 4)) * gpu_count
            memory_mb = 1024 * int(gpu_config.get("memory_num", 16)) * gpu_count
            shm_mb = int(gpu_config.get("shared_memory_num", 4096)) * gpu_count

        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
        job_name = f"{project_name}-{random_suffix}"

        project_detail = client._request(
            "GET", f"/gateway/business/api/project/getUserProjectDetail?projectId={project_id}"
        )
        proj_data = project_detail.get("data", {})
        try:
            proj_config = json.loads(proj_data.get("config", "{}"))
        except (json.JSONDecodeError, ValueError):
            proj_config = {}
        existing_models = proj_config.get("models", [])
        existing_datasets = proj_config.get("datasets", [])

        config_obj = {
            "apiVersion": "2.0",
            "kind": "debug" if is_debug else "execution",
            "jobName": job_name,
            "retryCount": 0,
            "taskRoles": [{
                "taskName": "Task1",
                "taskNumber": 1,
                "image": image_path,
                "gpuType": gpu_type,
                "gpuNumber": gpu_count,
                "cpuNumber": cpu_num,
                "memoryMB": memory_mb,
                "shmMB": shm_mb,
                "minSucceededTaskCount": None,
                "minFailedTaskCount": None,
                "command": command,
            }],
            "code": {
                "projectId": project_name,
                "mountPath": "/code",
                "timeStamp": "",
                "version": "",
            },
            "model": {"modelId": "", "mountPath": "", "token": ""},
            "models": existing_models,
            "datasets": existing_datasets,
            "output": {"jobId": ""},
        }

        task_list_result = client.get_task_list(
            project_id=str(project_id), page=1, page_size=1
        )
        code_no = 1
        if task_list_result.get("message", {}).get("code") == 0:
            code_no = task_list_result.get("data", {}).get("total", 0) + 1

        payload = {
            "projectId": int(project_id),
            "projectName": project_name,
            "jobType": 2 if is_debug else 1,
            "codeNo": code_no,
            "config": json.dumps(config_obj),
        }

        click.echo(f"正在启动任务: {job_name}")
        click.echo(f"  镜像:     {image_path}")
        click.echo(f"  节点:     {gpu_type} x{gpu_count}")
        click.echo(f"  模式:     {'debug' if is_debug else 'execution'}")
        click.echo(f"  命令:     {command[:80]}{'...' if len(command) > 80 else ''}")

        team_id = config.get("default_team_id")
        if team_id and str(team_id) != "-99":
            token = config.get("token", "")
            add_url = f"{client.base_url}/orderservice/calculationPower/addTeamTaskRelation"
            add_payload = urlencode({"teamId": team_id, "taskName": job_name, "cluster": "LN0100", "token": token})
            http_requests.post(add_url, data=add_payload, headers={"Content-Type": "application/x-www-form-urlencoded"}, cookies=client.session.cookies)

        # 先尝试 createJob
        result = client.create_job(payload)
        if result.get("message", {}).get("code") == 0:
            data = result.get("data", {})
            if isinstance(data, dict):
                new_config_str = data.get("config", "")
                if new_config_str:
                    try:
                        new_cfg = json.loads(new_config_str)
                        task_code = new_cfg.get("output", {}).get("jobId", "")
                    except Exception:
                        task_code = ""
                else:
                    task_code = ""
            else:
                task_code = ""
            click.echo(f"任务创建成功！codeNo: {task_code or code_no}")

            if tag:
                new_job_id = data.get("id") or data.get("jobId", "")
                if new_job_id:
                    try:
                        tag_result = client.save_job_tag(str(project_id), str(new_job_id), tag)
                        if tag_result.get("message", {}).get("code") == 0:
                            click.echo(f"任务标签已设置: {tag}")
                    except Exception:
                        pass
            return

        # createJob 失败则回退到 saveJob
        save_body = {
            "filePath": f"{project_name}/code",
            "notes": proj_data.get("notes", ""),
            "profile": proj_data.get("profile", ""),
            "projectName": project_name,
            "userId": config.get("userId", ""),
            "id": int(project_id),
            "language": proj_data.get("language", ""),
            "algorithm": proj_data.get("algorithm", ""),
            "config": json.dumps(config_obj),
        }
        save_result = client._request("PUT", "/gateway/business/api/saveJob?dataSetIds=", json=save_body)
        if save_result.get("message", {}).get("code") == 0:
            click.echo("任务配置已保存到项目。请在 Web 端点击运行。")
            click.echo(f"  {client.base_url}/index  ->  项目: {project_name}  ->  运行")
        else:
            error_msg = result.get("message", {}).get("message", "未知错误")
            click.echo(f"任务创建失败: {error_msg}", err=True)
            sys.exit(1)
    except Exception as e:
        click.echo(f"启动任务出错: {e}", err=True)
        sys.exit(1)


@main.command("create-debug")
@click.option("--image", "-i", required=True, help="镜像名称或路径")
@click.option("--command", "-x", default="sleep 3h", help="启动命令 (默认: sleep 3h)")
@click.option("--gpu-count", "-c", default=1, type=int, help="GPU数量 (默认: 1)")
def debug_machine(image: str, command: str, gpu_count: int):
    """创建调试机并获取 SSH 连接信息."""
    client = get_client()
    config = load_config()

    if not client.check_login():
        click.echo("未登录，请先使用 'bitahub login' 命令登录", err=True)
        sys.exit(1)

    image_path = _resolve_image(image)

    project_id = config.get("current_project_id")
    project_name = config.get("current_project_name")
    if not project_id:
        click.echo("未指定项目，请先使用 'bitahub use <项目ID>' 命令切换项目", err=True)
        sys.exit(1)

    try:
        charge_result = client.get_task_charge_config()
        if charge_result.get("message", {}).get("code") != 0:
            click.echo("获取计费配置失败", err=True)
            sys.exit(1)

        gpu_configs = charge_result.get("data", [])
        gpu_config = None
        for gc in gpu_configs:
            if gc.get("gpu_type") == "debug":
                gpu_config = gc
                break
        if not gpu_config:
            click.echo("未找到 debug 节点配置", err=True)
            sys.exit(1)

        if gpu_count == 0:
            cpu_num = int(gpu_config.get("cpuRange", "4").split(",")[0])
            memory_mb = cpu_num * int(gpu_config.get("memoryScale", 6)) * 1024
            shm_mb = int(cpu_num * int(gpu_config.get("memoryScale", 6)) / int(gpu_config.get("memory_num", 16)) * int(gpu_config.get("shared_memory_num", 8192)))
        else:
            cpu_num = int(gpu_config.get("cpu_num", 4)) * gpu_count
            memory_mb = 1024 * int(gpu_config.get("memory_num", 16)) * gpu_count
            shm_mb = int(gpu_config.get("shared_memory_num", 8192)) * gpu_count

        random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=5))
        job_name = f"{project_name}-{random_suffix}"

        project_detail = client._request(
            "GET", f"/gateway/business/api/project/getUserProjectDetail?projectId={project_id}"
        )
        proj_data = project_detail.get("data", {})
        try:
            proj_config = json.loads(proj_data.get("config", "{}"))
        except (json.JSONDecodeError, ValueError):
            proj_config = {}

        config_obj = {
            "apiVersion": "2.0",
            "kind": "debug",
            "jobName": job_name,
            "retryCount": 0,
            "taskRoles": [{
                "taskName": "Task1",
                "taskNumber": 1,
                "image": image_path,
                "gpuType": "debug",
                "gpuNumber": gpu_count,
                "cpuNumber": cpu_num,
                "memoryMB": memory_mb,
                "shmMB": shm_mb,
                "minSucceededTaskCount": None,
                "minFailedTaskCount": None,
                "command": command,
            }],
            "code": {"projectId": project_name, "mountPath": "/code", "timeStamp": "", "version": ""},
            "model": {"modelId": "", "mountPath": "", "token": ""},
            "models": proj_config.get("models", []),
            "datasets": proj_config.get("datasets", []),
            "output": {"jobId": ""},
        }

        task_list_result = client.get_task_list(project_id=str(project_id), page=1, page_size=1)
        code_no = 1
        if task_list_result.get("message", {}).get("code") == 0:
            code_no = task_list_result.get("data", {}).get("total", 0) + 1

        payload = {
            "projectId": int(project_id),
            "projectName": project_name,
            "jobType": 2,
            "codeNo": code_no,
            "config": json.dumps(config_obj),
        }

        click.echo(f"正在创建调试机: {job_name}")

        result = client.create_job(payload)
        if result.get("message", {}).get("code") != 0:
            save_body = {
                "filePath": f"{project_name}/code",
                "notes": proj_data.get("notes", ""),
                "profile": proj_data.get("profile", ""),
                "projectName": project_name,
                "userId": config.get("userId", ""),
                "id": int(project_id),
                "language": proj_data.get("language", ""),
                "algorithm": proj_data.get("algorithm", ""),
                "config": json.dumps(config_obj),
            }
            save_result = client._request("PUT", "/gateway/business/api/saveJob?dataSetIds=", json=save_body)
            if save_result.get("message", {}).get("code") == 0:
                click.echo("调试机配置已保存，请在 Web 端运行。")
            else:
                click.echo(f"创建失败: {result.get('message', {}).get('message')}", err=True)
                sys.exit(1)
            return

        # 设置默认标签 "debug"
        new_job_id = result.get("data", {}).get("id") or result.get("data", {}).get("jobId", "")
        if new_job_id:
            try:
                client.save_job_tag(str(project_id), str(new_job_id), "debug")
            except Exception:
                pass

        click.echo("调试机已创建，等待 SSH 就绪...")

        task_id = None
        state = ""
        for attempt in range(30):
            time.sleep(5)
            task_list = client.get_task_list(project_id=str(project_id), page=1, page_size=20)
            if task_list.get("message", {}).get("code") == 0:
                for t in task_list.get("data", {}).get("list", []):
                    if t.get("jobName") == job_name:
                        state = t.get("state", "")
                        task_id = str(t.get("id", ""))
                        if state == "RUNNING":
                            break
                        elif state in ("FAILED", "STOPPED", "UNDERPOWERED"):
                            click.echo(f"\n调试机启动失败，状态: {state}", err=True)
                            sys.exit(1)
                if state == "RUNNING":
                    break
            elapsed = (attempt + 1) * 5
            state_text = {"CREATED": "已创建", "TAGING": "提交中", "WAITING": "排队中", "RUNNING": "运行中"}.get(state, state)
            click.echo(f"\r  等待中 [{elapsed}s/{150}s] 状态: {state_text}   ", nl=False)
            sys.stdout.flush()

        click.echo()
        if not task_id or state != "RUNNING":
            click.echo(f"调试机尚未就绪，当前状态: {state}。稍后使用 status -t 查看", err=True)
            return

        click.echo(f"调试机已就绪 (codeNo: {code_no})")
        click.echo()

        ssh_result = client.get_task_ssh_info(job_name)
        key_pair = ssh_result.get("keyPair", {})
        containers = ssh_result.get("containers", [])

        if key_pair.get("privateKey") and containers:
            container = containers[0]
            ssh_ip = container.get("sshIp", "")
            ssh_port = container.get("sshPort", "")
            key = key_pair.get("privateKey", "")
            key_file = key_pair.get("privateKeyFileName", "bitahub_debug_key")

            click.echo("=" * 60)
            click.echo("  SSH 连接信息")
            click.echo("=" * 60)
            click.echo(f"  IP:       {ssh_ip}")
            click.echo(f"  端口:     {ssh_port}")
            click.echo(f"  用户:     root")
            click.echo(f"  密钥文件: {key_file}")
            click.echo()
            click.echo("  连接步骤:")
            click.echo(f"  1. 保存密钥:")
            click.echo(f"     echo '{key}' > ~/.ssh/{key_file}")
            click.echo(f"  2. 设置权限:")
            click.echo(f"     chmod 600 ~/.ssh/{key_file}")
            click.echo(f"  3. SSH 连接:")
            click.echo(f"     ssh -i ~/.ssh/{key_file} -p {ssh_port} root@{ssh_ip}")
            click.echo()
            click.echo(f"  调试机将在 3 小时后自动关闭")
            click.echo(f"  使用 bitahub status -t {task_id} 查看详情")
        else:
            click.echo("未获取到 SSH 信息，请稍后使用 status -t 查看")
            if ssh_result.get("message"):
                click.echo(f"  {ssh_result.get('message')}")

    except Exception as e:
        click.echo(f"创建调试机出错: {e}", err=True)
        sys.exit(1)


@main.command("watch")
@click.option("--interval", "-i", default=30, type=int, help="检查间隔 (秒)")
def watch_debug(interval: int):
    """调试机看门狗，自动维持调试机运行."""
    client = get_client()
    config = load_config()

    if not client.check_login():
        click.echo("未登录，请先使用 'bitahub login' 命令登录", err=True)
        sys.exit(1)

    project_id = config.get("current_project_id")
    project_name = config.get("current_project_name")
    if not project_id:
        click.echo("未指定项目，请先使用 'bitahub use <项目ID>' 命令切换项目", err=True)
        sys.exit(1)

    import time
    click.echo(f"调试机看门狗已启动 (检查间隔: {interval}s)")
    click.echo(f"项目: {project_name}")
    click.echo("按 Ctrl+C 停止")

    last_config = None

    try:
        while True:
            result = client.get_task_list(project_id=str(project_id), page=1, page_size=50)
            if result.get("message", {}).get("code") != 0:
                click.echo("获取任务列表失败，等待重试...")
                time.sleep(interval)
                continue

            tasks = result.get("data", {}).get("list", [])
            debug_tasks = [t for t in tasks if t.get("jobType") == 2]
            running_debug = [t for t in debug_tasks if t.get("state") in ("WAITING", "RUNNING", "PRERUNNING", "CREATED", "TAGING", "TAGSUCCESS", "RESTARTING")]

            if not running_debug:
                if not debug_tasks:
                    click.echo(f"[{_format_time(time.time())}] 无调试机，等待手动创建...")
                    time.sleep(interval)
                    continue

                last_debug = debug_tasks[0]
                click.echo(f"[{_format_time(time.time())}] 调试机已停止，重新启动...")
                detail_result = client.get_task_detail(str(last_debug.get("id")))
                if detail_result.get("message", {}).get("code") == 0:
                    detail = detail_result.get("data", {})
                    config_str = detail.get("config", "")
                    if config_str:
                        try:
                            last_config = json.loads(config_str)
                        except Exception:
                            pass

                if last_config:
                    last_config["jobName"] = f"{project_name}-{''.join(__import__('random').choices(__import__('string').ascii_lowercase + __import__('string').digits, k=5))}"
                    payload = {
                        "projectId": project_id,
                        "projectName": project_name,
                        "jobType": 2,
                        "codeNo": 0,
                        "config": json.dumps(last_config),
                    }
                    run_result = client.create_job(payload)
                    if run_result.get("message", {}).get("code") == 0:
                        click.echo(f"[{_format_time(time.time())}] 调试机已重新创建: {last_config['jobName']}")
                    else:
                        click.echo(f"[{_format_time(time.time())}] 重新创建失败: {run_result.get('message', {}).get('message')}")
            else:
                debug_names = [t.get("jobName") for t in running_debug]
                click.echo(f"[{_format_time(time.time())}] 调试机运行中: {', '.join(debug_names)}")

            time.sleep(interval)
    except KeyboardInterrupt:
        click.echo()
        click.echo("调试机看门狗已停止")


if __name__ == "__main__":
    main()

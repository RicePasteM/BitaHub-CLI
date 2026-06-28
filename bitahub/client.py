"""BitaHub API client."""

import re
import requests
from typing import Dict, Any
from .config import load_config, save_config
from .encrypt import encrypt_password


class BitaHubClient:
    """BitaHub API客户端."""

    def __init__(self, base_url: str = "https://bitahub.ustc.edu.cn"):
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })
        self._load_auth()

    def _load_auth(self):
        """从配置加载认证信息."""
        config = load_config()
        token = config.get("token")
        user_id = config.get("userId")
        cookies = config.get("cookies")

        if token:
            self.session.headers["token"] = token
        if user_id:
            self.session.headers["userId"] = user_id
        if cookies:
            for name, value in cookies.items():
                self.session.cookies.set(name, value, domain=".ustc.edu.cn")

    def _save_auth(self, token: str, user_id: str, cookies: dict):
        """保存认证信息到配置."""
        config = load_config()
        config["token"] = token
        config["userId"] = user_id
        config["cookies"] = cookies
        save_config(config)

    def login(self, username: str, password: str) -> Dict[str, Any]:
        """
        登录BitaHub.

        Args:
            username: 用户名（邮箱）
            password: 密码

        Returns:
            登录响应数据
        """
        # 加密密码
        encrypted_pwd = encrypt_password(password)

        # 构建登录URL
        url = f"{self.base_url}/gateway/business/api/login?username={username}&password={encrypted_pwd}"

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": self.base_url,
            "Referer": f"{self.base_url}/login",
        }

        try:
            response = self.session.post(url, headers=headers, data={})
            result = response.json()

            if result.get("message", {}).get("code") == 0:
                # 登录成功，从响应中提取token和userId
                data = result.get("data", {})
                token = data.get("token", "")
                user_id = data.get("id", "")

                # 获取cookies
                cookies = {}
                for cookie in response.cookies:
                    cookies[cookie.name] = cookie.value

                if token and user_id:
                    self._save_auth(token, user_id, cookies)
                    self.session.headers["token"] = token
                    self.session.headers["userId"] = user_id

                # 保存用户名和密码
                config = load_config()
                config["username"] = username
                config["password"] = password
                save_config(config)

            return result
        except Exception as e:
            return {
                "message": {
                    "status": 500,
                    "code": -1,
                    "message": f"登录出错: {str(e)}"
                }
            }

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """
        发送API请求.

        Args:
            method: HTTP方法
            endpoint: API端点
            **kwargs: 其他请求参数

        Returns:
            API响应数据
        """
        url = f"{self.base_url}{endpoint}"
        resp = self.session.request(method, url, **kwargs)
        return resp.json()

    def get_projects(self, page: int = 1, page_size: int = 18) -> Dict[str, Any]:
        """
        获取项目列表.

        Args:
            page: 页码
            page_size: 每页数量

        Returns:
            项目列表数据
        """
        endpoint = f"/gateway/business/api/project?origin=&cp={page}&ps={page_size}"
        return self._request("GET", endpoint)

    def get_gpu_resources(self, gpu_type: str = "") -> Dict[str, Any]:
        """
        获取GPU资源列表.

        Args:
            gpu_type: GPU类型筛选

        Returns:
            GPU资源数据
        """
        endpoint = f"/gateway/business/api/resources?GPUType={gpu_type}"
        return self._request("POST", endpoint)

    def get_storage_list(self) -> Dict[str, Any]:
        """
        获取存储列表.
        """
        endpoint = "/gateway/business/api/storage/list"
        return self._request("GET", endpoint)

    def get_team_list(self) -> Dict[str, Any]:
        """
        获取团队列表.
        """
        endpoint = "/gateway/business/api/team/getTeamList"
        return self._request("POST", endpoint)

    def get_user_info(self) -> Dict[str, Any]:
        """
        获取用户信息.
        """
        endpoint = "/gateway/business/api/user/info"
        return self._request("GET", endpoint)

    def get_task_list(
        self, project_id: str, page: int = 1, page_size: int = 20,
        job_tag: str = "", task_status: str = ""
    ) -> Dict[str, Any]:
        """
        获取指定项目的任务列表.

        Args:
            project_id: 项目ID
            page: 页码
            page_size: 每页数量
            job_tag: 任务标签筛选
            task_status: 任务状态筛选

        Returns:
            任务列表数据
        """
        endpoint = (
            f"/gateway/business/api/projectDetail"
            f"?cp={page}&ps={page_size}&projectId={project_id}"
            f"&jobTag={job_tag}&taskStatus={task_status}"
        )
        return self._request("GET", endpoint)

    def get_task_detail(self, job_id: str) -> Dict[str, Any]:
        """
        获取任务详情.

        Args:
            job_id: 任务ID

        Returns:
            任务详情数据
        """
        endpoint = f"/gateway/business/api/project/getUserTaskDetail?jobId={job_id}"
        return self._request("GET", endpoint)

    def get_task_log(self, container_log_url: str) -> str:
        """
        获取任务日志（末尾约 16KB）.

        Args:
            container_log_url: 容器日志URL

        Returns:
            日志文本内容
        """
        return self._fetch_log(container_log_url, start=-16384)

    def get_task_full_log(self, container_log_url: str) -> str:
        """
        获取完整任务日志.

        Args:
            container_log_url: 容器日志URL

        Returns:
            日志文本内容
        """
        return self._fetch_log(container_log_url, start=0)

    def get_task_tail_log(self, container_log_url: str, lines: int = 50) -> str:
        """
        获取任务日志末尾指定行数.

        Args:
            container_log_url: 容器日志URL
            lines: 行数（默认50），取最后 lines*200 字节再裁剪

        Returns:
            日志文本内容
        """
        text = self._fetch_log(container_log_url, start=-(lines * 256))
        text_lines = text.split('\n')
        return '\n'.join(text_lines[-lines:])

    def _fetch_log(self, container_log_url: str, start: int = -16384) -> str:
        """
        从日志接口获取日志.

        Args:
            container_log_url: 容器日志URL
            start: 起始字节偏移，负数表示从末尾起

        Returns:
            清洗后的日志文本
        """
        url = f"{self.base_url}/logHandle?url={container_log_url}stdout/?start={start}"
        resp = self.session.get(url)
        text = resp.text
        if re.search(r'<pre[^>]*>', text, re.IGNORECASE):
            match = re.search(r'<pre[^>]*>(.*?)</pre>', text, re.DOTALL | re.IGNORECASE)
            if match:
                text = match.group(1)
        text = re.sub(r'<[^>]+>', '', text)
        text = text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
        return text

    def get_job_operation(self, job_id: str, operate_type: int = 1) -> Dict[str, Any]:
        """
        获取任务操作详情（含容器日志URL、SSH信息等）.

        Args:
            job_id: 任务ID
            operate_type: 操作类型

        Returns:
            任务操作详情
        """
        endpoint = f"/gateway/business/api/jobOperation?jobId={job_id}&operateType={operate_type}"
        return self._request("POST", endpoint)

    def get_container_log_urls(self, job_id: str):
        """
        从任务操作详情中提取所有容器的日志URL.

        Args:
            job_id: 任务ID

        Returns:
            [(name, log_url), ...] 列表
        """
        result = self.get_job_operation(job_id, 1)
        urls = []
        if result.get("message", {}).get("code") == 0:
            detail = result.get("data", {}).get("jobDetail", {})
            for role_name, role_data in detail.get("taskRoles", {}).items():
                for ts in role_data.get("taskStatuses", []):
                    url = ts.get("containerLog", "")
                    if url:
                        urls.append((ts.get("name", role_name), url))
        return urls

    def get_task_retry_log(self, job_name: str) -> Dict[str, Any]:
        """
        获取任务重试日志.

        Args:
            job_name: 任务名称

        Returns:
            重试日志数据
        """
        url = f"{self.base_url}/rest-server/api/v1/jobs/{job_name}/retrylog"
        resp = self.session.get(url)
        return resp.json()

    def get_task_ssh_info(self, job_name: str) -> Dict[str, Any]:
        """
        获取任务SSH连接信息.

        Args:
            job_name: 任务名称

        Returns:
            SSH连接信息
        """
        url = f"{self.base_url}/rest-server/api/v1/jobs/{job_name}/ssh"
        resp = self.session.get(url)
        return resp.json()

    def check_login(self) -> bool:
        """
        检查是否已登录.
        """
        try:
            result = self.get_storage_list()
            return result.get("message", {}).get("code") == 0
        except Exception:
            return False

    def get_language_list(self) -> Dict[str, Any]:
        """
        获取语言列表.
        """
        return self._request("GET", "/gateway/images/api/language/getList")

    def get_framework_list(self) -> Dict[str, Any]:
        """
        获取框架列表.
        """
        return self._request("GET", "/gateway/images/api/framework/getList")

    def get_images_list(self, language: str, framework: str) -> Dict[str, Any]:
        """
        获取平台镜像列表.

        Args:
            language: 语言
            framework: 框架
        """
        endpoint = f"/gateway/images/api/images/getList?language={language}&framework={framework}"
        return self._request("GET", endpoint)

    def get_user_images_list(
        self, page_num: int = 1, page_size: int = 50
    ) -> Dict[str, Any]:
        """
        获取用户自定义镜像列表.
        """
        endpoint = "/gateway/images/api/images/getUserImagesList"
        return self._request("POST", endpoint, json={"pageNum": page_num, "pageSize": page_size})

    def get_team_list_with_power(self) -> Dict[str, Any]:
        """
        获取团队列表（含算力信息）.
        """
        endpoint = "/gateway/business/api/team/getTeamListWithPower"
        return self._request("POST", endpoint)

    def get_user_calculation_power(self) -> Dict[str, Any]:
        """
        获取用户个人算力余额.
        """
        config = load_config()
        token = config.get("token", "")
        endpoint = f"/orderservice/calculationPower/getUserCalculationPower?number=1&token={token}"
        return self._request("GET", endpoint)

    def get_task_charge_config(self) -> Dict[str, Any]:
        """
        获取任务计费配置（含GPU节点类型和定价）.
        """
        return self._request("POST", "/gateway/business/api/taskChargeConfig?number=1")

    def create_job(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建并运行任务.

        Args:
            payload: 任务配置，包含 projectId, projectName, jobType, codeNo, config
        """
        return self._request("POST", "/gateway/business/api/createJob", json=payload)

    def save_job_tag(self, project_id: str, job_id: str, job_tag: str) -> Dict[str, Any]:
        """
        设置任务标签.
        """
        config = load_config()
        payload = {
            "projectId": project_id,
            "jobId": job_id,
            "jobTag": job_tag,
            "userId": config.get("userId", ""),
        }
        return self._request("POST", "/gateway/business/api/project/saveJobTag", json=payload)

    def stop_job(self, job_id: str) -> Dict[str, Any]:
        """
        停止任务.
        """
        endpoint = f"/gateway/business/api/jobOperation?jobId={job_id}&operateType=2"
        return self._request("POST", endpoint)

    def delete_task(self, task_id: str) -> Dict[str, Any]:
        """
        删除任务.
        """
        endpoint = f"/gateway/fileCenter/api/task/delete?taskId={task_id}"
        return self._request("GET", endpoint)

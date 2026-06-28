"""使用 Selenium CDP 抓取 BitaHub createJob API 实际请求格式.
复用已登录的 token/cookies，无需重新输入密码."""
import json
import time
import sys
sys.path.insert(0, ".")
from bitahub.config import load_config

from selenium import webdriver
from selenium.webdriver.chrome.service import Service

config = load_config()

options = webdriver.ChromeOptions()
options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

driver = webdriver.Chrome(options=options)

base_url = config.get("base_url", "https://bitahub.ustc.edu.cn")
project_id = config.get("current_project_id")
project_name = config.get("current_project_name") or ""

try:
    # 先访问网站设置 cookies 的 domain
    driver.get(base_url)
    time.sleep(1)

    # 注入已保存的 cookies
    cookies = config.get("cookies") or {}
    for name, value in cookies.items():
        driver.add_cookie({"name": name, "value": value, "domain": ".ustc.edu.cn"})

    # 注入 token 到 localStorage
    token = config.get("token") or ""
    user_id = config.get("userId") or ""
    username = config.get("username") or ""
    driver.execute_script("""
        localStorage.setItem('mystorage', JSON.stringify({
            data: {
                userInfo: {token: arguments[0], userId: arguments[1], id: arguments[2]},
                noticeCount: '', searchValue: '', curDataSet: '', curProject: '',
                curTask: '', curTaskConfig: '', curPublicProject: '',
                taskFromHome: '', taskDataSet: '', curEditFile: '', jobCodeNo: '',
                noticeContent: ''
            }
        }));
    """, token, user_id, user_id)

    # 导航到项目运行页
    if project_id:
        run_url = f"{base_url}/index#/project/run?projectid={project_id}"
    else:
        run_url = f"{base_url}/index#/project/run"
    driver.get(run_url)
    print(f"已打开: {run_url}")
    time.sleep(5)

    print("\n请在浏览器中手动操作:")
    print("1. 选择镜像、GPU类型、GPU数量")
    print("2. 输入启动命令: echo hello")
    print("3. 点击「保存并运行任务」按钮")
    print(f"\n完成后按 Enter 查看结果...")
    input()

    # 解析性能日志
    logs = driver.get_log("performance")
    create_job_requests = []
    all_api_requests = []

    for entry in logs:
        try:
            log = json.loads(entry["message"])
            message = log.get("message", {})
            method = message.get("method", "")

            if method == "Network.requestWillBeSent":
                request = message.get("params", {}).get("request", {})
                url = request.get("url", "")
                if "api" in url or "gateway" in url:
                    r = {
                        "url": url,
                        "method": request.get("method"),
                        "postData": request.get("postData", ""),
                        "headers": dict(request.get("headers", {})),
                    }
                    all_api_requests.append(r)
                    if "createJob" in url:
                        create_job_requests.append(r)
        except Exception:
            pass

    for i, req in enumerate(create_job_requests):
        print(f"\n{'='*60}")
        print(f"createJob 请求 #{i+1}")
        print(f"{'='*60}")
        print(f"URL: {req['url']}")
        print(f"Method: {req['method']}")
        print(f"\n关键 Headers:")
        for k in ("Content-Type", "token", "userId", "Cache-Control", "Origin", "Referer"):
            if k in req["headers"]:
                print(f"  {k}: {req['headers'][k]}")
        print(f"\nRequest Body:")
        try:
            body = json.loads(req["postData"])
            print(json.dumps(body, indent=2, ensure_ascii=False)[:3000])
        except Exception:
            print(req["postData"][:2000])

    if not create_job_requests:
        print("\n未捕获到 createJob，最近 API 请求:")
        for req in all_api_requests[-10:]:
            print(f"  {req['method']} {req['url']}")

finally:
    print("\n按 Enter 关闭浏览器...")
    input()
    driver.quit()

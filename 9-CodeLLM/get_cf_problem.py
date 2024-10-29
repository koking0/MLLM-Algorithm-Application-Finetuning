import concurrent.futures
import json
import os
import random
import re
import time
import traceback

import bs4
import requests
from tomd import Tomd

def is_valid_ip_port(address):
    pattern = r"^(\d{1,3}\.){3}\d{1,3}:\d+$"
    if re.match(pattern, address):
        return True
    else:
        return False


def get_proxy():
    global proxies
    app_key = "1049242532485419008"
    app_secret = "DlU4ESOX"
    api_url = "https://api.xiaoxiangdaili.com/ip/get"
    res = requests.get(api_url, params={"appKey": app_key, "appSecret": app_secret, "wt": "text", "cnt": 1}, timeout=10)
    content = str(res.content, 'utf-8')
    print("proxy API response: " + content)
    if not is_valid_ip_port(content) and "请求过于频繁" in content:
        return proxies
    proxy_meta = "http://%(user)s:%(pass)s@%(proxy)s" % {
        "proxy": content,
        "user": app_key,
        "pass": app_secret,
    }
    return {"http": proxy_meta, "https": proxy_meta}


def get_submission_detail(contest_status, contest_id, problem_index):
    global proxies
    try:
        contest_status_dir = os.path.join(dataset_dir, str(contest_id), problem_index)
        submission_id = contest_status["id"]
        contest_status_file_name = os.path.join(contest_status_dir, f"{submission_id}.json")
        if os.path.exists(contest_status_file_name):
            print(f"比赛{contest_id}的题目{problem_index}的提交{submission_id}已存在，跳过。")
            return
        submission_url = f"https://codeforces.com/contest/{contest_id}/submission/{submission_id}"
        submission_response = requests.get(submission_url, proxies=proxies, timeout=10)
        soup = bs4.BeautifulSoup(submission_response.content, "html.parser")
        pre_tag = soup.find("pre", {"id": "program-source-text"})
        contest_status["code"] = pre_tag.text
        json.dump(contest_status, open(contest_status_file_name, "w"))
        print(f"比赛{contest_id}的题目{problem_index}的提交{submission_id}已保存：{contest_status_file_name}")
    except Exception as e:
        print(f"Exception: {e}.")
        time.sleep(random.randint(5, 10))
        proxies = get_proxy()


def count_files(directory):
    count = 0
    for _, _, filenames in os.walk(directory):
        count += len(filenames)  # 计算当前目录中的文件数量
    return count


def strip_html_tags(input_str):
    # 将<br>, <br/>, <p> 和 <div>标签转为换行符
    input_str = re.sub(r'<br\s*?/?>', '\n', input_str)  # 处理<br>和<br/>标签
    input_str = re.sub(r'</p>', '\n', input_str)  # 处理</p>标签
    input_str = re.sub(r'</div>', '\n', input_str)  # 处理</div>标签
    # 使用正则表达式去除所有其他HTML标签
    clean = re.compile('<.*?>')
    return re.sub(clean, '', input_str).lstrip()


def get_problem_json(contest_idx, problem_idx, problem_dict):
    problem_path = os.path.join(dataset_dir, str(contest_idx), problem_idx, "problem.json")
    if os.path.exists(problem_path):
        print(f"contest: {contest_idx} problem: {problem_idx} problem.json exists.")
        return

    problem_page_url = f"https://codeforces.com/contest/{contest_idx}/problem/{problem_idx}"
    soup = bs4.BeautifulSoup(requests.get(problem_page_url).content, "lxml")
    problem_statement = soup.find(name="div", class_="problem-statement")

    tags = {
        "title": "title",
        "time-limit": "time-limit",
        "memory-limit": "memory-limit",
        "problem-description": "header",
        "input-specification": "input-specification",
        "output-specification": "output-specification",
        "note": "note"
    }

    for key, tag in tags.items():
        if key == "problem-description":
            content = problem_statement.find("div", class_=tag).find_next_sibling("div")
        else:
            content = problem_statement.find("div", class_=tag)
        if content:
            problem_dict[key] = Tomd(str(content)).markdown if Tomd(str(content)) else content.text
            problem_dict[key] = problem_dict[key].replace("$$$", "$").strip()

    problem_dict["demo-input"] = [strip_html_tags(str(item.find("pre"))) for item in
                                  problem_statement.find_all("div", class_="input")]
    problem_dict["demo-output"] = [strip_html_tags(str(item.find("pre"))) for item in
                                   problem_statement.find_all("div", class_="output")]

    with open(problem_path, "w") as f:
        json.dump(problem_dict, f)
        print(f"contest: {contest_idx} problem: {problem_idx} problem.json saved")


def get_problem_dict(problem_list, contest_idx, problem_idx):
    for item in problem_list:
        if item["contestId"] == contest_idx and item["index"] == problem_idx:
            return item
    return {}


def get_problem_test_data(status):
    contest_idx, problem_idx, submission_idx = status["problem"]["contestId"], status["problem"]["index"], status["id"]
    test_path = os.path.join(dataset_dir, str(contest_idx), problem_idx, "test.json")
    if os.path.exists(test_path):
        return


def main():
    # 使用全局代理变量
    global proxies
    # 请求Codeforces的问题列表API并解析JSON响应
    problem_list_response = requests.get("https://codeforces.com/api/problemset.problems").json()
    problem_list = problem_list_response["result"]["problems"]
    # 为了避免请求过快，这里会暂停一个随机的时间间隔
    time.sleep(random.randint(5, 10))
    # 请求Codeforces的比赛列表API并解析JSON响应
    contest_list_response = requests.get("https://codeforces.com/api/contest.list").json()
    contest_list = contest_list_response["result"]
    # 根据比赛ID排序比赛列表
    contest_list.sort(key=lambda x: x["id"])
    # 再次暂停随机时间
    time.sleep(random.randint(5, 10))

    # 遍历所有的比赛
    for contest in contest_list:
        # 只处理已经结束的比赛
        if contest["phase"] == "FINISHED" and contest['id'] < 1010:
            contest_idx = contest["id"]
            # 为每个比赛创建一个目录
            contest_dir = os.path.join(dataset_dir, str(contest_idx))
            print(f"创建比赛{contest_idx}文件夹")
            os.makedirs(contest_dir, exist_ok=True)
            # 构建获取比赛状态的API URL
            status_url = f"https://codeforces.com/api/contest.status?contestId={contest_idx}"
            from_index = 1
            count = 1000

            # 无限循环，直到没有更多的提交
            while True:
                # 构建批量获取比赛状态的URL
                status_url_batch = f"{status_url}&from={from_index}&count={count}"
                # 尝试获取比赛状态
                try:
                    contest_status_response = requests.get(status_url_batch, timeout=10).json()
                except Exception as e:
                    # 如果请求失败，打印错误信息并尝试更换代理
                    print(f"请求{status_url_batch}失败，错误信息：{e}")
                    time.sleep(random.randint(5, 10))
                    proxies = get_proxy()
                    continue
                try:
                    contest_status_list = contest_status_response["result"]
                except Exception as e:
                    print('又错啦！jump！')
                    break
                print(f"获取比赛{contest_idx}从{from_index}开始的{count}个提交")
                contest_status_list.sort(key=lambda x: x["id"])
                # 如果没有提交，跳出循环
                if len(contest_status_list) == 0:
                    break
                # 获取当前比赛的所有题目索引
                contest_problem_index_set = set()
                for submission in contest_status_list:
                    contest_problem_index_set.add(submission["problem"]["index"])
                # 遍历每个题目
                for problem_idx in contest_problem_index_set:
                    contest_problem_dir = os.path.join(dataset_dir, str(contest_idx), problem_idx)
                    os.makedirs(contest_problem_dir, exist_ok=True)
                    try:
                        # 获取并保存题目的详细信息
                        problem_dict = get_problem_dict(problem_list, contest_idx, problem_idx)
                        get_problem_json(contest_idx, problem_idx, problem_dict)
                    except Exception as e:
                        print(f"get contest:{contest_idx} problem: {problem_idx} error: {e}")
                        traceback.print_exc()
                        time.sleep(random.randint(5, 10))
                        proxies = get_proxy()
                        continue
                print(f"比赛{contest_idx}包含题目：{contest_problem_index_set}")

                # 检查文件数量是否超过1000
                if count_files(contest_dir) > 1000:
                    print(f"比赛{contest_idx}文件夹文件数量超过1000")
                    break  # 如果超过则跳过当前比赛
                # 使用多线程处理每个提交
                with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                    futures = []
                    for status in contest_status_list:
                        status_idx = status["problem"]["index"]
                        # 如果编程语言为C++，则获取提交的详细信息
                        if status["programmingLanguage"] in ["GNU C++14", "GNU C++17", "GNU C++20 (64)", "MS C++ 2017", "GNU C++17 (64)"]:
                            # futures.append(executor.submit(get_problem_test_data, status))
                            futures.append(executor.submit(get_submission_detail, status, contest_idx, status_idx))
                    for future in concurrent.futures.as_completed(futures):
                        try:
                            future.result()

                        except Exception as exc:
                            print(f"Thread generated an exception: {exc}")
                from_index += count


if __name__ == '__main__':
    dataset_dir = r"E:\Datasets\CodeForceDataSet-python-raw"
    os.makedirs(dataset_dir, exist_ok=True)
    proxies = get_proxy()
    # get_problem_json("84", "E", {})
    main()

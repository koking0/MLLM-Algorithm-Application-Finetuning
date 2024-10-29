import json
import os
import time

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By

fail_problem = set()


def get_test_cases(contest_idx, problem_idx, problem_dir, submission_idx):
    test_cases = []
    driver = uc.Chrome(headless=True, use_subprocess=False)
    driver.get(f"https://codeforces.com/contest/{contest_idx}/submission/{submission_idx}/")
    # 点击 class 为 click-to-view-tests 的元素
    elements = driver.find_elements(By.XPATH, '//*[@id="pageContent"]/div[4]/div[2]/a')
    elements[0].click()
    time.sleep(2)
    input_elements = driver.find_elements(By.CLASS_NAME, 'input-view')
    answer_elements = driver.find_elements(By.CLASS_NAME, 'answer-view')
    for input_element, answer_element in zip(input_elements, answer_elements):
        input_element = input_element.find_element(By.CLASS_NAME, 'input')
        answer_element = answer_element.find_element(By.CLASS_NAME, 'answer')
        if input_element.text and answer_element.text:
            test_cases.append({"input": input_element.text, "output": answer_element.text})
    print(f"获取题目{contest_idx}-{problem_idx}的测试用例：{test_cases}")
    if test_cases:
        # 存储为 JSON 文件
        with open(os.path.join(problem_dir, "test_cases.json"), "w") as f:
            json.dump(test_cases, f)
            print(f"contest: {contest_idx} problem: {problem_idx} test.json saved")
    else:
        fail_problem.add(f"{contest_idx}-{problem_idx}")


def main():
    # 遍历 dataset_dir 下的所有子文件夹
    for root, dirs, files in os.walk(dataset_dir):
        for dir in dirs:
            if dir.isdigit():
                contest_idx = dir
                contest_dir = os.path.join(dataset_dir, dir)
                # 遍历比赛目录下的所有子文件夹
                for root, dirs, files in os.walk(contest_dir):
                    for dir in dirs:
                        # 检查文件夹是否是以字母命名的
                        if dir.isalpha():
                            # 获取题目ID
                            problem_idx = dir
                            # 获取题目目录
                            problem_dir = os.path.join(contest_dir, dir)
                            # 如果该题目目录下没有 test_cases.json 文件
                            if not os.path.exists(os.path.join(problem_dir, "test_cases.json")):
                                # 获取该文件夹下的一个以数字命名的 JSON 文件
                                for root, dirs, files in os.walk(problem_dir):
                                    for file in files:
                                        if file.endswith(".json") and file.split('.')[0].isdigit():
                                            # 加载 JSON 文件，判断其中 verdict 是否为 OK，如果不是则跳过
                                            with open(os.path.join(problem_dir, file), "r") as f:
                                                data = json.load(f)
                                                if data["verdict"] != "OK":
                                                    continue
                                            # 获取提交ID
                                            submission_idx = file.split('.')[0]
                                            # 获取题目的测试用例
                                            try:
                                                get_test_cases(contest_idx, problem_idx, problem_dir, submission_idx)
                                            except:
                                                print(f"获取题目{contest_idx}-{problem_idx}的测试用例失败")
                                                fail_problem.add(f"{contest_idx}-{problem_idx}")
                                            break


if __name__ == '__main__':
    dataset_dir = r"E:\Datasets\CodeForceDataSet-python-raw"
    os.makedirs(dataset_dir, exist_ok=True)
    main()
    # 保存 fail_problem
    with open(os.path.join(dataset_dir, "fail_problem.json"), "w") as f:
        json.dump(list(fail_problem), f)
        print(f"fail_problem.json saved")

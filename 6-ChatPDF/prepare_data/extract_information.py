import glob
import json
import re
from concurrent.futures import ThreadPoolExecutor
import pandas as pd


# 获取特定属性的函数
def get_info(line_dict, answer, keywords_re, check_chinese, all_person=None):
    # 当给定属性为空，且关键字在当前行中存在时进行提取
    if answer == "" and (not all_person or all_person != "") and re.search(keywords_re, line_dict["inside"]):
        answer_list = eval(line_dict["inside"])
        for item in answer_list:
            # 判断是否需要检查中文，并设置条件
            chinese_condition = not re.search("[\u4e00-\u9fa5]", item) if check_chinese else True
            if chinese_condition and not re.search(keywords_re.replace("'", ""), item) and item.strip():
                return item
    return answer


# 处理文件，提取相关数据的函数
def process_file(file_path):
    # 定义需要提取的属性和对应的正则表达式
    attributes = {
        "mail": ["电子信箱|电子邮箱", True], "registered_address": ["注册地址", False],
        "office_address": ["办公地址", False], "chinese_name": ["公司的中文名称", False],
        "chinese_short_name": ["中文简称", False], "english_name": ["公司的外文名称|公司的外文名称(?:（如有）)?", True],
        "english_short_name": ["公司的外文名称缩写|公司的外文名称缩写(?:（如有）)?", True],
        "website": ["公司(?:国际互联网)?网址", True], "boss": ["公司的法定代表人", False],
        "all_person": ["(?:报告期末)?在职员工的数量合计(?:（人）)?", True],
        "person11": ["生产人员", True], "person12": ["销售人员", True], "person13": ["技术人员", True],
        "person14": ["财务人员", True], "person15": ["行政人员", True], "person21": ["本科及以上", True],
        "person22": ["本科", True], "person23": ["硕士及以上", True], "person24": ["硕士", True],
        "person25": ["博士及以上", True], "person26": ["博士", True], "person27": ["公司研发人员的数量", True]
    }

    # 初始化存储提取数据的字典
    data = {k: "" for k in attributes}
    data["stock_code"] = ""
    data["short_name"] = ""

    # 打开并读取文件内容
    with open(file_path, "r", encoding="utf-8") as file:
        lines = [json.loads(line.replace("\n", "")) for line in file.readlines()]

        # 遍历文件的每一行
        for i, line_dict in enumerate(lines):
            try:
                if line_dict["type"] not in ["页眉", "页脚", "text"]:
                    # 提取股票代码
                    if data["stock_code"] == "" and re.search("股票代码|证券代码", line_dict["inside"]):
                        text = line_dict["inside"] + "\n"
                        text += lines[i + 1]["inside"]
                        match = re.search(r"(?:0|6|3)\d{5}", text)
                        if match:
                            data["stock_code"] = match.group()

                    # 提取股票简称
                    if data["short_name"] == "" and re.search("股票简称", line_dict["inside"]):
                        exclude_keyword = "代码|股票|简称|交易所|A股|A 股|公司|上交所|科创版|名称"
                        text_list = eval(line_dict["inside"])
                        text_list += eval(lines[i + 1]["inside"])
                        for item in text_list:
                            if not re.search(exclude_keyword, item) and item not in ["", " "]:
                                data["short_name"] = item
                                break

                    # 提取其他属性
                    for key, (regex, chinese_flag) in attributes.items():
                        all_person = data["all_person"] if "person" in key else None
                        data[key] = get_info(line_dict, data[key], regex, chinese_flag, all_person)

                    # 若所有数据都已提取，则跳出循环
                    if all(data.values()):
                        break
            except:
                # 如果出现错误，打印出问题行的内容
                print(line_dict)

    # 提取文件名中的信息
    file_name = file_path.split("\\")[-1]
    file_details = file_name.split("__")
    new_row = {
        "文件名": file_name, "发布日期": file_details[0], "公司名称": file_details[1],
        "股票代码": file_details[2], "股票简称": file_details[3], "报告年份": file_details[4],
        "代码": data["stock_code"], "简称": data["short_name"], "电子信箱": data["mail"],
        "注册地址": data["registered_address"], "办公地址": data["office_address"],
        "中文名称": data["chinese_name"], "中文简称": data["chinese_short_name"],
        "外文名称": data["english_name"], "外文名称缩写": data["english_short_name"],
        "公司网址": data["website"], "法定代表人": data["boss"],
        "职工总数": data["all_person"], "生产人员": data["person11"], "销售人员": data["person12"],
        "技术人员": data["person13"], "财务人员": data["person14"], "行政人员": data["person15"],
        "本科及以上人员": data["person21"], "本科人员": data["person22"], "硕士及以上人员": data["person23"],
        "硕士人员": data["person24"], "博士及以上人员": data["person25"], "博士人员": data["person26"],
        "研发人数": data["person27"]
    }
    print(f"process complete on file: {file_name}")
    return new_row


if __name__ == '__main__':
    # 指定文件夹路径
    folder_path = r"D:\Code\DataSet\chatglm_llm_fintech_raw_dataset\alltxt"
    # 使用glob模块获取文件夹内的所有文件名称，并进行排序
    file_paths = sorted(glob.glob(folder_path + "/*"), reverse=True)

    # 使用ThreadPoolExecutor并行处理文件
    with ThreadPoolExecutor(max_workers=32) as executor:
        results = list(executor.map(process_file, file_paths))

    # 将结果存入DataFrame，并输出为Excel文件
    df = pd.DataFrame(results)
    df.to_excel("1-company_information.xlsx", index=False)

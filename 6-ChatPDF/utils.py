import difflib
import heapq
import os

txt_file_directory = r"D:\Code\DataSet\chatglm_llm_fintech_raw_dataset\alltxt"


def string_similar(s1, s2):
    return difflib.SequenceMatcher(None, s1, s2).quick_ratio()


def compute_similarity(clean_file_name, q, years):
    base_score = string_similar(clean_file_name, q)
    parts = clean_file_name.split("__")
    company_full_name, company_short_name, file_year = parts[0], parts[2], parts[3][:4]

    company_in_q = company_full_name in q or company_short_name in q
    year_in_q = file_year in years

    if not company_in_q:
        return 0.5 * base_score
    if not year_in_q:
        return 0.25 + 0.5 * base_score
    return 0.5 + 0.5 * base_score


def find_most_related_file(q, file_directory=txt_file_directory):
    # 统计问题中涉及的年份个数
    years = []
    for year in ["2019", "2020", "2021"]:  # 初赛问题中的年份只涉及这三个
        if year in q:
            years.append(year)

    similarities = []  # 用于存储每个文件与问题相似度
    # 遍历文件夹中的每一个文件
    for file_name in os.listdir(file_directory):
        if file_name.endswith(".txt"):
            clean_file_name = "__".join(file_name.split("__")[1:])
            file_path = os.path.join(file_directory, file_name)
            # 计算文件名与问题之间的相似度
            similarity = compute_similarity(clean_file_name, q, years)
            # 使用堆来存储最相关的 n 个文件，通过将相似度取负，实际上是创建了一个“大根堆”
            heapq.heappush(similarities, (-similarity, file_path))

    # 获取与问题最相关的 n 个文件
    n = len(years)
    most_related_files = [(abs(similarity), file_path) for similarity, file_path in
                          [heapq.heappop(similarities) for _ in range(n)]]
    return most_related_files


if __name__ == '__main__':
    print(find_most_related_file("2019年四方科技电子信箱是什么?", txt_file_directory))

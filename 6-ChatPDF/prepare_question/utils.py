import json
import os
import pickle
import re

import zhipuai
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import FAISS

zhipuai.api_key = ""

# 获取当前脚本所在的目录
current_directory = os.path.dirname(os.path.abspath(__file__))
# 连接目录和文件名来得到完整的文件路径
file_path = os.path.join(current_directory, "columns_list.pkl")
# 使用pickle从文件中加载列表
with open(file_path, "rb") as file:
    loaded_columns_list = pickle.load(file)
column_list = loaded_columns_list
embeddings = HuggingFaceEmbeddings(model_name="shibing624/text2vec-base-chinese")
vectorstore = FAISS.from_texts(column_list, embeddings)


def trim_string(s):
    return re.sub(r'^[ \'\"]*|[ \'\"]*$', '', s)


def get_llm_classification(question):
    assistant_role_msg = """你是一个提取问题句子要素清单的机器人，可以根据输入的问题句子，输出JSON格式的要素清单，模板：{"company": "", "year": [], "keyword": [], "formula": true, "type": ""}。
    其中company表示提取的公司名，year表示提取的年份，keyword表示提取的字段关键词，formula表示是否要使用公式。type字段表示问题类型，'type': '1'型问题为单字段的精准查询，'type': '1-2'型问题会涉及到两个或多个字段，'type': '2-1'型问题涉及到简单的公式计算，'type': '2-2'型问题涉及到查询多条记录，'type': '3-1'型问题是根据年报的具体文档段落做总结的开放式问题，'type': '3-2'型问题为金融领域专业知识问答。
    对于不确定的信息，你可以将输出空字符串或空列表。
    例如，给定问题"华翔股份2021年营业利润是多少元?"，应该输出:{"company": "华翔股份", "year": [2021], "keyword": ["营业利润"], "formula": false, "type": "1"}。
    给定问题"2021年利润总额最高的上市公司是？"，应该输出:{"company": "", "year": [2021], "keyword": ["利润总额"], "formula": false, "type": "1"}。
    给定问题"2019年，宁夏银星能源股份有限公司固定资产和无形资产分别是多少元?"，应该输出:{"company": "宁夏银星能源股份有限公司", "year": [2019], "keyword": ["固定资产", "无形资产"], "formula": false, "type": "1-2"}。
    给定问题"在北京注册的上市公司中，2019年资产总额最高的前四家上市公司是哪些家？金额为？"，应该输出:{"company": "", "year": [2019], "keyword": ["注册地址", "资产总额"], "formula": false, "type": "1-2"}。
    给定问题"2020年贵州燃气集团股份有限公司速动比率为多少?保留2位小数。"，应该输出:{"company": "贵州燃气集团股份有限公司", "year": [2020], "keyword": ["速动比率"], "formula": true, "type": "2-1"}。
    给定问题"2021年津药药业的法定代表人与上一年是否相同?"，应该输出:{"company": "津药药业", "year": [2020, 2021], "keyword": ["法定代表人"], "formula": false, "type": "2-2"}。
    给定问题"请简要分析爱丽家居科技股份有限公司2020年核心竞争力的情况。"，应该输出:{"company": "爱丽家居科技股份有限公司", "year": [2020], "keyword": ["核心竞争力"], "formula": false, "type": "3-1"}。
    给定问题"请简要介绍2021年久吾高科重大资产和股权出售情况。"，应该输出:{"company": "久吾高科", "year": [2021], "keyword": ["重大资产和股权出售"], "formula": false, "type": "3-1"}。
    给定问题"合同资产是指什么？"，应该输出:{"company": "", "year": [], "keyword": ["合同资产"], "formula": false, "type": "3-2"}。
    ……
    对于输出应该严格按照JSON格式输出，不要输出任何多余的字符。
    """
    response = zhipuai.model_api.invoke(
        model="chatglm_pro",
        prompt=[
            {"role": "user", "content": assistant_role_msg + f"\n那么，给定问题\"{question}\"，应该输出:"},
        ],
        ref={"enable": False}
    )

    result = response["data"]["choices"][0]["content"]
    result = trim_string(result).replace("\\", "")
    result = json.loads(result)
    return result


def get_llm_sql(question, years, columns):
    assistant_role_msg = """你的任务是将我所提出的问题转换为SQL。我会给你提供要查询的表名、涉及到的年份和涉及到的数据库表列名，你需要基于此写出对应的SQL语句。
    接下来我将给你提供几个例子：
    Input: 查询的表名为company，涉及到的年份：2020、2021，涉及到的列名有: 法定代表人,公司名称,股票简称,股票代码,合同资产,报告年份。问题：2021年公司名称为晋西车轴股份有限公司的公司法定代表人与2020年相比是否都是相同的？
    Output: select 公司名称,股票简称,报告年份,法定代表人 from company where 报告年份 in ('2021', '2020') and (公司名称 in ('晋西车轴股份有限公司') or 股票简称 in ('晋西车轴股份有限公司'));
    Input: 查询的表名为company，涉及到的年份：2021，涉及到的列名有: 公司名称,硕士人员,职工总数,股票代码,股票简称,博士人员,报告年份。问题：朗新科技2021年的硕士员工人数有多少？
    Output: select 公司名称,股票简称,报告年份,硕士人员 from company where 报告年份 in ('2021') and (公司名称 in ('朗新科技') or 股票简称 in ('朗新科技');
    Input:查询的表名为company，涉及到的年份：2019，涉及到的列名有: 公司名称,固定资产,无形资产,股票代码,股票简称,报告年份。问题：2019年银星能源固定资产和无形资产分别是多少元?
    Output: select 公司名称,股票简称,报告年份,固定资产,无形资产 from company where 报告年份 in ('2019') and (公司名称 in ('银星能源') or 股票简称 in ('银星能源');
    Input: 查询的表名为company，涉及到的年份：2019，涉及到的列名有: 公司名称,股票代码,股票简称,报告年份,注册地址,资产总计。问题：在北京注册的上市公司中，2019年资产总额最高的前四家上市公司是哪些家？金额为？
    Output: select 公司名称,股票简称,报告年份,资产总计 from company where 报告年份 in ('2019') and 注册地址 like '%北京%' order by 资产总计 desc limit 4;
    ……
    对于Output应该严格按照sqlite的sql格式输出，并且所有select的字段中都要包含“公司名称,股票简称,报告年份”这几项，还要注意区分WHERE筛选条件中到底是用“公司名称”还是“股票简称”，不要输出任何多余的字符。
    """
    columns = ["公司名称", "股票简称", "股票代码", "报告年份"] + columns
    columns_msg = ','.join(columns).replace(" ", '')
    years_msg = '、'.join([str(i) + "年" for i in years]).replace(" ", '')
    message = f"查询的表名为company，涉及到的年份：{years_msg}，涉及到的列名有: {columns_msg}。问题：{question}"
    response = zhipuai.model_api.invoke(
        model="chatglm_pro",
        prompt=[
            {"role": "user", "content": assistant_role_msg + f"\n那么，再给定Input: {message}，应该Output:"},
        ],
        temperature=1.0,
        ref={"enable": False}
    )

    result = response["data"]["choices"][0]["content"].replace('，', ',')
    return trim_string(result)


def answer_normalize(question, answer):
    assistant_msg = f"""请你根据查询结果回答问题，要求语言流畅，表意清晰，完整通顺。
    查询结果：{answer}
    问题：{question}
    回答：
    """
    response = zhipuai.model_api.invoke(
        model="chatglm_pro",
        prompt=[
            {"role": "user", "content": assistant_msg},
        ],
        temperature=1.0,
        ref={"enable": False}
    )

    result = response["data"]["choices"][0]["content"].replace('，', ',')
    return trim_string(result)


def execute_sql(cursor, sql):
    # 查询数据
    cursor.execute(sql)
    results = cursor.fetchall()
    # 获取列名
    columns = [desc[0] for desc in cursor.description]
    # 转换查询结果为字典
    data = [dict(zip(columns, row)) for row in results]
    # 转换字典为JSON格式
    json_data = json.dumps(data, ensure_ascii=False, indent=4)
    return json_data


def get_similarity_column_name(keyword):
    results_with_scores = vectorstore.similarity_search_with_score(keyword, k=2)
    return [doc.page_content for doc, _ in results_with_scores]


if __name__ == '__main__':
    print(get_similarity_column_name("总负债"))

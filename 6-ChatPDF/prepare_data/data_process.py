import pandas as pd

# 1. 读取两个Excel文件数据
# 使用pandas的read_excel方法，加载Excel文件到DataFrame中
df1 = pd.read_excel("1-company_information.xlsx", engine="openpyxl")
df2 = pd.read_excel("2-company_financial.xlsx", engine="openpyxl")

# 2. 数据完整性检查
# 确保两个Excel文件中都包含"文件名"这一列，否则抛出错误
if "文件名" not in df1.columns or "文件名" not in df2.columns:
    raise ValueError("One of the Excel files does not have the '文件名' column.")

# 3. 数据合并
# 使用merge方法，根据指定的键列合并两个DataFrame
merge_keys = ["文件名", "公司名称", "股票代码", "股票简称", "报告年份", "发布日期"]
df = df1.merge(df2, on=merge_keys, how="inner")

# 4. 定义计算公式
# 创建一个字典存储需要计算的新指标及其相关信息
# 其中，'公式'表示计算公式，'数值'表示公式中需要的数据列
formula_name_list = {
    "营业成本率": {"公式": "营业成本率=营业成本/营业收入", "数值": ["营业成本", "营业收入"]},
    "投资收益占营业收入比率": {"公式": "投资收益占营业收入比率=投资收益/营业收入", "数值": ["投资收益", "营业收入"]},
    "管理费用率": {"公式": "管理费用率=管理费用/营业收入", "数值": ["管理费用", "营业收入"]},
    "财务费用率": {"公式": "财务费用率=财务费用/营业收入", "数值": ["财务费用", "营业收入"]},
    "资产负债比率": {"公式": "资产负债比率=负债合计/资产总计", "数值": ["负债合计", "资产总计"]},
    "现金比率": {"公式": "现金比率=货币资金/流动负债合计", "数值": ["货币资金", "流动负债合计"]},
    "非流动负债比率": {"公式": "非流动负债比率=非流动负债合计/负债合计", "数值": ["非流动负债合计", "负债合计"]},
    "流动负债比率": {"公式": "流动负债比率=流动负债合计/负债合计", "数值": ["流动负债合计", "负债合计"]},
    "净利润率": {"公式": "净利润率=净利润/营业收入", "数值": ["净利润", "营业收入"]},
    "企业研发经费与利润比值": {"公式": "企业研发经费与利润比值=研发费用/净利润", "数值": ["研发费用", "净利润"]},
    "研发人员占职工人数比例": {"公式": "研发人员占职工人数比例=研发人数/职工总数", "数值": ["研发人数", "职工总数"]},
    "毛利率": {"公式": "毛利率=(营业收入-营业成本)/营业收入", "数值": ["营业收入", "营业成本"]},
    "营业利润率": {"公式": "营业利润率=营业利润/营业收入", "数值": ["营业利润", "营业收入"]},
    "流动比率": {"公式": "流动比率=流动资产合计/流动负债合计", "数值": ["流动资产合计", "流动负债合计"]},
    "三费比重": {
        "公式": "三费比重=(销售费用+管理费用+财务费用)/营业收入",
        "数值": ["销售费用", "管理费用", "财务费用", "营业收入"]
    },
    "企业研发经费占费用比例": {
        "公式": "企业研发经费占费用比例=研发费用/(销售费用+财务费用+管理费用+研发费用)",
        "数值": ["研发费用", "销售费用", "财务费用", "管理费用"]
    },
    "企业研发经费与营业收入比值": {
        "公式": "企业研发经费与营业收入比值=研发费用/营业收入",
        "数值": ["研发费用", "营业收入"]
    },
    "企业硕士及以上人员占职工人数比例": {
        "公式": "企业硕士及以上人员占职工人数比例=(硕士人员 + 博士人员)/职工总数",
        "数值": ["硕士人员", "博士人员", "职工总数"]
    },
    "速动比率": {
        "公式": "速动比率=(流动资产合计-存货)/流动负债合计",
        "数值": ["流动资产合计", "存货", "流动负债合计"]
    },
}

# 5. 针对不需要乘以100的指标（不以百分比形式展现的指标），创建一个列表
not_percentage_list = [
    "企业研发经费占费用比例", "企业研发经费与利润比值", "企业研发经费与营业收入比值",
    "研发人员占职工人数比例", "企业硕士及以上人员占职工人数比例", "流动比率", "速动比率"
]

# 6. 初始化新指标列
# 对DataFrame增加新列，用于存储计算后的结果
for new_name in formula_name_list:
    df[new_name] = ""

# 7. 数据预处理
# 去除"报告年份"列中的“年”后缀
df["报告年份"] = df["报告年份"].str.replace("年", "")

# 8. 计算新指标
# 遍历每行数据，根据定义的公式计算新指标，并存储到相应的列中
for index, row in df.iterrows():
    for new_name, details in formula_name_list.items():
        formula = details["公式"].split("=")[1]
        value_dict = {col_name: str(row[col_name]) for col_name in details["数值"]}
        for col_name, currency_this in value_dict.items():
            formula = formula.replace(col_name, currency_this).replace(",", "").replace("，", "")
        try:
            # 如果指标需要以百分比展示，那么计算结果乘以100
            if new_name not in not_percentage_list:
                formula = "100*" + formula
            result = f"{formula} = {eval(formula)}{'%' if new_name not in not_percentage_list else ''}"
        except Exception as e:
            print(f"process formula {formula} error: {e}")
            result = "缺少数据，所以值为空"

        value_dict.update({
            "公式": formula_name_list[new_name]["公式"],
            new_name: result
        })
        df.at[index, new_name] = value_dict  # 更新字段

# 9. 保存计算后的结果到新的Excel文件
df.to_excel("company.xlsx", engine="openpyxl", index=False)

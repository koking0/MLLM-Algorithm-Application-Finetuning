import glob
import json
import re
import pandas as pd

from concurrent.futures import ThreadPoolExecutor


# 定义cut_all_text函数，用于按照特定的正则模式截取文本内容
def cut_all_text(check, check_re_1, check_re_2, all_text, line_dict, text):
    # 若尚未开始匹配，并且all_text满足check_re_1的模式，则开始匹配
    if not check and re.search(check_re_1, all_text):
        check = True
    if check:
        # 过滤页眉和页脚的文本内容
        if line_dict["type"] not in ["页眉", "页脚"]:
            # 若all_text满足check_re_2的模式，则停止匹配
            if not re.search(check_re_2, all_text):
                # 如果当前行有内容，则添加到text中
                if line_dict["inside"] != "":
                    text += line_dict["inside"] + "\n"
            else:
                check = False
    return text, check


def check_data(year, answer_dict, text_check, add_word, stop_re):
    text_list = text_check.split("\n")
    data = []
    check_len = 0
    for text in text_list:
        # 检查文本是否以“[项目”开始，但不包含“调整数”。
        if re.search("\['项目", text) and not re.search("调整数", text) and check_len == 0:
            check_len = len(eval(text))
        # 检查文本是否以“[”开始，也就是我们要处理的列表
        if re.search("^[\[]", text):
            try:
                text_l = eval(text)
                text_l[0] = text_l[0].replace(" ", "").replace("(", "（").replace(")", "）")
                text_l[0] = text_l[0].replace(":", "：").replace("／", "/")
                # 删除一些特定的前后缀，例如“一、”、“（一）”、“1.”和”加：“、”减：”、“其中：”或“（元/股）”。
                pattern = r"(?:[一二三四五六七八九十]、|（[一二三四五六七八九十]）|\d\.|加：|减：|其中：|（元/股）)"
                cut_re = re.match(pattern, text_l[0])
                if cut_re:
                    text_l[0] = text_l[0].replace(cut_re.group(), "")
                text_l[0] = text_l[0].split("（")[0]
                # 若当前行数据的长度与列名数据的长度相同，并且text_l[0]为汉字，则将其添加到data列表中
                if check_len != 0 and check_len == len(text_l) and re.search("[\u4e00-\u9fa5]", text_l[0]):
                    data.append(text_l)
            except Exception as e:
                print(f"Error parsing: {text}. Reason: {e}")
        # 如果文本与stop_re正则表达式匹配，意味着已经达到停止解析的条件。
        if data != [] and re.search(stop_re, text):
            break

    if data:
        data_df = pd.DataFrame(data[1:], columns=data[0])
        data_df.replace("", "无", inplace=True)  # 将空字符串替换为“无”
        if year + add_word in data_df.columns and "项目" in data_df.columns:
            data_df = data_df.drop_duplicates(subset="项目", keep="first")
            for key in answer_dict:
                try:
                    match_answer = data_df[data_df["项目"] == key]
                    if not match_answer.empty:
                        if answer_dict[key] == "":  # 如果answer_dict中的对应key的值为空，则更新它
                            answer_dict[key] = match_answer[year + add_word].values[0]
                except Exception as e:
                    print(f"Error match key: {key}. Reason: {e}")
    return answer_dict


def process_file(file_path):
    file_name = file_path.split("\\")[-1]
    publish_date, company_name, stock_code, short_name, year, _ = file_name.split("__")
    all_text = ""
    texts = [""] * 5
    checks = [False] * 5
    answer_dict = {key: "" for key in item_list}

    patterns = [
        ("(?:财务报表.{0,15}|1、)(?:合并资产负债表)$", "(?:母公司资产负债表)$"),
        ("(?:负责人.{0,15}|2、)(?:母公司资产负债表)$", "(?:合并利润表)$"),
        ("(?:负责人.{0,15}|3、)(?:合并利润表)$", "(?:母公司利润表)$"),
        ("(?:负责人.{0,15}|4、)(?:母公司利润表)$", "(?:合并现金流量表)$"),
        ("(?:负责人.{0,15}|5、)(?:合并现金流量表)$", "(?:母公司现金流量表)$")
    ]

    with open(file_path, "r", encoding="utf-8") as file:
        for line in file:
            line_dict = json.loads(line.strip())
            try:
                if line_dict["type"] not in ["页眉", "页脚"]:
                    all_text += line_dict["inside"]

                for i, (pattern1, pattern2) in enumerate(patterns):
                    texts[i], checks[i] = cut_all_text(checks[i], pattern1, pattern2, all_text, line_dict, texts[i])

                if re.search("(?:负责人.{0,15}|6、)(?:母公司现金流量表)$", all_text):
                    break
            except Exception as e:
                print(f"process line {line_dict} error: {e}")

    titles = ["合并资产负债表", "母公司资产负债表", "合并利润表", "母公司利润表", "合并现金流量表"]
    cuts = [text.split(title)[0] for text, title in zip(texts, titles)]
    answer_dict = check_data(year, answer_dict, texts[0][len(cuts[0]):], "12月31日", "母公司合并资产负债表")
    answer_dict = check_data(year, answer_dict, texts[2][len(cuts[2]):], "度", "母公司合并利润表")
    answer_dict = check_data(year, answer_dict, texts[4][len(cuts[4]):], "度", "母公司合并现金流量表")

    new_row = {
        "文件名": file_name, "发布日期": publish_date, "公司名称": company_name,
        "股票代码": stock_code, "股票简称": short_name, "报告年份": year,
        **{title: text[len(cut):] for text, cut, title in zip(texts, cuts, titles)},
        **answer_dict
    }
    print(f"process complete on file: {file_name}")
    return new_row


if __name__ == "__main__":
    # 文件夹路径
    folder_path = r"D:\Code\DataSet\chatglm_llm_fintech_raw_dataset\alltxt"
    # 获取文件夹内所有文件名称
    file_paths = glob.glob(folder_path + "/*")
    file_paths = sorted(file_paths, reverse=True)
    # 打印文件名称
    item_list = [
        "货币资金", "结算备付金", "拆出资金", "交易性金融资产", "以公允价值计量且其变动计入当期损益的金融资产",
        "衍生金融资产", "应收票据", "应收账款", "应收款项融资", "预付款项", "应收保费", "应收分保账款",
        "应收分保合同准备金", "其他应收款", "应收利息", "应收股利", "买入返售金融资产", "存货", "合同资产",
        "持有待售资产", "一年内到期的非流动资产", "其他流动资产", "流动资产合计", "发放贷款和垫款", "债权投资",
        "可供出售金融资产", "其他债权投资", "持有至到期投资", "长期应收款", "长期股权投资", "其他权益工具投资",
        "其他非流动金融资产", "投资性房地产", "固定资产", "在建工程", "生产性生物资产", "油气资产", "使用权资产",
        "无形资产", "开发支出", "商誉", "长期待摊费用", "递延所得税资产", "其他非流动资产", "非流动资产合计",
        "资产总计", "短期借款", "向中央银行借款", "拆入资金", "交易性金融负债",
        "以公允价值计量且其变动计入当期损益的金融负债", "衍生金融负债", "应付票据",
        "应付账款", "预收款项", "合同负债", "卖出回购金融资产款", "吸收存款及同业存放", "代理买卖证券款",
        "代理承销证券款", "应付职工薪酬", "应交税费", "其他应付款", "应付利息", "应付股利", "应付手续费及佣金",
        "应付分保账款", "持有待售负债", "一年内到期的非流动负债", "其他流动负债", "流动负债合计", "保险合同准备金",
        "长期借款", "应付债券", "租赁负债", "长期应付款", "长期应付职工薪酬", "预计负债", "递延收益", "递延所得税负债",
        "其他非流动负债", "非流动负债合计", "负债合计", "股本", "实收资本", "其他权益工具", "资本公积", "库存股",
        "其他综合收益", "专项储备", "盈余公积", "一般风险准备", "未分配利润", "归属于母公司所有者权益合计",
        "少数股东权益", "所有者权益合计", "负债和所有者权益总计", "营业总收入", "营业收入", "利息收入", "已赚保费",
        "手续费及佣金收入", "营业总成本", "营业成本", "利息支出", "手续费及佣金支出", "退保金", "赔付支出净额",
        "提取保险责任合同准备金净额", "保单红利支出", "分保费用", "税金及附加", "销售费用", "管理费用", "研发费用",
        "财务费用", "利息费用", "其他收益", "投资收益", "其中：对联营企业和合营企业的投资收益",
        "以摊余成本计量的金融资产终止确认收益", "汇兑收益", "净敞口套期收益", "公允价值变动收益", "信用减值损失",
        "资产减值损失", "资产处置收益", "营业利润", "营业外收入", "营业外支出", "利润总额", "所得税费用", "净利润",
        "按经营持续性分类", "持续经营净利润", "终止经营净利润", "按所有权归属分类", "归属于母公司所有者的净利润",
        "少数股东损益", "其他综合收益的税后净额", "归属母公司所有者的其他综合收益的税后净额",
        "不能重分类进损益的其他综合收益", "重新计量设定受益计划变动额", "权益法下不能转损益的其他综合收益",
        "其他权益工具投资公允价值变动", "企业自身信用风险公允价值变动", "其他", "将重分类进损益的其他综合收益",
        "权益法下可转损益的其他综合收益", "其他债权投资公允价值变动", "可供出售金融资产公允价值变动损益",
        "金融资产重分类计入其他综合收益的金额", "持有至到期投资重分类为可供出售金融资产损益",
        "其他债权投资信用减值准备", "现金流量套期储备", "外币财务报表折算差额", "其他",
        "归属于少数股东的其他综合收益的税后净额", "综合收益总额", "归属于母公司所有者的综合收益总额",
        "归属于少数股东的综合收益总额", "基本每股收益", "稀释每股收益", "销售商品、提供劳务收到的现金",
        "客户存款和同业存放款项净增加额", "向中央银行借款净增加额", "向其他金融机构拆入资金净增加额",
        "收到原保险合同保费取得的现金", "收到再保业务现金净额", "保户储金及投资款净增加额",
        "收取利息、手续费及佣金的现金", "拆入资金净增加额", "回购业务资金净增加额",
        "代理买卖证券收到的现金净额", "收到的税费返还", "收到其他与经营活动有关的现金", "经营活动现金流入小计",
        "购买商品、接受劳务支付的现金", "客户贷款及垫款净增加额", "存放中央银行和同业款项净增加额",
        "支付原保险合同赔付款项的现金", "拆出资金净增加额", "支付利息、手续费及佣金的现金", "支付保单红利的现金",
        "支付给职工以及为职工支付的现金", "支付的各项税费", "支付其他与经营活动有关的现金", "经营活动现金流出小计",
        "经营活动产生的现金流量净额", "收回投资收到的现金", "取得投资收益收到的现金",
        "处置固定资产、无形资产和其他长期资产收回的现金净额", "处置子公司及其他营业单位收到的现金净额",
        "收到其他与投资活动有关的现金", "投资活动现金流入小计", "购建固定资产、无形资产和其他长期资产支付的现金",
        "投资支付的现金", "质押贷款净增加额", "取得子公司及其他营业单位支付的现金净额", "支付其他与投资活动有关的现金",
        "投资活动现金流出小计", "投资活动产生的现金流量净额", "吸收投资收到的现金", "子公司吸收少数股东投资收到的现金",
        "取得借款收到的现金", "收到其他与筹资活动有关的现金", "筹资活动现金流入小计", "偿还债务支付的现金",
        "分配股利、利润或偿付利息支付的现金", "子公司支付给少数股东的股利、利润", "支付其他与筹资活动有关的现金",
        "筹资活动现金流出小计", "筹资活动产生的现金流量净额", "汇率变动对现金及现金等价物的影响",
        "现金及现金等价物净增加额", "期初现金及现金等价物余额", "期末现金及现金等价物余额"]

    with ThreadPoolExecutor(max_workers=32) as executor:
        results = list(executor.map(process_file, file_paths))

    df = pd.DataFrame(results)
    df.to_excel("2-company_financial.xlsx", index=False)

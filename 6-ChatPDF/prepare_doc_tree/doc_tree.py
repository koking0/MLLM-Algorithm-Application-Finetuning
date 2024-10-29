import json
import os
import re

from langchain.embeddings import HuggingFaceEmbeddings
from langchain.schema import Document
from langchain.vectorstores import FAISS

# 定义匹配模式和不需要的模式
patterns = [
    re.compile("目录"),
    re.compile("第[一二三四五六七八九十]+[章节]"),
    re.compile("[一二三四五六七八九十]+[、. ]"),
    re.compile("[（(][一二三四五六七八九十]+[)）][、. ]*"),
    re.compile("[1234567890]+[、. ]"),
    re.compile("[(（][1234567890]+[)）][、. ]*")
]

dirty_patterns = [
    re.compile("\d+/\d+"),
    re.compile("年度报告"),
    re.compile(".*?适用.*?不适用")
]

# 初始化词嵌入编码器
encoder = HuggingFaceEmbeddings(model_name="shibing624/text2vec-base-chinese")


# 一些实用函数
def strip_comma(string):
    """移除逗号"""
    return string.replace(",", "")


def is_number(string):
    """判断是否为数字"""
    return string in "1234567890" or re.fullmatch("-{0,1}[\d]+\.{0,1}[\d]+", strip_comma(string)) is not None


def preprocess_key(cell):
    """预处理键"""
    cell = re.sub("[（(].+[)）][、. ]{0,1}", "", cell)
    cell = re.sub("[\d一二三四五六七八九十]+[、. ]", "", cell)
    cell = re.sub("其中：|减：|加：|其中:|减:|加:|：|:", "", cell)
    return cell.strip()


def is_dirty_cell(txt, is_fin_table):
    """检查单元格是否为不需要的"""
    if txt == "":
        return True
    if is_fin_table:
        return not (is_number(txt) and abs(float(strip_comma(txt))) > 99)
    return False


def build_vector_store(lines):
    """构建向量存储"""
    store = FAISS.from_documents([Document(page_content=line, metadata={"id": id}) for id, line in enumerate(lines)],
                                 embedding=encoder)
    return store


def vector_search(docs, query, k=3):
    """进行向量搜索"""
    store = build_vector_store([str(i) for i in docs])
    searched = store.similarity_search_with_relevance_scores(query, k=k)
    return [(docs[i[0].metadata["id"]], i[1]) for i in searched]


class DocTreeNode:
    def __init__(self, content, parent=None, type_=-1, is_excel=False):
        """
        构造函数。

        :param content: 节点的内容。
        :param parent: 父节点。
        :param type_: 节点的类型。默认为-1，表示普通文本。
        :param is_excel: 该节点是否来自Excel表格。默认为False。
        """
        self.type_ = type_  # -1: 普通的文本内容，0、1、2、3分别为四级标题
        self.is_excel = is_excel
        self.content = content
        self.children = []
        self.parent = parent

    def __str__(self):
        """返回节点内容的字符串表示。"""
        return self.content

    def get_all_leaves(self, keyword, only_excel_node=True, include_node=True):
        """
        获取包含特定关键字的所有叶节点。

        :param keyword: 要查找的关键字。
        :param only_excel_node: 是否仅返回来自Excel的节点。
        :param include_node: 是否在结果中包含当前节点。
        :return: 包含关键字的叶节点列表。
        """
        leaves = []
        for child in self.children:
            if child.type_ == -1:
                leaves.append(child)
                continue

            if include_node:
                leaves.append(child)

            if keyword in str(child):
                leaves += child.get_all_leaves(keyword, only_excel_node=only_excel_node)
        if only_excel_node:
            leaves = [i for i in leaves if i.is_excel]
        return leaves

    def search_children(self, query):
        """
        在子节点中查找包含特定查询字符串的节点。

        :param query: 要查找的字符串。
        :return: 包含查询字符串的节点列表。
        """
        res = []
        for child in self.children:
            if child.type_ == -1:
                if len(re.findall("[^\u4e00-\u9fa5]" + query + "[^\u4e00-\u9fa5]", str(child))) > 0:
                    res.append(child)
            else:
                res += child.search_children(query)
        return res

    def vector_search_children(self, query, k=3):
        """
        使用向量搜索在所有子节点中查找与查询字符串最相关的节点。

        :param query: 要查找的字符串。
        :param k: 要返回的最相关节点的数量。
        :return: 最相关的节点及其相似度分数的列表。
        """
        all_children = self.get_all_leaves("", only_excel_node=False)
        return vector_search(all_children, query, k=k)


def my_group_by(iterable):
    """
    对iterable中的数据进行分组，分为"excel"和"text"两种类型。

    :param iterable: 输入的可迭代对象，其中的元素应为字典。
    :return: 一个生成器，每次产生一组数据的类型和对应的数据列表。
    """
    feature = "text"
    items = []

    for i in iterable:
        if i["type"] == "excel":
            if feature == "excel":
                items.append(i)
            else:
                yield feature, items
                items = [i]
                feature = "excel"
        else:
            if feature == "excel":
                yield feature, items
                items = [i]
                feature = "text"
            else:
                items.append(i)
    yield feature, items


def bs_generator(items, bs):
    """
    将items分成大小为bs的块，并产生每一个块。

    :param items: 要被分块的列表。
    :param bs: 块的大小。
    :return: 一个生成器，每次产生一个块。
    """
    for i in range(0, len(items), bs):
        yield items[i:i + bs]


def join_excel_data(raw_part, is_fin_table, bs=5):
    """
    将Excel中的数据处理成字典列表。

    :param raw_part: 输入的数据部分。
    :param is_fin_table: 标记是否为财务表格。
    :param bs: 块的大小。
    :return: 处理后的字典列表。
    """
    try:
        # 尝试解析JSON数据并去除无效的行
        part = [json.loads(i["inside"].replace("'", '"')) for i in raw_part]
        invalid_row_ids = [j for j in range(1, len(part) - 1) if all([m == "" for m in part[j]])]
        part = [row for i, row in enumerate(part) if i not in invalid_row_ids]

        if not part:
            return []

        all_dicts = []
        for rows in bs_generator(part, bs=bs):
            dic = {}
            for row in rows:
                row = [preprocess_key(row[0])] + [cell for cell in row[1:] if not is_dirty_cell(cell, is_fin_table)]
                if len(row) >= 2:
                    dic[row[0]] = row[1]
                else:
                    dic[row[0]] = ""
            all_dicts.append(json.dumps(dic, ensure_ascii=False))
        return all_dicts
    except json.decoder.JSONDecodeError as e:
        return []


def group_leave_nodes(leave_lines, is_fin_table):
    """
    根据给定的行数据分组叶节点。

    :param leave_lines: 叶节点数据行。
    :param is_fin_table: 标记是否为财务表格。
    :return: 处理后的文档和标记列表。
    """
    all_docs = []
    is_excels = []

    for key, part in my_group_by(leave_lines):
        if not part:
            continue

        if key == "excel":
            part_texts = join_excel_data(part, is_fin_table)
            all_docs += part_texts
            is_excels += [True] * len(part_texts)
        else:
            part_text = "\n".join([i["inside"] for i in part])
            all_docs.append(part_text)
            is_excels.append(False)
    return all_docs, is_excels


class DocTree:
    def __init__(self, txt_path):
        """
        初始化函数。

        :param txt_path: 文档的路径。
        """
        self.path = txt_path
        self.lines = self._read_file()
        self.json_lines = self._parse_json()
        self.root = DocTreeNode("@root", type_=-1)
        self.mid_nodes = []
        self.leaves = []
        self._build_tree()

    def _read_file(self):
        """
        读取文件内容并按行分割。

        :return: 文档的每一行组成的列表。
        """
        with open(self.path, encoding="utf-8") as f:
            return f.read().split("\n")

    def _parse_json(self):
        """
        从文档行中解析JSON数据。

        :return: 解析后的JSON数据列表。
        """
        return [json.loads(line) for line in self.lines if self._is_valid_json(line)]

    @staticmethod
    def _is_valid_json(line):
        """
        检查字符串是否为有效的JSON。

        :param line: 要检查的字符串。
        :return: 如果字符串是有效的JSON则返回True，否则返回False。
        """
        try:
            json.loads(line)
            return True
        except Exception:
            return False

    @staticmethod
    def _identify_pattern(text):
        """
        根据文本内容识别其模式（例如标题、子标题等）。

        :param text: 要识别的文本内容。
        :return: 模式标识符和匹配内容。
        """
        if is_number(text):
            return -2, ""

        for pat in dirty_patterns:
            if re.search(pat, text):
                return -2, re.search(pat, text).group(0)

        for i, pat in enumerate(patterns):
            match = re.search(pat, text)
            if match and (text.startswith(match.group(0)) or (i == 6 and text.endswith(match.group(0)))):
                return i, match.group(0)

        return -1, ""

    def _build_tree(self):
        """
        基于解析后的数据构建文档的树形结构。
        """
        current_parent = self.root
        leaf_nodes = []

        for line in self.json_lines:
            text = line.get("inside", "")
            type_ = line.get("type", -2)

            if type_ in ("页眉", "页脚") or not text:
                continue

            pattern, match = self._identify_pattern(text)
            if pattern == -2:
                continue

            if pattern == -1 or type_ == "excel":
                leaf_nodes.append(line)
            else:
                # 将叶节点添加到树中
                if leaf_nodes:
                    self._add_leaf_nodes(leaf_nodes, current_parent)
                    leaf_nodes.clear()

                # 添加新的标题节点
                current_parent = self._add_title_node(text, pattern, current_parent)

    def _add_leaf_nodes(self, leaf_nodes, parent):
        """
        将叶节点添加到文档树中。

        :param leaf_nodes: 要添加的叶节点列表。
        :param parent: 叶节点的父节点。
        """
        node_texts, is_excels = group_leave_nodes(leaf_nodes, parent.type_ == 6)
        for text, is_excel in zip(node_texts, is_excels):
            node = DocTreeNode(text, type_=-1, parent=parent, is_excel=is_excel)
            parent.children.append(node)
            self.leaves.append(node)

    def _add_title_node(self, text, pattern, parent):
        """
        根据识别的模式添加新的标题节点。

        :param text: 节点文本。
        :param pattern: 识别的模式。
        :param parent: 当前节点的父节点。
        :return: 新创建的节点。
        """
        while pattern <= parent.type_:
            parent = parent.parent

        node = DocTreeNode(text, type_=pattern, parent=parent)
        parent.children.append(node)
        self.mid_nodes.append(node)

        return node

    def vector_search_node(self, query, k=1):
        """
        使用向量搜索查询文档中的节点。

        :param query: 查询字符串。
        :param k: 返回的结果数量。
        :return: 搜索的结果。
        """
        return vector_search(self.mid_nodes, query, k=k)


def doc_tree_search(doc_tree, keyword, depth=3, max_length=3000):
    """
    使用文档树进行搜索，并返回包含特定关键字的节点及其子节点的内容。

    :param doc_tree: DocTree对象，包含文档的树形结构。
    :param keyword: 要查找的关键字。
    :param depth: 要查找的子节点深度，默认为0，只返回该节点。
    :param max_length: results的最大内容累加长度。
    :return: 包含关键字的节点及其子节点的内容列表。
    """
    nodes = doc_tree.vector_search_node(keyword)
    results = []
    current_length = [0]  # 使用列表包装以在递归函数中修改和检查

    def dfs_recursive(item, current_depth):
        node_str = str(item)
        current_length[0] += len(node_str)

        if max_length and current_length[0] > max_length:
            return

        results.append(node_str)
        if current_depth < depth:
            for child in item.children:
                dfs_recursive(child, current_depth + 1)

    for node, _ in nodes:
        dfs_recursive(node, 1)

    return results


if __name__ == "__main__":
    TXT_PATH = r"D:\Code\DataSet\chatglm_llm_fintech_raw_dataset\alltxt"
    file = "2020-02-29__上海汇通能源股份有限公司__600605__汇通能源__2019年__年度报告.txt"
    test_txt_file_path = os.path.join(TXT_PATH, file)
    dt = DocTree(test_txt_file_path)
    # 调用dt_search函数搜索答案
    answers = doc_tree_search(dt, "核心竞争力")
    for idx, ans in enumerate(answers):
        print(f"Answer {idx + 1}: {ans}")

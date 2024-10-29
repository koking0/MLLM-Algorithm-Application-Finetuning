# -*- coding: utf-8 -*-
# @Time        : 2023/7/19 18:04
# @File        : get_train_data.py
# @Description : None
# ----------------------------------------------
# ☆ ☆ ☆ ☆ ☆ ☆ ☆ 
# >>> Author    : Alex
# >>> Mail      : liu_zhao_feng_alex@163.com
# >>> Github    : https://github.com/koking0
# >>> Blog      : https://alex007.blog.csdn.net/
# ☆ ☆ ☆ ☆ ☆ ☆ ☆
import os
import json
import requests
from bs4 import BeautifulSoup

# 创建文件夹
data_dir = "./train_data"
if not os.path.exists(data_dir):
    os.makedirs(data_dir)

# 请求数码兽图鉴页面
url = "http://digimons.net/digimon/chn.html"
response = requests.get(url)
soup = BeautifulSoup(response.content, "html.parser")

# 遍历所有的 li 标签
digimon_list = soup.find("ul", id="digimon_list")
for digimon in digimon_list.find_all("li"):
    try:
        # 获取数码兽名称和详情页面链接
        name = digimon.find('a')["href"].split('/')[0]
        detail_url = "http://digimons.net/digimon/" + digimon.find('a')["href"]
        print(f"detail_url: {detail_url}")

        # 进入详情页面，获取数码兽介绍和图片链接
        response = requests.get(detail_url)
        soup = BeautifulSoup(response.content, "html.parser")
        caption = soup.find("div", class_="profile_eng").find('p').text.strip()
        img_url = f"http://digimons.net/digimon/{name}/{name}.jpg"

        # 保存图片
        img_data = requests.get(img_url).content
        file_name = f"{len(os.listdir(data_dir)) + 1:04d}.png"
        with open(os.path.join(data_dir, file_name), "wb") as f:
            f.write(img_data)

        # 将数据整理成指定的格式，并保存到对应的文件中
        metadata = {"file_name": file_name, "text": f"{name}. {caption}"}
        with open(os.path.join(data_dir, "metadata.jsonl"), 'a') as f:
            f.write(json.dumps(metadata) + '\n')
    except Exception as _:
        pass

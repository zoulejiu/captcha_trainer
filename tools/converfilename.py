import re
import os
import hashlib

# 训练集路径
root = r"D:\11"
all_files = os.listdir(root)

for file in all_files:
    old_path = os.path.join(root, file)

    # 已被修改过忽略
    if len(file.split(".")[0]) > 32:
        continue

    # 采用标注_文件md5码.图片后缀 进行命名
    with open(old_path, "rb") as f:
        _id = hashlib.md5(f.read()).hexdigest()
    new_path = os.path.join(root, file.replace(".", "_{}.".format(_id)))

    # 重复标签的时候会出现形如：abcd (1).jpg 这种形式的文件名
    new_path = re.sub(" \(\d+\)", "", new_path)
    print(new_path)
    os.rename(old_path, new_path)
import os
import json
image_dir = r"D:\TrainSet\train\label"
image_list = os.listdir(image_dir)

labels = set()
for img in image_list:
    split_result = img.split("_")
    if len(split_result) == 2:
        label, name = split_result
        if label:
            for word in label:
                labels.add(word)
    else:
        pass
print(labels)
print("共有标签{}种".format(len(labels)))
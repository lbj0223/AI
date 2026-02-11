import json
#写入json数据文件
user = {
    "name": "LBJ",
    "age": 18,
    "gender": "男",
    "hobbies": ["football", "basketball", "swimming"]
}
with open("resources/user.json", "w", encoding="utf-8") as f:
    #indent=4 缩进4个空格
    #ensure_ascii=False 保留中文
    json.dump(user, f, ensure_ascii=False,indent=4)

#读取json数据文件
with open("resources/user.json", "r", encoding="utf-8") as f:
    user = json.load(f)
    print(user)
    print(type( user))

#读文件
# 1.打开文件
# f=open("./resources/文件操作实验.txt","r",encoding="utf-8")
# 2.读取文件
# content=f.read()
# print(content)
# content_list=f.readlines()
# for line in content_list:
#     print(line.strip())
# 3.关闭文件
# f.close()



# #写文件
# # 1.打开文件
# f=open("./resources/文件操作实验.txt","w",encoding="utf-8")
#
# # 2.写入文件
# f.write("桃花潭水深千尺,\n")
# f.write("不及汪伦送我情。")
#
# # 3.关闭文件
# f.close()



#----------------------------------------------------------
#1.打开文件
with open("./resources/文件操作实验.txt","w",encoding="utf-8") as f:
    #2.写入文件
    f.write("桃花潭水深千尺,\n")
    f.write("不及汪伦送我情。")

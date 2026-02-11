import sys
from pix2tex.cli import LatexOCR
from PIL import Image


def run_tj_recognition(image_path):
    print(f"--- 题镜 AI：正在识别题目 ---")

    try:
        # 1. 初始化模型（第一次运行会自动下载模型权重文件，请保持网络通畅）
        model = LatexOCR()

        # 2. 加载你拍摄的图片
        img = Image.open(image_path)

        # 3. 执行识别：将图像转化为 LaTeX 代码
        # 这对应你申报书中提到的“结构化提取”核心步骤
        latex_result = model(img)

        print("\n[识别成功！]")
        print("LaTeX 代码如下：")
        print("-" * 30)
        print(latex_result)
        print("-" * 30)

        # 提示：你可以在 https://www.latexlive.com/ 粘贴这段代码查看渲染效果

    except Exception as e:
        print(f"发生错误：{e}")


if __name__ == "__main__":
    # 请确保你在项目文件夹下放了一张名为 'test_math.png' 的数学题图片
    run_tj_recognition('test_math.png')
import io
import json
import os
import re
from time import sleep

import requests
from lxml import etree, html
from PIL import Image
from protonmail import ProtonMail
from rapidocr import RapidOCR


class RetryException(Exception):
    pass


# 重试请求
def run_with_retry(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except RetryException:
        print("重试中... 等待5s后继续")
        sleep(5)
        return run_with_retry(func, *args, **kwargs)


# 打印html内容
def format_html(html_content: str):
    tree = html.fromstring(html_content)
    all_text = tree.text_content()
    clean_text = " ".join(all_text.split())
    return clean_text


# 识别验证码
def ocr_captcha(url: str):
    captcha_response = session.get(url)

    image = Image.open(io.BytesIO(captcha_response.content))
    # 放大图片，拉伸垂直以提高像素图片识别率
    # image = image.resize((image.width * 5, image.height * 6), Image.Resampling.NEAREST)

    # 使用OCR识别验证码
    captcha_output = engine(image)

    # 清理识别结果，只保留数字和字母，转换为小写
    captcha_text = "".join(c for c in captcha_output.txts if c.isalnum()).lower()

    return captcha_text


# 阻塞等待新邮件
def get_tk_code():
    print("等待新邮件...")
    new_message = proton.wait_for_new_message(
        interval=1, timeout=30, rise_timeout=True, read_message=True
    )
    # 主题应为 "MoeCode"
    if "MoeCode" not in new_message.subject:
        raise Exception("邮件主题不匹配")

    # 提取6位数字验证码 - Dear, Your moe code is xxxxxx .
    print(new_message.body)
    match = re.search(r"\d{6}", new_message.body)
    if not match:
        raise Exception("未找到6位数字验证码")

    tkcode = match.group(0)
    print(f"成功提取邮箱验证码：{tkcode}")
    return tkcode


# 提交预申请请求 + captcha
def pre_request(id: str):
    response = session.post(url, headers=headers)

    if response.status_code != 200 or response.text.find("停止申请") != -1:
        print(f"请求失败，状态码：{response.status_code}, {format_html(response.text)}")
        raise RetryException()

    tree = etree.HTML(response.text)
    captcha_img = tree.xpath('//img[@id="captcha_img"]/@src')[0]
    captcha_img_url = f"https://icp.gov.moe/{captcha_img[2:]}"  # 移除链接头部的 "./"

    print("请求首屏成功，准备解析验证码...")

    # 识别验证码

    captcha_text = ocr_captcha(captcha_img_url)  # "https://icp.gov.moe/captcha.php"
    print(f"识别到的验证码：{captcha_text}")

    # 提交预申请请求
    response = session.post(
        url,
        headers=headers,
        data={
            "NO1": id,
            "NO7": config["email_mail"],
            "authcode": captcha_text,
            "submit": "下一步",
        },
    )

    if response.status_code != 200 or response.text.find("停止申请") != -1:
        print(f"请求失败，状态码：{response.status_code}, {format_html(response.text)}")
        raise RetryException()

    print("站点初始信息提交成功")


# 提交站点详细信息 + 邮箱验证码
def site_info():
    try:
        tkcode = get_tk_code()
    except Exception as e:
        print(f"获取邮箱验证码失败：{e}")
        raise RetryException()

    # 提交站点详细信息
    response = session.post(
        url,
        headers=headers,
        data={
            "NO2": config["name"],
            "NO3": config["domain"],
            "NO4": config["homepage"],
            "NO5": config["description"],
            "NO6": config["owner"],
            "tkcode": tkcode,
            "submit": "确认无误！Go !",
        },
    )

    if response.status_code != 200 or response.text.find("停止申请") != -1:
        print(f"提交站点详细信息失败，状态码：{response.status_code}, {response.text}")
        raise RetryException()

    print("站点详细信息提交成功")


if __name__ == "__main__":
    print("本工具已启动")
    # 加载配置
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    moe_id = config["moe_number"]  # TODO: 多个 ID 抢取
    url = f"https://icp.gov.moe/join.php?id={moe_id}"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
        "Referrer": url,
    }

    print("初始化OCR和请求服务中...")
    session = requests.Session()
    engine = RapidOCR(params={})

    print("初始化邮箱服务中...")
    proton = ProtonMail()

    # 加载 Protonmail 会话
    if os.path.exists("session.pickle"):
        proton.load_session("session.pickle")
    else:
        proton.login(config["email_mail"], config["email_pass"])
        proton.save_session("session.pickle")

    print("登陆成功，初始化完成，准备抢id...")

    run_with_retry(pre_request, moe_id)
    run_with_retry(site_info)

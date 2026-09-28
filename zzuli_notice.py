import requests
from bs4 import BeautifulSoup
import json
import os

# ====================== 配置区 ======================
URLS = [
    {
        "name": "电子信息学院院内通知",
        "url": "http://dzxx.zzuli.edu.cn/p23451c5034/list.htm"
    },
    {
        "name": "研究生院招生通知",
        "url": "https://yjsc.zzuli.edu.cn/2878/list.psp"
    },
    {
        "name": "校级校长办通知公告",
        "url": "https://yuanban.zzuli.edu.cn/_t94/2734/list26.psp"
    },
    {
        "name": "教务处通知公告",
        "url": "https://jwc.zzuli.edu.cn/3160/list.htm"
    },
    {
        "name": "学生处通知公告",
        "url": "https://students.zzuli.edu.cn/2366/list.htm"
    }
]
# 从github secrets读取密钥，这里不用填写
SERVERCHAN_SENDKEY = os.getenv("SERVERCHAN_SENDKEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
RECORD_FILE = "history.json"
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
# ====================================================

def load_history():
    try:
        with open(RECORD_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_history(history):
    with open(RECORD_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def get_page_notice(url_info):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    resp = requests.get(url_info["url"], headers=headers, timeout=15)
    resp.encoding = "utf-8"
    soup = BeautifulSoup(resp.text, "html.parser")
    items = soup.select("li")
    res = []
    for item in items:
        a_tag = item.find("a")
        if not a_tag:
            continue
        title = a_tag.get_text(strip=True)
        link = a_tag.get("href")
        if not link or not title:
            continue
        # 拼接完整链接
        if link.startswith("/"):
            domain = url_info["url"].split("/",3)[0] + "//" + url_info["url"].split("/")[2]
            link = domain + link
        elif not link.startswith("http"):
            link = url_info["url"].rsplit("/",1)[0] + "/" + link
        res.append({"title": title, "link": link, "source": url_info["name"]})
    return res

def get_notice_detail(notice_url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    resp = requests.get(notice_url, headers=headers, timeout=15)
    resp.encoding = "utf-8"
    soup = BeautifulSoup(resp.text, "html.parser")
    # 提取正文，剔除导航栏
    body_text = soup.get_text(strip=True, separator=" ")
    # 限制长度，防止文本过长
    return body_text[:2500]

def ai_summary(content):
    if not DEEPSEEK_API_KEY:
        return "无DeepSeek密钥，无法生成摘要"
    prompt = """
你是校园通知摘要助手。阅读下面通知正文，生成80~120字摘要。
重点提取：截止时间、报名条件、材料要求、保研/考研/实验室招募相关信息。
只输出摘要，不要多余话。
"""
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": content}
        ],
        "temperature": 0.3
    }
    headers = {"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"}
    resp = requests.post(DEEPSEEK_URL, json=payload, headers=headers, timeout=30)
    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"摘要生成失败：{e}")
        return "摘要生成失败"

def send_wechat(title, content):
    if not SERVERCHAN_SENDKEY:
        print("无SendKey，跳过推送")
        return
    data = {"title": title, "desp": content}
    requests.post(f"https://sctapi.ftqq.com/{SERVERCHAN_SENDKEY}.send", data=data)

def main():
    history = load_history()
    new_notices = []
    for site in URLS:
        try:
            notices = get_page_notice(site)
        except Exception as e:
            print(f"【{site['name']}】抓取失败：{e}")
            continue
        for notice in notices:
            uid = notice["link"]
            if uid not in history:
                history[uid] = notice["title"]
                # 获取详情正文
                detail_text = get_notice_detail(notice["link"])
                notice["summary"] = ai_summary(detail_text)
                new_notices.append(notice)
    save_history(history)
    if len(new_notices) == 0:
        send_wechat("郑州轻工业大学通知监控", "【今日无新增校园通知】")
        return
    msg = ""
    for n in new_notices:
        msg += f"【{n['title']}】\n来源：{n['source']}\n摘要：{n['summary']}\n直达链接：{n['link']}\n\n"
    send_wechat("✅ 轻大新通知", msg)

if __name__ == "__main__":
    main()

"""
晚安成电自动提醒主脚本
用法:
  python3 main.py first   # 22:30 第一次提醒
  python3 main.py second  # 23:00 升级扫描
"""
import json
import smtplib
import ssl
import sys
import csv
import time
import os
from datetime import datetime, date
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from email.utils import formataddr
from pathlib import Path

import requests
import yaml

BASE_DIR = Path(__file__).parent
CFG = yaml.safe_load(open(BASE_DIR / "config.yaml", encoding="utf-8"))
COOKIE_FILE = BASE_DIR / "cookies.json"
DONE_FLAG = BASE_DIR / f"done_{date.today().isoformat()}.flag"

API = CFG["uestc"]["api_base"]
ADMIN = CFG["admin_email"]
TEST = CFG.get("test_mode", False)
THRESHOLD = CFG.get("no_checkin_threshold", 25)
MAIL_INTERVAL = 5  # 每封邮件间隔秒数，防限流


def load_session():
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    })
    with open(COOKIE_FILE, encoding="utf-8") as f:
        for c in json.load(f):
            s.cookies.set(c["name"], c["value"], domain=c["domain"], path=c.get("path", "/"))
    return s


def check_login(s):
    try:
        r = s.get(f"{API}/auth/user-info", timeout=10)
        return r.json().get("code") == 0
    except Exception as e:
        print(f"[!] 登录检查异常: {e}")
        return False


def fetch_missing(s):
    today = date.today().isoformat()
    r = s.get(f"{API}/class-cadre/my-classes", timeout=10)
    classes = r.json()["data"]
    class_key = classes[0]["classKey"]
    class_name = classes[0]["manageClass"]
    r = s.get(f"{API}/class-cadre/checkin-list",
              params={"businessDate": today, "classKey": class_key, "keyword": "",
                      "pageIndex": 1, "pageSize": 200}, timeout=10)
    data = r.json()["data"]
    # 按学号排序
    data.sort(key=lambda x: x.get("studentSn", ""))
    return data, class_name


def send_email(to_addr, subject, body, html=False, retries=3):
    smtp = CFG["smtp"]
    for attempt in range(retries):
        try:
            msg = MIMEMultipart()
            msg["From"] = formataddr((str(Header(smtp["sender_name"], "utf-8")), smtp["user"]))
            msg["To"] = to_addr
            msg["Subject"] = Header(subject, "utf-8")
            msg.attach(MIMEText(body, "html" if html else "plain", "utf-8"))
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(smtp["host"], smtp["port"], context=ctx, timeout=30) as server:
                server.login(smtp["user"], smtp["auth_code"])
                server.sendmail(smtp["user"], to_addr, msg.as_string())
            return True
        except Exception as e:
            print(f"    发信重试{attempt+1}: {e}")
            if attempt < retries - 1:
                time.sleep(10 * (attempt + 1))
            else:
                return False


def get_duty():
    roster = CFG["duty_roster"]
    if not roster:
        return None
    week = datetime.now().isocalendar()[1] + CFG.get("duty_offset", 0)
    return roster[week % len(roster)]


def load_email_map():
    m = {}
    path = BASE_DIR / "students.csv"
    if path.exists():
        with open(path, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                m[row["姓名"].strip()] = row["邮箱"].strip()
    return m


def missing_table(missing):
    rows = "".join(
        f"<tr><td>{i+1}</td><td>{stu['studentName']}</td><td>{stu['studentSn']}</td>"
        f"<td>{stu.get('dormitoryLocation','')}</td><td>{stu.get('studentPhone','')}</td></tr>"
        for i, stu in enumerate(missing)
    )
    return f"""<table border="1" cellpadding="6" cellspacing="0">
<tr><th>#</th><th>姓名</th><th>学号</th><th>宿舍</th><th>电话</th></tr>{rows}</table>"""


def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else "first"
    today = date.today().isoformat()
    stage_label = "22:30首次提醒" if stage == "first" else "23:00升级扫描"
    print(f"=== {today} {stage_label} ===")

    # 检查今天是否已经打满卡（first阶段打满后会写flag）
    if stage == "second" and DONE_FLAG.exists():
        print("[*] 22:30已全部打卡，跳过23:00扫描")
        return

    s = load_session()
    if not check_login(s):
        print("[!] cookie失效")
        send_email(ADMIN, f"【告警】{today} 晚安成电cookie已失效",
                   "脚本运行时检测到学工系统cookie过期，请重新导出cookie覆盖服务器cookies.json")
        sys.exit(1)

    try:
        missing, class_name = fetch_missing(s)
    except Exception as e:
        print(f"[!] 获取名单失败: {e}")
        send_email(ADMIN, f"【告警】{today} 获取未打卡名单失败",
                   f"获取名单时出错：{e}，请检查服务器网络或cookie状态")
        sys.exit(1)

    n = len(missing)
    print(f"[*] 班级{class_name}，未打卡{n}人")

    # === 全部已打卡 ===
    if n == 0:
        print("[✓] 今日全部已打卡")
        duty = get_duty()
        # 给管理员发日报
        send_email(ADMIN, f"【日报】{today} {stage_label}：全部已打卡",
                   f"<p>今日班级同学已全部完成晚安成电打卡。</p>"
                   f"<p>值班班委：{duty['name'] if duty else '无'}</p>"
                   f"<p>测试模式：{TEST}</p>", html=True)
        # 给值班班委发通知
        if duty:
            duty_to = ADMIN if TEST else duty["email"]
            send_email(duty_to, f"{today} 晚安成电：今日全部已打卡",
                       f"<p>今日班级同学已全部完成晚安成电打卡，无需联系。</p>", html=True)
        # first阶段打满了，写flag让second跳过
        if stage == "first":
            DONE_FLAG.touch()
            print("[*] 已写入完成标记，23:00将自动跳过")
        return

    # 阈值保护
    if n >= THRESHOLD:
        msg = f"今日未打卡{n}人（>={THRESHOLD}），判定为非打卡日，跳过同学提醒和班委通知。"
        print(f"[!] {msg}")
        send_email(ADMIN, f"【日报】{today} 非打卡日（{n}人未打卡）",
                   f"<p>{msg}</p><p>测试模式：{TEST}</p>", html=True)
        return

    email_map = load_email_map()
    duty = get_duty()
    results = []

    # === 1. 给未打卡同学发提醒 ===
    if stage == "first":
        subject_tpl = "晚安成电打卡提醒（{}）"
        body_tpl = """<p>Hi {name}~</p>
        <p>现在十点半啦，看了一下今天的晚安成电打卡情况，你还没打哦~</p>
        <p>打卡截止到 <b>23:30</b>，别忘啦，流程如下：</p>
        <p>微信搜「成电智慧学工」服务号 → 点进智慧学工小程序 → 晚安成电</p>
        <p>在宿舍的话直接点【在校打卡】就行</p>
        <p>不在宿舍的话记得选一下情况填个说明，辛苦啦~</p>
        <p>已经请假的同学忽略这条就好！打完早点休息 🌙</p>
        <p style="color:#888;font-size:12px;">此邮件由0915班自动打卡提醒脚本发送，不用回复~</p>"""
    else:
        subject_tpl = "最后提醒：晚安成电还没打卡（{}）"
        body_tpl = """<p>Hi {name}~</p>
        <p>现在十一点了，再过半小时（23:30）晚安成电就关闭了，你今天还没打卡噢。</p>
        <p>麻烦现在抽空打一下，不然会被辅导员点名的~</p>
        <p>微信搜「成电智慧学工」→ 智慧学工小程序 → 晚安成电。如有特殊情况记得填报。</p>
        <p>打完早点休息，晚安！</p>
        <p style="color:#888;font-size:12px;">此邮件由0915班自动打卡提醒脚本发送，不用回复~</p>"""

    for stu in missing:
        name = stu["studentName"]
        real_email = email_map.get(name)
        if not real_email:
            results.append((name, "无邮箱", False))
            continue
        if TEST:
            results.append((name, real_email, True))
            print(f"  [测试] {name} -> {real_email} (仅记录)")
            continue
        ok = send_email(real_email, subject_tpl.format(today), body_tpl.format(name=name), html=True)
        results.append((name, real_email, ok))
        print(f"  [{'✓' if ok else '✗'}] {name} -> {real_email}")
        time.sleep(MAIL_INTERVAL)

    success = sum(1 for _, _, ok in results if ok)

    # === 2. 给值班班委发邮件 ===
    if duty:
        duty_to = ADMIN if TEST else duty["email"]
        if stage == "first":
            duty_body = f"""<h2>晚安成电 {today} 22:30 已完成首轮提醒</h2>
            <p>值班班委：{duty['name']}</p>
            <p>今日未打卡 <b>{n}</b> 人，已全部发送提醒邮件。</p>
            <p>23:00将进行第二次扫描，届时把仍未打卡的完整名单发给你。</p>"""
            duty_subj = f"值班班委：{today} 22:30已提醒{n}人"
        else:
            duty_body = f"""<h2>晚安成电 {today} 23:00 未打卡名单</h2>
            <p>值班班委：{duty['name']}</p>
            <p>共 <b>{n}</b> 人仍未打卡，请电话联系；联系不上的请联系辅导员。</p>
            <p>二次提醒邮件已发送。</p>
            {missing_table(missing)}"""
            duty_subj = f"值班班委：{today} 23:00未打卡{n}人"
        ok = send_email(duty_to, duty_subj, duty_body, html=True)
        print(f"[{'✓' if ok else '✗'}] 班委邮件 -> {duty_to}")
        time.sleep(MAIL_INTERVAL)

    # === 3. 给管理员发日报 ===
    fail_list = "".join(f"<li>{n}: {e}</li>" for n, e, ok in results if not ok) or "<li>无</li>"
    admin_body = f"""<h2>晚安成电日报 {today}（{stage_label}）</h2>
    <ul>
      <li>未打卡人数：{n}</li>
      <li>同学提醒成功：{success}/{len(missing)}</li>
      <li>测试模式：{'是（同学邮件仅记录不发）' if TEST else '否'}</li>
      <li>值班班委：{duty['name'] if duty else '无'}</li>
    </ul>
    <h3>失败明细</h3><ul>{fail_list}</ul>
    <h3>未打卡名单</h3>{missing_table(missing)}"""
    send_email(ADMIN, f"【日报】{today} {stage_label}：{n}人未打卡，成功{success}封",
               admin_body, html=True)
    print(f"[✓] 日报已发管理员")
    print("=== 完成 ===")


if __name__ == "__main__":
    main()

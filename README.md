# 晚安成电自动提醒系统

> 电子科技大学"晚安成电"打卡自动提醒工具，帮班委解放双手。

## 这是什么

"晚安成电"是学校替代晚点名的每日打卡制度，班委每天需要：
1. 晚上10点半查一次未打卡名单
2. 挨个发消息提醒
3. 11点再查一次，把还没打的人名单整理出来打电话联系

这个脚本把上面三步全自动化了。部署在云服务器上，每晚自动跑，班委只需要收邮件就行。

## 功能

- **22:30 首轮提醒**：自动查未打卡名单，给每个同学发邮件提醒
- **23:00 二轮扫描**：再查一次，给还没打的人发最后提醒，把完整名单（含电话宿舍）发给值班班委
- **自动排班**：班委按周轮换，脚本自动算今天谁值班，邮件发给对应的人
- **管理员日报**：你自己每天收一封运行日报，确认系统正常
- **假期自动跳过**：如果某天超过25人没打卡，自动判定为非打卡日，不打扰任何人
- **cookie失效告警**：登录态过期时自动发邮件通知你重新导出

## 前置条件

1. **班委账号**：必须是班委（班级干部）权限，才能看到全班未打卡名单
2. **一台Linux服务器**：任何云服务器都行，不需要很高配置
3. **163邮箱**：用来发邮件（QQ邮箱在云服务器IP上会被限流，亲测）
4. **Python 3.8+**

## 快速开始

### 第一步：获取 cookies.json

学校学工系统有浏览器指纹校验，纯用账号密码模拟登录拿不到有效session，必须从已登录的浏览器导出cookie。

操作方法：
1. 在电脑Chrome浏览器打开 `https://jzsz.uestc.edu.cn/`
2. 用学号密码登录，完成手机验证码二次验证
3. 按F12打开开发者工具，切到Application标签
4. 导出 `jzsz.uestc.edu.cn` 和 `idas.uestc.edu.cn` 下的所有cookie
5. 保存为 `cookies.json`，格式：

```json
[
  {"name": "SESSION", "value": "xxx", "domain": "jzsz.uestc.edu.cn", "path": "/"},
  {"name": "MULTIFACTOR_BROWSER_FINGERPRINT", "value": "xxx", "domain": "idas.uestc.edu.cn", "path": "/"}
]
```

> 关键cookie是 `SESSION` 和 `MULTIFACTOR_BROWSER_FINGERPRINT`，少一个都不行。

### 第二步：配置

```bash
cp config.yaml.example config.yaml
cp students.csv.example students.csv
```

编辑 `config.yaml`：
- 填入你的163邮箱SMTP授权码
- 填入管理员邮箱（你自己）
- 配置班委排班名单
- `test_mode` 先设为 `true`

编辑 `students.csv`：填入全班同学姓名和QQ邮箱。

### 第三步：安装依赖

```bash
pip3 install requests pyyaml
```

### 第四步：测试运行

```bash
python3 main.py first
```

这时候是测试模式，不会真给同学发邮件，只会把"应该发的"记录在日志里，同时给你自己邮箱发一封日报确认效果。

检查收到的日报邮件，确认名单、格式都没问题后，把 `config.yaml` 里的 `test_mode` 改成 `false`。

### 第五步：配置定时任务

```bash
crontab -e
```

添加两行：
```
30 22 * * * cd /path/to/goodnight-uestc && /usr/bin/python3 main.py first >> cron.log 2>&1
0 23 * * * cd /path/to/goodnight-uestc && /usr/bin/python3 main.py second >> cron.log 2>&1
```

## 文件说明

| 文件 | 说明 |
|------|------|
| `main.py` | 主脚本，包含所有逻辑 |
| `config.yaml` | 你的私有配置（不上传Git） |
| `cookies.json` | 你的登录cookie（不上传Git） |
| `students.csv` | 全班名单（不上传Git） |

## 班委排班怎么配

在 `config.yaml` 里的 `duty_roster` 按轮换顺序列出所有班委：

```yaml
duty_offset: 0  # 调整这个数字让本周轮到正确的人
duty_roster:
  - name: "班委A"
    email: "a@qq.com"
  - name: "班委B"
    email: "b@qq.com"
```

`duty_offset` 是周数偏移量，调一次让本周值班的人对上就行，之后自动轮换。

## 邮件效果

给同学的提醒邮件语气比较口语化，不生硬：

> Hi 张三~
> 现在十点半啦，看了一下今天的晚安成电打卡情况，你还没打哦~
> 打卡截止到 23:30，别忘啦...

给值班班委的邮件包含完整未打卡名单表格（姓名、学号、宿舍、电话），方便打电话联系。

## 注意事项

- **服务器时区**必须是 `Asia/Shanghai`，用 `timedatectl` 确认
- **发邮件间隔5秒**，改太快会被SMTP服务器限流
- **cookie有效期约1年**，失效时脚本会自动发告警邮件，重新导出覆盖即可
- **不要在白天手动运行测试发信**，会打扰同学。测试时保持 `test_mode: true`

## 常见问题

**Q: 为什么用163邮箱不用QQ邮箱？**
A: 腾讯云服务器IP段发QQ邮箱SMTP会被限流（连接直接被拒），163邮箱对云服务器友好。

**Q: cookie多久失效？**
A: 约1年。失效时你会收到告警邮件，重新在浏览器登录导出就行。

**Q: 假期怎么办？**
A: 如果某天未打卡人数超过25人（班级大部分人都没打），脚本自动判定为非打卡日，不发任何邮件，只给你发个说明。

## 免责声明

本工具仅用于帮班委减轻重复性通知工作，**不代表对"晚安成电"打卡制度的立场或认可**。使用者应遵守学校相关规定，自行承担使用风险。脚本不对学校API做任何破解或攻击，只是正常调用已授权的班委接口。

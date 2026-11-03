# 晚安成电自动提醒系统

电子科技大学（UESTC）"晚安成电"打卡自动提醒脚本，部署在云服务器上每晚自动查询未打卡名单并发送邮件提醒。

## 功能

- 每晚 22:30 自动查询全班未打卡名单，发送提醒邮件
- 每晚 23:00 二次扫描，给仍未打卡的同学发最后提醒
- 自动按周轮换值班班委，每班班委收到未打卡名单
- 管理员（你自己）每天收到运行日报
- 非打卡日（假期/寒暑假）自动跳过
- cookie 失效自动告警

## 前置条件

1. **云服务器**（任何 Linux 服务器，推荐腾讯云）
2. **班委账号**（需要班委权限才能看到全班未打卡名单）
3. **163邮箱**（用于发信，QQ邮箱在腾讯云服务器上会被限流）

## 快速开始

### 1. 获取 cookies.json

学校学工系统有浏览器指纹校验，纯模拟登录拿不到有效 session。需要：

1. 在自己电脑浏览器登录 `https://jzsz.uestc.edu.cn/`
2. 完成手机验证码二次验证
3. 用 Chrome DevTools Protocol (CDP) 导出完整 cookie 集合
4. 保存为 `cookies.json` 放在项目目录

cookies.json 格式：
```json
[
  {"name": "SESSION", "value": "...", "domain": "jzsz.uestc.edu.cn", "path": "/"},
  {"name": "MULTIFACTOR_BROWSER_FINGERPRINT", "value": "...", "domain": "idas.uestc.edu.cn", "path": "/"}
]
```

### 2. 配置

```bash
cp config.yaml.example config.yaml
cp students.csv.example students.csv
```

编辑 `config.yaml` 填入你的邮箱、班委排班等信息。
编辑 `students.csv` 填入全班同学姓名和QQ邮箱。

### 3. 安装依赖

```bash
pip install requests pyyaml
```

### 4. 测试

```bash
# 先测试模式运行（不真发同学邮件）
python3 main.py first
```

确认日报收到、名单正确后，把 `config.yaml` 里 `test_mode` 改为 `false`。

### 5. 配置 cron

```bash
crontab -e
```

添加：
```
30 22 * * * cd /opt/goodnight-uestc && /usr/bin/python3 main.py first >> cron.log 2>&1
0 23 * * * cd /opt/goodnight-uestc && /usr/bin/python3 main.py second >> cron.log 2>&1
```

## 文件说明

| 文件 | 说明 |
|------|------|
| `main.py` | 主脚本 |
| `config.yaml` | 配置（不上传Git） |
| `cookies.json` | 学工系统cookie（不上传Git） |
| `students.csv` | 学生名单（不上传Git） |

## 注意事项

- cookies 有效期约1年，失效时脚本会发告警邮件
- 发邮件间隔5秒，避免被SMTP服务器限流
- 服务器时区必须是 `Asia/Shanghai`
- 不要在非打卡时段手动运行脚本测试发信

## License

MIT

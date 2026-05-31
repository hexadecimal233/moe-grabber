# 萌备自动化抢号工具

本工具会在指定时间执行萌备抢号任务。

支持的邮箱服务为 Proton Mail，到时候可能会加 IMAP 协议连接其他邮箱服务。

## 特性

- [x] 自动重试
- [x] 验证码识别和邮箱验证码获取
- [x] 遇到已经被抢则会试着抢下一个可用的萌备号

## Roadmap

- [ ] 更高精度的 OCR 模型
- [ ] 支持更多邮箱服务

## 运行

1. 安装依赖

```bash
uv sync
```

2. 配置 `config.json` 文件，填写相关信息（可参考 `config.json.example`）。

3. 运行脚本

```bash
uv run moe-grabber
```

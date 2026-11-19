# PSR Ask（LangBot Runner）

将现有 PSR ToB `POST /ask`（`protocol_version: tob-go-v1`）接入 LangBot。插件只做请求/结果转换与可信身份上下文传递；知识检索、问数执行与业务授权仍由查询服务完成。

## 兼容组合（本提交）

| 项 | 选定值 |
| --- | --- |
| 插件 | `PSRAsk` `0.1.0`（本目录） |
| 插件 SDK | `langbot-plugin>=0.7.4,<0.8`（开发验证时可用 0.7.x） |
| 后端合同 | ToB Go `/ask`，`tob-go-v1`；成功体为 `answer`+`citations`（知识）或 `result.columns/rows`（问数） |
| 认证 | `Authorization: Bearer <user-ticket>`；插件只按**环境变量名**取票据，值不进仓 |

目标 LangBot Core / Plugin Runtime 版本由交付环境安装时记录；本仓不绑定未验证的 Core 镜像 digest。

## 配置

Runner 配置字段：

- `ask-base-url`：服务根地址（不含 `/ask`）。可用环境变量 `QUERY_BOT_PSR_ASK_BASE_URL` 覆盖（交付侧）。
- `identity-ticket-env`：临时探测用的票据环境变量名（默认 `QUERY_BOT_PSR_USER_TICKET`）。**不是** B0 员工身份，也**不是**“一人粘贴、人人共用”的生产路径。
- `identity-map-file`：可选 JSON，将 Host `actor_id` 映射到票据环境变量名。正式按请求员工身份由交付侧身份合同定义。
- `timeout-seconds`：默认 120。

内部地址、真实身份映射与票据值只在交付环境维护。

## 本地合成测试

```bash
cd plugins/psr-ask
python -m pip install -r requirements.txt pytest pytest-asyncio
python -m pytest -q
```

测试仅使用 `examples/` 下的合成 JSON，不访问内网、不读取真实票据。

## 未覆盖

- 真实 Lark → 会话投递（交付仓 + BRE-291）
- 真实 `/ask` 业务答案（需能访问内网 ToB 的交付环境与有效用户票据）

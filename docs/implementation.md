# 兼容版本与接入步骤

本文是实现入口。公开仓只记录可公开的兼容约定与合成验证；内部地址、身份映射与真实运行证据在交付仓维护。

## 先核实三个边界

1. **宿主扩展接口**：核实选定 LangBot 版本的 Runner 或其他正式插件接口，采用对应版本示例。
2. **查询服务合同**：读取实际 PSR 的认证、请求、会话、答案、引用、错误与运行标识字段，不预设新协议。
3. **交付配置接口**：将应用、身份解析与后端配置保持可注入；公开示例使用合成值。

## 最小实现（PR1）

产品插件目录：`plugins/psr-ask/`（LangBot Runner，`usages: [agent]`）。

一次用户问题经 Runner 调用现有 ToB `POST /ask`，保留后端答案、引用/结果表与错误码语义；不由模型重写业务内容。

| 项目 | 本提交记录 |
| --- | --- |
| 插件 | `PSRAsk` `0.1.0`，路径 `plugins/psr-ask/` |
| 插件 SDK | `langbot-plugin>=0.7.4,<0.8`（见 `plugins/psr-ask/requirements.txt`） |
| PSR 合同（公开合成） | `protocol_version: tob-go-v1`；成功：`ok=true` + `answer`/`citations` 或 `result.columns`/`result.rows`；失败：`ok=false` + `code` |
| 身份 | Host `actor_id` → 票据**环境变量名**（可选 JSON 映射）；票据值不进仓 |
| 合成验证 | `plugins/psr-ask/tests/` + `examples/`；`python -m pytest -q`（在插件目录） |
| LangBot Core / Runtime | 交付安装时记录实际镜像/版本；本仓不绑定未验证 digest |
| 真实 `/ask` | 仅在可访问查询服务的交付主机验证；不在公开说明中写内部 URL |

## 有意义的验证

- 本地或组件验证：用合成请求核对身份上下文传递、答案/引用/错误转换及相关会话行为。
- 集成验收：在授权环境中由 Lark 发起真实查询，核对后端实际回执与正确会话回送。
- 公共产物只附可公开的验证摘要，原始业务证据留在交付环境。

相关官方文档：

- [Runner 说明](https://github.com/langbot-app/LangBot/blob/master/plugins/Runner/README.md)
- [插件独立构建与发布](https://github.com/langbot-app/LangBot/blob/master/plugins/RELEASING.md)
- [容器部署](https://langbot.app/docs/en/deploy/langbot/docker)

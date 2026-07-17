# xhs-cli

[xiaohongshu-cli](https://github.com/jackwener/xiaohongshu-cli) 这是逆向 API 出来的版本。
速度更加快更加稳定。但是风控上应该不如当前这个直接用浏览器操作真实。

**中文** | [English](README_EN.md)

[![PyPI](https://img.shields.io/pypi/v/xhs-cli)](https://pypi.org/project/xhs-cli/)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

小红书命令行工具 — 在终端中搜索笔记、查看主页、点赞、收藏、评论。

## 推荐项目

- [twitter-cli](https://github.com/jackwener/twitter-cli) - 在终端中操作 X/Twitter 的 CLI 工具
- [bilibili-cli](https://github.com/jackwener/bilibili-cli) - 哔哩哔哩 CLI 工具

## 功能

- **搜索** — 按关键词搜索笔记，Rich 表格展示
- **阅读** — 查看笔记内容、数据、评论
- **用户资料** — 查看用户信息、笔记、粉丝、关注
- **推荐 Feed** — 获取探索页推荐内容
- **话题** — 搜索话题标签
- **互动** — 点赞/取消、收藏/取消、评论、删除笔记
- **发布** — 发布图文笔记
- **认证** — 自动提取 Chrome cookie，或 browser-assisted 扫码登录（终端二维码渲染）
- **JSON 输出** — 所有数据命令支持 `--json`
- **Token 自动缓存** — `xsec_token` 搜索后自动缓存，后续命令免手动传

## 命令一览

| 分类 | 命令 | 说明 |
|------|------|------|
| Auth | `login`, `logout`, `status`, `whoami` | 登录、退出、状态检查、查看个人资料 |
| Read | `search`, `read`, `feed`, `topics` | 搜索笔记、阅读详情、推荐 Feed、搜索话题 |
| Users | `user`, `user-posts`, `followers`, `following` | 查看资料、列出笔记/粉丝/关注 |
| Engage | `like`, `unlike`, `comment`, `delete` | 点赞、取消点赞、评论、删除笔记 |
| Favorites | `favorite`, `unfavorite`, `favorites` | 收藏、取消收藏、查看收藏列表 |
| Post | `post` | 发布图文笔记 |

> 所有数据命令支持 `--json` 输出。`xsec_token` 自动缓存，无需手动传递。

## 安装

需要 Python 3.8+。

```bash
# 推荐：使用 uv
uv tool install xhs-cli

# 或使用 pipx
pipx install xhs-cli
```

<details>
<summary>从源码安装（开发用）</summary>

```bash
git clone git@github.com:jackwener/xhs-cli.git
cd xhs-cli
uv sync
```

</details>

## 本地一键冒烟测试

在本地已登录（有 `~/.xhs-cli/cookies.json`）的情况下，直接运行：

```bash
./scripts/smoke_local.sh
```

可选地传递 pytest 参数（例如只跑某个用例）：

```bash
./scripts/smoke_local.sh -k whoami
```

默认只跑无副作用命令（`integration and not live_mutation`）。如需额外验证
`like/favorite/comment/post/delete`，显式开启：

```bash
XHS_SMOKE_MUTATION=1 ./scripts/smoke_local.sh
```

可选环境变量：

```bash
XHS_SMOKE_COMMENT_TEXT="smoke test comment"
XHS_SMOKE_POST_IMAGES="/abs/a.jpg,/abs/b.jpg"
XHS_SMOKE_POST_TITLE="smoke title"
XHS_SMOKE_POST_CONTENT="smoke content"
```

## 使用

### 登录

```bash
# 自动从 Chrome 提取 cookie（推荐）
xhs login

# 强制使用二维码登录（用于排查登录问题）
xhs login --qrcode

# 手动提供 cookie 字符串（至少包含 a1 和 web_session）
xhs login --cookie "a1=xxx; web_session=yyy"

# 快速检查已保存的登录状态（不启动浏览器，不读取浏览器 cookie）
xhs status

# 查看个人资料
xhs whoami
xhs whoami --json

# 退出登录
xhs logout
```

### 搜索

```bash
xhs search "咖啡"
xhs search "咖啡" --json
```

### 阅读笔记

```bash
# 查看笔记（xsec_token 从缓存自动解析）
xhs read <note_id>

# 包含评论
xhs read <note_id> --comments

# 手动指定 xsec_token
xhs read <note_id> --xsec-token <token>
```

### 用户

```bash
# 查看用户资料（使用内部 user_id，非小红书号）
xhs user <user_id>

# 列出用户笔记
xhs user-posts <user_id>

# 粉丝 / 关注
xhs followers <user_id>
xhs following <user_id>
```

### 推荐 & 话题

```bash
xhs feed
xhs topics "旅行"
```

### 互动

```bash
# 点赞 / 取消（xsec_token 自动解析）
xhs like <note_id>
xhs like <note_id> --undo

# 收藏 / 取消
xhs favorite <note_id>
xhs favorite <note_id> --undo

# 评论
xhs comment <note_id> "好棒！"

# 删除自己的笔记
xhs delete <note_id>

# 查看收藏列表
xhs favorites
xhs favorites --max 10
```

### 发布笔记

```bash
xhs post "标题" --image photo1.jpg --image photo2.jpg --content "正文内容"
xhs post "标题" --image photo1.jpg --content "正文内容" --json
```

### 其他

```bash
xhs --version
xhs -v search "咖啡"   # 调试日志
xhs --help
```

## 架构

[... truncated: total 261 lines, first 200 kept; source: https://raw.githubusercontent.com/jackwener/xhs-cli/main/README.md; fetched_at 2026-07-17T18:42:31+08:00]

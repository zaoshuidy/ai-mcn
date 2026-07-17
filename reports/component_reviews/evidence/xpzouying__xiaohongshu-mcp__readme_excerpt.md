# xiaohongshu-mcp

<!-- ALL-CONTRIBUTORS-BADGE:START - Do not remove or modify this section -->
[![All Contributors](https://img.shields.io/badge/all_contributors-27-orange.svg?style=flat-square)](#contributors-)
<!-- ALL-CONTRIBUTORS-BADGE:END -->

[![善款已捐](https://img.shields.io/badge/善款已捐-CNY%201810.00-brightgreen?style=flat-square)](./DONATIONS.md)
[![爱心汇聚](https://img.shields.io/badge/爱心汇聚-CNY%201524.64-blue?style=flat-square)](./DONATIONS.md)
[![Docker Pulls](https://img.shields.io/docker/pulls/xpzouying/xiaohongshu-mcp?style=flat-square&logo=docker)](https://hub.docker.com/r/xpzouying/xiaohongshu-mcp)

MCP for 小红书 / xiaohongshu.com。让你的 AI 助手直接访问小红书数据。

### 🚀 快速开始：选择最适合你的版本

> [!IMPORTANT]
> #### 🔥 方案 A：Openclaw 深度集成 (推荐给开发者)
> - **Openclaw 太火啦 🔥🔥🔥 ，新增 Openclaw 支持，分为两种，请各位按需使用：**
> - [xiaohongshu-mcp-skills](https://github.com/autoclaw-cc/xiaohongshu-mcp-skills)（适用于已部署完本项目的用户）
> - [xiaohongshu-skills](https://github.com/autoclaw-cc/xiaohongshu-skills)（开箱即用版）

> [!TIP]
> #### ✨ 方案 B：x-mcp 浏览器插件版 (推荐给非技术同学 / 追求极简的用户)
> - **不想折腾 Docker 或部署环境？试试：[xpzouying/x-mcp](https://github.com/xpzouying/x-mcp)**
> - **零配置**：安装插件即用，无需任何代码、代理或复杂的环境配置。
> - **安全稳定**：直接在常用浏览器 (Chrome/Edge) 及本地网络运行，无服务器 IP 风险，且能解决 90% 的部署报错。

### 📖 相关资源

- **我的博客文章**：[haha.ai/xiaohongshu-mcp](https://www.haha.ai/xiaohongshu-mcp)
- **贡献指南**：[Contributing Guide](./CONTRIBUTING.md)

### 🛠️ 疑难杂症

如果您在部署传统 Docker 版本时遇到问题，**务必先查看：[各种疑难杂症 (Issues #56)](https://github.com/xpzouying/xiaohongshu-mcp/issues/56)**。

> *提示：如果环境排查太耗时，切换到 [x-mcp 插件版](https://github.com/xpzouying/x-mcp) 通常是更高效的选择。*

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=xpzouying/xiaohongshu-mcp&type=Timeline)](https://www.star-history.com/#xpzouying/xiaohongshu-mcp&Timeline)

## 赞赏支持

本项目所有的赞赏都会用于慈善捐赠。所有的慈善捐赠记录，请参考 [DONATIONS.md](./DONATIONS.md)。

**捐赠时，请备注 MCP 以及名字。**
如需更正/撤回署名，请开 Issue 或通过邮箱联系。

**支付宝（不展示二维码）：**

通过支付宝向 **xpzouying@gmail.com** 赞赏。

**微信：**

<img src="donate/wechat@2x.png" alt="WeChat Pay QR" width="260" />

## 项目简介

**主要功能**

> 💡 **提示：** 点击下方功能标题可展开查看视频演示

<details>
<summary><b>1. 登录和检查登录状态</b></summary>

第一步必须，小红书需要进行登录。可以检查当前登录状态。

**登录演示：**

https://github.com/user-attachments/assets/8b05eb42-d437-41b7-9235-e2143f19e8b7

**检查登录状态演示：**

https://github.com/user-attachments/assets/bd9a9a4a-58cb-4421-b8f3-015f703ce1f9

</details>

<details>
<summary><b>2. 发布图文内容</b></summary>

支持发布图文内容到小红书，包括标题、内容描述和图片。

**图片支持方式：**

支持两种图片输入方式：

1. **HTTP/HTTPS 图片链接**

   ```
   ["https://example.com/image1.jpg", "https://example.com/image2.png"]
   ```

2. **本地图片绝对路径**（推荐）
   ```
   ["/Users/username/Pictures/image1.jpg", "/home/user/images/image2.png"]
   ```

**为什么推荐使用本地路径：**

- ✅ 稳定性更好，不依赖网络
- ✅ 上传速度更快
- ✅ 避免图片链接失效问题
- ✅ 支持更多图片格式

**发布图文帖子演示：**

https://github.com/user-attachments/assets/8aee0814-eb96-40af-b871-e66e6bbb6b06

</details>

<details>
<summary><b>3. 发布视频内容</b></summary>

支持发布视频内容到小红书，包括标题、内容描述和本地视频文件。

**视频支持方式：**

仅支持本地视频文件绝对路径：

```
"/Users/username/Videos/video.mp4"
```

**功能特点：**

- ✅ 支持本地视频文件上传
- ✅ 自动处理视频格式转换
- ✅ 支持标题、内容描述和标签
- ✅ 等待视频处理完成后自动发布

**注意事项：**

- 仅支持本地视频文件，不支持 HTTP 链接
- 视频处理时间较长，请耐心等待
- 建议视频文件大小不超过 1GB

</details>

<details>
<summary><b>4. 搜索内容</b></summary>

根据关键词搜索小红书内容。

**搜索帖子演示：**

https://github.com/user-attachments/assets/03c5077d-6160-4b18-b629-2e40933a1fd3

</details>

<details>
<summary><b>5. 获取推荐列表</b></summary>

获取小红书首页推荐内容列表。

**获取推荐列表演示：**

https://github.com/user-attachments/assets/110fc15d-46f2-4cca-bdad-9de5b5b8cc28

</details>

<details>
<summary><b>6. 获取帖子详情（包括互动数据和评论）</b></summary>

获取小红书帖子的完整详情，包括：

- 帖子内容（标题、描述、图片等）
- 用户信息
- 互动数据（点赞、收藏、分享、评论数）
- 评论列表及子评论

**⚠️ 重要提示：**

- 需要提供帖子 ID 和 xsec_token（两个参数缺一不可）
- 这两个参数可以从 Feed 列表或搜索结果中获取
- 必须先登录才能使用此功能

**获取帖子详情演示：**

https://github.com/user-attachments/assets/76a26130-a216-4371-a6b3-937b8fda092a

</details>

<details>
<summary><b>7. 发表评论到帖子</b></summary>

支持自动发表评论到小红书帖子。

**功能说明：**

- 自动定位评论输入框
- 输入评论内容并发布
- 支持 HTTP API 和 MCP 工具调用

**⚠️ 重要提示：**

- 需要先登录才能使用此功能
- 需要提供帖子 ID、xsec_token 和评论内容
- 这些参数可以从 Feed 列表或搜索结果中获取

**发表评论演示：**

[... truncated: total 1079 lines, first 200 kept; source: https://raw.githubusercontent.com/xpzouying/xiaohongshu-mcp/main/README.md; fetched_at 2026-07-17T18:42:20+08:00]

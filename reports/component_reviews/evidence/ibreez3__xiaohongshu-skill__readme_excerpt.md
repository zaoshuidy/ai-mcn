# Xiaohongshu Auto-Publish Skill

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Claude Code Skill](https://img.shields.io/badge/Claude%20Code-Skill-blue)](https://claude.ai/)

> **🎯 现在支持 OpenClaw！** 使用 HTTP API 适配器在 OpenClaw 中实现小红书自动化。详见 [OpenClaw 快速开始](QUICKSTART_OPENCRAW.md)。

A powerful plugin for automating content publishing to Xiaohongshu (Little Red Book) via the [xiaohongshu-mcp](https://github.com/xpzouying/xiaohongshu-mcp) server.

## Features

- Publish image/text content to Xiaohongshu
- Publish video content to Xiaohongshu
- Check login status and get QR code
- Search for content on Xiaohongshu
- Get detailed information about feeds
- Post comments to feeds
- List feeds from homepage
- Like and favorite feeds
- Get user profile information

## Requirements

### MCP Server
- [xiaohongshu-mcp](https://github.com/xpzouying/xiaohongshu-mcp) server running locally or remotely
- Node.js 18+ (for running the publish scripts)

### MCP Client (Choose One)

#### ✅ Compatible Clients
- **[Cursor](https://cursor.sh/)** (Recommended) - Full MCP support with SSE transport
- **[Claude Code](https://claude.ai/code)** - Official CLI with MCP support
- **[Cline](https://cline.dev/)** - AI assistant with MCP integration
- **[VSCode](https://code.visualstudio.com/)** - With MCP extension

#### ❌ Incompatible
- **OpenClaw** - Does not support SSE MCP transport (see [OPENCRAW_MCP_ISSUE.md](OPENCRAW_MCP_ISSUE.md) for details)

### Why OpenClaw Doesn't Work

xiaohongshu-mcp uses **SSE (Server-Sent Events)** for MCP transport, which requires:
1. Persistent HTTP connections
2. Server-to-client event streaming
3. Session state management

OpenClaw's Skill system uses simple function calls and cannot maintain SSE connections.

**Solution**: Use Cursor, Claude Code, or other MCP-compatible clients instead.

## Quick Start

### For OpenClaw Users (NEW!)

> **✨ 现在支持 OpenClaw！** 通过 HTTP API 适配器实现小红书自动化

**三步快速开始：**

1. **启动 xiaohongshu-mcp**:
   ```bash
   cd /path/to/xiaohongshu-mcp && npm start
   ```

2. **安装适配器**:
   ```bash
   ./install-adapter.sh
   ```

3. **重启 OpenClaw 并开始使用**:
   ```
   /check-login      # 检查登录状态
   /publish "标题" "内容" ["/path/img.jpg"] ["标签"]
   ```

📖 **完整指南**: [OpenClaw 使用指南](OPENCRAW_GUIDE.md) | [快速开始](QUICKSTART_OPENCRAW.md)

---

### For Standard MCP Clients

### Using Cursor (Recommended)

1. **Install Cursor**: https://cursor.sh/

2. **Create MCP config** (`.cursor/mcp.json`):
   ```json
   {
     "mcpServers": {
       "xiaohongshu-mcp": {
         "url": "http://localhost:18060/mcp",
         "description": "小红书 MCP 服务"
       }
     }
   }
   ```

3. **Start xiaohongshu-mcp**:
   ```bash
   cd /path/to/xiaohongshu-mcp
   npm start
   ```

4. **Restart Cursor** and start publishing!

### Using Claude Code CLI

```bash
# Add MCP server
claude mcp add --transport http xiaohongshu-mcp http://localhost:18060/mcp

# Verify connection
claude mcp list
```

### Using MCP Inspector (for testing)

```bash
npx @modelcontextprotocol/inspector
# Open browser and connect to: http://localhost:18060/mcp
```

---

## Prerequisites

Before using this skill, you need to deploy and run the [xiaohongshu-mcp](https://github.com/xpzouying/xiaohongshu-mcp) server:

1. Clone the xiaohongshu-mcp repository:
   ```bash
   git clone https://github.com/xpzouying/xiaohongshu-mcp.git
   cd xiaohongshu-mcp
   ```

2. Install dependencies and start the server:
   ```bash
   npm install
   npm start
   ```

3. By default, the MCP server will run on `http://127.0.0.1:18060/mcp`

This Skill depends on the xiaohongshu-mcp server for all operations. Special thanks to [xpzouying](https://github.com/xpzouying) for developing the xiaohongshu-mcp project, which made this Skill possible.

## Installation

### For OpenClaw

#### Quick Install (Recommended)

Run the installation script:

```bash
./install.sh
```

The script will:
- Check if OpenClaw is installed
- Verify xiaohongshu-mcp server status
- Copy files to OpenClaw skills directory
- Set proper permissions
- Verify the installation

Then:

1. Start xiaohongshu-mcp server (if not running):
   ```bash
   cd /path/to/xiaohongshu-mcp
   npm start
   ```

2. Restart OpenClaw:
   ```bash
   openclaw restart
   # or completely quit and reopen OpenClaw
   ```

3. Test the installation:
   ```bash
   node test-mcp-client.js
   ```

#### Manual Install

```bash
# Create installation directory
mkdir -p ~/.openclaw/skills/xiaohongshu-auto-publish

# Copy files
cp index.js ~/.openclaw/skills/xiaohongshu-auto-publish/
cp openclaw.plugin.json ~/.openclaw/skills/xiaohongshu-auto-publish/
cp -r commands ~/.openclaw/skills/xiaohongshu-auto-publish/
cp -r skills ~/.openclaw/skills/xiaohongshu-auto-publish/

# Set permissions
chmod +x ~/.openclaw/skills/xiaohongshu-auto-publish/index.js
```

For detailed installation instructions, see [INSTALL.md](INSTALL.md).

### Uninstall


[... truncated: total 424 lines, first 200 kept; source: https://raw.githubusercontent.com/ibreez3/xiaohongshu-skill/main/README.md; fetched_at 2026-07-17T18:42:41+08:00]

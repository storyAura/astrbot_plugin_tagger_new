# AstrBot 图像标签识别插件（新版）

> 本项目 Fork 自 [yudengghost/astrbot_plugin_tagger](https://github.com/yudengghost/astrbot_plugin_tagger)，在原版基础上进行了多项功能增强和改进。

## 简介
这是一个基于AstrBot的图像标签识别插件，可以帮助你识别图片并生成AI绘画标签。插件使用了SmilingWolf开发的wd-tagger模型，能够准确识别图像中的各种元素。

## 相比原版的改进

### 🎛️ 可配置模型与阈值
- **原版**：模型（`wd-swinv2-tagger-v3`）和阈值（通用 0.35 / 角色 0.85）均为硬编码，无法修改
- **新版**：新增 `_conf_schema.json` 配置文件，支持在 AstrBot 管理面板中直接配置：
  - **模型选择**：支持 12 种模型可选（包括 `wd-eva02-large-tagger-v3`、`wd-swinv2-tagger-v3`、`wd-vit-tagger-v3` 等模型）
  - **通用标签阈值（general_threshold）**：可自定义通用标签的识别灵敏度
  - **角色识别阈值（character_threshold）**：可自定义角色识别的灵敏度

### 👥 多用户并发支持
- **原版**：同一时间只能处理一个用户的请求，多人同时使用会互相覆盖
- **新版**：按用户ID独立管理等待状态，支持多个用户同时使用，互不干扰

### 💬 引用图片识别
- **原版**：仅支持发送 `/tag` 后再发送图片
- **新版**：新增引用消息图片提取功能，支持直接引用一张包含图片的消息并发送 `/tag` 命令即可识别，无需重新发送图片

### 📎 命令与图片同时发送
- **原版**：必须先发送 `/tag` 命令，等待提示后再发送图片（两步操作）
- **新版**：支持在发送 `/tag` 命令时同时附带图片，一步完成识别

## 如何使用
1. 发送 `/tag` 命令后在60秒内发送图片
2. 或引用一张图片并发送 `/tag` 命令
3. 或发送 `/tag` 命令的同时附带图片
4. 机器人会返回识别出的标签列表

## 安装说明
1. 下载插件并解压
2. 将插件文件夹放入AstrBot的plugins目录
3. 重启机器人即可使用

## 环境要求
- AstrBot v0.1.5.4或更高版本
- Python 3.7+
- aiohttp库（用于网络请求）

## 关于作者
- 作者：storyAura（Fork自 [yudengghost](https://github.com/yudengghost/astrbot_plugin_tagger)）
- 项目地址：https://github.com/storyAura/astrbot_plugin_tagger_new
- 原始项目：https://github.com/yudengghost/astrbot_plugin_tagger
- 问题反馈：如有问题请在GitHub提交issue

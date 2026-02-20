from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.core.message.components import Image, Reply
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
import time
import re
from typing import Optional
import aiohttp
import json
import ssl

API_URL = "https://smilingwolf-wd-tagger.hf.space/gradio_api"

@register("tagger_new", "storyAura", "一个用于识别图像tag标签的插件", "1.0.0", "https://github.com/storyAura/astrbot_plugin_tagger_new")
class MyPlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.waiting_users = {}  # {user_id: {'start_time': float}}
        self.config = config
        self.model_name = config.get("model_name", "SmilingWolf/wd-eva02-large-tagger-v3")
        self.general_threshold = config.get("general_threshold", 0.35)
        self.character_threshold = config.get("character_threshold", 0.85)
    
    # 获取图片数据
    async def get_image_data(self, event: AstrMessageEvent, file_id: str) -> bytes:
        """从协议端API获取图片数据"""
        try:
            # 调用协议端API
            if event.get_platform_name() != "aiocqhttp":
                raise Exception("当前只支持QQ平台")
                
            assert isinstance(event, AiocqhttpMessageEvent)
            client = event.bot
            
            # 准备请求参数
            payloads = {
                "file_id": file_id
            }
            
            print(f"[调试信息] 开始获取图片数据...")
            print(f"[调试信息] 请求参数: {payloads}")
            
            # 调用协议端API
            result = await client.api.call_action('get_image', **payloads)
            print(f"[调试信息] API返回结果: {result}")
            
            if not isinstance(result, dict):
                raise Exception("API返回格式错误")
            
            file_error = None
            url_error = None
            
            # 先尝试从文件读取
            file_path = result.get('file')
            if file_path:
                print(f"[调试信息] 尝试从文件读取: {file_path}")
                try:
                    with open(file_path, 'rb') as f:
                        data = f.read()
                        print(f"[调试信息] 文件读取成功，数据大小: {len(data)} 字节")
                        return data
                except Exception as e:
                    file_error = str(e)
                    print(f"[调试信息] 文件读取失败: {file_error}")
            
            # 如果文件读取失败，尝试从URL下载
            url = result.get('url')
            if url:
                print(f"[调试信息] 尝试从URL下载: {url}")
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url) as response:
                            print(f"[调试信息] URL响应状态码: {response.status}")
                            if response.status == 200:
                                data = await response.read()
                                print(f"[调试信息] URL下载成功，数据大小: {len(data)} 字节")
                                return data
                            else:
                                url_error = f"HTTP状态码: {response.status}"
                                print(f"[调试信息] URL下载失败: {url_error}")
                except Exception as e:
                    url_error = str(e)
                    print(f"[调试信息] URL下载出错: {url_error}")
            
            # 如果两种方式都失败了，抛出详细错误信息
            error_msg = []
            if file_path and file_error:
                error_msg.append(f"文件读取失败: {file_error}")
            if url and url_error:
                error_msg.append(f"URL下载失败: {url_error}")
            if not error_msg:
                error_msg.append("未找到可用的图片来源")
                
            raise Exception(" | ".join(error_msg))
            
        except Exception as e:
            raise Exception(f"获取图片数据失败: {str(e)}")
    
    # 上传图片
    async def upload_image(self, session: aiohttp.ClientSession, image_bytes: bytes) -> str:
        """上传图片到API服务器"""
        try:
            # 准备文件数据
            form = aiohttp.FormData()
            form.add_field('files', image_bytes, filename='image.png')
            
            # 上传图片
            async with session.post(f"{API_URL}/upload", data=form) as response:
                if response.status != 200:
                    raise Exception(f"上传失败: HTTP {response.status}")
                    
                result = await response.json()
                return result[0]  # 返回图片的相对路径
                
        except Exception as e:
            raise Exception(f"上传图片失败: {str(e)}")
    
    # 调用 /predict 命名端点
    async def call_predict(self, session: aiohttp.ClientSession, image_path: str) -> str:
        """通过 Gradio 命名端点 /predict 提交分析请求并获取结果"""
        try:
            # 准备请求数据
            payload = {
                "data": [
                    {
                        "path": image_path,
                        "url": f"{API_URL}/file={image_path}",
                        "size": None,
                        "mime_type": ""
                    },
                    self.model_name,
                    self.general_threshold,
                    False,
                    self.character_threshold,
                    False
                ]
            }
            
            # 1. 提交预测请求，获取 event_id
            async with session.post(f"{API_URL}/call/predict", json=payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"提交预测请求失败: HTTP {response.status}, {error_text}")
                result = await response.json()
                event_id = result.get("event_id")
                if not event_id:
                    raise Exception(f"未获取到 event_id: {result}")
            
            # 2. 通过 event_id 获取 SSE 流式结果
            async with session.get(f"{API_URL}/call/predict/{event_id}") as response:
                if response.status != 200:
                    raise Exception(f"获取结果失败: HTTP {response.status}")
                
                async for line in response.content:
                    line = line.decode('utf-8').strip()
                    if not line:
                        continue
                    
                    # SSE 格式：先是 "event: xxx" 行，然后是 "data: xxx" 行
                    if line.startswith('data: '):
                        raw_data = line[6:]  # 跳过 'data: ' 前缀
                        try:
                            result_data = json.loads(raw_data)
                        except json.JSONDecodeError:
                            continue
                        
                        # result_data 是一个数组: [tags_str, rating_label, character_label, tags_label]
                        if isinstance(result_data, list) and len(result_data) >= 3:
                            general_tags = result_data[0]  # 标签字符串
                            character_info = result_data[2]  # 角色信息
                            
                            # 构建结果字符串
                            result = []
                            result.append(f"标签：\n{general_tags}")
                            
                            # 添加角色信息（如果有）
                            if isinstance(character_info, dict) and character_info.get('confidences'):
                                character_lines = ["角色："]
                                characters = sorted(
                                    character_info['confidences'],
                                    key=lambda x: x['confidence'],
                                    reverse=True
                                )
                                for char in characters:
                                    if char['confidence'] > 0.5:
                                        character_lines.append(
                                            f"{char['label']} ({char['confidence']*100:.1f}%)"
                                        )
                                if len(character_lines) > 1:
                                    result.append("\n".join(character_lines))
                            
                            return "\n".join(result)
            
            return "❌ 未收到有效的分析结果"
            
        except Exception as e:
            raise Exception(f"调用预测端点失败: {str(e)}")
    
    # 分析图片
    async def analyze_image(self, image_bytes: bytes) -> str:
        """使用API分析图片标签"""
        try:
            # 创建不验证SSL的客户端
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            connector = aiohttp.TCPConnector(ssl=ssl_context)
            async with aiohttp.ClientSession(connector=connector) as session:
                # 1. 上传图片
                image_path = await self.upload_image(session, image_bytes)
                
                # 2. 调用 /predict 端点并获取结果
                return await self.call_predict(session, image_path)
                
        except Exception as e:
            return f"❌ 调用API时出错：{str(e)}"
    
    async def get_image_from_reply(self, event: AstrMessageEvent) -> Optional[str]:
        """从引用的消息中提取图片file_id，如果没有则返回None"""
        try:
            messages = event.get_messages()
            reply = next((msg for msg in messages if isinstance(msg, Reply)), None)
            if not reply:
                return None
            
            # 获取被引用消息的ID
            reply_msg_id = reply.id
            if not reply_msg_id:
                return None
            
            # 通过OneBot API获取被引用消息的内容
            if event.get_platform_name() != "aiocqhttp":
                return None
            
            assert isinstance(event, AiocqhttpMessageEvent)
            client = event.bot
            
            result = await client.api.call_action('get_msg', message_id=int(reply_msg_id))
            print(f"[调试信息] get_msg 返回: {result}")
            
            if not isinstance(result, dict):
                return None
            
            # 从返回的消息中提取图片
            msg_content = result.get('message', [])
            
            # 消息可能是数组格式（消息段列表）
            if isinstance(msg_content, list):
                for seg in msg_content:
                    if isinstance(seg, dict) and seg.get('type') == 'image':
                        data = seg.get('data', {})
                        file_id = data.get('file')
                        if file_id:
                            return file_id
            
            # 消息可能是字符串格式（CQ码）
            elif isinstance(msg_content, str):
                match = re.search(r'\[CQ:image,file=([^,\]]+)', msg_content)
                if match:
                    return match.group(1)
            
            return None
        except Exception as e:
            print(f"[调试信息] 从引用消息获取图片失败: {e}")
            return None
    
    async def process_image(self, event: AstrMessageEvent, file_id: str):
        """处理图片：获取数据、分析、返回结果"""
        try:
            yield (event.make_result()
                  .message("✅ 已收到图片")
                  .message("\n正在分析中..."))
            
            # 从协议端API获取图片数据
            image_data = await self.get_image_data(event, file_id)
            
            # 调用API分析图片
            tags = await self.analyze_image(image_data)
            
            # 返回分析结果
            yield event.make_result().message(f"{tags}")
            
        except Exception as e:
            yield (event.make_result()
                  .message("❌ 处理过程中出现错误")
                  .message(f"\n错误信息：{str(e)}"))
    
    @filter.command("tag")
    async def tag(self, event: AstrMessageEvent):
        """给图片添加标签。可以引用一张图片并发送此命令，或发送此命令后在60秒内发送图片。"""
        user_id = event.get_sender_id()
        user_name = event.get_sender_name()
        
        # 1. 先检查消息中是否直接包含图片（比如同时发送了图片和命令）
        messages = event.get_messages()
        image = next((msg for msg in messages if isinstance(msg, Image)), None)
        if image and image.file:
            async for result in self.process_image(event, image.file):
                yield result
            return
        
        # 2. 检查是否引用了包含图片的消息
        reply_file_id = await self.get_image_from_reply(event)
        if reply_file_id:
            async for result in self.process_image(event, reply_file_id):
                yield result
            return
        
        # 3. 没有图片也没有引用，进入等待模式
        self.waiting_users[user_id] = {
            'start_time': time.time()
        }
        
        yield event.make_result().message(f"{user_name}，请在60秒内发送一张图片，我将识别图像标签喵~")
        
    @filter.regex(".*")
    async def handle_message(self, event: AstrMessageEvent):
        """处理所有消息，仅响应正在等待图片的用户"""
        try:
            # 如果是tag命令，直接返回
            if event.get_message_str().strip().startswith("tag"):
                return
            
            user_id = event.get_sender_id()
            
            # 只检查当前发送者是否在等待列表中，其他用户的消息完全忽略
            if user_id not in self.waiting_users:
                return
                
            # 检查是否超时（60秒）
            current_time = time.time()
            if current_time - self.waiting_users[user_id]['start_time'] > 60:
                del self.waiting_users[user_id]
                yield event.make_result().message("❌ 超时了，请重新发送 /tag 命令")
                return
                
            # 检查消息中是否包含图片
            messages = event.get_messages()
            image = next((msg for msg in messages if isinstance(msg, Image)), None)
            if not image:
                return
                
            # 找到图片，清除该用户的等待状态
            del self.waiting_users[user_id]
            
            if not image.file:
                yield event.make_result().message("❌ 无法获取图片ID")
                return
            
            async for result in self.process_image(event, image.file):
                yield result
                
        except Exception as e:
            yield (event.make_result()
                  .message("❌ 处理过程中出现错误")
                  .message(f"\n错误信息：{str(e)}"))

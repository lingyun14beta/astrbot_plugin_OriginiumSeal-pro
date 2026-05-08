from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
import astrbot.api.message_components as Comp
import os
import tempfile
from PIL import Image
import io
import aiohttp
from datetime import datetime, timedelta

@register("OriginiumSeal_pro", "bushikq", "将指定用户头像添加源石封印效果", "2.0.0", "https://github.com/zhewang448/astrbot_plugin_OriginiumSeal-pro")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.plugin_dir = os.path.dirname(os.path.abspath(__file__))
        self.seal_image_path = os.path.join(self.plugin_dir, "Sealed.png")
        self.cooldown = {}
        if not os.path.exists(self.seal_image_path):
            logger.info(f"印章图片不存在: {self.seal_image_path}")
        else:
            self.seal_img = Image.open(self.seal_image_path).convert("RGBA")

    @filter.command("制作源石头像")
    async def make_sealed_avatar(self, event: AstrMessageEvent):
        '''当用户发送"制作源石头像@目标用户"时，将其头像加上"封印"效果'''
        temp_img_path = None
        try:
            # 1. 冷却检查
            sender_id = event.get_sender_id()
            now = datetime.now()
            if sender_id in self.cooldown and now - self.cooldown[sender_id] < timedelta(seconds=10):
                yield event.plain_result("操作太频繁，请稍后再试")
                return
            self.cooldown[sender_id] = now
            # 清理过期冷却条目
            self.cooldown = {k: v for k, v in self.cooldown.items() if now - v < timedelta(seconds=10)}

            # 2. 获取目标用户（排除发送者自身和bot自身）
            bot_id = str(event.message_obj.self_id)
            target_user_id = next(
                (str(seg.qq) for seg in event.get_messages()
                 if isinstance(seg, Comp.At)
                 and str(seg.qq) != sender_id
                 and str(seg.qq) != bot_id),
                sender_id
            )

            # 3. 检查印章图片是否存在
            if not hasattr(self, 'seal_img'):
                yield event.plain_result("无法处理头像: 印章图片不存在")
                return

            # 4. 获取用户头像
            avatar_url = f"https://q1.qlogo.cn/g?b=qq&nk={target_user_id}&s=640"
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(avatar_url) as response:
                    if response.status != 200:
                        yield event.plain_result(f"获取头像失败: HTTP {response.status}")
                        return
                    avatar_data = await response.read()

            # 5. 处理头像图片
            avatar_img = Image.open(io.BytesIO(avatar_data))
            seal_img = self.seal_img.copy()
            seal_img = seal_img.resize(avatar_img.size)

            r, g, b, a = seal_img.split()
            a = a.point(lambda i: i * 0.7)
            seal_img = Image.merge('RGBA', (r, g, b, a))

            if avatar_img.mode != 'RGBA':
                avatar_img = avatar_img.convert('RGBA')
            result_img = Image.alpha_composite(avatar_img, seal_img)

            # 6. 保存到临时文件并发送
            img_bytes = io.BytesIO()
            result_img.save(img_bytes, format='PNG')
            img_bytes.seek(0)

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False, dir=self.plugin_dir) as tmp:
                temp_img_path = tmp.name
                tmp.write(img_bytes.getvalue())

            yield event.image_result(temp_img_path)

        except Exception as e:
            logger.error(f"处理头像时出错: {str(e)}")
            yield event.plain_result(f"处理头像时出错: {str(e)}")

        finally:
            # 7. 清理临时文件
            if temp_img_path and os.path.exists(temp_img_path):
                try:
                    os.remove(temp_img_path)
                except Exception:
                    pass

    async def terminate(self):
        pass

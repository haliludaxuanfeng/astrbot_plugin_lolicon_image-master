from astrbot.api.message_components import *
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
import httpx
import asyncio
import logging


@register("setu", "FateTrial", "一个发送随机涩图的插件", "2.0.0")
class SetuPlugin(Star):

    def __init__(self, context: Context):
        super().__init__(context)
        self.cd = 10  # 冷却时间（秒）
        self.last_usage = {}  # 记录每个用户的上次使用时间
        self.semaphore = asyncio.Semaphore(10)  # 限制并发请求最多 10 个
        self.logger = logging.getLogger("SetuPlugin")  # 日志管理

    async def fetch_setu(self, num: int = 1):
        """请求随机涩图（非 R18），支持 num 参数获取多张"""
        url = f"https://api.lolicon.app/setu/v2?r18=0&excludeAI=1&num={num}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
                if data and data.get('data'):
                    self.logger.info(f"✅ 成功获取 {len(data['data'])} 张涩图")
                else:
                    self.logger.warning("⚠️ API 返回数据为空")
                return data
            except Exception as e:
                self.logger.error(f"❌ 获取涩图失败: {e}")
                return None

    async def fetch_taisele(self, num: int = 1):
        """请求 R18 涩图，支持 num 参数获取多张"""
        url = f"https://api.lolicon.app/setu/v2?r18=1&excludeAI=1&num={num}"
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                data = resp.json()
                if data and data.get('data'):
                    self.logger.info(f"✅ 成功获取 {len(data['data'])} 张 R18 涩图")
                else:
                    self.logger.warning("⚠️ API 返回数据为空")
                return data
            except Exception as e:
                self.logger.error(f"❌ 获取 R18 涩图失败: {e}")
                return None

    async def handle_setu_request(self,
                                  event: AstrMessageEvent,
                                  num: int,
                                  is_r18=False):
        """处理涩图请求，包括解析数量、冷却检查、API 获取和发送"""
        user_id = event.get_sender_id()
        now = asyncio.get_event_loop().time()

        if user_id in self.last_usage and (now -
                                           self.last_usage[user_id]) < self.cd:
            remaining_time = self.cd - (now - self.last_usage[user_id])
            yield event.plain_result(f"冷却中，请等待 {remaining_time:.1f} 秒后重试。")
            return

        self.logger.info(f"📌 用户请求 {num} 张 {'R18 ' if is_r18 else ''}涩图")

        try:
            # 传递 num 参数，确保 API 正确返回多张涩图
            data = await (self.fetch_taisele(num)
                          if is_r18 else self.fetch_setu(num))

            if data and data['data']:
                images = [item['urls']['original'] for item in data['data']]
                async for result in self.send_images(event, images):
                    yield result

                self.last_usage[user_id] = now  # 记录冷却时间
            else:
                yield event.plain_result("没有找到涩图。")

        except Exception as e:
            self.logger.error(f"❌ 发送涩图失败: {e}")
            yield event.plain_result("发生未知错误，请稍后重试。")

    async def send_images(self, event: AstrMessageEvent, images):
        """发送多张涩图（不显示 URL）"""
        chain = [At(qq=event.get_sender_id()), Plain(f"给你 {len(images)} 张涩图：")]

        for img_url in images:
            chain.append(Image.fromURL(img_url))  # 正确使用 Image.fromURL 发送图片

        self.logger.info(f"📌 成功发送 {len(images)} 张涩图")
        yield event.chain_result(chain)

    @filter.command("setu")
    async def setu(self, event: AstrMessageEvent, num: int = 1):
        """处理普通涩图请求，支持 /setu 3"""
        num = min(max(num, 1), 10)  # 限制最多 10 张涩图
        async for result in self.handle_setu_request(event,
                                                     num=num,
                                                     is_r18=False):
            yield result

    @filter.command("taisele")
    async def taisele(self, event: AstrMessageEvent, num: int = 1):
        """处理 R18 涩图请求，支持 /taisele 3"""
        num = min(max(num, 1), 10)  # 限制最多 10 张涩图
        async for result in self.handle_setu_request(event,
                                                     num=num,
                                                     is_r18=True):
            yield result

    @filter.command("setucd")
    async def set_setu_cd(self, event: AstrMessageEvent, cd: int):
        """设置涩图冷却时间"""
        if cd <= 0:
            yield event.plain_result("冷却时间必须大于 0。")
            return
        self.cd = cd
        yield event.plain_result(f"涩图指令冷却时间已设置为 {cd} 秒。")

    @filter.command("setu_help")
    async def setu_help(self, event: AstrMessageEvent):
        """涩图插件帮助信息"""
        help_text = """
        **涩图插件帮助**
        **可用命令:**
        - `/setu` 或 `/setu <数字>`: 发送一张或多张随机涩图（默认 1 张，最多 10 张）。
        - `/taisele` 或 `/taisele <数字>`: 发送一张或多张 R18 涩图。
        - `/setucd <冷却时间>`: 设置涩图指令的冷却时间（秒）。
        - `/setu_help`: 显示此帮助信息。
        """
        yield event.plain_result(help_text)

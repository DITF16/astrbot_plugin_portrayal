from astrbot.api.event import filter
import astrbot.api.message_components as Comp
from astrbot.api.star import Context, Star, register
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot import logger
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)


@register(
    "astrbot_plugin_portrayal",
    "Zhalslar",
    "根据群友的聊天记录，调用llm分析群友的性格画像",
    "1.0.0",
    "https://github.com/Zhalslar/astrbot_plugin_portrayal",
)
class Relationship(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        # 用于分析的消息数量
        self.message_count = config.get("message_count", 200)

    @filter.command("画像")
    async def get_portrayal(self, event: AiocqhttpMessageEvent):
        """
        抽查指定群聊的消息，并分析指定群友画像
        """
        client = event.bot

        # 获取@的群友
        target_id: str = next(
            (
                str(seg.qq)
                for seg in event.get_messages()
                if (isinstance(seg, Comp.At)) and str(seg.qq) != event.get_self_id()
            ),
            event.get_sender_id(),
        )
        if not target_id:
            yield event.plain_result("请@指定群友")
            return
        group_id = event.get_group_id()
        message_seq = 0
        contexts: list[dict] = []
        # 持续获取群聊历史消息直到达到要求
        while len(contexts) < self.message_count:
            payloads = {
                "group_id": group_id,
                "message_seq": message_seq,
                "count": 200,
                "reverseOrder": True,
            }
            result: dict = await client.api.call_action(
                "get_group_msg_history", **payloads
            )
            round_messages = result["messages"]
            if not round_messages:
                break
            message_seq = round_messages[0]["message_id"]

            contexts.extend(
                [
                    {"role": "user", "content": msg["message"][0]["data"]["text"]}
                    for msg in round_messages
                    if (
                        msg["sender"]["user_id"] == int(target_id)
                        and len(msg["message"]) == 1
                        and msg["message"][0]["type"] == "text"
                    )
                ]
            )
        nickname, gender = await self.get_nickname(event, target_id)
        llm_respond = await self.get_llm_respond(nickname, gender, contexts)
        if llm_respond:
            url = await self.text_to_image(llm_respond)
            yield event.image_result(url)
        else:
            yield event.plain_result("分析失败")

    async def get_llm_respond(
        self, nickname: str, gender: str, contexts: list[dict]
    ) -> str | None:
        """调用llm回复"""
        try:
            gender_text = "他" if gender == "male" else "她"
            system_prompt = f"请根据 {nickname} 的聊天记录，分析{gender_text}的性格特点, 并给出性格标签, 注意要用可爱、调侃的语气，尽量夸奖这位群友，注意给出你的分析过程"
            prompt = f"这是 {nickname} 的聊天记录"
            llm_response = await self.context.get_using_provider().text_chat(
                system_prompt=system_prompt,
                prompt=prompt,
                contexts=contexts,
            )
            return llm_response.completion_text

        except Exception as e:
            logger.error(f"LLM 调用失败：{e}")
            return None

    async def get_nickname(
        self, event: AiocqhttpMessageEvent, user_id: str | int
    ) -> tuple[str, str]:
        """获取指定群友的昵称和性别"""
        client = event.bot
        group_id = event.get_group_id()
        all_info = await client.get_group_member_info(
            group_id=int(group_id), user_id=int(user_id)
        )
        nickname = all_info.get("card") or all_info.get("nickname")
        gender = all_info.get("sex")
        return nickname, gender

from astrbot.api.event import filter
import astrbot.api.message_components as Comp
from astrbot.api.star import Context, Star, register
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot import logger
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)
import markdown

@register(
    "astrbot_plugin_portrayal",
    "Zhalslar/DITF16(改)",
    "根据群友的聊天记录，调用llm分析群友的性格画像",
    "2.0.0",
    "https://github.com/DITF16/astrbot_plugin_portrayal",
)
class Relationship(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        # 用于分析的消息数量
        self.message_count = config.get("message_count", 200)
        # 系统提示词模板
        self.system_prompt_template = config.get(
            "system_prompt_template", "请根据聊天记录分析群友的性格"
        )
        # 最大允许的查询轮数
        self.max_query_rounds = config.get("max_query_rounds", 10)

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

        nickname, gender = await self.get_nickname(event, target_id)
        yield event.plain_result(f"稍等，我看看{nickname}的聊天记录...")

        group_id = event.get_group_id()
        query_rounds = 0
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
            query_rounds += 1
            if query_rounds >= self.max_query_rounds:
                break
        llm_respond = await self.get_llm_respond(nickname, gender, contexts)
        if llm_respond:
            # 将纯文本转换成 HTML
            html_content = markdown.markdown(llm_respond, extensions=['fenced_code', 'tables'])

            data_for_template = {
                "content": html_content,
                "title": f"{nickname} 的性格画像"
            }

            url = await self.html_render(TMPL_SUMMER_MIST, data_for_template)

            print(llm_respond)
            yield event.image_result(url)
        else:
            yield event.plain_result("分析失败")

    async def get_llm_respond(
        self, nickname: str, gender: str, contexts: list[dict]
    ) -> str | None:
        """调用llm回复"""
        try:
            system_prompt = self.system_prompt_template.format(
                nickname=nickname, gender=("他" if gender == "male" else "她")
            )
            llm_response = await self.context.get_using_provider().text_chat(
                system_prompt=system_prompt,
                prompt=f"这是 {nickname} 的聊天记录",
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


TMPL_SUMMER_MIST = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700&family=JetBrains+Mono&display=swap" rel="stylesheet">
    <style>
        html, body {
            margin: 0;
            padding: 0;
            font-family: 'Noto Sans SC', sans-serif;
        }

        .page-container {
            width: 100%;
            min-height: 100vh; 
            /* 渐变背景 */
            background: linear-gradient(170deg, #e0f7fa 0%, #e8f5e9 50%, #fef9e7 100%);
            display: flex;
            flex-direction: column;
        }

        .page-header {
            padding: 50px 50px 20px 50px; 
            text-align: center;
            flex-shrink: 0;
        }
        .page-header h1 {
            font-size: 48px; 
            color: #004d40;
            margin: 0;
            font-weight: 700;
        }

        .content-body {
            padding: 0 50px 70px 50px; 
            color: #34495e;
            font-size: 32px;
            line-height: 1.8; 
        }

        .content-body h2 {
            font-size: 1.3em; 
            color: #00695c;
            border-bottom: 3px solid #b2dfdb; 
            padding-bottom: 15px;
            margin-top: 40px;
            margin-bottom: 30px;
        }
        .content-body p { 
            margin-top: 0;
            margin-bottom: 30px;
        }
        .content-body strong { 
            color: #004d40; 
            font-weight: 700;
        }
        .content-body a { color: #2980b9; text-decoration: none; font-weight: 500; }

        .content-body blockquote {
            margin: 30px 0;
            padding: 25px 35px;
            background-color: rgba(255, 255, 255, 0.6);
            border-left: 6px solid #81d4fa;
        }

        .content-body ul, .content-body ol { 
            padding-left: 50px;
            margin-bottom: 30px;
        }
        .content-body li {
            margin-bottom: 20px;
        }

        .content-body code {
            font-family: 'JetBrains Mono', monospace;
            background-color: #e8eaed;
            color: #2c3e50;
            padding: 5px 10px;
            border-radius: 6px;
            font-size: 0.9em;
        }
        .content-body pre {
            background-color: #f3f4f6;
            padding: 25px;
            border-radius: 8px;
            border: 1px solid #e5e7eb;
            white-space: pre-wrap;
            word-wrap: break-word;
            font-size: 0.9em;
            line-height: 1.7;
        }
        .content-body pre code { background: none; padding: 0; }

        .content-body hr {
            border: none;
            border-top: 2px solid #dce1e6;
            margin: 40px 0;
        }
    </style>
</head>
<body>
    <div class="page-container">
        <header class="page-header">
            <h1>{{ title | default('画像') }}</h1>
        </header>
        <main class="content-body">
            {{ content | safe }}
        </main>
    </div>
</body>
</html>
'''
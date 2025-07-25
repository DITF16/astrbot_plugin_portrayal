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
    "1.0.0",
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
            # 1. 使用 markdown 库将纯文本转换成 HTML
            #    我们添加了 'fenced_code' 和 'tables' 扩展，使其能支持代码块和表格
            html_content = markdown.markdown(llm_respond, extensions=['fenced_code', 'tables'])

            # 2. 将转换后的 HTML 内容作为数据传递给模板
            data_for_template = {
                "content": html_content
            }

            # 3. 调用渲染函数，注意模板变量名也要相应修改
            url = await self.html_render(TMPL_MARKDOWN_RENDERER, data_for_template)

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

TMPL_MARKDOWN_RENDERER = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@400;500;700&family=JetBrains+Mono&display=swap" rel="stylesheet">
    <style>
        body {
            font-family: 'Noto Sans SC', -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", "Arial", sans-serif;
            /* 核心：动态的极光渐变背景 */
            background: linear-gradient(-45deg, #1f005c, #2d004f, #002c42, #004b4b);
            background-size: 400% 400%;
            animation: gradientBG 15s ease infinite;

            margin: 0;
            padding: 40px;
            display: flex;
            justify-content: center;
            align-items: flex-start;
            min-height: 100vh;
            box-sizing: border-box;
        }

        /* 背景移动的动画 */
        @keyframes gradientBG {
            0% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
            100% { background-position: 0% 50%; }
        }

        .markdown-body {
            box-sizing: border-box;
            width: 700px;
            max-width: 100%;
            
            /* 核心：玻璃拟态/磨砂玻璃效果 */
            background: rgba(0, 0, 0, 0.35);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px); /* 兼容性 */
            border: 1px solid rgba(255, 255, 255, 0.18);
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);

            border-radius: 10px;
            padding: 45px;
            color: #e0e7ff; /* 基础文字颜色 - 淡紫色白 */
            line-height: 1.8;
        }

        /* --- 字体颜色层次 --- */

        .markdown-body h1, .markdown-body h2, .markdown-body h3 {
            font-weight: 700;
            color: #ffffff; /* 标题用纯白，更突出 */
            text-shadow: 0 0 5px rgba(255, 255, 255, 0.2); /* 轻微发光效果 */
            border-bottom: 1px solid rgba(255, 255, 255, 0.2);
            padding-bottom: 0.4em;
            margin-top: 24px;
            margin-bottom: 16px;
        }
        .markdown-body h1 { font-size: 2em; }
        .markdown-body h2 { font-size: 1.5em; }
        
        .markdown-body strong {
            color: #c4b5fd; /* 加粗文字 - 亮紫色 */
        }

        .markdown-body a {
            color: #67e8f9; /* 链接 - 明亮的青色 */
            text-decoration: none;
            border-bottom: 1px dotted #67e8f9;
        }
        .markdown-body a:hover {
            color: #a5f3fc;
            border-bottom-style: solid;
        }

        /* --- 块级元素样式 --- */

        .markdown-body blockquote {
            margin: 16px 0;
            padding: 10px 20px;
            background: rgba(0, 0, 0, 0.2); /* 更深的半透明背景 */
            border-left: 4px solid #a78bfa; /* 引用条 - 紫罗兰色 */
            color: #c7d2fe; /* 引用内文字 - 稍暗的蓝紫色 */
            border-radius: 0 6px 6px 0;
        }
        .markdown-body blockquote p {
            margin: 0;
        }
        
        /* 代码块样式 */
        .markdown-body pre {
            font-family: 'JetBrains Mono', monospace;
            padding: 20px;
            overflow: auto;
            font-size: 85%;
            line-height: 1.5;
            background-color: rgba(0, 0, 0, 0.4); /* 最深的背景，模拟终端 */
            border-radius: 6px;
            margin: 16px 0;
        }
        /* 行内代码与代码块内文字 */
        .markdown-body code {
            font-family: 'JetBrains Mono', monospace;
            color: #a5f3fc; /* 代码文字 - 亮青色 */
            font-size: 90%;
            padding: 0.2em 0.4em;
            background-color: rgba(0, 0, 0, 0.3); /* 行内代码背景 */
            border-radius: 4px;
        }
        .markdown-body pre code {
            padding: 0;
            background: none; /* 代码块内的code标签不需要额外背景 */
        }

        .markdown-body hr {
            height: 1px;
            padding: 0;
            margin: 24px 0;
            /* 发光的分割线 */
            background: linear-gradient(to right, transparent, rgba(255, 255, 255, 0.3), transparent);
            border: 0;
        }
        
        .markdown-body ul, .markdown-body ol { padding-left: 2em; }
        .markdown-body li::marker { color: #a78bfa; } /* 列表标记颜色 */

        /* 表格样式 */
        .markdown-body table { border-collapse: collapse; width: 100%; margin: 16px 0;}
        .markdown-body th, .markdown-body td { border: 1px solid rgba(255, 255, 255, 0.2); padding: 8px 15px; }
        .markdown-body th { background-color: rgba(0, 0, 0, 0.2); color: #c4b5fd; }
    </style>
</head>
<body>
    <div class="markdown-body">
        {{ content | safe }}
    </div>
</body>
</html>
'''
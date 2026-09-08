"""
Idea 工具函数 - 从 refined_idea（Markdown 字符串）提取可读文本。
供 Plan、Task、Reflection 等下游使用。
"""


def get_idea_text(refined: str | None) -> str:
    """从 refined_idea（Markdown 字符串）提取可读文本。"""
    if not refined or not isinstance(refined, str):
        return ""
    return refined.strip()

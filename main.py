from astrbot.api.all import *
from astrbot.api.event.filter import command, event_message_type, EventMessageType
import json
import os
import datetime
import logging
import random
import hashlib
from typing import Dict, Any

logger = logging.getLogger("CheckInPlugin")

# 数据存储路径
DATA_DIR = os.path.join("data", "plugins", "astrbot_checkin_plugin")
os.makedirs(DATA_DIR, exist_ok=True)
DATA_FILE = os.path.join(DATA_DIR, "checkin_data.json")

# 训练手册提示
MOTIVATIONAL_MESSAGES = [
    "别死！",
    "困惑之时，不要思考——只需大喊“为了民主！”，"
    "然后勇敢地冲锋陷阵。",
    "为！了！超！级！地！球！",
    "Say hello to DEMOCRACY！",
    "喝酒不开船。",
    "多多称赞队友的出色表现。我们都走在历史的康庄大道上！",
    "绝地喷射仓具备基础转向功能。尽量降落在敌人周围！",
    "机器人配备过度反应协议，因此，火力压制对付他们格外有效。",
    "管理式民主是先进文明的支柱。",
    "进行可能产生孩子的行为之前，记得先填好C-01授权表格。",
    "不要担心，就算你没能完成目标，你也绝对不会被送入自由营。那只是异见分子散播的谣言。",
    "对于试图对话的敌人，要毫不犹豫地开枪击毙。一定不能为花言巧语所欺骗。",
    "如果你发现队友同情敌人，请向民主官举报。思想犯罪是会害死人的！",
    "牢记自由！",
    "扣↓↑←↓↑→↓↑送地狱火。",
    "扣↓→↑↑↑送地狱火",
    "抽到这条tip的人发一张腿照。",
    "抽到这条tip的人发一张腿照。",
    "抽到这条tip的人发一张腿照。",
    "抽到这条tip的人发一张腿照。",
    "抽到这条tip的人发一张腿照。",
    "抽到这条tip的人抽到这条tip。",
    "点击输入文本。",
    "吃什么？",
    "我重启了。",
    "注意休息！…前提是你想被当作懦夫的话。",
    "🈶🈚民主？",
    "抽到这条tip的人今天记得服役。",
    "👊🔥🌪🔥 神龙裂破！",
    "👆😡👆 MUSCLE!",
    "每天进行脱敏训练，确保你能冷静面对敌人的暴行。"
]

def _load_data() -> dict:
    """加载签到数据"""
    try:
        if not os.path.exists(DATA_FILE):
            return {}
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"数据加载失败: {str(e)}")
        return {}

def _save_data(data: dict):
    """保存签到数据"""
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"数据保存失败: {str(e)}")

def _get_context_id(event: AstrMessageEvent) -> str:
    """多平台兼容的上下文ID生成（已修复QQ官方Webhook问题）"""
    try:
        # 优先处理QQ官方Webhook结构
        if hasattr(event, 'message') and hasattr(event.message, 'source'):
            source = event.message.source
            if hasattr(source, 'group_id') and source.group_id:
                return f"group_{source.group_id}"
            if hasattr(source, 'user_id') and source.user_id:
                return f"private_{source.user_id}"
        
        # 处理标准事件结构
        if hasattr(event, 'group_id') and event.group_id:
            return f"group_{event.group_id}"
        if hasattr(event, 'user_id') and event.user_id:
            return f"private_{event.user_id}"
        
        # 生成唯一备用ID
        event_str = f"{event.get_message_id()}-{event.get_time()}"
        return f"ctx_{hashlib.md5(event_str.encode()).hexdigest()[:6]}"
        
    except Exception as e:
        logger.error(f"上下文ID生成异常: {str(e)}")
        return "default_ctx"

def _generate_rewards() -> int:
    """生成1-10随机战争债券奖章"""
    return random.randint(1, 10)

@register("签到插件", "Kimi&Meguminlove", "多维度排行榜签到系统", "1.0.3", "https://github.com/Meguminlove/astrbot_checkin_plugin")
class CheckInPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.data = _load_data()

    @command("训练手册", alias = ["手册"])
    async def meg(self, event: AstrMessageEvent):
        selected_msg = random.choice(MOTIVATIONAL_MESSAGES)
        yield event.plain_result(
            f"🔊 训练手册提示: {selected_msg}"
        )

    @command("解冻", alias=["打卡"])
    async def check_in(self, event: AstrMessageEvent):
        """每日签到"""
        try:
            ctx_id = _get_context_id(event)
            user_id = event.get_sender_id()
            today = datetime.date.today().isoformat()

            # 初始化数据结构（新增username字段）
            ctx_data = self.data.setdefault(ctx_id, {})
            user_data = ctx_data.setdefault(user_id, {
                "username": event.get_sender_name(),  # 确保存储的是用户昵称
                "total_days": 0,
                "continuous_days": 0,
                "month_days": 0,
                "total_rewards": 0,
                "month_rewards": 0,
                "last_checkin": None
            })
            
            # 更新用户名（防止用户改名）
            user_data['username'] = event.get_sender_name()

            # 检查重复签到
            if user_data["last_checkin"] == today:
                yield event.plain_result("终端拒绝受理。理由：重复的解冻请求。\n❕输入 /解冻排行 可以查看奖章排行榜。")
                return

            # 计算连续签到
            last_date = user_data["last_checkin"]
            current_month = today[:7]
            
            if last_date:
                last_day = datetime.date.fromisoformat(last_date)
                if (datetime.date.today() - last_day).days == 1:
                    user_data["continuous_days"] += 1
                else:
                    user_data["continuous_days"] = 1
                
                # 跨月重置月数据
                if last_date[:7] != current_month:
                    user_data["month_days"] = 0
                    user_data["month_rewards"] = 0
            else:
                user_data["continuous_days"] = 1

            # 生成奖励
            rewards = _generate_rewards()
            user_data.update({
                "total_days": user_data["total_days"] + 1,
                "month_days": user_data["month_days"] + 1,
                "total_rewards": user_data["total_rewards"] + rewards,
                "month_rewards": user_data["month_rewards"] + rewards,
                "last_checkin": today
            })

            _save_data(self.data)
            
            # 构造响应
            selected_msg = random.choice(MOTIVATIONAL_MESSAGES)
            name = event.get_sender_name()
            yield event.plain_result(
                f"✅【解冻成功】\n民主向你问好，{name}\n"
                f"🌎 终端提示: 你已坚持宣扬管理式民主{user_data['continuous_days']}天\n"
                f"🎖️ 获得战争债券奖章: {rewards}个\n"
                f"🔊 训练手册提示: {selected_msg}"
            )

        except Exception as e:
            logger.error(f"解冻异常: {str(e)}", exc_info=True)
            yield event.plain_result("🔧 解冻服务暂时不可用。")

    def _get_rank(self, event: AstrMessageEvent, key: str) -> list:
        """获取当前上下文的排行榜"""
        ctx_id = _get_context_id(event)
        ctx_data = self.data.get(ctx_id, {})
        return sorted(
            ctx_data.items(),
            key=lambda x: x[1][key],
            reverse=True
        )[:10]

    # @command("解冻排行榜", alias=["解冻排行"])
    # async def show_rank_menu(self, event: AstrMessageEvent):
    #     """排行榜导航菜单"""
    #     yield event.plain_result(
    #         "📊 排行榜类型：\n"
    #         "/解冻总奖励排行榜 - 累计获得超级货币\n"
    #         "/解冻月奖励排行榜 - 本月获得超级货币\n"
    #         "/解冻总天数排行榜 - 历史解冻总天数\n"
    #         "/解冻月天数排行榜 - 本月解冻天数\n"
    #         "/解冻今日排行榜 - 今日解冻潜兵榜"
    #     )

    # @command("解冻排行榜", alias=["解冻排行"])
    # async def total_rewards_rank(self, event: AstrMessageEvent):
    #     """总奖励排行榜"""
    #     ranked = self._get_rank(event, "total_rewards")
    #     msg = ["🌎 累计奖章排行榜"] + [
    #         f"{i+1}. 潜兵 {data.get('username', '未知')} - {data['total_rewards']}个"
    #         for i, (uid, data) in enumerate(ranked)
    #     ]
    #     yield event.plain_result("\n".join(msg))

    @command("解冻排行榜", alias=["解冻排行"])
    async def month_rewards_rank(self, event: AstrMessageEvent):
        """月奖励排行榜"""
        ranked = self._get_rank(event, "month_rewards")
        msg = ["🌎 本月奖章排行榜"] + [
            f"{i+1}. 潜兵 {data.get('username', '未知')} - {data['month_rewards']}个"
            for i, (uid, data) in enumerate(ranked)
        ]
        yield event.plain_result("\n".join(msg))

    #
    # @command("签到总天数排行榜", alias=["签到总天数排行"])
    # async def total_days_rank(self, event: AstrMessageEvent):
    #     """总天数排行榜"""
    #     ranked = self._get_rank(event, "total_days")
    #     msg = ["🏆 累计契约天数榜"] + [
    #         f"{i+1}. 契约者 {data.get('username', '未知')} - {data['total_days']}天"
    #         for i, (uid, data) in enumerate(ranked)
    #     ]
    #     yield event.plain_result("\n".join(msg))
    #
    # @command("签到月天数排行榜", alias=["签到月天数排行"])
    # async def month_days_rank(self, event: AstrMessageEvent):
    #     """月天数排行榜"""
    #     ranked = self._get_rank(event, "month_days")
    #     msg = ["🏆 本月契约天数榜"] + [
    #         f"{i+1}. 契约者 {data.get('username', '未知')} - {data['month_days']}天"
    #         for i, (uid, data) in enumerate(ranked)
    #     ]
    #     yield event.plain_result("\n".join(msg))
    #
    # @command("签到今日排行榜", alias=["签到今日排行", "签到日排行"])
    # async def today_rank(self, event: AstrMessageEvent):
    #     """今日签到榜"""
    #     ctx_id = _get_context_id(event)
    #     today = datetime.date.today().isoformat()
    #
    #     ranked = sorted(
    #         [(uid, data) for uid, data in self.data.get(ctx_id, {}).items()
    #          if data["last_checkin"] == today],
    #         key=lambda x: x[1]["continuous_days"],
    #         reverse=True
    #     )[:10]
    #
    #     msg = ["🏆 今日契约榜"] + [
    #         f"{i+1}. 契约者 {data.get('username', '未知')} - 连续 {data['continuous_days']}天"
    #         for i, (uid, data) in enumerate(ranked)
    #     ]
    #     yield event.plain_result("\n".join(msg))
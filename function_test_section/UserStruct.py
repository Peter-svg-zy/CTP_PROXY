import Global_Param as g



# 深度数据
class MarketData(object):
    def __init__(self):
        # 交易日
        self.TradingDay = None
        # 保留的无效字段
        self.reserve1 = None
        # 交易所代码
        self.ExchangeID = None
        # 保留的无效字段
        self.reserve2 = None
        # 最新价
        self.LastPrice = None
        # 上次结算价
        self.PreSettlementPrice = None
        # 昨收盘
        self.PreClosePrice = None
        # 昨持仓量
        self.PreOpenInterest = None
        # 今开盘
        self.OpenPrice = None
        # 最高价
        self.HighestPrice = None
        # 最低价
        self.LowestPrice = None
        # 数量
        self.Volume = None
        # 成交金额
        self.Turnover = None
        # 持仓量
        self.OpenInterest = None
        # 今收盘
        self.ClosePrice = None
        # 本次结算价
        self.SettlementPrice = None
        # 涨停板价
        self.UpperLimitPrice = None
        # 跌停板价
        self.LowerLimitPrice = None
        # 昨虚实度
        self.PreDelta = None
        # 今虚实度
        self.CurrDelta = None
        # 最后修改时间
        self.UpdateTime = None
        # 最后修改毫秒
        self.UpdateMillisec = None
        # 申买价一
        self.BidPrice1 = None
        # 申买量一
        self.BidVolume1 = None
        # 申卖价一
        self.AskPrice1 = None
        # 申卖量一
        self.AskVolume1 = None
        # 申买价二
        self.BidPrice2 = None
        # 申买量二
        self.BidVolume2 = None
        # 申卖价二
        self.AskPrice2 = None
        # 申卖量二
        self.AskVolume2 = None
        # 申买价三
        self.BidPrice3 = None
        # 申买量三
        self.BidVolume3 = None
        # 申卖价三
        self.AskPrice3 = None
        # 申卖量三
        self.AskVolume3 = None
        # 申买价四
        self.BidPrice4 = None
        # 申买量四
        self.BidVolume4 = None
        # 申卖价四
        self.AskPrice4 = None
        # 申卖量四
        self.AskVolume4 = None
        # 申买价五
        self.BidPrice5 = None
        # 申买量五
        self.BidVolume5 = None
        # 申卖价五
        self.AskPrice5 = None
        # 申卖量五
        self.AskVolume5 = None
        # 当日均价
        self.AveragePrice = None
        # 业务日期
        self.ActionDay = None
        # 合约代码
        self.InstrumentID = None
        # 合约在交易所的代码
        self.ExchangeInstID = None
        # 上带价
        self.BandingUpperPrice = None
        # 下带价
        self.BandingLowerPrice = None


class orderInfo(object):
    def __init__(self, orderRef, strategyID):
        self.frontID = g.frontID  # 前置编号
        self.sessionID = g.sessionID  # 会话编号
        self.maxOrderRef = orderRef  # 最大报单引用
        self.pOrder = None
        self.strategyID = strategyID
        self.orderPrice = None
        self.instrumentID = None


# 持仓
class positionInfo(object):
    def __init__(self):
        self.strategyID = 0
        self.pInvestorPosition = None


# 委托买卖类型
class bs(object):
    buyOpen = 'buyopen'
    sellOpen = 'sellopen'
    buyClose = 'buyclose'
    sellClose = 'sellclose'
    buyCloseToday = 'buyclosetoday'
    sellCloseToday = 'sellclosetoday'


# 持仓明细
class positionDetailInfo(object):
    def __init__(self):
        self.strategyID = 0
        self.position_list = []
        self.openPrice_list = []
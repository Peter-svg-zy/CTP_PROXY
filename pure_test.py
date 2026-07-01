import Global_Param_test as g


"""
本案例以15分钟k线为例，核心思想：突破周期内的布林上下轨顺势而为，下跌止损，让利润奔腾
纯示例代码，展示Aberration逻辑,简单实现策略见test.py
"""

#策略固定参数
period=88
num_std=2


def bollinger_bands(close,period,num_std):
    """计算布林上下轨道
       close：收盘价列表，【收盘价1，收盘价2，。。。。。】
       period:周期数
       num_std:标准差倍数
       return:布林上下轨值
    """
    middle_band=close.rolling(window=period).mean()
    std=close.rolling(window=period).std()  #一个窗口内的标准差
    return middle_band + num_std*std

def xAverager(close,period):
    """
     核心公式如下：
     EMA(today) = Price(today) × α + EMA(yesterday) × (1 - α)
     α = 2 / (period + 1)
     和普通average主要区别，日期越近权重越大，普通average权重一样
    """
    #return close.rolling(window=period).mean()普通average
    return close.ewm(span=period, adjust=False).mean()


class AberrationStrategy:
    """
    Aberration生成买，平，卖信号
    data为存储bar的列表，包含close列
    return 返回交易信号，买，卖。平仓
    """
    def __init__(self,period,num_std):
        self.period=period
        self.num_std = num_std
        self.position=None #持仓信号，0: 无持仓, 1: 多头, -1: 空头
        self.sign=None     #买/卖信号

    def generate_signals(self,data):
        df=data.copy()#浅拷贝
        df= df.rename(columns={
            '收盘价': 'close',
            '开盘价': 'open',
            '最高价': 'high',
            '最低价': 'low',
            '成交量': 'volume',
            '持仓量': 'open_interest',
            '合约名称': 'contract_name',
            '上一刻成交量': 'prev_volume',
            '当前时间': 'current_time'
        })
        df['Babove_line']=bollinger_bands(df['close'],self.period,self.num_std)
        df['Bunder_line']=bollinger_bands(df['close'],self.period,-self.num_std)
        df['xAverage_line']=bollinger_bands(df['close'],self.period)
        #初始化
        df['sign']=None
        df['position']=None
        df['Babove_line_prev']=df['Babove_line'].shift(1)
        df['Bunder_line_prev']=df['Bunder_line'].shift(1)
        df['xAverage_line_prev']=df['xAverage_line'].shift(1)
        #无持仓
        if self.position ==0:
            #突破上轨做多
            if df['close'].iloc[g.current_bar_num] >= df['Babove_line_prev'].iloc[g.current_bar_num]:
                df.loc[df.index[g.current_bar_num], 'position'] = 1
                df.loc[df.index[g.current_bar_num], 'signal'] = 1
               #******多策略后续加锁
                self.sign = 1
                self.position=1 #买开
                # ******多策略后续加锁
            #突破下轨做空
            elif df['close'].iloc[g.current_bar_num] <= df['Bunder_line_prev'].iloc[g.current_bar_num]:
                df.loc[df.index[g.current_bar_num], 'position'] = 1
                df.loc[df.index[g.current_bar_num], 'signal'] = -1
                # ******多策略后续加锁
                self.sign = -1
                self.position=1 #卖开
                # ******多策略后续加锁
        #持仓多头
        elif self.position ==1:
            #从上而下突破均线卖平
           if df['close'].iloc[g.current_bar_num] >= df['xAverage_line_prev'].iloc[g.current_bar_num]:
               df.loc[df.index[g.current_bar_num], 'position'] = 0
               df.loc[df.index[g.current_bar_num], 'signal'] =-2
               self.sign=-2
               self.position=0

        #持仓空头
        elif self.position==-1:
             if df['close'].iloc[g.current_bar_num] >= df['xAverage_line_prev'].iloc[g.current_bar_num]:
                 df.loc[df.index[g.current_bar_num], 'position']=0
                 df.loc[df.index[g.current_bar_num], 'signal']=2
                 self.sign=2
                 self.position=0

        return df, self.sign


if __name__=='__main__':
 data=g.bar15_list #data为15分钟k线列表
 abstagey=AberrationStrategy(period=period,num_std=num_std)
 df,sign=abstagey.generate_signals(data)



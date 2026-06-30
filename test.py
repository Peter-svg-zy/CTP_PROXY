import numpy as np
import pandas as pd
"""本案例以15分钟k线为例"""


def bollinger_bands(close,period,num_std):
    """计算布林上下轨道
       close：收盘价列表，【收盘价1，收盘价2，。。。。。】
       period:周期数
       num_std:标准差倍数
       return:布林上下轨值
    """
    middle_band=close.rolling(window=period).mean()
    std=close.rolling(window=period).std()  #一个窗口内的标准差
    if num_std>0:
        return middle_band + num_std*std
    else:
        return middle_band - num_std*std

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
    """
    def __init__(self,close,period,num_std):
        self.close = close
        self.period=period
        self.num_std = num_std
        self.position=0 #持仓信号，0: 无持仓, 1: 多头, -1: 空头

    def generate_signals(self,data):
        df=data.copy()#浅拷贝
        df = df.rename(columns={
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

        # 计算指标
        df['var0'] = bollinger_bands(df['close'], self.period, 2)  # 上轨
        df['var1'] = bollinger_bands(df['close'], self.period, -2)  # 下轨
        df['var2'] = xAverager(df['close'], self.period)  # 指数均线

        # 初始化信号列
        df['signal'] = 0
        df['position'] = 0

        # 使用前一根bar的指标值
        df['var0_prev'] = df['var0'].shift(1)
        df['var1_prev'] = df['var1'].shift(1)
        df['var2_prev'] = df['var2'].shift(1)

        current_position = 0

        for i in range(1, len(df)):
            # 无持仓时
            if current_position == 0:
                # 价格突破上轨做多
                if df['close'].iloc[i] >= df['var0_prev'].iloc[i]:
                    df.loc[df.index[i], 'signal'] = 1  # 买入信号
                    current_position = 1
                # 价格突破下轨做空
                elif df['close'].iloc[i] <= df['var1_prev'].iloc[i]:
                    df.loc[df.index[i], 'signal'] = -1  # 卖空信号
                    current_position = -1

            # 持有多头时
            elif current_position == 1:
                # 价格跌破均线平多
                if df['close'].iloc[i] <= df['var2_prev'].iloc[i]:
                    df.loc[df.index[i], 'signal'] = -2  # 卖出平仓信号
                    current_position = 0

            # 持有空头时
            elif current_position == -1:
                # 价格突破均线平空
                if df['close'].iloc[i] >= df['var2_prev'].iloc[i]:
                    df.loc[df.index[i], 'signal'] = 2  # 买入平仓信号
                    current_position = 0

            df.loc[df.index[i], 'position'] = current_position

        return df


# 回测函数
def backtest_strategy(data, initial_capital=100000):
    """
    简单的回测函数

    Parameters:
    data: DataFrame with signals and close price
    initial_capital: 初始资金

    Returns:
    DataFrame with portfolio values
    """
    df = data.copy()

    # 计算收益率
    df['returns'] = df['close'].pct_change()

    # 根据持仓方向计算策略收益
    df['strategy_returns'] = df['position'].shift(1) * df['returns']

    # 计算累计收益
    df['cumulative_returns'] = (1 + df['strategy_returns'].fillna(0)).cumprod()
    df['portfolio_value'] = initial_capital * df['cumulative_returns']

    return df


# 使用示例
if __name__ == "__main__":
    # 假设你已经有数据
    # data = pd.read_csv('your_data.csv')  # 需要包含 'close' 列

    # 示例数据创建
    np.random.seed(42)
    dates = pd.date_range(start='2020-01-01', periods=500, freq='D')
    close_prices = 100 + np.cumsum(np.random.randn(500) * 2)
    data = pd.DataFrame({'close': close_prices}, index=dates)

    # 初始化策略
    strategy = AberrationStrategy(ma_period=88)

    # 生成信号
    signals = strategy.generate_signals(data)

    # 回测
    results = backtest_strategy(signals)

    # 显示结果
    print("信号统计:")
    print(signals['signal'].value_counts())
    print("\n回测结果:")
    print(f"初始资金: 100,000")
    print(f"最终资金: {results['portfolio_value'].iloc[-1]:,.2f}")
    print(f"总收益率: {(results['portfolio_value'].iloc[-1] / 100000 - 1) * 100:.2f}%")

    # 计算策略指标
    results['strategy_returns'].fillna(0)
    sharpe_ratio = np.sqrt(252) * results['strategy_returns'].mean() / results['strategy_returns'].std()
    max_drawdown = (results['portfolio_value'] / results['portfolio_value'].cummax() - 1).min()

    print(f"夏普比率: {sharpe_ratio:.2f}")
    print(f"最大回撤: {max_drawdown * 100:.2f}%")




import pandas as pd
import numpy as np


def bollinger_band(close, period, num_std):
    """计算布林带"""
    ma = close.rolling(window=period).mean()
    std = close.rolling(window=period).std()
    if num_std >= 0:
        return ma + num_std * std
    else:
        return ma + num_std * std


def xaverage(close, period):
    """计算指数移动平均"""
    return close.ewm(span=period, adjust=False).mean()


class AberrationStrategy:
    def __init__(self, ma_period=88):
        self.ma_period = ma_period
        self.position = 0  # 0: 无持仓, 1: 多头, -1: 空头

    def generate_signals(self, data):
        """
        生成交易信号

        Parameters:
        data: DataFrame, 必须包含 'close' 列

        Returns:
        DataFrame with signals
        """
        df = data.copy() #浅拷贝

        # 计算指标
        df['var0'] = bollinger_band(df['close'], self.ma_period, 2)  # 上轨
        df['var1'] = bollinger_band(df['close'], self.ma_period, -2)  # 下轨
        df['var2'] = xaverage(df['close'], self.ma_period)  # 指数均线

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
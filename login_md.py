from CTP_API import thostmduserapi as tdapi
from CTP_API import thostmduserapi as mdapi
import Global_Param as g
from function import *

"""纯行情登录实现功能"""

#创建回调接口spi
class CFtdcMdSpi(mdapi.CThostFtdcMdSpi):
    def __init__(self, mduserapi):
        mdapi.CThostFtdcMdSpi.__init__(self)
        self.mduserapi =mduserapi
    # 当客户端与交易后台建立起通信连接时（还未登录前），该方法被调用，可以在该方法内实现用户登录
    def OnFrontConnected(self):
        loginfield = mdapi.CThostFtdcReqUserLoginField()
        loginfield.BrokerID = g.broker_id
        loginfield.UserID = g.investorID
        loginfield.Password =g.password

        ret= self.mduserapi.ReqUserLogin(loginfield,0)   #在这里调用用户登录接口，调用用户登录接口后触发其回调接口
        if ret == 0:
            print('发送用户登录行情请求成功')
        else:
            print('发送用户登录行情账户请求失败！')
            judge_ret(ret)

    def OnRspUserLogin(self, pRspUserLogin, pRspInfo, nRequestID, bIsLast):   # 用户登录的回调接口
        """pRspUserLogin:结构体，包含交易日，登录时间
           pRspInfo:响应信息结构体包含ErrorId和 ErrorMsg，None登录成功
           nRequestID:用户操作请求ID，这里就是上方ret填入参数的0
           bIsLast:指示该次返回是否为针对nRequestID的最后一次返回
        """
        if pRspInfo.ErrorID != 0 and pRspInfo != None:
            print('行情连接失败\n错误信息为：{}\n错误代码为：{}'.format(pRspInfo.ErrorMsg, pRspInfo.ErrorID))
        else:
            print('行情账户登录成功！')
            # g.subID = ["FG266", "SA266", 'au2609', 'sc2609']
            # # 订阅行情
            # ret = self.mduserapi.SubscribeMarketData([id.encode('utf-8') for id in g.subID],
            #                                          len(g.subID))
            # if ret == 0:
            #     print('发送订阅合约请求成功！')
            # else:
            #     print('发送订阅合约请求失败！')
            #     judge_ret(ret)


class CTP_MdLogin(object):
    def __init__(self, **kwargs):
        pass
    def connect_to_md(self):
        self.mduserapi=mdapi.CThostFtdcMdApi_CreateFtdcMdApi('./con_file/')  # 创建api实例
        self.mduserspi=CFtdcMdSpi(self.mduserapi)   # spi实例
        g.mduserapi=self.mduserapi
        g.mduserspi=self.mduserspi
            # 登录行情前置服务器
        self.mduserapi.RegisterFront(g.market_server_front)
            # 将spi注册给api
        self.mduserapi.RegisterSpi(self.mduserspi)
            # 第5步，API正式启动，dll底层会自动去连上面注册的地址
        self.mduserapi.Init()
        self.mduserapi.Join()

if __name__ == '__main__':
    ctp_login = CTP_MdLogin()
    ctp_login.connect_to_md()





def judge_ret(ret):
    if ret == -1:
        print('失败原因：网络连接失败')
    elif ret == -2:
        print('失败原因：表示未处理请求超过许可数')
    elif ret == -3:
        print('失败原因：表示每秒发送请求数超过许可数')
    else:
        print('失败原因：未知。\nret：{}'.format(ret))
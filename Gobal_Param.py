import numpy as np
import threading

postion=None    #多策略为字典类型
signal=None     #多策略为字典类型
current_bar_num=None  #多策略为字典类型
plock=threading.Lock()
bar15_list=[]   #分钟kxian
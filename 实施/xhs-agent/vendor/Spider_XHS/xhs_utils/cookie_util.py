def trans_cookies(cookies_str):
    # 空格符不同的处理逻辑
    if '; ' in cookies_str:
        ck = {i.split('=')[0]: '='.join(i.split('=')[1:]) for i in cookies_str.split('; ')}
    else:
        ck = {i.split('=')[0]: '='.join(i.split('=')[1:]) for i in cookies_str.split(';')}
    return ck
# 这个函数的逻辑是将cookie字符串转换为字典格式
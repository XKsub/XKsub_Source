# version 0.2.2
# 2022.09.15

try:
    import re
    import sys
    from pathlib import Path
    import time
    import json
    import os
    import subprocess
    import requests
    import argparse
    import traceback

    import socket
    import socks
    socks.set_default_proxy(socks.SOCKS5, "127.0.0.1", 7890)
    socket.socket = socks.socksocket

    zhconvert_request_interval = 5.0
    zhconvert_config = dict()

    # 跳过样式
    zhconvert_config['ignoreTextStyles'] = '''
OP JP
ED JP
Text - JP
'''

    # 繁化姬模组
    # 模组列表 https://api.zhconvert.org/service-info?prettify=1
    modules = {
        '*': 0,
        'ChineseVariant': -1,
        'Computer': -1,
        'ProperNoun': -1,
        'Repeat': -1,
        'RepeatAutoFix': -1,
        'Unit': -1
    }

    zhconvert_config['modules'] = str(json.dumps(modules))

    # 转换后取代
    zhconvert_config['userPostReplace'] = '''
思源黑体 CN=思源黑體 TW
思源宋体 CN=思源宋體 TW
思源黑体=思源黑體
Source Han Serif CN=Source Han Serif
Source Han Sans CN=Source Han Sans TW
SourceHanSansSC=SourceHanSansTC
Source Han Sans SC=Source Han Sans TC
Source Han Serif SC=Source Han Serif TC
华康流叶体W3=華康流葉體
DFHannotateW7-GB=DFHannotateW7-B5

活儿=活

高空彈跳=蹦極

翹發=翹髮
聯絡=聯繫
进发=進發

畫圖軟體=小畫家


莎奈=紗奈
就能將妳眼中映出的真實=就能將你眼中映出的真實

風捲=風卷
Style: OPCN,华康浪漫雪W9(P),58=Style: OPCN,華康浪漫雪W9(P),48
华康竹风体=華康竹風體
汽缸=氣缸
韭崎=韮崎
鯰川=鮎川
沙保裡=沙保里
好啦  痛痛痛痛…=好啦  疼痛疼痛…

'''



    def ass_zhconvert_sctc(ass_event_string):
        from typing import Union

        ZHCONVERT_API = 'https://api.zhconvert.org'

        def zhconvert(**kwargs):
            """繁化姬轉換
            API doc : https://docs.zhconvert.org/api/convert/
            """

            def request(endpoint: str, payload: dict):
                global zhconvert_request_interval
                start = time.time()
                with requests.get(f'{ZHCONVERT_API}{endpoint}', data=payload) as response:
                    if response.status_code == 200:
                        response.encoding = 'utf-8'
                        time.sleep(max(0.0, zhconvert_request_interval - (time.time() - start)))
                        return json.loads(response.text)
                    raise Exception(
                        f'zhconvert Request error. status code: {response.status_code}')

            def text(response) -> Union[None, str]:
                if response['code'] != 0:
                    return None
                return response['data']['text']

            ALLOW_KEYS = [
                'text',
                'converter',
                'ignoreTextStyles',
                'jpTextStyles',
                'jpStyleConversionStrategy',
                'jpTextConversionStrategy',
                'modules',
                'userPostReplace',
                'userPreReplace',
                'userProtectReplace',
                'diffCharLevel',
                'diffContextLines',
                'diffEnable',
                'diffIgnoreCase',
                'diffIgnoreWhiteSpaces',
                'diffTemplate',
            ]
            error_keys = [key for key in kwargs.keys() if key not in ALLOW_KEYS]
            if error_keys:
                raise Exception(f"Invalid key: {', '.join(error_keys)}")
            if kwargs.get('text', None) is None or kwargs.get('converter', None) is None:
                raise Exception(f"Miss necessary key")
            response = request('/convert', kwargs)
            return response

        no_module = dict(zhconvert_config)
        no_module['modules'] = "{}"
        twTC = zhconvert(text=ass_event_string, converter="WikiTraditional",**zhconvert_config)

        twTC    = re.sub(r"(Comment: Processed by 繁化姬) (\w|-)* @ \d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}( \| https://zhconvert.org)", r"\1\3", twTC['data']['text'])

        return twTC


    def read_ass(filename:os.PathLike)->str:
        read = True
        contents = ""
        with open(filename, "r", encoding="utf-8") as file:
            for line in file:
                if read:
                    if re.match(r"\[Aegisub Project Garbage\]|\[Aegisub Extradata\]", line):
                        read = False
                        continue
                    contents += line
                
                else:
                    if re.match(r"\[V4\+ Styles\]|\[Events\]", line):
                        read = True
                        contents += line
            # motion data
            contents = re.sub(r"{=\d*}", "", contents)
            contents = re.sub(r"([^\n])$", r"\1\n", contents)
            contents = re.sub(r"\n+$", r"\n", contents)
            contents = re.sub(r"\{外:[\dABCDEF]{32}\}", "", contents)
        
        return contents

    def auto_metadata(content:str, filename:Path)->str:
        output = re.sub(r"Original Translation: \n|Original Editing: \n|Original Timing: \n|Synch Point: \n|Script Updated By: \n|Update Details: \n", "", content)
        output = re.sub(r"\nTitle: [^\n]*\n", f"\nTitle: {filename.stem}\n", output)
        return output

    def auto_comment(content:str)->str:
        output = re.sub(r"Dialogue: (\d+,\d+:\d{2}:\d{2}\.\d{2},\d+:\d{2}:\d{2}\.\d{2},(?P<style>[^,]*),chs,\d+,\d+,\d+,[^,]*,.+\n)", r"Comment: \1", content)
        output = re.sub(r"Comment: (\d+,\d+:\d{2}:\d{2}\.\d{2},\d+:\d{2}:\d{2}\.\d{2},(?P<style>[^,]*),cht,\d+,\d+,\d+,[^,]*,.+\n)", r"Dialogue: \1", output)

        output = re.sub(r"Dialogue: (\d+,\d+:\d{2}:\d{2}\.\d{2},\d+:\d{2}:\d{2}\.\d{2},(?P<style>[^,]*),[^,]*,\d+,\d+,\d+,chs,.+\n)", r"Comment: \1", output)
        output = re.sub(r"Comment: (\d+,\d+:\d{2}:\d{2}\.\d{2},\d+:\d{2}:\d{2}\.\d{2},(?P<style>[^,]*),[^,]*,\d+,\d+,\d+,cht,.+\n)", r"Dialogue: \1", output)
        return output

    def iriya(*subs):
        for sub in subs:
            result = subprocess.run(["iriya", str(sub)], capture_output=False)
            if result.returncode != 0:
                while True:
                    x = input("Iriya returned an error. Continue? (Y/N)\a")
                    if x[0].lower() == 'y':
                        break
                    if x[0].lower() == 'n':
                        exit(3)
                    print("Please enter Y or N.")

    def check_matrix(content:str)->None:
        m = re.search(r"YCbCr Matrix: (.*)\n", content)
        if not m:
            print(f"WARNING: YCbCr Matrix value is not assgined. Please make sure it is intended.\a")
            return

        if m[1] != "TV.709":
            print(f"WARNING: YCbCr Matrix = {m[1]} is not TV.709. Please make sure it is intended.\a")

    def check_asterisk(content:str)->None:
        m = re.findall(r"\n(.*\{[^}]*\*[^{]*\}.*)\n", content)
        for s in m:
            print(s)



    if __name__ == '__main__':
        parser = argparse.ArgumentParser(description="One key Fanhua and clean ass garbage.")
        parser.add_argument(dest='files', type=str, action='store',
                            nargs='+', const=None, default=None,
                            help='Enter a source ass file to be processed.')
        parser.add_argument("-s", "--silent", dest='silent', action="store_true",
                            help="Do not show diff. \nDefault = show diff")
        parser.add_argument("-c", "--no-auto-comment", dest='comment', action="store_false",
                            help="Do not auto comment. This feature requires to mark 'chs'/'cht' in Name or Effect field.")
        parser.add_argument("-i", "--no-iriya", dest='iriya', action="store_false",
                            help="Do not use iriya to check font availability. Default = check")
        parser.add_argument("-m", "--no-matrix-check", dest="matrix_check", action="store_false",
                            help="Do not show warning when YCbCr Matrix is not TV.709. Default = Show warning")
        parser.add_argument("-a", "--no-auto-meta", dest="metadata", action="store_false",
                            help="Do not change metadata (Title, Original Translation etc.). Default = Auto clean metadata")
        parser.add_argument("--nonstop", dest="stop", action="store_false",
                            help="Do not need to press enter to exit. It is useful when using this script in automation.")
        parser.add_argument("--no-asterisk", dest="asterisk", action="store_false",
                            help="Do not print out all lines with asterisks in curly bracket e.g. { * }")
        args = parser.parse_args()

        for f in args.files:
            filename = Path(f).resolve()
            
            print (f"Processing {filename}")
            contents = read_ass(filename)

            if args.metadata:
                contents = auto_metadata(contents, filename)
            
            chs = filename.with_stem(filename.stem + '.chs_jpn')
            cht = filename.with_stem(filename.stem + '.cht_jpn')

            with open(chs, "w", encoding="utf-8") as file:
                file.write(contents)

            twTC = ass_zhconvert_sctc(contents)

            if twTC[0] != "\ufeff":
                twTC = "\ufeff" + twTC

            # 简繁注释转换
            if args.comment:
                twTC = auto_comment(twTC)
            
            with open(cht, 'w', encoding='utf-8') as file:
                file.write(twTC)

            # 生成 diff
            if args.asterisk:
                print("The following line(s) might need your attention:")
                check_asterisk(contents)
                print("\n--------------------------------------\n")
            
            if args.iriya:
                print("iriya report:")
                iriya(chs, cht)
                print("\n--------------------------------------\n")

            if args.matrix_check:
                check_matrix(contents)
            

        if args.stop:
            input("Press enter to exit.")

except Exception as e:
    traceback.print_exception(type(e), value=e, tb=e.__traceback__)
    os.system("pause")

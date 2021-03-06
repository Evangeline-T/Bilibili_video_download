# !/usr/bin/python
# -*- coding:utf-8 -*-

'''
项目: B站视频下载 - 多线程下载

版本1: 加密API版,不需要加入cookie,直接即可下载1080p视频

20190422 - 增加多P视频单独下载其中一集的功能
20190702 - 增加视频多线程下载 速度大幅提升
20201125 - 取消视频合并功能；模块化；保存文件地址修改 by Evangeline
TODO: 
    如果要下载100多集连续video，需要断点下载，记录cid，方便下次继续下载。
下载完成后再删除临时保存的cid文件
'''

import requests, time, hashlib, urllib.request, re, json
import os, sys, threading


def parse_page(url, parameters=None):
    """Fetch page content with configured headers."""
    headers = {
        'user-agent':('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_6) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/84.0.4147.105 Safari/537.36'),
        'accept-language':'zh-CN,zh;q=0.9,en;q=0.8'}
    res = requests.get(url, params=parameters, headers=headers)
    return res


class BiliSpider(object):
    """Spider to get video_list for download_video function.
    Input:
        link: string, url for video or bvid or avid.
    Return:
        start_url: string, 'https://api.bilibili.com/x/web-interface/view?bvid=BV1Ra4y1L7tT'
        cid_list: list of dictionary
    """
    def __init__(self, link):
        self.start = link

    def get_bvid_from_aid(self, aid):
        """Get bvid using aid, generated from get_aid function.
        Build connection to get json data.
        aid: string
        Return bvid: string
        """
        url = 'https://api.bilibili.com/x/web-interface/archive/stat'
        parameters = {'aid':aid}
        res = parse_page(url, parameters)
        info = json.loads(res.text)
        bvid = info['data']['bvid']
        return bvid    
              
    def bvid_from_input(self):
        """Get bvid from link or get_bvid function.
        Update self.bvid:string; self.start_url
        """
        for part in self.start.split('/'):
            if part.startswith('BV'):  # 输入bvid号码，数字+字母；也可以从link中提取
               return part.split('?')[0]
            elif part.startswith('av'):      # 从link中提取avid号码
                aid = part.split('?')[0][2:]  # delete 'av' at the begining
                return self.get_bvid_from_aid(aid)
            elif part.isdigit():  # 输入avid号码，纯数字
                return self.get_bvid_from_aid(part)
    
    def collect_cid_list(self):
        """Return cid from start_url for get_play_list function."""
        bvid = self.bvid_from_input()
        start_url = 'https://api.bilibili.com/x/web-interface/view?bvid=' + bvid
        
        html = parse_page(start_url).json()
        data = html['data']
        folderTitle = data['title'].replace(' ', '_')
        folderTitle = re.sub(r'[\/\\:*?"<>|]', '', folderTitle)  # 替换为空的
        cid_list = []
        if '?p=' in self.start:  # https://www.bilibili.com/video/BV1Zs411x7q7?p=6
            # 单独下载分P视频中的一集
            p = self.start.split('?p=')[-1]
            if p.isdigit():
                cid_list.append(data['pages'][int(p) - 1])
            else:
                print(f'p is {p}, it should be digits.')
        else:
            # 如果p不存在就是全集下载
            cid_list = data['pages']
        return start_url, cid_list, folderTitle
    

# 下载视频进度条显示
'''
 urllib.urlretrieve 的回调函数：
def callbackfunc(blocknum, blocksize, totalsize):
    @blocknum:  已经下载的数据块
    @blocksize: 数据块的大小
    @totalsize: 远程文件的大小
'''
def Schedule_cmd(blocknum, blocksize, totalsize):
    speed = (blocknum * blocksize) / (time.time() - start_time)
    # speed_str = " Speed: %.2f" % speed
    speed_str = " Speed: %s" % format_size(speed)
    recv_size = blocknum * blocksize

    # 设置下载进度条
    f = sys.stdout
    pervent = recv_size / totalsize
    percent_str = "%.2f%%" % (pervent * 100)
    n = round(pervent * 50)
    s = ('#' * n).ljust(50, '-')
    f.write(percent_str.ljust(8, ' ') + '[' + s + ']' + speed_str)
    f.flush()
    # time.sleep(0.1)
    f.write('\r')


def Schedule(blocknum, blocksize, totalsize):
    speed = (blocknum * blocksize) / (time.time() - start_time)
    # speed_str = " Speed: %.2f" % speed
    speed_str = " Speed: %s" % format_size(speed)
    recv_size = blocknum * blocksize

    # 设置下载进度条
    f = sys.stdout
    pervent = recv_size / totalsize
    percent_str = "%.2f%%" % (pervent * 100)
    n = round(pervent * 50)
    s = ('#' * n).ljust(50, '-')
    print(percent_str.ljust(6, ' ') + '-' + speed_str)
    f.flush()
    time.sleep(2)
    # print('\r')


# 字节bytes转化K\M\G
def format_size(bytes):
    try:
        bytes = float(bytes)
        kb = bytes / 1024
    except:
        print("传入的字节格式不对")
        return "Error"
    if kb >= 1024:
        M = kb / 1024
        if M >= 1024:
            G = M / 1024
            return "%.3fG" % (G)
        else:
            return "%.3fM" % (M)
    else:
        return "%.3fK" % (kb)


#  下载视频主程序
def down_video(video_list, title, start_url, page, currentVideoPath):
    """下载每一P的video_list.title:每一P的标题，分集标题"""
    print('[正在下载P{}段视频,请稍等...]:'.format(page) + title)
    # currentVideoPath = os.path.join(sys.path[0], 'bilibili_video', title)  # 当前目录作为下载目录 TODO title 改成总集名字？
    # if not os.path.exists(currentVideoPath):
    #     os.makedirs(currentVideoPath)  # 建立分集文件夹
    for i, v_url in enumerate(video_list):               # 下载分集下的所有分割视频
        opener = urllib.request.build_opener()
        # 请求头
        opener.addheaders = [
            # ('Host', 'upos-hz-mirrorks3.acgvideo.com'),  #注意修改host,不用也行
            ('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.13; rv:56.0) Gecko/20100101 Firefox/56.0'),
            ('Accept', '*/*'),
            ('Accept-Language', 'en-US,en;q=0.5'),
            ('Accept-Encoding', 'gzip, deflate, br'),
            ('Range', 'bytes=0-'),  # Range 的值要为 bytes=0- 才能下载完整视频
            ('Referer', start_url),  # 注意修改referer,必须要加的!
            ('Origin', 'https://www.bilibili.com'),
            ('Connection', 'keep-alive'),
        ]
        urllib.request.install_opener(opener)
        # # 创建文件夹存放下载的视频
        # if not os.path.exists(currentVideoPath):
        #     os.makedirs(currentVideoPath)
        # 开始下载
        if len(video_list) > 1:
            urllib.request.urlretrieve(url=v_url, filename=os.path.join(currentVideoPath, r'{}-{}.flv'.format(title, i+1)),reporthook=Schedule_cmd)  # 写成mp4也行  title + '-' + num + '.flv'
        else:
            urllib.request.urlretrieve(url=v_url, filename=os.path.join(currentVideoPath, r'{}.flv'.format(title)),reporthook=Schedule_cmd)  # 写成mp4也行  title + '-' + num + '.flv'

# # 合并视频(20190802新版)
# def combine_video(title_list):
#     video_path = os.path.join(sys.path[0], 'bilibili_video')  # 下载目录
#     for title in title_list:
#         current_video_path = os.path.join(video_path ,title)
#         if len(os.listdir(current_video_path)) >= 2:
#             # 视频大于一段才要合并
#             print('[下载完成,正在合并视频...]:' + title)
#             # 定义一个数组
#             L = []
#             # 遍历所有文件
#             for file in sorted(os.listdir(current_video_path), key=lambda x: int(x[x.rindex("-") + 1:x.rindex(".")])):
#                 # 如果后缀名为 .mp4/.flv
#                 if os.path.splitext(file)[1] == '.flv':
#                     # 拼接成完整路径
#                     filePath = os.path.join(current_video_path, file)
#                     # 载入视频
#                     video = VideoFileClip(filePath)
#                     # 添加到数组
#                     L.append(video)
#             # 拼接视频
#             final_clip = concatenate_videoclips(L)
#             # 生成目标视频文件
#             final_clip.to_videofile(os.path.join(current_video_path, r'{}.mp4'.format(title)), fps=24, remove_temp=False)
#             print('[视频合并完成]' + title)
#         else:
#             # 视频只有一段则直接打印下载完成
#             print('[视频合并完成]:' + title)


class BiliRobot(object):
    """BiliRobot has a Spider to collect cid_list, and a DownloadProcess."""
    def __init__(self, link, quality):
        """link: url, avid or bvid
           quality: video quality, string
        """
        self.Spider = BiliSpider(link)
        self.quality = quality

        # 访问API地址
    def get_play_list(self, start_url, cid, quality):  # TODO change quality to top
        entropy = 'rbMCKn@KuamXWlPMoJGsKcbiJKUfkPF_8dABscJntvqhRSETg'
        appkey, sec = ''.join([chr(ord(i) + 2) for i in entropy[::-1]]).split(':')
        params = 'appkey=%s&cid=%s&otype=json&qn=%s&quality=%s&type=' % (appkey, cid, quality, quality)
        chksum = hashlib.md5(bytes(params + sec, 'utf8')).hexdigest()
        url_api = 'https://interface.bilibili.com/v2/playurl?%s&sign=%s' % (params, chksum)
        headers = {
            'Referer': start_url,  # 注意加上referer
            'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/55.0.2883.87 Safari/537.36'
        }
        # print(url_api)
        html = requests.get(url_api, headers=headers).json()
        # print(json.dumps(html))
        video_list = []
        for i in html['durl']:
            video_list.append(i['url'])
        # print(video_list)
        return video_list

    def downlod_videos(self):
        """Major download process."""
        # 获取cid_list
        initial_url, cid_list, folderTitle = self.Spider.collect_cid_list()
        
        # create folder for the video
        currentVideoPath = os.path.join(sys.path[0], 'bilibili_video', folderTitle)  # 当前目录作为下载目录 TODO title 改成总集名字？
        if not os.path.exists(currentVideoPath):
            os.makedirs(currentVideoPath)  # 建总集文件夹

        # 创建线程池， 还没开始下载
        threadpool = []
        title_list = []
        for item in cid_list:       # item is dictionary
            cid = str(item['cid'])
            title = item['part']
            if title == '':
                title = folderTitle
            title = re.sub(r'[\/\\:*?"<>|]', '', title)  # 替换为空的
            print('[下载视频的cid]:' + cid)
            print('[下载视频的标题]:' + title)
            title_list.append((cid, title))
            page = str(item['page'])
            start_url = initial_url + "/?p=" + page
            video_list = self.get_play_list(start_url, cid, self.quality)
            # down_video(video_list, title, start_url, page)
            # 定义线程
            th = threading.Thread(target=down_video, args=(video_list, title, start_url, page, currentVideoPath))
            # 将线程加入线程池
            threadpool.append(th)

        # 开始线程， 开始下载
        for th in threadpool:
            th.start()
        # 等待所有线程运行完毕
        for th in threadpool:
            th.join()

        # 最后合并视频
        print('MISSION COMPLETE', title_list, f'{len(title_list)} / {len(cid_list)}')
        # TODO 删除临时文件，cid_list.json, downloaded_cid.txt
        # combine_video(title_list)

if __name__ == '__main__':
    # 用户输入av号或者视频链接地址
    print('*' * 30 + 'B站视频下载小助手' + '*' * 30)
    start = input('请输入您要下载的B站av号或者视频链接地址:')
    quality = input('请输入您要下载视频的清晰度(1080p:80;720p:64;480p:32;360p:16)(填写80或64或32或16)\n按回车默认720p，如果视频提供的清晰度低于此，默认下载视频最高清晰度:')
    quality = '64' if quality =='' else quality
    # folderName = input('请输入您希望存放视频的文件夹，不要有空格，使用下划线代替空格:')

    # 开始运行主程序
    start_time = time.time()
    robot = BiliRobot(start, quality)
    robot.downlod_videos()     
    end_time = time.time()  # 结束时间

    # 程序结束，报告下载用时
    print('下载总耗时%.2f秒,约%.2f分钟' % (end_time - start_time, int(end_time - start_time) / 60))
    # 如果是windows系统，下载完成后打开下载目录
    currentVideoPath = os.path.join(sys.path[0], 'bilibili_video')  # 当前目录作为下载目录
    if (sys.platform.startswith('win')):
        os.startfile(currentVideoPath)


# 分P视频下载测试: https://www.bilibili.com/video/av19516333/
# 下载总耗时14.21秒,约0.23分钟

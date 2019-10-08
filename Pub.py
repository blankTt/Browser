import null as null
import requests
import pymysql
import re
from soupsieve.util import lower
from bs4 import BeautifulSoup
from pdfminer.pdfparser import PDFParser, PDFDocument, PDFSyntaxError
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import LAParams, LTTextBox
from pdfminer.pdfinterp import PDFTextExtractionNotAllowed
from rake import Rake

'''
@author blank

'''
root_url = 'https://www.ml4aad.org/automl/literature-on-neural-architecture-search/' #网页url
list  = []  #all except list5
list1 = []  #出版实现爬虫下载pdf并且解析内容进行分类
list2 = []  #未出版
list3 = []  #属于EC
list4 = []  #不属于EC
list5 = []  #有问题的
list6 = []  #处理手动下载

# 连接database
conn = pymysql.connect(
    host="127.0.0.1",
    port=3306,
    user="root",
    password="123456",
    database="crawer",
    charset="utf8"
)
# 得到一个可以执行SQL语句的光标对象
cursor = conn.cursor()

def get_page(url):
    page = requests.get(url)
    html = page.text
    return html

def get_list_all(html):
    soup = BeautifulSoup(html, "html.parser")
    data = soup.select('#post-722 > ul > li')
    for item in data:
        if item is None:
            continue
        var = str(item)
        sstr = item.get_text()
        '''
        截取paper的标题和链接
        每一篇文章都有()分隔，但要特别注意有些标题有嵌套括号
        部分文章链接没有<a>标签，经确定文章已被下架，或者有些文章直接没有链接，统一按照没有用<a></a>标签处理，对于这些文章存储在其他表中,
        部分文章url失效，404处理
        部分文章有多个链接,因为后一个链接比较新，所以直接采用后一个链接作为主要链接
        '''
        if(var.find('<a')  < 0): #没有链接或者链接不可用(没有<a>标签)
            dict = {
                "title": sstr[0:sstr.rfind('(')],
                "problem": "link is wrong"
            }
            list5.append(dict)
            continue

        dict = {
            "title": sstr[0:sstr.rfind('(')], #从后往前查找'('
            "link": sstr[sstr.rfind('http'):] #从后往前查找'http'(一般情况是查找')'但是可能存在多个链接，所以查找'http')
        }

        if (var.find('<strong>') != -1): #通过<strong>标签来区分出版和未出版(如果出版，显示的标题是粗体)
            list1.append(dict)
        else:
            list2.append(dict)

def get_urls(list):
    pdfs = []
    for item in list:
        if (item["link"][-4:] == '.pdf'): #链接后缀直接有.pdf,可以直接下载，首先处理
            pdfs.append(item)

        elif(item["link"].find("https://arxiv.org/abs")>=0): # 处理此类url https://arxiv.org/abs/1909.02453
            temp1 = "https://arxiv.org/pdf/"
            temp1 += item["link"][-10:]
            temp = item
            temp["link"] = temp1
            pdfs.append(temp)

        elif(item["link"].find("https://link.springer.com/chapter")>=0):  #处理https://link.springer.com/chapter/10.1007/978-3-030-13001-5_12
            temp2 = "https://link.springer.com/content/pdf/"
            temp2 += item["link"][-28:] + ".pdf"
            temp = item
            temp["link"] = temp2
            pdfs.append(temp)

        elif(item["link"].find("https://ieeexplore.ieee.org")>=0):     #处理https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber=8791709
            temp3 = "https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber="
            temp3 += item["link"][-7:]
            temp = item
            temp["link"] = temp3
            pdfs.append(temp)

        elif(item["link"].find("https://openreview.net")>=0):   #处理https://openreview.net/forum?id=Syg3FDjntN and https://openreview.net/pdf?id=BJ-MRKkwG
            if(item["link"][23:28] == 'forum'):
                var = item["link"].replace("forum","pdf")
                temp = item
                temp["link"] = var
                pdfs.append(temp)
            else:
                pdfs.append(item)
            continue

        elif(item["link"].find("https://www.mitpressjournals.org") >= 0): # 处理https://www.mitpressjournals.org/doi/abs/10.1162/evco_a_00253
            var = item["link"].replace("abs", "pdf")
            temp = item
            temp["link"] = var
            pdfs.append(temp)

        elif(item["link"].find("https://www.nature.com") >= 0): #处理https://www.nature.com/articles/s42256-018-0006-z
            temp = item
            temp["link"] = item["link"]+'.pdf'
            pdfs.append(temp)

        elif(item["link"].find("https://www.worldscientific.com") >= 0):  # 处理https://www.worldscientific.com/doi/abs/10.1142/S1469026818500086
            var = item["link"].replace("abs", "pdf")
            temp = item
            temp["link"] = var
            pdfs.append(temp)

        elif(item["link"].find("https://papers.nips.cc") >= 0):   # 处理https://papers.nips.cc/paper/207-the-cascade-correlation-learning-architecture
            temp = item
            temp["link"] = item["link"] + ".pdf"
            pdfs.append(temp)

        elif(item["link"].find("https://hal.archives-ouvertes.fr") >= 0):   #直接下载
            pdfs.append(item)

        elif(item["link"].find("http://www.complex-systems.com") >= 0): #处理http://www.complex-systems.com/abstracts/v04_i04_a06/
            # 链接无法自动下载，所以改为手动
            dict = {
                "title" : str(item["title"]),
                "problem" : "can not be downloaded automatically"
            }
            list5.append(dict)
            list6.append(item)
        
        elif (item["link"].find("https://www.sciencedirect.com") >= 0):  # 处理https://www.sciencedirect.com/science/article/pii/S1361841518307734
            # 链接无法自动下载，所以改为手动
            dict = {
                "title" : str(item["title"]),
                "problem" : "can not be downloaded automatically"
            }
            list5.append(dict)
            list6.append(item)

        elif (item["link"].find("https://dl.acm.org") >= 0):  # 处理https://dl.acm.org/citation.cfm?id=2834896
            # 链接无法自动下载，所以改为手动
            dict = {
                "title": item["title"],
                "problem": "can not be downloaded automatically"
            }
            if (item["link"] == "https://dl.acm.org/citation.cfm?id=94034"):
                dict["problem"] = "the pdf does not exist"
                list5.append(dict)
            else:
                list6.append(item)
        else:
            dict = {
                "title": item["title"],
                "problem": "Unknown"
            }
            list5.append(dict)

        #if(requests.head(item["link"]).status_code == 404):
        #    dict = {
        #        "title" : item["title"],
        #        "problem" : "link is wrong"
        #    }
        #    list5.append(dict)
        #    continue

    return pdfs


def download_pdf(pdfs):
    i = 1
    for pdf in pdfs:
        path = r"D:\\Download\\autoDocuments\\" + str(i) + ".pdf"
        r = requests.get(pdf["link"])
        f = open(path,"wb")
        f.write((r.content))
        i += 1
    f.close()

def out_data1():  #分类已出版还是未出版、

    sql1 = "INSERT IGNORE INTO pub(title,link) VALUES (%s,%s);"
    sql2 = "INSERT IGNORE INTO unpub(title,link) VALUES (%s,%s);"
    for item in list1:
        cursor.execute(sql1, [item['title'], item['link']])
    for item in list2:
        cursor.execute(sql2, [item['title'], item['link']])
    conn.commit()

def out_data2():  # 分类EC和notEC

    sql1 = "INSERT IGNORE INTO ec(title,link) VALUES (%s,%s);"
    sql2 = "INSERT IGNORE INTO unec(title,link) VALUES (%s,%s);"
    for item in list3:
        cursor.execute(sql1, [item['title'], item['link']])
    for item in list4:
        cursor.execute(sql2, [item['title'], item['link']])
    conn.commit()
    cursor.close()
    conn.close()

def out_data3():  # 分类有问题的

    sql = "INSERT IGNORE INTO problem(title,problem) VALUES (%s,%s);"
    for item in list5:
        cursor.execute(sql, [item['title'], item['problem']])
    conn.commit()


def out_data4():
    sql = "INSERT IGNORE INTO hand(title,link) VALUES (%s,%s);"
    for item in list6:
        cursor.execute(sql, [item['title'], item['link']])
    conn.commit()

def pdf_miner_word(pdf,path):     #得到文档abstract中的内容
    try:
        # 用文件对象来创建一个pdf文档分析器
        praser = PDFParser(open(path, 'rb'))
        # 创建一个PDF文档
        doc = PDFDocument()
        # 连接分析器 与文档对象
        praser.set_document(doc)
        doc.set_parser(praser)

        # 提供初始化密码
        # 如果没有密码 就创建一个空的字符串
        doc.initialize()

        # 检测文档是否提供txt转换，不提供就忽略
        if not doc.is_extractable:
            raise PDFTextExtractionNotAllowed
        else:
            # 创建PDf 资源管理器 来管理共享资源
            rsrcmgr = PDFResourceManager()
            # 创建一个PDF设备对象
            laparams = LAParams()
            device = PDFPageAggregator(rsrcmgr, laparams=laparams)
            # 创建一个PDF解释器对象
            interpreter = PDFPageInterpreter(rsrcmgr, device)

            # 循环遍历列表，每次处理一个page的内容
            for page in doc.get_pages():
                interpreter.process_page(page)
                # 接受该页面的LTPage对象
                layout = device.get_result()
                # 这里layout是一个LTPage对象，里面存放着这个 page 解析出的各种对象
                # 包括 LTTextBox, LTFigure, LTImage, LTTextBoxHorizontal 等
                list = []
                for x in layout:
                    if isinstance(x, LTTextBox):
                        list.append(lower(x.get_text().strip()))
                strinfo = re.compile(' ')
                for i in range(len(list)):
                    if (strinfo.sub('', list[i]) == 'abstract'):
                        if(path[-6:-4]=='h6'):
                            return list[i+3]
                        elif(path[-6:-4]=='h8'):
                            return list[i+4]
                        else:
                            return list[i+1]
                    elif (list[i][0:8] == 'abstract'):
                        return list[i][9:]
                    elif (list[i] == '1 introduction'):
                        return list[i+1]
                    elif (list[i] == 'summary'):
                        return list[i+1]
    except PDFSyntaxError:
        dict = {
            "title" : pdf['title'],
            "problem" : "fail to open pdf"
        }
        list5.append(dict)

def load_match_words(match_word_file):
    match_words = []
    for line in open(match_word_file):
        if line.strip()[0:1] != "#":
            for word in line.split():  # in case more than one per line
                match_words.append(lower(word))
    return match_words

def pre_process_abstract(abstract): #预处理abstract的单词内容
    abstract.strip()
    abstract.replace('-','')
    return abstract


def abstract_analyze(pdf,abstract):
    match_word_file = "Matchlist.txt"
    match = load_match_words(match_word_file)
    stop_words_path = "SmartStoplist.txt"
    r = Rake(stop_words_path)
    temp= r.run(abstract)
    matched = []
    for item in temp:
        if(item[1] >= 3):          #以分数3的界限分隔
            matched.append(item)
    matched = temp
    flag = False
    for item in matched:
        if(item[0] in match):
            list3.append(pdf)
            flag = True
            break
    if(flag == False):
        list4.append(pdf)


if __name__=='__main__':
    get_list_all(get_page(root_url))

    #out_data1()
    list = list1 + list2
    pdfs = get_urls(list)

    #out_data4()
    print("Downloading...")
    #download_pdf(pdfs)
    print("Download finish")

    for i in range(len(pdfs)):
        path = "D:\Download\\autoDocuments\\" + str(i+1) + ".pdf"
        if(pdf_miner_word(pdfs[i],path) != None):
           abstract_analyze(pdfs[i],pre_process_abstract(pdf_miner_word(pdfs[i],path)))

    for i in range(len(list6)):
        link = "http://www.blanktt.top/Browser/unautoDocuments/h" + str(i+1) + ".pdf"
        list6[i]['link'] = link

    for i in range(len(list6)):
        path = "D:\Download\\unautoDocuments\\h" + str(i+1) + ".pdf"
        if(pdf_miner_word(list6[i],path) != None):
           abstract_analyze(list6[i],pre_process_abstract(pdf_miner_word(list6[i],path)))

    out_data3()
    out_data2()

    print("success!")





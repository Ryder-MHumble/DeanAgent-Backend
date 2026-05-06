from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import asyncpg

from app.config import settings


VENUE = "ICML 2026"
SOURCE_ID = "icml_2026_author_import"
ADDED_BY = "system:icml2026_import"
DEFAULT_REPORT_PATH = Path("data/runtime/icml2026_scholar_import_report.json")


@dataclass(frozen=True)
class ExistingScholar:
    id: str
    name: str
    name_en: str
    university: str
    source_id: str = ""
    icml_paper_uids: tuple[str, ...] = ()
    icml_original_affiliations: tuple[str, ...] = ()


@dataclass
class AuthorIdentity:
    key: str
    name: str
    university: str
    original_affiliations: set[str] = field(default_factory=set)
    paper_uids: set[str] = field(default_factory=set)
    rows: list[dict[str, Any]] = field(default_factory=list)
    scholar_id: str = ""
    match_status: str = "new"
    existing_candidates: list[str] = field(default_factory=list)


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def normalize_person_name(value: Any) -> str:
    text = unicodedata.normalize("NFKC", clean_text(value))
    text = re.sub(r"\s+", " ", text)
    return text.casefold().strip()


def normalize_affiliation_name(value: Any) -> str:
    text = unicodedata.normalize("NFKC", clean_text(value))
    text = text.replace("&", " and ")
    text = text.replace("（", "(").replace("）", ")")
    text = re.sub(r"\s+", " ", text).strip()
    if "," in text:
        parts = [part.strip() for part in re.split(r"[,;]+", text) if part.strip()]
        unique_parts = list(dict.fromkeys(part.casefold() for part in parts))
        if len(unique_parts) == 1:
            text = parts[0]
    text = text.casefold()
    text = re.sub(r"^the\s+", "", text)
    text = re.sub(r"[^0-9a-z\u4e00-\u9fff]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def stable_bigint(*parts: Any) -> int:
    joined = "|".join(clean_text(part) for part in parts)
    digest = hashlib.sha256(joined.encode("utf-8")).digest()
    value = int.from_bytes(digest[:8], "big") & ((1 << 63) - 1)
    return value or 1


def stable_hex(*parts: Any) -> str:
    joined = "|".join(clean_text(part) for part in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def stable_short_id(prefix: str, *parts: Any, length: int = 24) -> str:
    return f"{prefix}_{hashlib.sha1('|'.join(clean_text(p) for p in parts).encode('utf-8')).hexdigest()[:length]}"


_MANUAL_AFFILIATION_TRANSLATIONS_RAW = {
    "Aalto University": "阿尔托大学",
    "Alibaba Group": "阿里巴巴集团",
    "Adobe Systems": "Adobe",
    "Anhui University": "安徽大学",
    "Amazon": "Amazon",
    "Ant Group": "蚂蚁集团",
    "Apple": "Apple",
    "Arizona State University": "亚利桑那州立大学",
    "Anthropic": "Anthropic",
    "Australian National University": "澳大利亚国立大学",
    "Baidu": "百度",
    "Beihang University": "北京航空航天大学",
    "Beijing Institute of Technology": "北京理工大学",
    "Beijing Jiaotong University": "北京交通大学",
    "Beijing Normal University": "北京师范大学",
    "Beijing University of Aeronautics and Astronautics": "北京航空航天大学",
    "Beijing University of Post and Telecommunications": "北京邮电大学",
    "Beijing University of Posts and Telecommunications": "北京邮电大学",
    "Beijing University of Technology": "北京工业大学",
    "Boston University": "波士顿大学",
    "Brown University": "布朗大学",
    "ByteDance Inc.": "字节跳动",
    "ByteDance": "字节跳动",
    "Bytedance": "字节跳动",
    "California Institute of Technology": "加州理工学院",
    "Carnegie Mellon University": "卡内基梅隆大学",
    "Case Western Reserve University": "凯斯西储大学",
    "Central South University": "中南大学",
    "Chinese Academy of Sciences": "中国科学院",
    "China Telecom": "中国电信",
    "China University of Geoscience": "中国地质大学",
    "Chongqing University": "重庆大学",
    "City University of Hong Kong": "香港城市大学",
    "Columbia University": "哥伦比亚大学",
    "Cornell University": "康奈尔大学",
    "Dalian University of Technology": "大连理工大学",
    "Dartmouth College": "达特茅斯学院",
    "Deakin University": "迪肯大学",
    "Duke University": "杜克大学",
    "East China Normal University": "华东师范大学",
    "Emory University": "埃默里大学",
    "EPFL": "洛桑联邦理工学院",
    "EPFL - EPF Lausanne": "洛桑联邦理工学院",
    "ETH Zurich": "苏黎世联邦理工学院",
    "ETHZ - ETH Zurich": "苏黎世联邦理工学院",
    "Facebook": "Meta",
    "Fudan University": "复旦大学",
    "Georgia Institute of Technology": "佐治亚理工学院",
    "Google": "Google",
    "Google DeepMind": "Google DeepMind",
    "Google Research": "Google Research",
    "George Mason University": "乔治梅森大学",
    "Griffith University": "格里菲斯大学",
    "Guangdong University of Technology": "广东工业大学",
    "Hangzhou Dianzi University": "杭州电子科技大学",
    "Hanyang University": "汉阳大学",
    "Harbin Institute of Technology": "哈尔滨工业大学",
    "Harvard University": "哈佛大学",
    "Hong Kong Polytechnic University": "香港理工大学",
    "Hong Kong University of Science and Technology": "香港科技大学",
    "HKUST": "香港科技大学",
    "Harbin Institute of Technology (Shenzhen)": "哈尔滨工业大学（深圳）",
    "Hefei University of Technology": "合肥工业大学",
    "Hunan University": "湖南大学",
    "Huawei Technologies Ltd.": "华为",
    "Huawei Noah's Ark Lab": "华为诺亚方舟实验室",
    "Huazhong Agricultural University": "华中农业大学",
    "Huazhong University of Science and Technology": "华中科技大学",
    "Imperial College London": "帝国理工学院",
    "INRIA": "法国国家信息与自动化研究所",
    "Institute of Automation, Chinese Academy of Sciences": "中国科学院自动化研究所",
    "Institute of automation, Chinese academy of science, Chinese Academy of Sciences": "中国科学院自动化研究所",
    "Institute of Computing Technology, Chinese Academy of Sciences": "中国科学院计算技术研究所",
    "Institute of Information Engineering, Chinese Academy of Sciences": "中国科学院信息工程研究所",
    "Institute of Software, Chinese Academy of Sciences": "中国科学院软件研究所",
    "Indian Institute of Technology, Delhi": "印度理工学院德里分校",
    "International Business Machines": "IBM",
    "Jilin University": "吉林大学",
    "Jinan University": "暨南大学",
    "JD.com": "京东",
    "Johns Hopkins University": "约翰斯·霍普金斯大学",
    "KAIST": "韩国科学技术院",
    "Korea Advanced Institute of Science & Technology": "韩国科学技术院",
    "Korea University": "高丽大学",
    "KTH Royal Institute of Technology": "瑞典皇家理工学院",
    "KU Leuven": "鲁汶大学",
    "Karlsruher Institut für Technologie": "卡尔斯鲁厄理工学院",
    "King Abdullah University of Science and Technology": "阿卜杜拉国王科技大学",
    "Kuaishou- 快手科技": "快手科技",
    "LG AI Research": "LG AI Research",
    "Li Auto Inc.": "理想汽车",
    "Ludwig-Maximilians-Universität München": "慕尼黑大学",
    "Massachusetts Institute of Technology": "麻省理工学院",
    "McGill University": "麦吉尔大学",
    "Macquarie University": "麦考瑞大学",
    "Meituan": "美团",
    "Meta": "Meta",
    "Microsoft": "Microsoft",
    "Microsoft Research": "Microsoft Research",
    "Microsoft Research Asia": "微软亚洲研究院",
    "Michigan State University": "密歇根州立大学",
    "MIT": "麻省理工学院",
    "Mohamed bin Zayed University of Artificial Intelligence": "穆罕默德·本·扎耶德人工智能大学",
    "Monash University": "蒙纳士大学",
    "Nanjing University": "南京大学",
    "nanjing university": "南京大学",
    "Nanjing University of Aeronautics and Astronautics": "南京航空航天大学",
    "Nanjing University of Science and Technology": "南京理工大学",
    "Nankai University": "南开大学",
    "Nanyang Technological University": "南洋理工大学",
    "National University of Defense Technology": "国防科技大学",
    "National University of Singapore": "新加坡国立大学",
    "National Yang Ming Chiao Tung University": "台湾阳明交通大学",
    "Nanjing University of Posts and Telecommunications": "南京邮电大学",
    "New York University": "纽约大学",
    "Northeastern University": "东北大学",
    "Northwestern University": "西北大学",
    "Northwest Polytechnical University Xi'an": "西北工业大学",
    "NVIDIA": "NVIDIA",
    "OpenAI": "OpenAI",
    "Pennsylvania State University": "宾夕法尼亚州立大学",
    "Peking University": "北京大学",
    "Pohang University of Science and Technology": "浦项科技大学",
    "POSTECH": "浦项科技大学",
    "Princeton University": "普林斯顿大学",
    "Purdue University": "普渡大学",
    "Qualcomm AI Research": "Qualcomm AI Research",
    "Renmin University of China": "中国人民大学",
    "Rice University": "莱斯大学",
    "Rutgers University": "罗格斯大学",
    "Samsung": "Samsung",
    "Scale AI": "Scale AI",
    "Seoul National University": "首尔国立大学",
    "Shandong University": "山东大学",
    "Shanghai AI Laboratory": "上海人工智能实验室",
    "Shanghai Artificial Intelligence Laboratory": "上海人工智能实验室",
    "Shanghai Jiaotong University": "上海交通大学",
    "Shanghai Jiao Tong University": "上海交通大学",
    "Shanghai University of Finance and Economics": "上海财经大学",
    "ShanghaiTech University": "上海科技大学",
    "Shanxi University": "山西大学",
    "Shenzhen University": "深圳大学",
    "Sichuan University": "四川大学",
    "Singapore Management University": "新加坡管理大学",
    "Singapore University of Technology and Design": "新加坡科技设计大学",
    "South China University of Technology": "华南理工大学",
    "Soochow University": "苏州大学",
    "Southeast University": "东南大学",
    "Southern University of Science and Technology": "南方科技大学",
    "Stanford University": "斯坦福大学",
    "SUN YAT-SEN UNIVERSITY": "中山大学",
    "Sungkyunkwan University": "成均馆大学",
    "Southwest Jiaotong University": "西南交通大学",
    "Technical University of Munich": "慕尼黑工业大学",
    "Technion": "以色列理工学院",
    "Technion - Israel Institute of Technology, Technion": "以色列理工学院",
    "Technische Universität München": "慕尼黑工业大学",
    "Technische Universität Berlin": "柏林工业大学",
    "Technische Universität Darmstadt": "达姆施塔特工业大学",
    "Tel Aviv University": "特拉维夫大学",
    "Tencent": "腾讯",
    "Tencent AI Lab": "腾讯 AI Lab",
    "Tencent Youtu Lab": "腾讯优图实验室",
    "Texas A&M University - College Station": "德州农工大学",
    "Texas A&M University": "德州农工大学",
    "The Chinese University of Hong Kong": "香港中文大学",
    "Chinese University of Hong Kong": "香港中文大学",
    "The Chinese University of Hong Kong, Shenzhen": "香港中文大学（深圳）",
    "The Hong Kong University of Science and Technology": "香港科技大学",
    "The Hong Kong University of Science and Technology (Guangzhou)": "香港科技大学（广州）",
    "The University of Hong Kong": "香港大学",
    "The University of Tokyo": "东京大学",
    "Tianjin University": "天津大学",
    "Tongji University": "同济大学",
    "Tsinghua University": "清华大学",
    "Tsinghua University, Tsinghua University": "清华大学",
    "UC Berkeley": "加州大学伯克利分校",
    "UCLA": "加州大学洛杉矶分校",
    "Ulsan National Institute of Science and Technology": "蔚山科学技术院",
    "Université de Montréal": "蒙特利尔大学",
    "University College London": "伦敦大学学院",
    "University College London, University of London": "伦敦大学学院",
    "University of Alberta": "阿尔伯塔大学",
    "University of Amsterdam": "阿姆斯特丹大学",
    "University of British Columbia": "英属哥伦比亚大学",
    "University of Arizona": "亚利桑那大学",
    "University of California, Berkeley": "加州大学伯克利分校",
    "University of California, Davis": "加州大学戴维斯分校",
    "University of California, Irvine": "加州大学欧文分校",
    "University of California, Los Angeles": "加州大学洛杉矶分校",
    "University of California, Riverside": "加州大学河滨分校",
    "University of California, Santa Barbara": "加州大学圣塔芭芭拉分校",
    "University of California, San Diego": "加州大学圣地亚哥分校",
    "University of Cambridge": "剑桥大学",
    "University of Chicago": "芝加哥大学",
    "University of Central Florida": "中佛罗里达大学",
    "University of Chinese Academy of Sciences": "中国科学院大学",
    "University of Copenhagen": "哥本哈根大学",
    "University of Edinburgh": "爱丁堡大学",
    "University of Electronic Science and Technology of China": "电子科技大学",
    "University of Hong Kong": "香港大学",
    "University of Illinois at Urbana-Champaign": "伊利诺伊大学厄巴纳-香槟分校",
    "University of Illinois Urbana-Champaign": "伊利诺伊大学厄巴纳-香槟分校",
    "University of Illinois at Chicago": "伊利诺伊大学芝加哥分校",
    "University of Macau": "澳门大学",
    "University of Maryland, College Park": "马里兰大学帕克分校",
    "University of Michigan": "密歇根大学",
    "University of Melbourne": "墨尔本大学",
    "University of Minnesota - Twin Cities": "明尼苏达大学双城分校",
    "University of Michigan - Ann Arbor": "密歇根大学安娜堡分校",
    "University of North Carolina at Chapel Hill": "北卡罗来纳大学教堂山分校",
    "University of Notre Dame": "圣母大学",
    "University of Oxford": "牛津大学",
    "University of Pennsylvania": "宾夕法尼亚大学",
    "University of Science and Technology of China": "中国科学技术大学",
    "University of Science and Technology Beijing": "北京科技大学",
    "University of Southern California": "南加州大学",
    "University of Sydney": "悉尼大学",
    "University of Technology Sydney": "悉尼科技大学",
    "University of Tübingen": "蒂宾根大学",
    "University of Texas at Austin": "德克萨斯大学奥斯汀分校",
    "University of the Chinese Academy of Sciences": "中国科学院大学",
    "University of Toronto": "多伦多大学",
    "University of Virginia": "弗吉尼亚大学",
    "University of Virginia, Charlottesville": "弗吉尼亚大学",
    "University of Washington": "华盛顿大学",
    "University of Waterloo": "滑铁卢大学",
    "University of Wisconsin - Madison": "威斯康星大学麦迪逊分校",
    "University of New South Wales": "新南威尔士大学",
    "Vanderbilt University": "范德堡大学",
    "Virginia Polytechnic Institute and State University": "弗吉尼亚理工大学",
    "Virginia Tech": "弗吉尼亚理工大学",
    "Westlake University": "西湖大学",
    "Wuhan University": "武汉大学",
    "Xi'an Jiaotong University": "西安交通大学",
    "Xiamen University": "厦门大学",
    "Xidian University": "西安电子科技大学",
    "Xi'an University of Electronic Science and Technology": "西安电子科技大学",
    "Xiaomi Corporation": "小米",
    "Xiaohongshu": "小红书",
    "Yale University": "耶鲁大学",
    "Yonsei University": "延世大学",
    "Zhejiang University": "浙江大学",
}

MANUAL_AFFILIATION_TRANSLATIONS = {
    normalize_affiliation_name(key): value for key, value in _MANUAL_AFFILIATION_TRANSLATIONS_RAW.items()
}


_DOMESTIC_AFFILIATION_PATTERNS_RAW: list[tuple[str, str]] = [
    (r"\bhkust\b.*\b(gz|guangzhou|guang zhou)\b", "香港科技大学（广州）"),
    (
        r"\bhong kong university of science and technology\b.*\b(gz|guangzhou|guang zhou|guangdong)\b",
        "香港科技大学（广州）",
    ),
    (r"\bcuhk\b.*\b(sz|shenzhen|shen zhen)\b", "香港中文大学（深圳）"),
    (r"\bcuhk\b", "香港中文大学"),
    (r"\bchinese university of hong\s*kong\b.*\b(shenzhen|shen zhen)\b", "香港中文大学（深圳）"),
    (r"\bchinese university of hong\s*kong\b", "香港中文大学"),
    (r"\bcity university of hong kong\b.*\bdongguan\b", "香港城市大学（东莞）"),
    (r"\bhong kong polytechnic university\b.*\bshenzhen\b", "香港理工大学深圳研究院"),
    (r"\bhong kong metropolitan university\b", "香港都会大学"),
    (r"\bhong kong baptist univer", "香港浸会大学"),
    (r"\beducation university of hong kong\b", "香港教育大学"),
    (r"\bthe education university of hong kong\b", "香港教育大学"),
    (r"\bhkust\b", "香港科技大学"),
    (r"\bhong kong univer.*science.*technology\b", "香港科技大学"),
    (r"\bcity university of macau\b", "澳门城市大学"),
    (r"\b(macao|macau) university of science", "澳门科技大学"),
    (r"\b(macao|macau) polytechnic university\b", "澳门理工大学"),
    (r"\buniversity of macao\b", "澳门大学"),
    (r"\bnational taiwan univ", "台湾大学"),
    (r"\bnational tsing hua university\b", "台湾清华大学"),
    (r"\bzhejiang university of science and technology\b", "浙江科技大学"),
    (r"\bzhejiang sci tech university\b", "浙江理工大学"),
    (r"\bzhejiang university of technology\b", "浙江工业大学"),
    (r"\bzhejiang normal university\b", "浙江师范大学"),
    (r"\bzhejiang gongshang university\b", "浙江工商大学"),
    (r"\bzhejiang chinese medical university\b", "浙江中医药大学"),
    (r"\bzhejiang univer", "浙江大学"),
    (r"\bwestlake university\b", "西湖大学"),
    (r"\bshanghai aritifcal intelligence\b", "上海人工智能实验室"),
    (r"\bshanghai artificial intelligence\b", "上海人工智能实验室"),
    (r"\bshanghai ai lab\b", "上海人工智能实验室"),
    (r"\bshanghai academy of artificial intelligence for science\b", "上海科学智能研究院"),
    (r"\bshanghai innovation (institute|institution|institue|institude)\b", "上海创智学院"),
    (r"\bshanghai qi\s*zhi institute\b", "上海期智研究院"),
    (r"\bshanghai qizhi (institute|insititute)\b", "上海期智研究院"),
    (r"\bshanghai qiji zhifeng\b", "上海期智峰科技"),
    (r"\bshanghai university of international business and economics\b", "上海对外经贸大学"),
    (r"\bshanghai university of engineering science\b", "上海工程技术大学"),
    (r"\bshanghai university of electric(ity)? power\b", "上海电力大学"),
    (r"\buniversity of shanghai for science and technology\b", "上海理工大学"),
    (r"\bshanghai lixin university of (accounting and finance|commerce)\b", "上海立信会计金融学院"),
    (r"\bshanghai institute for mathematics and interdisciplinary sciences\b", "上海数学与交叉学科研究院"),
    (r"\bshanghai institute of microsystem and information technology\b", "中国科学院上海微系统与信息技术研究所"),
    (r"\bshanghai institute of intelligent technology\b", "上海智能技术研究所"),
    (r"\bshanghai development center of computer software technology\b", "上海市计算机软件技术开发中心"),
    (r"\bshanghai normal university\b", "上海师范大学"),
    (r"\bshanghai ocean university\b", "上海海洋大学"),
    (r"\bshanghai polytechnic university\b", "上海第二工业大学"),
    (r"\bshanghai university\b", "上海大学"),
    (r"\bnyu shanghai\b", "上海纽约大学"),
    (r"\bshanghai jiao tong univer", "上海交通大学"),
    (r"\bsjtu\b", "上海交通大学"),
    (r"\bfudan univer", "复旦大学"),
    (r"\bfudan\b", "复旦大学"),
    (r"\bdonghua university\b", "东华大学"),
    (r"\beast china university of science and technology\b", "华东理工大学"),
    (r"\bbeijing academy of artificial intelligence\b", "北京智源人工智能研究院"),
    (r"\bbaai\b", "北京智源人工智能研究院"),
    (r"\bbeijing academy of quantum information sciences\b", "北京量子信息科学研究院"),
    (r"\bbeijing zhongguancun academy\b", "北京中关村学院"),
    (r"\bbeijing university of chemical technology\b", "北京化工大学"),
    (r"\bbeijing technology and business university", "北京工商大学"),
    (r"\bbeijing information science", "北京信息科技大学"),
    (r"\bbeijing foreign studies university\b", "北京外国语大学"),
    (r"\bbeijing language and culture university\b", "北京语言大学"),
    (r"\bbeijing electronic science and technology institute\b", "北京电子科技学院"),
    (r"\bbeijing medical university\b", "北京大学医学部"),
    (r"\bpeking union medical college hospital\b", "北京协和医院"),
    (r"\bpeking union medical college\b", "北京协和医学院"),
    (r"\bbeijing normal\s*hong kong baptist university\b", "北师香港浸会大学"),
    (r"\bbeijing normal hong kong baptist university\b", "北师香港浸会大学"),
    (r"\bbeijing university of post", "北京邮电大学"),
    (r"\bbeijing univerisity of post", "北京邮电大学"),
    (r"\bbj?upt\b", "北京邮电大学"),
    (r"\bbeijing jiaotong univer", "北京交通大学"),
    (r"\bbeijing insti(tu|du)te of technology\b", "北京理工大学"),
    (r"\bbeijing institude of technology\b", "北京理工大学"),
    (r"\bbeijing institution of technology\b", "北京理工大学"),
    (r"\bpeking university health science center\b", "北京大学医学部"),
    (r"\bpeking university shenzhen graduate school\b", "北京大学深圳研究生院"),
    (r"\bpeking unive", "北京大学"),
    (r"\btsinghua shenzhen international graduate school\b", "清华大学深圳国际研究生院"),
    (r"\btsinghua berkeley shenzhen institute\b", "清华-伯克利深圳学院"),
    (r"\btsinghua univer", "清华大学"),
    (r"\btsinghua\b", "清华大学"),
    (r"\brenmin uiversity of china\b", "中国人民大学"),
    (r"\bminzu university of china\b", "中央民族大学"),
    (r"\bcentral university of finance and economics\b", "中央财经大学"),
    (r"\bcommunication university of china\b", "中国传媒大学"),
    (r"\bchina agricultural university\b", "中国农业大学"),
    (r"\bchina meteorological administration\b", "中国气象局"),
    (r"\bchina academy of information and communications technolog", "中国信息通信研究院"),
    (r"\bcaict\b", "中国信息通信研究院"),
    (r"\bchina university of petroleum\b.*\bbeijing\b", "中国石油大学（北京）"),
    (r"\bchina university of petroleum\b.*\beast china\b", "中国石油大学（华东）"),
    (r"\bchina university of petroleum\b", "中国石油大学"),
    (r"\bchina university of mining (and )?technology\b.*\bbeijing\b", "中国矿业大学（北京）"),
    (r"\bchina university of mining (and )?technology\b", "中国矿业大学"),
    (r"\bchina university of geoscience", "中国地质大学"),
    (r"\bchina jiliang university\b", "中国计量大学"),
    (r"\bocean university of china\b", "中国海洋大学"),
    (r"\bnorth university of china\b", "中北大学"),
    (r"\bnorth china electric power university\b", "华北电力大学"),
    (r"\bnorth china university of technology\b", "北方工业大学"),
    (r"\bnorth china university of water resources and electric power\b", "华北水利水电大学"),
    (r"\bnorthwest university( xi an| of china)?\b", "西北大学"),
    (r"\buniversity of science and technology of china\b", "中国科学技术大学"),
    (r"\bunversity of science and technology of china\b", "中国科学技术大学"),
    (r"\bustc\b", "中国科学技术大学"),
    (r"\buniversity of electronic science.*technology of china\b", "电子科技大学"),
    (r"\buniversity of electronic science ans technology of china\b", "电子科技大学"),
    (r"\buniversity of electroninc science and technology of china\b", "电子科技大学"),
    (r"\buestc\b", "电子科技大学"),
    (r"\bacademy of mathematics and systems science\b", "中国科学院数学与系统科学研究院"),
    (r"\bchinese academy of mathematics and systems science\b", "中国科学院数学与系统科学研究院"),
    (r"\binstitute of automation\b.*\b(chinese academy|chinese academic|casia|cas)\b", "中国科学院自动化研究所"),
    (r"\bchinese academy of science\b.*\binstitute of automation\b", "中国科学院自动化研究所"),
    (r"\bchinese academy of sciences\b.*\binstitute of automation\b", "中国科学院自动化研究所"),
    (r"\bcasia\b", "中国科学院自动化研究所"),
    (r"\bcair cas\b", "中国科学院自动化研究所"),
    (r"\bnlpr\b", "中国科学院自动化研究所"),
    (r"\binstitute of computing technology\b.*\b(cas|chinese academy)\b", "中国科学院计算技术研究所"),
    (r"\binstitute of information engineering\b.*\b(cas|chinese academy)\b", "中国科学院信息工程研究所"),
    (r"\binstitution of information engineering\b.*\bchinese academic", "中国科学院信息工程研究所"),
    (r"\binstitute of microelectronics\b.*\b(chinese academy|cas)\b", "中国科学院微电子研究所"),
    (r"\binstitute of mechanics\b.*\bcas\b", "中国科学院力学研究所"),
    (r"\binstitute of microbiology\b.*\bcas\b", "中国科学院微生物研究所"),
    (r"\binstitute of semiconductors\b.*\bchinese academy\b", "中国科学院半导体研究所"),
    (r"\binstitute of software\b.*\b(cas|iscas|chinese academy)\b", "中国科学院软件研究所"),
    (r"\bcomputer network information center\b.*\bchinese academy\b", "中国科学院计算机网络信息中心"),
    (r"\buniversity of chinese academ", "中国科学院大学"),
    (r"\bucas\b", "中国科学院大学"),
    (r"\bthe university of chinese academy\b", "中国科学院大学"),
    (r"\bchinese academy of science", "中国科学院"),
    (r"\bchinese of academy of sciences\b", "中国科学院"),
    (r"\bcas\b", "中国科学院"),
    (r"\bcentral china normal university\b", "华中师范大学"),
    (r"\btaiyuan university of technology\b", "太原理工大学"),
    (r"\btaiyuan university of science and technology\b", "太原科技大学"),
    (r"\byunnan normal university\b", "云南师范大学"),
    (r"\byunnan university\b", "云南大学"),
    (r"\bxinjiang university\b", "新疆大学"),
    (r"\bfuzhou university\b", "福州大学"),
    (r"\bhebei university of technology\b", "河北工业大学"),
    (r"\bhebei normal university\b", "河北师范大学"),
    (r"\bhebei university\b", "河北大学"),
    (r"\bjiangnan university\b", "江南大学"),
    (r"\blanzhou university\b", "兰州大学"),
    (r"\bnorthwest normal university\b", "西北师范大学"),
    (r"\bguizhou university\b", "贵州大学"),
    (r"\binner mongolia university\b", "内蒙古大学"),
    (r"\bjiangxi university of finance and economics\b", "江西财经大学"),
    (r"\bjiangxi normal university science and technology college\b", "江西师范大学科学技术学院"),
    (r"\bningbo university\b", "宁波大学"),
    (r"\bningbo institute of digital twin\b", "宁波数字孪生研究院"),
    (r"\bshaanxi normal university\b", "陕西师范大学"),
    (r"\bwenzhou kean university\b", "温州肯恩大学"),
    (r"\bwenzhou business college\b", "温州商学院"),
    (r"\bwenzhou medical university\b", "温州医科大学"),
    (r"\bfujian university of technology\b", "福建理工大学"),
    (r"\bfujian normal university\b", "福建师范大学"),
    (r"\bjiangsu ocean university\b", "江苏海洋大学"),
    (r"\bjiangsu university of science and technology\b", "江苏科技大学"),
    (r"\bjiangsu second normal university\b", "江苏第二师范学院"),
    (r"\bliaoning technical university\b", "辽宁工程技术大学"),
    (r"\bhenan university of science and technology\b", "河南科技大学"),
    (r"\bhenan univer", "河南大学"),
    (r"\bchangsha university of science and technology\b", "长沙理工大学"),
    (r"\bchangsha university\b", "长沙学院"),
    (r"\bguilin university of electronic technology\b", "桂林电子科技大学"),
    (r"\bguilin institute of information technolog", "桂林信息科技学院"),
    (r"\bhainan university\b", "海南大学"),
    (r"\bkunming university of science and technology\b", "昆明理工大学"),
    (r"\bnanchang university\b", "南昌大学"),
    (r"\buniversity of jinan\b", "济南大学"),
    (r"\btongji university\b", "同济大学"),
    (r"\bsichuan university\b", "四川大学"),
    (r"\bsouth china normal university\b", "华南师范大学"),
    (r"\bsouth china agricultural university\b", "华南农业大学"),
    (r"\bsouth china university of technology\b", "华南理工大学"),
    (r"\bscut\b", "华南理工大学"),
    (r"\bsouthern university of science and technology", "南方科技大学"),
    (r"\bsun yat sen university cancer center\b", "中山大学肿瘤防治中心"),
    (r"\bsysu\b", "中山大学"),
    (r"\bnanjing university of information science", "南京信息工程大学"),
    (r"\bnanjing audit university\b", "南京审计大学"),
    (r"\bnanjing forestry university\b", "南京林业大学"),
    (r"\bnanjing normal university\b", "南京师范大学"),
    (r"\bnanjing agricultural university\b", "南京农业大学"),
    (r"\bnanjing les information technology\b", "南京莱斯信息技术"),
    (r"\bnanjing seetacloud technology\b", "南京硅基智能"),
    (r"\bguangzhou university\b", "广州大学"),
    (r"\bguangzhou institute of technology\b", "广州工学院"),
    (r"\bguangdong institute of intelligence science and technology\b", "广东省智能科学与技术研究院"),
    (r"\bguangdong laboratory of artificial intelligence and digital economy\b", "广东省人工智能与数字经济实验室"),
    (r"\bshenzhen university of advanced (technolog|technoloh)", "深圳理工大学"),
    (r"\bshenzhen research institute of big data\b", "深圳市大数据研究院"),
    (r"\bshenzhen msu bit university\b", "深圳北理莫斯科大学"),
    (r"\bshenzhen technology university\b", "深圳技术大学"),
    (r"\bshenzhen institute of technology\b", "深圳技术大学"),
    (r"\bshenzhen institute of computing sciences\b", "深圳计算科学研究院"),
    (r"\bshenzhen polytechnic university\b", "深圳职业技术大学"),
    (r"\bshenzhen city polytechnic\b", "深圳城市职业学院"),
    (r"\bshenzhen loop area insti(tu|du)te\b", "深圳河套学院"),
    (r"\bshenzhen loop area institude\b", "深圳河套学院"),
    (r"\bshenzhen dji\b", "大疆"),
    (r"\bchongqing university of posts? and telecommunications\b", "重庆邮电大学"),
    (r"\bchongqing university of technology\b", "重庆理工大学"),
    (r"\bchongqing jiaotong university\b", "重庆交通大学"),
    (r"\bchongqing normal university\b", "重庆师范大学"),
    (r"\btianjin university of technology\b", "天津理工大学"),
    (r"\btianjin normal university\b", "天津师范大学"),
    (r"\btianjin university of finance", "天津财经大学"),
    (r"\btianjin university of commerce\b", "天津商业大学"),
    (r"\btianjin medical university\b", "天津医科大学"),
    (r"\btianjin artificial intelligence innovation center\b", "天津市人工智能创新中心"),
    (r"\bwuhan university of technology\b", "武汉理工大学"),
    (r"\bwuhan university of science and technology\b", "武汉科技大学"),
    (r"\bwuhan institute of technology\b", "武汉工程大学"),
    (r"\bwuhan research institute of posts and telecommunications\b", "武汉邮电科学研究院"),
    (r"\bwuhan dameng database\b", "达梦数据库"),
    (r"\bshandong university of finance and economics\b", "山东财经大学"),
    (r"\bshandong university of science and technology\b", "山东科技大学"),
    (r"\bshandong normal university\b", "山东师范大学"),
    (r"\bshandong technology and business university\b", "山东工商学院"),
    (r"\bqilu university of technology\b", "齐鲁工业大学（山东省科学院）"),
    (r"\bshandong inspur database technology\b", "浪潮数据库"),
    (r"\bharbin institute of technology\b.*\bweihai\b", "哈尔滨工业大学（威海）"),
    (r"\bharbin institute of technology\b.*\bshen zhen\b", "哈尔滨工业大学（深圳）"),
    (r"\bharbin engineering university\b", "哈尔滨工程大学"),
    (r"\bharbin university of science and technology\b", "哈尔滨理工大学"),
    (r"\bdalian maritime university\b", "大连海事大学"),
    (r"\bdalian martime university\b", "大连海事大学"),
    (r"\bdalian jiaotong university\b", "大连交通大学"),
    (r"\bdalian university\b", "大连大学"),
    (r"\bhuaqiao university\b", "华侨大学"),
    (r"\bthe university of nottingham ningbo china\b", "宁波诺丁汉大学"),
    (r"\buniversity of nottingham ningbo china\b", "宁波诺丁汉大学"),
    (r"\bxi an jiaotong liverpool university\b", "西交利物浦大学"),
    (r"\bxian jiaotong university\b", "西安交通大学"),
    (r"\bxi an jiaotong university\b", "西安交通大学"),
    (r"\bxi an university of science and technology\b", "西安科技大学"),
    (r"\bxi an university\b", "西安大学"),
    (r"\bxi an academy of fine art\b", "西安美术学院"),
    (r"\bxidian university\b", "西安电子科技大学"),
    (r"\bxiamen university of technology\b", "厦门理工学院"),
    (r"\bxiamen ocean vocation college\b", "厦门海洋职业技术学院"),
    (r"\banhui university of science and technology\b", "安徽理工大学"),
    (r"\bhubei university of arts and science\b", "湖北文理学院"),
    (r"\bhubei university\b", "湖北大学"),
    (r"\bhunan university of technology and business\b", "湖南工商大学"),
    (r"\bshaoyang university\b", "邵阳学院"),
    (r"\beastern institute of technology\b.*\bningbo\b", "宁波东方理工大学"),
    (r"\bhefei institute of technology\b", "合肥工业大学"),
    (r"\binstitute of artificial intelligence\b.*\bhefei comprehensive national science center\b", "合肥综合性国家科学中心人工智能研究院"),
    (r"\bhefei comprehensive national science center\b", "合肥综合性国家科学中心"),
    (r"\binstitute for advanced algorithms research\b.*\bshanghai\b", "上海先进算法研究院"),
    (r"\bpengcheng lab", "鹏城实验室"),
    (r"\bpengcheng laboratory\b", "鹏城实验室"),
    (r"\bpcl\b", "鹏城实验室"),
    (r"\bshanghai academy of artificial intelligence for science\b", "上海科学智能研究院"),
    (r"\bintel labs china\b", "英特尔中国研究院"),
    (r"\bchina academy of space technology\b", "中国空间技术研究院"),
    (r"\bchina citic bank\b", "中信银行"),
    (r"\bbank of nanjing\b", "南京银行"),
    (r"\bchina resources group\b", "华润集团"),
    (r"\bchina three gorges corporation\b", "中国长江三峡集团"),
    (r"\bchina electronics technology group corporation 15th research institute\b", "中国电子科技集团公司第十五研究所"),
    (r"\bsouthwest china institute of electronic technology\b", "西南电子技术研究所"),
    (r"\bhong kong science and technology park\b", "香港科技园"),
    (r"\bnus chongqing research institute\b", "新加坡国立大学重庆研究院"),
    (r"\bbeijing humanoid robot innovation center\b", "北京人形机器人创新中心"),
    (r"\bbeijing innovation center of humanoid robotics\b", "北京人形机器人创新中心"),
    (r"\bbeijing academy of blockchain and edge computing\b", "北京区块链与边缘计算研究院"),
    (r"\bbeijing institute of computer technology and application\b", "北京计算机技术及应用研究所"),
    (r"\bbeijing automobile works\b", "北京汽车制造厂"),
    (r"\bbeijing baichuan intelligence\b", "百川智能"),
    (r"\bbeijing dp technology\b", "深势科技"),
    (r"\bbeijing knowledge atlas technology\b", "海致科技"),
    (r"\bbeijing meitu home technology\b", "美图"),
    (r"\bbeijing qihoo technology\b", "奇虎科技"),
    (r"\bbeijing simple ai technology\b", "面壁智能"),
    (r"\bbeijing wenge technology\b", "闻歌科技"),
    (r"\bbeijing yuanli science and technology\b", "元力科技"),
    (r"\bspin matrix\b.*\bbeijing\b", "北京旋量科技"),
    (r"\bshenzhen yuanshi intelligence\b", "元石智能"),
    (r"\bzhejiang geely holding group\b", "吉利控股集团"),
    (r"\bmemtensor\b.*\bshanghai\b", "忆阻矩阵"),
    (r"\bshanghai mosi intelligent technology\b", "上海墨思智能"),
    (r"\banhui heartvoice medical technology\b", "安徽心声医疗科技"),
    (r"\binf technology\b.*\bshanghai\b", "上海 INF Technology"),
    (r"\bintelligent game and decision lab\b", "智能博弈与决策实验室"),
    (r"\bchina industrial securities\b", "兴业证券"),
    (r"\bchina rongtong academy of sciences\b", "中国融通科学研究院"),
    (r"\bchongqing ant consumer finance\b", "重庆蚂蚁消费金融"),
    (r"\bsichuan lan bridge information technology\b", "四川蓝桥信息技术"),
    (r"\bsichuan newstrong\b", "四川新视创伟超高清科技"),
    (r"\bbaidu", "百度"),
    (r"\balibaba cloud\b", "阿里云"),
    (r"\balibaba", "阿里巴巴集团"),
    (r"\bdamo academy\b", "阿里达摩院"),
    (r"\bqwen\b.*\balibaba\b", "阿里通义"),
    (r"\bant group\b", "蚂蚁集团"),
    (r"\bbytedance\b", "字节跳动"),
    (r"\bbyte\s*dance\b", "字节跳动"),
    (r"\btiktok\b", "字节跳动"),
    (r"\bhuawei noah", "华为诺亚方舟实验室"),
    (r"\bnoah s ark\b.*\bhuawei\b", "华为诺亚方舟实验室"),
    (r"\bhuawei", "华为"),
    (r"\btencent hunyuan", "腾讯混元"),
    (r"\btencent youtu", "腾讯优图实验室"),
    (r"\btencent shannon lab\b", "腾讯玄武实验室"),
    (r"\btencent wechat ai\b", "腾讯微信 AI"),
    (r"\bwechat (ai|vision)\b.*\btencent\b", "腾讯微信 AI"),
    (r"\btencent", "腾讯"),
    (r"\bkuaishou", "快手科技"),
    (r"\bkling team\b", "快手科技"),
    (r"\b(ai research of jd|jd ai research|jd explore academy)", "京东探索研究院"),
    (r"\bjd(\s|\.)?com\b", "京东"),
    (r"\bchina mobile\b", "中国移动"),
    (r"\bjiutian research\b.*\bchina mobile\b", "中国移动九天研究院"),
    (r"\bchina telecom\b", "中国电信"),
    (r"\bchina unicom\b", "中国联通"),
    (r"\bchina southern power grid\b", "南方电网"),
    (r"\bping an technology\b", "平安科技"),
    (r"\bmeituan", "美团"),
    (r"\bdu xiaoman", "度小满"),
    (r"\bdidi\b", "滴滴"),
    (r"\bxiaomi ev\b", "小米汽车"),
    (r"\bxiaomi", "小米"),
]

DOMESTIC_AFFILIATION_PATTERNS = [
    (re.compile(pattern), value) for pattern, value in _DOMESTIC_AFFILIATION_PATTERNS_RAW
]


def match_domestic_affiliation(raw_affiliation: Any) -> str:
    normalized = normalize_affiliation_name(raw_affiliation)
    if not normalized:
        return ""
    for pattern, translated in DOMESTIC_AFFILIATION_PATTERNS:
        if pattern.search(normalized):
            return translated
    return ""


def translate_affiliation(raw_affiliation: Any, org_name_mapping: dict[str, str]) -> str:
    raw = clean_text(raw_affiliation)
    if not raw:
        return ""

    normalized = normalize_affiliation_name(raw)
    if normalized in MANUAL_AFFILIATION_TRANSLATIONS:
        return MANUAL_AFFILIATION_TRANSLATIONS[normalized]
    domestic_match = match_domestic_affiliation(raw)
    if domestic_match:
        return domestic_match
    if normalized in org_name_mapping:
        return org_name_mapping[normalized]

    for part in [p.strip() for p in re.split(r"[,;]+", raw) if p.strip()]:
        part_key = normalize_affiliation_name(part)
        if part_key in MANUAL_AFFILIATION_TRANSLATIONS:
            return MANUAL_AFFILIATION_TRANSLATIONS[part_key]
        domestic_part_match = match_domestic_affiliation(part)
        if domestic_part_match:
            return domestic_part_match
        if part_key in org_name_mapping:
            return org_name_mapping[part_key]

    if re.search(r"[\u4e00-\u9fff]", raw):
        if "-" in raw:
            tail = raw.rsplit("-", 1)[-1].strip()
            if re.search(r"[\u4e00-\u9fff]", tail):
                return tail
        return raw
    return raw


def affiliation_match_key(value: Any) -> str:
    return normalize_affiliation_name(translate_affiliation(value, {}))


def has_chinese_text(value: Any) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", clean_text(value)))


def choose_existing_scholar(
    author_name: str,
    translated_affiliation: str,
    candidates: list[ExistingScholar],
) -> ExistingScholar | None:
    name_key = normalize_person_name(author_name)
    same_name = [
        candidate
        for candidate in candidates
        if name_key in {normalize_person_name(candidate.name), normalize_person_name(candidate.name_en)}
    ]
    if not same_name:
        return None

    target_affiliation_key = affiliation_match_key(translated_affiliation)
    if target_affiliation_key:
        exact_affiliation = [
            candidate
            for candidate in same_name
            if affiliation_match_key(candidate.university) == target_affiliation_key
        ]
        if len(exact_affiliation) == 1:
            return exact_affiliation[0]

        empty_affiliation = [candidate for candidate in same_name if not clean_text(candidate.university)]
        if len(same_name) == 1 and empty_affiliation:
            return same_name[0]
        return None

    if len(same_name) == 1:
        return same_name[0]
    return None


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return [text]
        return parsed if isinstance(parsed, list) else []
    return []


def _json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _paper_authors(paper: dict[str, Any]) -> list[str]:
    return [clean_text(item) for item in _json_list(paper.get("authors")) if clean_text(item)]


def _paper_affiliation_items(paper: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in _json_list(paper.get("affiliations")) if isinstance(item, dict)]


def _paper_affiliations_as_text(paper: dict[str, Any]) -> list[str]:
    affiliations: list[str] = []
    seen: set[str] = set()
    for item in _paper_affiliation_items(paper):
        affiliation = clean_text(item.get("affiliation"))
        if not affiliation or affiliation in seen:
            continue
        seen.add(affiliation)
        affiliations.append(affiliation)
    return affiliations


def _author_affiliations(paper: dict[str, Any], author_index: int, author_name: str) -> list[str]:
    by_order: list[str] = []
    by_name: list[str] = []
    target_name = normalize_person_name(author_name)
    for item in _paper_affiliation_items(paper):
        affiliation = clean_text(item.get("affiliation"))
        if not affiliation:
            continue
        try:
            order = int(item.get("author_order") or 0)
        except Exception:
            order = 0
        if order == author_index:
            by_order.append(affiliation)
        elif normalize_person_name(item.get("author_name")) == target_name:
            by_name.append(affiliation)
    values = by_order or by_name
    return list(dict.fromkeys(values))


def _to_iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.isoformat()
    text = clean_text(value)
    return text or None


def _to_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = clean_text(value)
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _title_fingerprint(title: Any) -> str:
    normalized = re.sub(
        r"\s+",
        " ",
        re.sub(r"[^\w\u4e00-\u9fff]+", " ", clean_text(title).casefold()),
    ).strip()
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:20]


def _canonical_uid(paper: dict[str, Any]) -> str:
    doi = clean_text(paper.get("doi")).casefold()
    if doi:
        doi = doi.replace("https://doi.org/", "").replace("http://doi.org/", "").replace("doi:", "").strip()
        return f"doi:{doi}"
    arxiv_id = clean_text(paper.get("arxiv_id")).casefold()
    if arxiv_id:
        arxiv_id = arxiv_id.replace("https://arxiv.org/abs/", "").replace("http://arxiv.org/abs/", "")
        arxiv_id = arxiv_id.replace("arxiv:", "").replace("abs/", "").replace("pdf/", "").strip("/")
        return f"arxiv:{arxiv_id}"
    date_token = (_to_iso(paper.get("publication_date")) or "").split("T", 1)[0]
    digest = hashlib.sha1(f"{_title_fingerprint(paper.get('title'))}|{date_token}".encode("utf-8")).hexdigest()[:24]
    return f"fingerprint:{digest}"


def _openreview_url(raw_id: Any) -> str:
    raw = clean_text(raw_id)
    return f"https://openreview.net/forum?id={raw}" if raw else ""


def build_publication_payload(paper: dict[str, Any]) -> dict[str, Any]:
    authors = _paper_authors(paper)
    raw_id = clean_text(paper.get("raw_id"))
    detail_url = clean_text(paper.get("detail_url"))
    publication_date = _to_iso(paper.get("publication_date")) or "2026-01-01T00:00:00+00:00"
    affiliations = _paper_affiliations_as_text(paper)
    source_details = {
        "import_channel": "icml_2026_author_import",
        "paper_uid": clean_text(paper.get("paper_uid")) or clean_text(paper.get("paper_id")),
        "paper_id": clean_text(paper.get("paper_id")),
        "raw_id": raw_id,
        "source_id": "icml",
        "venue": "ICML",
        "venue_year": 2026,
        "detail_url": detail_url,
        "openreview_url": _openreview_url(raw_id),
    }
    return {
        "canonical_uid": _canonical_uid({**paper, "publication_date": publication_date}),
        "publication_id": stable_short_id("pub", _canonical_uid({**paper, "publication_date": publication_date})),
        "title": clean_text(paper.get("title")),
        "doi": clean_text(paper.get("doi")) or None,
        "arxiv_id": clean_text(paper.get("arxiv_id")) or None,
        "abstract": clean_text(paper.get("abstract")) or None,
        "publication_date": publication_date,
        "authors": authors,
        "affiliations": affiliations,
        "venue": VENUE,
        "year": 2026,
        "url": detail_url or _openreview_url(raw_id),
        "source_type": "bulk_import",
        "source_details": source_details,
        "compliance_details": {
            "imported_from": "icml_2026_official",
            "paper_source_id": "icml",
            "venue": VENUE,
        },
    }


def build_author_id(author_name: str, university: str) -> str:
    return stable_hex("icml2026-author", normalize_person_name(author_name), affiliation_match_key(university))


def build_identity_key(author_name: str, translated_affiliation: str) -> str:
    return f"{normalize_person_name(author_name)}|{affiliation_match_key(translated_affiliation)}"


async def load_org_name_mapping(conn: asyncpg.Connection) -> dict[str, str]:
    rows = await conn.fetch(
        """
        SELECT name, org_name
        FROM institutions
        WHERE entity_type = 'organization'
          AND NULLIF(btrim(name), '') IS NOT NULL
        """
    )
    mapping: dict[str, str] = {}
    for row in rows:
        chinese_name = clean_text(row["name"])
        org_name = clean_text(row["org_name"])
        if org_name:
            mapping[normalize_affiliation_name(org_name)] = chinese_name
        mapping[normalize_affiliation_name(chinese_name)] = chinese_name
    return mapping


async def load_existing_scholars(conn: asyncpg.Connection) -> list[ExistingScholar]:
    rows = await conn.fetch(
        """
        SELECT id, name, name_en, university, source_id, custom_fields
        FROM scholars
        """
    )
    scholars: list[ExistingScholar] = []
    for row in rows:
        custom_fields = _json_dict(row["custom_fields"])
        icml_fields = _json_dict(custom_fields.get("icml_2026_import"))
        scholars.append(
            ExistingScholar(
                id=clean_text(row["id"]),
                name=clean_text(row["name"]),
                name_en=clean_text(row["name_en"]),
                university=clean_text(row["university"]),
                source_id=clean_text(row["source_id"]),
                icml_paper_uids=tuple(
                    clean_text(item) for item in _json_list(icml_fields.get("paper_uids")) if clean_text(item)
                ),
                icml_original_affiliations=tuple(
                    clean_text(item)
                    for item in _json_list(icml_fields.get("original_affiliations"))
                    if clean_text(item)
                ),
            )
        )
    return scholars


def scholars_by_name(scholars: list[ExistingScholar]) -> dict[str, list[ExistingScholar]]:
    mapping: dict[str, list[ExistingScholar]] = {}
    for scholar in scholars:
        for name in (scholar.name, scholar.name_en):
            key = normalize_person_name(name)
            if not key:
                continue
            mapping.setdefault(key, [])
            if scholar not in mapping[key]:
                mapping[key].append(scholar)
    return mapping


async def load_icml2026_papers(conn: asyncpg.Connection) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT
          paper_uid,
          paper_id,
          canonical_uid,
          raw_id,
          title,
          abstract,
          doi,
          arxiv_id,
          authors,
          affiliations,
          detail_url,
          publication_date
        FROM papers
        WHERE source_id = 'icml'
          AND venue_year = 2026
        ORDER BY paper_uid
        """
    )
    return [dict(row) for row in rows]


def build_identities(
    papers: list[dict[str, Any]],
    org_name_mapping: dict[str, str],
) -> dict[str, AuthorIdentity]:
    identities: dict[str, AuthorIdentity] = {}
    for paper in papers:
        paper_payload = build_publication_payload(paper)
        paper_uid = clean_text(paper.get("paper_uid")) or clean_text(paper.get("paper_id"))
        for author_index, author_name in enumerate(_paper_authors(paper), start=1):
            affiliations = _author_affiliations(paper, author_index, author_name)
            original_affiliation = "; ".join(affiliations)
            translated = translate_affiliation(affiliations[0], org_name_mapping) if affiliations else ""
            key = build_identity_key(author_name, translated or original_affiliation)
            identity = identities.setdefault(
                key,
                AuthorIdentity(
                    key=key,
                    name=author_name,
                    university=translated,
                ),
            )
            if translated and not identity.university:
                identity.university = translated
            for affiliation in affiliations:
                identity.original_affiliations.add(affiliation)
            identity.paper_uids.add(paper_uid)
            identity.rows.append(
                {
                    "paper": paper,
                    "publication": paper_payload,
                    "author_order": author_index,
                    "author_name": author_name,
                    "original_affiliation": original_affiliation,
                    "translated_affiliation": translated,
                }
            )
    return identities


def resolve_identities(
    identities: dict[str, AuthorIdentity],
    candidates_by_name: dict[str, list[ExistingScholar]],
    existing_publication_owner_links: dict[tuple[str, str, int], str] | None = None,
) -> None:
    existing_publication_owner_links = existing_publication_owner_links or {}
    for identity in identities.values():
        candidates = candidates_by_name.get(normalize_person_name(identity.name), [])
        identity.existing_candidates = [candidate.id for candidate in candidates]
        publication_linked_ids: set[str] = set()
        for row in identity.rows:
            publication = row.get("publication") if isinstance(row, dict) else None
            if not isinstance(publication, dict):
                continue
            year = publication.get("year") or 2026
            try:
                year_int = int(year)
            except Exception:
                year_int = 2026
            linked_id = existing_publication_owner_links.get(
                (normalize_person_name(identity.name), title_key(publication.get("title")), year_int)
            )
            if linked_id:
                publication_linked_ids.add(linked_id)
        paper_linked_candidates = [
            candidate
            for candidate in candidates
            if set(candidate.icml_paper_uids) & identity.paper_uids
        ]
        original_affiliation_candidates = [
            candidate
            for candidate in candidates
            if identity.original_affiliations
            and {
                normalize_affiliation_name(affiliation)
                for affiliation in candidate.icml_original_affiliations
            }
            & {
                normalize_affiliation_name(affiliation)
                for affiliation in identity.original_affiliations
            }
        ]
        deterministic_id_candidates = [
            candidate for candidate in candidates if candidate.id == build_author_id(identity.name, identity.university)
        ]
        existing = None
        if len(publication_linked_ids) == 1:
            linked_id = next(iter(publication_linked_ids))
            existing = next((candidate for candidate in candidates if candidate.id == linked_id), None)
        if existing is not None:
            pass
        elif len(paper_linked_candidates) == 1:
            existing = paper_linked_candidates[0]
        elif len(original_affiliation_candidates) == 1:
            existing = original_affiliation_candidates[0]
        elif len(deterministic_id_candidates) == 1:
            existing = deterministic_id_candidates[0]
        else:
            existing = choose_existing_scholar(identity.name, identity.university, candidates)
        if existing:
            identity.scholar_id = existing.id
            identity.match_status = "matched_existing"
        else:
            identity.scholar_id = build_author_id(identity.name, identity.university)
            identity.match_status = "new_after_ambiguous_name" if candidates else "new"


def scholar_custom_fields(identity: AuthorIdentity) -> dict[str, Any]:
    return scholar_custom_fields_for_identities([identity])


def scholar_custom_fields_for_identities(identities: list[AuthorIdentity]) -> dict[str, Any]:
    if not identities:
        return {"icml_2026_import": {}}
    first = identities[0]
    original_affiliations: set[str] = set()
    paper_uids: set[str] = set()
    translated_affiliations: set[str] = set()
    match_statuses: set[str] = set()
    paper_refs = []
    seen: set[str] = set()
    for identity in identities:
        original_affiliations.update(identity.original_affiliations)
        paper_uids.update(identity.paper_uids)
        if identity.university:
            translated_affiliations.add(identity.university)
        match_statuses.add(identity.match_status)
        for row in identity.rows:
            paper = row["paper"]
            paper_uid = clean_text(paper.get("paper_uid")) or clean_text(paper.get("paper_id"))
            if paper_uid in seen:
                continue
            seen.add(paper_uid)
            paper_refs.append(
                {
                    "paper_uid": paper_uid,
                    "raw_id": clean_text(paper.get("raw_id")),
                    "title": clean_text(paper.get("title")),
                    "detail_url": clean_text(paper.get("detail_url")),
                }
            )
    return {
        "icml_2026_import": {
            "author_name": first.name,
            "translated_affiliation": "; ".join(sorted(translated_affiliations)),
            "translated_affiliations": sorted(translated_affiliations),
            "original_affiliations": sorted(original_affiliations),
            "paper_count": len(paper_uids),
            "paper_uids": sorted(paper_uids),
            "papers": paper_refs,
            "match_status": "; ".join(sorted(match_statuses)),
            "imported_at": datetime.now(UTC).isoformat(),
        }
    }


def build_new_scholar_rows(identities: dict[str, AuthorIdentity]) -> list[tuple[Any, ...]]:
    rows: list[tuple[Any, ...]] = []
    for identity in identities.values():
        if not identity.match_status.startswith("new"):
            continue
        rows.append(
            (
                identity.scholar_id,
                identity.name,
                identity.name,
                identity.university or None,
                SOURCE_ID,
                f"icml2026://author/{identity.scholar_id}",
                datetime.now(UTC),
                datetime.now(UTC),
                True,
                0.2,
                "",
                ["ICML 2026"],
                len(identity.paper_uids),
                -1,
                -1,
                json.dumps(scholar_custom_fields(identity), ensure_ascii=False),
            )
        )
    return rows


def build_existing_scholar_updates(identities: dict[str, AuthorIdentity]) -> list[tuple[Any, ...]]:
    grouped: dict[str, list[AuthorIdentity]] = {}
    for identity in identities.values():
        if identity.match_status != "matched_existing":
            continue
        grouped.setdefault(identity.scholar_id, []).append(identity)
    rows: list[tuple[Any, ...]] = []
    for scholar_id, items in grouped.items():
        paper_uids: set[str] = set()
        for item in items:
            paper_uids.update(item.paper_uids)
        rows.append(
            (
                scholar_id,
                json.dumps(scholar_custom_fields_for_identities(items), ensure_ascii=False),
                len(paper_uids),
            )
        )
    return rows


def build_scholar_university_updates(
    identities: dict[str, AuthorIdentity],
    existing_scholars: list[ExistingScholar],
) -> list[tuple[Any, ...]]:
    existing_by_id = {scholar.id: scholar for scholar in existing_scholars}
    grouped: dict[str, list[AuthorIdentity]] = {}
    for identity in identities.values():
        if identity.match_status != "matched_existing":
            continue
        grouped.setdefault(identity.scholar_id, []).append(identity)

    rows: list[tuple[Any, ...]] = []
    for scholar_id, items in grouped.items():
        existing = existing_by_id.get(scholar_id)
        if existing is None:
            continue

        translated_affiliations = sorted(
            {item.university for item in items if item.university and has_chinese_text(item.university)}
        )
        if not translated_affiliations:
            continue

        current_university = clean_text(existing.university)
        current_translated = translate_affiliation(current_university, {})
        if current_translated in translated_affiliations:
            desired_university = current_translated
        elif len(translated_affiliations) == 1:
            desired_university = translated_affiliations[0]
        else:
            continue

        if not desired_university or desired_university == current_university:
            continue

        original_affiliation_keys = {
            normalize_affiliation_name(affiliation)
            for item in items
            for affiliation in item.original_affiliations
            if clean_text(affiliation)
        }
        current_key = normalize_affiliation_name(current_university)
        current_is_import_artifact = (
            existing.source_id == SOURCE_ID
            or not current_university
            or (current_key and current_key in original_affiliation_keys)
            or (not has_chinese_text(current_university) and current_translated == desired_university)
        )
        if not current_is_import_artifact:
            continue

        rows.append((scholar_id, desired_university))
    return rows


def _translated_affiliations_from_originals(
    original_affiliations: list[Any],
    org_name_mapping: dict[str, str],
) -> list[str]:
    translated: list[str] = []
    seen: set[str] = set()
    for affiliation in original_affiliations:
        value = translate_affiliation(affiliation, org_name_mapping)
        if not value or not has_chinese_text(value):
            continue
        if value in seen:
            continue
        seen.add(value)
        translated.append(value)
    return translated


def _repair_university_value(
    *,
    current_university: Any,
    source_id: Any,
    translated_affiliations: list[str],
) -> str:
    current = clean_text(current_university)
    if not translated_affiliations:
        return ""
    current_translated = translate_affiliation(current, {})
    if current_translated in translated_affiliations and current_translated != current:
        return current_translated
    if current and has_chinese_text(current):
        return ""
    if clean_text(source_id) == SOURCE_ID and len(translated_affiliations) == 1:
        return translated_affiliations[0]
    if not current and len(translated_affiliations) == 1:
        return translated_affiliations[0]
    return ""


def build_scholar_affiliation_repair_rows(
    scholar_rows: list[dict[str, Any]],
    org_name_mapping: dict[str, str],
) -> tuple[list[tuple[str, str | None, str]], int]:
    rows: list[tuple[str, str | None, str]] = []
    university_update_count = 0
    for row in scholar_rows:
        custom_fields = _json_dict(row.get("custom_fields"))
        icml_fields = _json_dict(custom_fields.get("icml_2026_import"))
        original_affiliations = _json_list(icml_fields.get("original_affiliations"))
        translated_affiliations = _translated_affiliations_from_originals(
            original_affiliations,
            org_name_mapping,
        )
        if not translated_affiliations:
            continue

        repaired_icml_fields = {
            **icml_fields,
            "translated_affiliation": "; ".join(translated_affiliations),
            "translated_affiliations": translated_affiliations,
        }
        repaired_custom_fields = {
            **custom_fields,
            "icml_2026_import": repaired_icml_fields,
        }
        repaired_university = _repair_university_value(
            current_university=row.get("university"),
            source_id=row.get("source_id"),
            translated_affiliations=translated_affiliations,
        )
        custom_changed = repaired_icml_fields != icml_fields
        university_changed = bool(repaired_university)
        if not custom_changed and not university_changed:
            continue
        if university_changed:
            university_update_count += 1
        rows.append(
            (
                clean_text(row.get("id")),
                repaired_university or None,
                json.dumps(repaired_custom_fields, ensure_ascii=False),
            )
        )
    return rows, university_update_count


def build_owner_affiliation_repair_rows(
    owner_rows: list[dict[str, Any]],
    org_name_mapping: dict[str, str],
) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for row in owner_rows:
        source_details = _json_dict(row.get("source_details"))
        original_affiliation = clean_text(source_details.get("author_original_affiliation"))
        if not original_affiliation:
            continue
        translated = translate_affiliation(original_affiliation, org_name_mapping)
        if not translated or not has_chinese_text(translated):
            continue
        if clean_text(source_details.get("author_translated_affiliation")) == translated:
            continue
        source_details["author_translated_affiliation"] = translated
        rows.append((clean_text(row.get("owner_link_id")), json.dumps(source_details, ensure_ascii=False)))
    return rows


def title_key(title: Any) -> str:
    return _title_fingerprint(title)


async def load_existing_scholar_publication_keys(conn: asyncpg.Connection) -> set[tuple[str, str, int]]:
    rows = await conn.fetch(
        """
        SELECT scholar_id, title, year
        FROM scholar_publications
        WHERE year = 2026
          AND (venue = 'ICML 2026' OR venue = 'ICML' OR venue ILIKE 'ICML%')
        """
    )
    return {(clean_text(row["scholar_id"]), title_key(row["title"]), int(row["year"])) for row in rows}


async def load_existing_scholar_publication_owner_links(
    conn: asyncpg.Connection,
) -> dict[tuple[str, str, int], str]:
    rows = await conn.fetch(
        """
        SELECT sp.scholar_id, sp.title, sp.year, s.name, s.name_en
        FROM scholar_publications sp
        JOIN scholars s ON s.id = sp.scholar_id
        WHERE sp.year = 2026
          AND sp.added_by = $1
        """,
        ADDED_BY,
    )
    links: dict[tuple[str, str, int], str | None] = {}
    for row in rows:
        for name in (row["name"], row["name_en"]):
            name_key = normalize_person_name(name)
            if not name_key:
                continue
            key = (name_key, title_key(row["title"]), int(row["year"]))
            scholar_id = clean_text(row["scholar_id"])
            if key in links and links[key] != scholar_id:
                links[key] = None
            else:
                links[key] = scholar_id
    return {key: scholar_id for key, scholar_id in links.items() if scholar_id}


def build_scholar_publication_rows(
    identities: dict[str, AuthorIdentity],
    existing_keys: set[tuple[str, str, int]],
) -> tuple[list[tuple[Any, ...]], int]:
    rows: list[tuple[Any, ...]] = []
    skipped = 0
    seen: set[tuple[str, str, int]] = set(existing_keys)
    for identity in identities.values():
        for item in identity.rows:
            publication = item["publication"]
            key = (identity.scholar_id, title_key(publication["title"]), 2026)
            if key in seen:
                skipped += 1
                continue
            seen.add(key)
            paper_uid = publication["source_details"]["paper_uid"]
            rows.append(
                (
                    stable_bigint("icml2026-scholar-publication", identity.scholar_id, paper_uid),
                    identity.scholar_id,
                    publication["title"],
                    publication["venue"],
                    publication["year"],
                    publication["authors"],
                    publication["url"],
                    0,
                    False,
                    ADDED_BY,
                )
            )
    return rows, skipped


def build_publication_rows(papers: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    rows: list[tuple[Any, ...]] = []
    seen: set[str] = set()
    for paper in papers:
        payload = build_publication_payload(paper)
        canonical_uid = payload["canonical_uid"]
        if canonical_uid in seen:
            continue
        seen.add(canonical_uid)
        rows.append(
            (
                payload["publication_id"],
                canonical_uid,
                payload["title"],
                payload["doi"],
                payload["arxiv_id"],
                payload["abstract"],
                _to_datetime(payload["publication_date"]),
                json.dumps(payload["authors"], ensure_ascii=False),
                json.dumps(payload["affiliations"], ensure_ascii=False),
            )
        )
    return rows


def build_owner_rows(
    identities: dict[str, AuthorIdentity],
    publication_id_by_uid: dict[str, str],
) -> list[tuple[Any, ...]]:
    rows: list[tuple[Any, ...]] = []
    seen: set[tuple[str, str]] = set()
    for identity in identities.values():
        for item in identity.rows:
            publication = item["publication"]
            publication_id = publication_id_by_uid.get(publication["canonical_uid"])
            if not publication_id:
                continue
            owner_key = (publication_id, identity.scholar_id)
            if owner_key in seen:
                continue
            seen.add(owner_key)
            source_details = {
                **publication["source_details"],
                "author_name": item["author_name"],
                "author_order": item["author_order"],
                "author_original_affiliation": item["original_affiliation"],
                "author_translated_affiliation": item["translated_affiliation"],
                "scholar_match_status": identity.match_status,
            }
            rows.append(
                (
                    stable_short_id("owner", publication_id, "scholar", identity.scholar_id),
                    publication_id,
                    "scholar",
                    identity.scholar_id,
                    None,
                    "bulk_import",
                    json.dumps(source_details, ensure_ascii=False),
                    json.dumps(publication["compliance_details"], ensure_ascii=False),
                    ADDED_BY,
                )
            )
    return rows


def build_report(
    *,
    papers: list[dict[str, Any]],
    identities: dict[str, AuthorIdentity],
    org_name_mapping: dict[str, str],
    scholar_publication_rows: list[tuple[Any, ...]],
    scholar_publication_skipped: int,
    scholar_university_updates: list[tuple[Any, ...]],
    publication_rows: list[tuple[Any, ...]],
    owner_rows: list[tuple[Any, ...]],
    apply: bool,
) -> dict[str, Any]:
    statuses: dict[str, int] = {}
    untranslated_affiliations: dict[str, int] = {}
    for identity in identities.values():
        statuses[identity.match_status] = statuses.get(identity.match_status, 0) + 1
        for affiliation in identity.original_affiliations:
            affiliation_key = normalize_affiliation_name(affiliation)
            translated = translate_affiliation(affiliation, org_name_mapping)
            handled_by_manual_map = affiliation_key in MANUAL_AFFILIATION_TRANSLATIONS
            if (
                translated == affiliation
                and not handled_by_manual_map
                and not re.search(r"[\u4e00-\u9fff]", affiliation)
            ):
                untranslated_affiliations[affiliation] = untranslated_affiliations.get(affiliation, 0) + 1

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "applied": apply,
        "summary": {
            "papers": len(papers),
            "paper_author_entries": sum(len(_paper_authors(paper)) for paper in papers),
            "unique_author_identities": len(identities),
            "identity_statuses": statuses,
            "new_scholars": sum(1 for item in identities.values() if item.match_status.startswith("new")),
            "matched_existing_scholars": statuses.get("matched_existing", 0),
            "scholar_publications_to_insert": len(scholar_publication_rows),
            "scholar_publications_existing_skipped": scholar_publication_skipped,
            "scholar_universities_to_update": len(scholar_university_updates),
            "publications_to_upsert": len(publication_rows),
            "publication_owner_links_to_upsert": len(owner_rows),
            "untranslated_affiliation_count": len(untranslated_affiliations),
        },
        "scholar_university_update_samples": [
            {"scholar_id": scholar_id, "university": university}
            for scholar_id, university in scholar_university_updates[:100]
        ],
        "untranslated_affiliations_top": [
            {"affiliation": name, "count": count}
            for name, count in sorted(untranslated_affiliations.items(), key=lambda item: (-item[1], item[0]))[:100]
        ],
        "ambiguous_name_samples": [
            {
                "name": item.name,
                "university": item.university,
                "created_scholar_id": item.scholar_id,
                "candidate_ids": item.existing_candidates,
                "paper_count": len(item.paper_uids),
            }
            for item in list(identities.values())
            if item.match_status == "new_after_ambiguous_name"
        ][:100],
    }


async def apply_import(
    conn: asyncpg.Connection,
    *,
    new_scholar_rows: list[tuple[Any, ...]],
    existing_scholar_updates: list[tuple[Any, ...]],
    scholar_university_updates: list[tuple[Any, ...]],
    publication_rows: list[tuple[Any, ...]],
    scholar_publication_rows: list[tuple[Any, ...]],
    owner_rows_builder: Any,
    canonical_uids: list[str],
) -> tuple[int, int, int, int, int]:
    async with conn.transaction():
        if new_scholar_rows:
            await conn.executemany(
                """
                INSERT INTO scholars (
                  id, name, name_en, university, source_id, source_url,
                  crawled_at, last_seen_at, is_active, data_completeness,
                  content, tags, publications_count, h_index, citations_count, custom_fields
                )
                VALUES (
                  $1, $2, $3, $4, $5, $6,
                  $7, $8, $9, $10,
                  $11, $12::text[], $13, $14, $15, $16::jsonb
                )
                ON CONFLICT (id) DO UPDATE
                SET
                  name_en = COALESCE(NULLIF(scholars.name_en, ''), EXCLUDED.name_en),
                  university = COALESCE(scholars.university, EXCLUDED.university),
                  custom_fields = COALESCE(scholars.custom_fields, '{}'::jsonb) || EXCLUDED.custom_fields,
                  publications_count = GREATEST(COALESCE(NULLIF(scholars.publications_count, -1), 0), EXCLUDED.publications_count),
                  last_seen_at = now(),
                  updated_at = now()
                """,
                new_scholar_rows,
            )

        if existing_scholar_updates:
            await conn.executemany(
                """
                UPDATE scholars
                SET
                  custom_fields = COALESCE(custom_fields, '{}'::jsonb) || $2::jsonb,
                  publications_count = GREATEST(COALESCE(NULLIF(publications_count, -1), 0), $3),
                  last_seen_at = now(),
                  updated_at = now()
                WHERE id = $1
                """,
                existing_scholar_updates,
            )

        if scholar_university_updates:
            await conn.executemany(
                """
                UPDATE scholars
                SET university = $2,
                    updated_at = now()
                WHERE id = $1
                """,
                scholar_university_updates,
            )

        if publication_rows:
            await conn.executemany(
                """
                INSERT INTO publications (
                  publication_id, canonical_uid, title, doi, arxiv_id, abstract,
                  publication_date, authors, affiliations
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8::jsonb, $9::jsonb)
                ON CONFLICT (canonical_uid) DO UPDATE
                SET
                  title = CASE
                    WHEN publications.title = '' AND EXCLUDED.title <> '' THEN EXCLUDED.title
                    ELSE publications.title
                  END,
                  doi = COALESCE(publications.doi, EXCLUDED.doi),
                  arxiv_id = COALESCE(publications.arxiv_id, EXCLUDED.arxiv_id),
                  abstract = COALESCE(publications.abstract, EXCLUDED.abstract),
                  publication_date = COALESCE(publications.publication_date, EXCLUDED.publication_date),
                  authors = CASE
                    WHEN publications.authors = '[]'::jsonb AND EXCLUDED.authors <> '[]'::jsonb THEN EXCLUDED.authors
                    ELSE publications.authors
                  END,
                  affiliations = CASE
                    WHEN publications.affiliations = '[]'::jsonb AND EXCLUDED.affiliations <> '[]'::jsonb THEN EXCLUDED.affiliations
                    ELSE publications.affiliations
                  END,
                  updated_at = now()
                """,
                publication_rows,
            )

        publication_id_rows = await conn.fetch(
            """
            SELECT canonical_uid, publication_id
            FROM publications
            WHERE canonical_uid = ANY($1::text[])
            """,
            canonical_uids,
        )
        publication_id_by_uid = {
            clean_text(row["canonical_uid"]): clean_text(row["publication_id"]) for row in publication_id_rows
        }
        owner_rows = owner_rows_builder(publication_id_by_uid)

        if scholar_publication_rows:
            await conn.executemany(
                """
                INSERT INTO scholar_publications (
                  id, scholar_id, title, venue, year, authors, url,
                  citation_count, is_corresponding, added_by
                )
                VALUES ($1, $2, $3, $4, $5, $6::text[], $7, $8, $9, $10)
                ON CONFLICT (id) DO UPDATE
                SET
                  title = EXCLUDED.title,
                  venue = EXCLUDED.venue,
                  year = EXCLUDED.year,
                  authors = EXCLUDED.authors,
                  url = EXCLUDED.url,
                  citation_count = EXCLUDED.citation_count,
                  is_corresponding = EXCLUDED.is_corresponding,
                  added_by = EXCLUDED.added_by
                """,
                scholar_publication_rows,
            )

        if owner_rows:
            await conn.executemany(
                """
                INSERT INTO publication_owners (
                  owner_link_id, publication_id, owner_type, owner_id,
                  project_group_name, source_type, source_details,
                  compliance_details, confirmed_by, confirmed_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb, $9, now())
                ON CONFLICT (publication_id, owner_type, owner_id) DO UPDATE
                SET
                  source_type = EXCLUDED.source_type,
                  source_details = publication_owners.source_details || EXCLUDED.source_details,
                  compliance_details = publication_owners.compliance_details || EXCLUDED.compliance_details,
                  confirmed_by = COALESCE(EXCLUDED.confirmed_by, publication_owners.confirmed_by),
                  confirmed_at = COALESCE(publication_owners.confirmed_at, now()),
                  updated_at = now()
                """,
                owner_rows,
            )

    return (
        len(new_scholar_rows),
        len(existing_scholar_updates),
        len(scholar_university_updates),
        len(scholar_publication_rows),
        len(owner_rows),
    )


async def run_import(*, apply: bool, report_path: Path) -> dict[str, Any]:
    conn = await asyncpg.connect(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        database=settings.POSTGRES_DB,
    )
    try:
        org_name_mapping = await load_org_name_mapping(conn)
        papers = await load_icml2026_papers(conn)
        existing_scholars = await load_existing_scholars(conn)
        identities = build_identities(papers, org_name_mapping)
        existing_publication_owner_links = await load_existing_scholar_publication_owner_links(conn)
        resolve_identities(
            identities,
            scholars_by_name(existing_scholars),
            existing_publication_owner_links=existing_publication_owner_links,
        )
        existing_sp_keys = await load_existing_scholar_publication_keys(conn)
        scholar_publication_rows, scholar_publication_skipped = build_scholar_publication_rows(
            identities,
            existing_sp_keys,
        )
        scholar_university_updates = build_scholar_university_updates(identities, existing_scholars)
        publication_rows = build_publication_rows(papers)
        canonical_uids = [row[1] for row in publication_rows]
        owner_rows_preview = build_owner_rows(
            identities,
            {
                row[1]: row[0]
                for row in publication_rows
            },
        )
        report = build_report(
            papers=papers,
            identities=identities,
            org_name_mapping=org_name_mapping,
            scholar_publication_rows=scholar_publication_rows,
            scholar_publication_skipped=scholar_publication_skipped,
            scholar_university_updates=scholar_university_updates,
            publication_rows=publication_rows,
            owner_rows=owner_rows_preview,
            apply=apply,
        )

        if apply:
            new_scholar_rows = build_new_scholar_rows(identities)
            existing_scholar_updates = build_existing_scholar_updates(identities)
            applied_counts = await apply_import(
                conn,
                new_scholar_rows=new_scholar_rows,
                existing_scholar_updates=existing_scholar_updates,
                scholar_university_updates=scholar_university_updates,
                publication_rows=publication_rows,
                scholar_publication_rows=scholar_publication_rows,
                owner_rows_builder=lambda publication_id_by_uid: build_owner_rows(identities, publication_id_by_uid),
                canonical_uids=canonical_uids,
            )
            report["applied_counts"] = {
                "new_scholars_upserted": applied_counts[0],
                "existing_scholars_updated": applied_counts[1],
                "scholar_universities_updated": applied_counts[2],
                "scholar_publications_inserted_or_updated": applied_counts[3],
                "publication_owner_links_upserted": applied_counts[4],
            }

        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report
    finally:
        await conn.close()


async def run_affiliation_repair(*, apply: bool, report_path: Path) -> dict[str, Any]:
    conn = await asyncpg.connect(
        host=settings.POSTGRES_HOST,
        port=settings.POSTGRES_PORT,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        database=settings.POSTGRES_DB,
    )
    try:
        org_name_mapping = await load_org_name_mapping(conn)
        scholar_rows = [
            dict(row)
            for row in await conn.fetch(
                """
                SELECT id, university, source_id, custom_fields
                FROM scholars
                WHERE custom_fields ? 'icml_2026_import'
                """
            )
        ]
        owner_rows = [
            dict(row)
            for row in await conn.fetch(
                """
                SELECT owner_link_id, source_details
                FROM publication_owners
                WHERE confirmed_by = $1
                """,
                ADDED_BY,
            )
        ]
        scholar_updates, scholar_university_updates = build_scholar_affiliation_repair_rows(
            scholar_rows,
            org_name_mapping,
        )
        owner_updates = build_owner_affiliation_repair_rows(owner_rows, org_name_mapping)

        if apply:
            async with conn.transaction():
                if scholar_updates:
                    await conn.executemany(
                        """
                        UPDATE scholars
                        SET
                          university = COALESCE($2, university),
                          custom_fields = $3::jsonb,
                          updated_at = now()
                        WHERE id = $1
                        """,
                        scholar_updates,
                    )
                if owner_updates:
                    await conn.executemany(
                        """
                        UPDATE publication_owners
                        SET source_details = $2::jsonb,
                            updated_at = now()
                        WHERE owner_link_id = $1
                        """,
                        owner_updates,
                    )

        report = {
            "generated_at": datetime.now(UTC).isoformat(),
            "applied": apply,
            "summary": {
                "scholars_scanned": len(scholar_rows),
                "scholar_affiliation_metadata_to_update": len(scholar_updates),
                "scholar_universities_to_update": scholar_university_updates,
                "publication_owner_affiliations_to_update": len(owner_updates),
            },
            "scholar_update_samples": [
                {"scholar_id": scholar_id, "university": university}
                for scholar_id, university, _ in scholar_updates[:100]
            ],
            "publication_owner_update_samples": [
                {"owner_link_id": owner_link_id}
                for owner_link_id, _ in owner_updates[:100]
            ],
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report
    finally:
        await conn.close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import ICML 2026 paper authors into scholars and publication tables.",
    )
    parser.add_argument("--apply", action="store_true", help="Write changes to the database. Default is dry-run.")
    parser.add_argument(
        "--repair-affiliations-only",
        action="store_true",
        help="Only repair existing ICML 2026 imported affiliation translations and scholar universities.",
    )
    parser.add_argument("--report", default=str(DEFAULT_REPORT_PATH), help="Path to JSON report.")
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    if args.repair_affiliations_only:
        report = await run_affiliation_repair(apply=bool(args.apply), report_path=Path(args.report))
    else:
        report = await run_import(apply=bool(args.apply), report_path=Path(args.report))
    print(json.dumps(report["summary"], ensure_ascii=False))
    print(f"report_saved={Path(args.report)}")


if __name__ == "__main__":
    asyncio.run(main())

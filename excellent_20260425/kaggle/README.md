# Kaggle Crawler

从 Kaggle 竞赛平台获取参赛学生信息。

## 认证配置

1. 登录 https://www.kaggle.com/settings
2. 滚动到 **API** 区域
3. 点击 **Create New API Token** 下载 `kaggle.json`
4. 保存到 `~/.kaggle/kaggle.json` 并设置权限：
   ```bash
   mkdir -p ~/.kaggle
   mv ~/Downloads/kaggle.json ~/.kaggle/
   chmod 600 ~/.kaggle/kaggle.json
   ```

## 数据说明

- **competitions**: 热门竞赛列表（前10个）
- **top_competitors**: 各竞赛排行榜前5名的参赛者

## 运行爬虫

```bash
source /tmp/.kaggle-env/bin/activate
python3 /data/dataset/excellent_20260425/kaggle/crawler.py
```

## 输出文件

- `results.json` - 竞赛和参赛者数据

## 爬取时间

2026-04-25

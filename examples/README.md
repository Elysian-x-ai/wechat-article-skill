# 示例

跑通脚本链路的最小样例：

```bash
cd examples
python ../skills/write-wechat-article/scripts/image_meta.py images/
python ../skills/write-wechat-article/scripts/make_plan.py article-sample.md images/ > plan.json
python ../skills/write-wechat-article/scripts/build_layout_js.py plan.json > layout.txt
```

`article-sample.md` 是一个虚构产品的短教程，用来演示"图随文走"的写法：

- 正文里的 `![说明](images/NN-xxx.png)` 标记就是图片应该出现的位置；
- 截图按 `NN-` 两位序号命名，序号即上传顺序，也是正文顺序；
- `make_plan.py` 从每个标记往上找**全文唯一**的段落作为锚点；找不到就报错退出，不会猜。

`images/` 里放的是生成的占位图（纯色块，标注了尺寸），用来让脚本跑得通。真实使用时应换成自己的截图。

> 注意：`make_plan.py` 输出到 stdout 的 `plan.json` 里 `src` / `id` 是空的 —— 这两项要等截图上传进素材库、harvest 出 CDN 地址后再用 `--cdn cdn.json` 合并。示例不涉及上传，所以忽略即可。

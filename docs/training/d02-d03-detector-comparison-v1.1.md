# D02/D03 Detector Comparison v1.1

三者均使用冻结 `detect-d02-d03-v0.1`；表内为真实 val 结果。YOLO26s 未达到晋级闸门，因此没有执行 candidate test，active detector 不变。

| Model | imgsz | P | R | mAP50 | mAP50-95 | D02 AP | D03 AP | latency ms/image | peak VRAM | model bytes |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| YOLO26n | 640 | 0.331108 | 0.242798 | 0.193225 | 0.083132 | 0.037191 | 0.129074 | 6.471 | NOT_AVAILABLE | 5394053 |
| YOLO26n | 960 | 0.358709 | 0.261359 | 0.221814 | 0.094648 | 0.040010 | 0.149285 | 8.191 | 10620080640 | 5459589 |
| YOLO26s | 640 | 0.321941 | 0.299039 | 0.238414 | 0.102231 | 0.039505 | 0.164956 | 10.177 | 7118001664 | 20319301 |

## Promotion gate

- overall mAP50-95 relative gain：8.012%
- D02 AP relative gain：-1.261%
- D02 Recall relative gain：7.368%
- 通过提升项：0/3（要求至少 2）
- latency：10.177 ms，限制 14.334 ms，结果 PASS
- 最终：`KEEP_CURRENT_ACTIVE`；candidate test 未执行。

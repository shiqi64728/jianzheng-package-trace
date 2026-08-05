# 外部manifest模板 v0.1

- `external-manifest-v0.1.template.csv`：仅包含外部schema表头，UTF-8 BOM，可用WPS/Excel打开。
- `external-manifest-v0.1.example.csv`：只包含虚拟classification、bbox、pair和statistics记录，不引用真实外部图片。
- 外部记录使用 `external_record_id`，不得添加内部 `package_id`、`sequence_id`、`node_id`、`capture_time` 或 `first_abnormal_node`。
- 所有路径必须相对于外部数据根目录并使用 `/`；模板和示例不得用于伪造真实物流节点。
- bbox示例只保留bbox，没有伪造polygon；pair示例保持 `unresolved`，没有伪造N1/N2。
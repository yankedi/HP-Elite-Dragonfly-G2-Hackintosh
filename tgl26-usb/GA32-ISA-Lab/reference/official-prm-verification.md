# PRM 来源复核

Intel 官方 Tiger Lake 索引：
https://www.intel.com/content/www/us/en/docs/graphics-for-linux/developer-reference/1-0/tiger-lake.html

索引的 Volume 8 官方附件： https://cdrdv2.intel.com/v1/dl/getcontent/703062

已下载为 `tgl-command-stream-official.pdf`：970784 B，SHA256
`8f69aa400472286fb2208aeaf90883418c6c3c6ae69c52f9344235daf04896b2`。
与先取的镜像 `tgl-command-stream.pdf` **逐字节相同**；因此镜像来源缺口已消除。

原文 December 2021 Revision1.0，Doc Ref IHD-OS-TGL-Vol8-12.21，Memory Data Ordering：
PIPE_CONTROL stalling + post-sync 为 non-posted，要求先前 posted memory writes 达到 global observable 点。
该规范说明 stall 等待前序依赖的机制，不能从规范推断本次等待对象必然是某一 Shader。

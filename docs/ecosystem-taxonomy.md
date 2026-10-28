# MoonBit 生态组件调研分类学（mooncakes.io 扫描清单）

> 目的：为系统性扫描 mooncakes.io（3061 包）提供**可枚举、无盲区**的三层分类学，替代"直觉+部分分类学"提问。
> 用法：每个叶子能力转化为 1-3 条语义检索查询（`python3 -m indexer.search "<能力关键词>"`），按状态列决定检索深度——UNEXPLORED 是本轮重点。
> 状态定义：EXPLORED = 此前调研已查询过（结果见 moonbit-ecosystem-gaps.md）；UNEXPLORED = 尚未系统查询，为空白挖掘重点。

## 分类体系对标

本分类学不凭空捏造，横向对标六个体系后合并裁剪：

| 对标体系 | 取用部分 |
|---|---|
| crates.io registrar categories | 大域骨架（database、network-programming、parser-implementations、text-processing 等） |
| PyPI trove classifiers | 科学计算、行业垂直维度标记 |
| awesome-rust / awesome-python / awesome-javascript | 子域目录结构（按"开发者实际找包的路径"组织） |
| ACM CCS (2012) | 保证理论计算机门类覆盖（软件及其工程 / 计算方法论 / 安全与隐私） |
| Wikipedia 软件类别 | 补齐应用软件门类（办公、行业、媒体） |
| 行业垂直实践 | 金融（FIX/清算）、医疗（DICOM/FHIR）、工控（Modbus/OPC-UA）、游戏（netcode/ECS）、科学计算（HDF5/CAS） |

## 统计总览

| 指标 | 数值 |
|---|---|
| 大域 | **14** |
| 子域 | **67** |
| 叶子能力 | **200** |
| EXPLORED（已查） | 86（43.0%） |
| UNEXPLORED（未查） | **114（57.0%）** |

按大域分布：

| # | 大域 | 子域 | 叶子 | EXPLORED | UNEXPLORED |
|---|---|---|---|---|---|
| A | 基础数据结构与算法 | 5 | 11 | 2 | 9 |
| B | 数据引擎与存储 | 5 | 25 | 10 | 15 |
| C | 分布式系统与中间件 | 4 | 13 | 4 | 9 |
| D | 网络与协议 | 4 | 15 | 7 | 8 |
| E | 语言工具链与运行时 | 4 | 9 | 0 | 9 |
| F | 安全与密码学 | 6 | 23 | 16 | 7 |
| G | 文本、排版与文档 | 6 | 18 | 8 | 10 |
| H | 科学计算与工程 | 5 | 13 | 4 | 9 |
| I | 多媒体与图形 | 5 | 12 | 7 | 5 |
| J | AI 与 LLM 应用 | 4 | 10 | 3 | 7 |
| K | 垂直行业 | 6 | 19 | 7 | 12 |
| L | 前端交互组件 | 6 | 18 | 12 | 6 |
| M | 系统与运行时 | 4 | 8 | 5 | 3 |
| N | 测试与质量 | 3 | 6 | 1 | 5 |
| **合计** | **14** | **67** | **200** | **86** | **114** |

---

# A. 基础数据结构与算法

通用算法积木层——多数应用包的下游依赖，生态成熟度的"地基"。

## A1 高级容器

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| 持久化不可变数据结构 | HAMT/RRB 等结构共享的不可变 Map/Vector，函数式状态管理与 undo 的底座 | im、immer | UNEXPLORED |

## A2 索引与并发容器

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| 有序索引与并发容器 | 跳表/B+树/ART 自适应字典，及 SPSC/MPMC 无锁队列、环形缓冲 | crossbeam-skiplist、art、rtrb | UNEXPLORED |
| 压缩位图与概率集合 | Roaring 位图、布隆过滤器、HyperLogLog 基数估计 | roaring、bloom、ddsketch | UNEXPLORED |

## A3 图与几何

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| 图算法库 | 最短路/连通性/拓扑排序/中心性/社区发现的通用图算法集 | petgraph、networkx | UNEXPLORED |
| 计算几何 | 凸包、Voronoi/Delaunay 三角化、多边形布尔运算、线段相交 | spade、shapely、geo + geo-types | UNEXPLORED |
| 组合优化与规划 | TSP、指派问题（匈牙利算法）、整数线性规划求解 | OR-Tools、PuLP、good_lp | UNEXPLORED |

## A4 数值与符号

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| 高精度 decimal 与大整数 | 任意精度十进制/整数运算，金融与科学计算刚需 | rust_decimal、num-bigint、decimal.js | EXPLORED |
| 符号计算与数论（CAS） | 表达式化简、方程求解、素数/模逆/中国剩余等数论工具 | sympy、mathics | UNEXPLORED |
| 自动微分 | 前向/反向模式求导，科学计算与 ML 框架的内核 | enzyme、autodiff | UNEXPLORED |
| 约束求解与 SAT | SAT/SMT/CP 求解器或其封装 | z3、varisat、picosat | EXPLORED |

## A5 随机与哈希

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| 非密码哈希族 | xxHash/murmur/FNV 等高速非安全哈希，哈希表与分片的基础 | xxhash-rust、twox-hash、murmur3 | UNEXPLORED（xxhash/murmur 部分已探） |

---

# B. 数据引擎与存储

从驱动到引擎本体：上轮只查了"驱动"，引擎内核（KV/LSM/时序/图/向量）全部未探。

## B1 存储引擎与驱动

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| SQL/NoSQL 数据库驱动 | postgres/mysql/redis/mongo/sqlite 客户端协议实现 | sqlx、redis-rs、rusqlite | EXPLORED |
| 嵌入式 KV 与 LSM 引擎 | 无服务端嵌入式键值存储（LSM-Tree/日志结构/B+树文件格式） | sled、rocksdb、redb | UNEXPLORED |
| WAL 与 MVCC 事务原语 | 预写日志、多版本并发控制、快照隔离等事务机制库 | redb、parity-db | UNEXPLORED |
| 嵌入式分析引擎（OLAP） | 进程内列式 SQL 引擎（duckdb 形态），面向分析负载 | duckdb、glaredb | UNEXPLORED |
| 时序数据库引擎 | 时间分区/降采样/保留策略的时序存储内核 | influxdb、questdb、timescale | UNEXPLORED |
| 图数据库与图查询 | 属性图存储与图遍历/图查询语言（cypher/gremlin 风格） | cozodb、memgraph | UNEXPLORED |

## B2 搜索与向量

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| 全文搜索引擎内核 | 倒排索引、分词、相关性打分的嵌入式搜索库 | tantivy、lucene、meilisearch | EXPLORED |
| 向量数据库与 ANN 索引 | HNSW/IVF/PQ 近邻索引与向量检索库 | qdrant、usearch、hnswlib | UNEXPLORED |

## B3 序列化与配置格式

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| JSON 族 | JSON/JSON5/JSONC 解析、JSONPath 查询、JSON Patch/merge | serde_json、jsonpath-rust | EXPLORED（隐含） |
| IDL 二进制协议族 | protobuf(+gRPC)/flatbuffers/avro/cbor schema 驱动序列化 | prost、flatc、apache-avro-rs、ciborium | EXPLORED |
| MsgPack 二进制序列化 | 比 JSON 紧凑的二进制对象格式（常用于 RPC/MQ 载荷） | rmp-serde、rmpv | UNEXPLORED |
| YAML/TOML/INI 配置格式 | 配置文件解析与写出（TOML 是 Rust/cargo 生态标配） | serde_yaml、toml | UNEXPLORED |
| XML 与 XPath | 流式 XML 解析、DOM、XPath/XSLT 查询变换 | quick-xml、roxmltree、libxml2 | UNEXPLORED |
| 通用压缩格式 | deflate/gzip/zstd/lz4/brotli/xz 流与块压缩 | flate2、zstd-rs、lz4_flex | EXPLORED |
| 归档格式读写 | tar/zip/7z/rar 归档创建与解包（含稀疏/符号链接/权限位） | tar、sevenz-rust、libarchive | UNEXPLORED（zip 解包已探，写入未探） |

## B4 科学与列式格式

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| Parquet 与 Arrow 列式内存 | 列式文件格式与零拷贝内存模型，数据互操作基础 | arrow-rs、parquet2 | UNEXPLORED |
| HDF5/NetCDF 科学格式 | 多维科学数组文件格式，地球/气候/物理数据事实标准 | hdf5、netcdf | UNEXPLORED |

## B5 查询处理与流水线

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| SQL 解析器与方言转换 | SQL→AST 解析、方言翻译、SQL 格式化 | sqlparser-rs、datafusion、sqlformat | UNEXPLORED |
| 查询构建器 | 类型安全 SQL/查询 DSL 组装器 | sea-query、knex、squirrel | EXPLORED |
| 公式引擎 | 表达式求值、电子表格函数集、依赖重算 | hyperformula、formulajs | EXPLORED |
| DataFrame 计算内核 | 惰性/并行列式数据帧与表达式优化执行 | polars、datafusion | UNEXPLORED |
| 流计算与 CDC | 事件时间窗口/join/watermark 语义，及变更数据捕获管道 | apache flink、arroyo、debezium | UNEXPLORED |
| CRDT 与离线同步 | 无冲突复制数据类型、协同编辑合并 | automerge、yjs、yrs | EXPLORED |
| 查询缓存 | 请求级数据缓存、失效/去重/重验证策略 | react-query、apollo client | EXPLORED |
| DAG 数据流水线编排 | 任务 DAG 声明、调度、缓存与血缘 | airflow、dagster、prefect | EXPLORED |

---

# C. 分布式系统与中间件

上轮完全未触及的大域：共识、消息、服务治理整族空白。

## C1 共识与协调

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| Raft/Paxos 共识库 | 复制状态机、领导者选举、日志复制（分布式存储的内核） | openraft、etcd-raft、raft-rs | UNEXPLORED |
| gossip 成员协议 | SWIM 式故障检测与成员传播（集群自组织） | hashicorp/memberlist、chitchat | UNEXPLORED |
| 分布式锁与领导选举 | 跨进程互斥、租约、选主原语 | redlock、etcd concurrency | UNEXPLORED |

## C2 消息系统

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| 消息队列协议客户端 | AMQP/Kafka(线协议)/NATS/STOMP 的生产级客户端 | lapin、rdkafka、nats.rs | UNEXPLORED |
| MQTT 生态 | MQTT 客户端/broker 库：QoS、遗嘱、保留消息、会话 | rumqttc、emqx、eclipse paho | UNEXPLORED |

## C3 服务治理与应用组件

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| 服务发现与注册中心 | 服务注册、健康检查、DNS/HTTP 发现接口 | consul、nacos、eureka | UNEXPLORED |
| 配置中心 | 集中配置存储、动态下发、灰度推送 | apollo、nacos、etcd | UNEXPLORED |
| 弹性模式 | 熔断器、重试预算、超时、舱壁隔离等容错模式库 | tower、resilience4j、failsafe-rs | UNEXPLORED |
| RBAC 权限模型 | 角色/策略/资源三元鉴权与策略引擎 | casbin、casl、oso | EXPLORED |
| 任务队列 | 延迟作业、优先级队列、重试死信的后台任务框架 | sidekiq、river、celery | EXPLORED |
| 功能开关 | 远程特性开关、灰度百分比、A/B 分流 | unleash、flagsmith、launchdarkly | EXPLORED |
| 规则引擎 | JsonLogic/RETE 等业务规则求值与链式编排 | jsonlogic、durable-rules | EXPLORED |

## C4 一致性协议

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| 分布式事务 | Saga/TCC/两阶段提交的编排与补偿框架 | dtm、seata | UNEXPLORED |

---

# D. 网络与协议

传输层已查较多，但应用协议（邮件/文件传输/代理）与 Web 服务端整族未探。

## D1 传输层

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| socket 与网络原语 | TCP/UDP socket、netcat 级工具原语 | mio、socket2 | EXPLORED |
| 异步运行时 | 事件循环、executor、定时器、任务调度 | tokio、smol、monoio | EXPLORED |
| QUIC/HTTP3 | QUIC 传输协议与 HTTP/3 客户端服务端 | quinn、s2n-quic、h3 | UNEXPLORED |
| WebRTC 与 ICE | 点对点实时音视频/数据通道、NAT 打洞 | webrtc-rs、str0m、mediasoup | UNEXPLORED |

## D2 Web 生态

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| HTTP(S) 客户端 | 连接池、重定向、代理、证书校验的完整客户端 | reqwest、hyper、ureq | EXPLORED |
| Web 服务端框架 | 路由、中间件、静态文件、优雅关停的服务框架 | axum、actix-web、rocket | UNEXPLORED |
| WebSocket | RFC 6455 全双工协议客户端/服务端（含压缩扩展） | tungstenite、tokio-tungstenite | UNEXPLORED |
| SSE 与 Webhook | Server-Sent Events 流解析与 webhook 签名验签/重投递 | eventsource-stream、svix | UNEXPLORED |
| HTTP 配套（multipart/cookie/OpenAPI） | multipart 编解码、cookie jar、OpenAPI 文档生成 | multer、utoipa、openapiv3 | EXPLORED |
| Web 抓取基元 | robots.txt/sitemap 解析、RSS/Atom 订阅、CSS 选择器 | scraper、feed-rs、sitemap | EXPLORED |

## D3 应用协议

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| DNS | DNS 编解码、解析器、DoH/DoT | hickory-dns、c-ares | EXPLORED |
| 邮件协议（SMTP/IMAP/POP3/MIME） | 邮件发送、收件箱拉取、MIME 解析与邮件地址解析 | lettre、async-imap、mail-parser | UNEXPLORED（MIME 解析部分已探） |
| FTP/SFTP 文件传输 | FTP/FTPS 客户端与 SFTP（SSH 子系统）传输 | suppaftp、ssh2 | UNEXPLORED |

## D4 观测与代理

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| pcap 抓包 | libpcap 格式解析与抓包统计 | pcap、pnet | EXPLORED |
| SOCKS 代理协议 | SOCKS4/5 客户端与服务端库（HTTP CONNECT 代理） | fast-socks5、shadowsocks-rust | UNEXPLORED |

---

# E. 语言工具链与运行时

MoonBit 定位为语言工具链友好生态（已有 30+ parser/codec 包），但工具链"深水区"全部未探。

## E1 语法分析

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| parser 生成器与增量解析 | PEG/LR/LALR parser 生成器，及 tree-sitter 式增量解析/语法高亮 | lalrpop、pest、tree-sitter | UNEXPLORED |

## E2 编译与执行

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| 字节码 VM 与解释器框架 | 可嵌入脚本语言的字节码编译+虚拟机骨架 | rune、rhai、wren | UNEXPLORED |
| 编译器后端与 JIT | SSA/IR、寄存器分配、机器码生成 | cranelift、inkwell (LLVM) | UNEXPLORED |
| WASM 工具链（解析/验证/汇编） | wasm 二进制解析、验证、文本格式互转、组件模型 | wasm-tools（wasmparser/wasm-encoder） | UNEXPLORED |
| WASM 运行时与 WASI | 嵌入式 wasm 执行引擎与宿主接口绑定 | wasmtime、wasmer、wasm3 | UNEXPLORED |

## E3 诊断与二进制分析

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| 调试器与 DWARF | GDB Remote/DAP 调试协议骨架与 DWARF 调试信息解析 | gdbstub、gimli | UNEXPLORED |
| 性能分析器 | CPU 采样、火焰图聚合、内存分配追踪 | pprof-rs、inferno | UNEXPLORED |
| 反汇编与 ELF/PE/Mach-O 解析 | 多架构反汇编器与可执行文件格式解析/重定位 | iced-x86、capstone、goblin | UNEXPLORED |

## E4 开发者集成

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| LSP 与代码格式化 | 语言服务器协议框架与 pretty-printer 代码格式化引擎 | tower-lsp、lsp-server、prettyplease | UNEXPLORED |

---

# F. 安全与密码学

应用安全扫描件已覆盖密集；前沿密码（ZK/MPC/门限/同态）与认证新范式整族未探。

## F1 密码原语

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| 密码学原语 | 对称/非对称/签名/MAC/密钥协商、密码哈希（argon2/bcrypt）、CSPRNG | rustcrypto、libsodium、ring | EXPLORED |
| TLS 协议栈 | TLS1.2/1.3 客户端服务端、证书链校验、会话恢复 | rustls、native-tls、boring | EXPLORED |
| 后量子密码 PQC | Kyber/ML-KEM、Dilithium/ML-DSA 等 NIST 标准化后量子算法 | liboqs、pqcrypto | UNEXPLORED |
| 侧信道防护 | constant-time 断言、秘密类型封装、时间安全比较 | subtle、secrecy | UNEXPLORED |

## F2 认证与密钥管理

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| JWT/OAuth/OIDC | 令牌签发校验、授权码/PKCE 流程、OIDC 发现 | jsonwebtoken、oauth2、openidconnect | EXPLORED |
| 一次性口令与 PAKE | TOTP/HOTP 及 SRP/OPAQUE 密码认证密钥协商 | totp-rs、srp、opaque-ke | EXPLORED |
| FPE 与 age 加密 | 格式保留加密（FF1/FF3）与 age 文件加密 | ff3、age | EXPLORED |
| SOPS 式密钥管理 | 密文入库的秘密管理、多后端解封流程 | sops、vals | EXPLORED |
| WebAuthn/passkey | FIDO2 无密码认证：注册/断言流程、CTAP | webauthn-rs、fido2-lib | UNEXPLORED |

## F3 前沿密码

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| 零知识证明（ZKP） | SNARK/STARK 证明系统、电路 DSL、递归证明 | arkworks、gnark、halo2 | UNEXPLORED |
| 安全多方计算（MPC） | 秘密分享协议、隐私集合求交、联合统计 | MP-SPDZ、JIFF | UNEXPLORED |
| 门限签名与秘密分享 | FROST 门限 Schnorr/ECDSA、Shamir 秘密分享 | frost-core、vsss-rs | UNEXPLORED |
| 同态加密（FHE） | BFV/CKKS/TFHE 全同态方案与 SIMD 明文打包 | tfhe-rs、concrete、SEAL | UNEXPLORED |

## F4 Web 与应用防护

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| WAF 与限流 | 规则引擎式 Web 应用防火墙与令牌桶/滑动窗限流 | coraza、governor | EXPLORED |
| Web 安全头/注入防护/脱敏 | CSP/HSTS 头管理、XSS/SQLi 载荷消毒、日志脱敏 | helmet、ammonia | EXPLORED |

## F5 扫描与供应链

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| SAST 与密钥扫描 | 静态代码污点分析与硬编码凭据检测 | semgrep、codeql、trufflehog | EXPLORED |
| fuzzing | 覆盖率引导模糊测试与语料管理 | afl++、cargo-fuzz | EXPLORED |
| SBOM 与许可合规 | 依赖物料清单生成（SPDX/CycloneDX）与许可证冲突检测 | syft、cyclonedx、askalono | EXPLORED |
| 签名验签与沙箱策略 | 制品签名（sigstore 风格）与执行沙箱策略语言 | cosign、minisign | EXPLORED |

## F6 审计与取证

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| 证书透明度与 MITM 代理 | CT 日志监控查询与中间人检测/测试代理 | certstream、mitmproxy | EXPLORED |
| SIEM 日志与 SSH 审计 | Sigma 规则日志检测与 SSH 配置/算法审计 | sigma、ssh-audit | EXPLORED |
| 文件完整性监控与压缩炸弹防护 | FIM 基线比对与解压炸弹防护 | tripwire、osquery | EXPLORED |
| YARA 规则检测 | YARA 规则引擎与样本模式匹配 | yara-rust、libyara | EXPLORED |

---

# G. 文本、排版与文档

Unicode/NLP 高层已探；排版"四件套"（字体/塑形/断行/光栅化）整族未探。

## G1 Unicode 与本地化

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| Unicode 底层算法与编码检测 | 规范化（NFC/NFD）、分段、双向算法（BiDi），及字符集探测/转换 | icu4x、unicode-segmentation、encoding_rs、chardetng | UNEXPLORED |
| i18n 国际化 | 消息目录、ICU 复数/性别/日期格式 | fluent、rust-i18n、gettext | EXPLORED |

## G2 NLP

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| 中文 NLP（分词/拼音/NER） | 分词、拼音转换与命名实体识别 | jieba-rs、pinyin、hanlp | EXPLORED |
| 机器翻译 | 神经/统计机器翻译推理与语料对齐 | Argos Translate、MarianNMT | EXPLORED |

## G3 模式匹配

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| 正则引擎与模糊匹配 | RE2/PCRE 语义正则引擎，及 fzf 式模糊匹配/编辑距离检索 | regex、pcre2、nucleo | UNEXPLORED |

## G4 字体与塑形

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| 字体解析 | OpenType/TTF/OTF/WOFF2 字体文件解析与子集化 | ttf-parser、fonttools | UNEXPLORED |
| 文本塑形（shaping） | 字形选择、阿拉伯文/天城文连字、组合标记定位 | rustybuzz、harfbuzz | UNEXPLORED |

## G5 排版

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| 断行/连字符/两端对齐 | Knuth-Plass 断行、多语言连字符表、字距调整 | knuth-plass、hypher | UNEXPLORED |
| 字形光栅化 | 轮廓转位图、抗锯齿/SDF、提示（hinting） | ab_glyph、swash、fontdue | UNEXPLORED |
| 段落排版引擎 | 双向文本、混合样式、行内对象的段落级布局 | cosmic-text、parley | UNEXPLORED |

## G6 文档与编辑基元

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| Markdown 解析与 AST | CommonMark/GFM 兼容解析、AST 变换与渲染出口 | pulldown-cmark、comrak | UNEXPLORED |
| PDF/DOCX/PPTX 生成 | 办公文档写出（含模板填充与分页） | typst、printpdf、docx-rs | EXPLORED |
| PDF 渲染 | PDF 内容流解释、字形定位、页面栅格化（阅读器方向） | pdfium-render、mupdf-rs | UNEXPLORED |
| LaTeX 与数学公式 | 公式 AST（MathML/TeX）解析与排版渲染 | tectonic、katex | UNEXPLORED |
| 富文本模型 | 文档树+标记模型、协同编辑数据结构 | prosemirror、slate、quill | EXPLORED |
| 模板引擎 | 逻辑最小化模板语法编译与安全渲染 | handlebars、tera、minijinja | EXPLORED |
| Diff-Merge | 文本/结构化 diff、三方合并、移动检测 | similar、diff-match-patch | EXPLORED |
| OCR | 光学字符识别引擎与版面分析 | tesseract、paddleocr | EXPLORED |

---

# H. 科学计算与工程

BLAS/单位/地理格网已探；信号处理（FFT/滤波/MIDI）与数值方法整族未探。

## H1 线性代数

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| BLAS 与基础线性代数 | 矩阵运算、分解（LU/QR/SVD/EVD）与 BLAS 接口 | ndarray、nalgebra、matrixmultiply | EXPLORED |
| 稀疏矩阵与求解器 | CSR/CSC 稀疏格式与直接/迭代求解 | sprs、suitesparse | UNEXPLORED |

## H2 数值与统计

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| ODE 与数值积分 | 常微分方程求解器（RK45/BDF）与自适应求积 | peroxide、sundials | UNEXPLORED |
| 统计分布与假设检验 | 概率分布、描述统计、t 检验/卡方/回归推断 | statrs、rand-distr | UNEXPLORED |

## H3 优化与量纲

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| 非线性优化与最小二乘 | 梯度下降族、Levenberg-Marquardt、约束优化 | argmin、nlopt | UNEXPLORED |
| 单位换算 | 量纲分析、单位换算与解析 | uom、units | EXPLORED |

## H4 信号处理

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| FFT 与谱分析 | 实/复 FFT、STFT、功率谱与窗函数 | rustfft、realfft | UNEXPLORED |
| 滤波器与重采样 | IIR/FIR 设计（biquad）、任意比率重采样 | biquad、rubato | UNEXPLORED |
| MIDI 与乐理 | MIDI 文件/事件编解码、音高/和弦/调式音乐理论库 | midly、rust-music-theory | UNEXPLORED |
| 音频指纹与声纹 | Chromaprint 式指纹、说话人嵌入与比对 | chromaprint、aubio | UNEXPLORED |

## H5 地理与时空

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| H3 地理格网 | 层级六边形格网索引与地理围栏 | h3o、uber/h3 | EXPLORED |
| 地图投影与坐标变换 | EPSG 投影、大地坐标↔平面坐标、椭球变换 | proj (georust)、proj4rs | UNEXPLORED |
| 天文历法与星历 | 日月位置、节气/月相、儒略日与星历计算 | swisseph、skyfield | EXPLORED |

---

# I. 多媒体与图形

编解码层已探；处理算子、色彩管理、GPU/渲染引擎层未探。

## I1 图像

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| 图像编解码 | PNG/JPEG/WebP/AVIF 等编码解码 | image、ravif、zune-image | EXPLORED |
| 图像处理算子 | 卷积、形态学、缩放/旋转、阈值与直方图（含 SIFT/Hough 经典 CV） | imageproc、photons、opencv | UNEXPLORED |
| 色彩管理 | ICC profile、CMYK↔RGB、宽色域（P3/Rec2020）变换 | lcms2-rs、palette | UNEXPLORED |

## I2 视频与元数据

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| 视频处理与 ffmpeg | 视频编解码、滤镜图、容器封装与 ffmpeg 绑定 | ffmpeg-next、ffmpeg-the-third | EXPLORED |
| 媒体文件元数据 | EXIF/ID3/IPTC 元数据读写与方向处理 | kamadak-exif、lofty、id3 | EXPLORED |

## I3 3D 渲染

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| 3D 格式（STL/GLTF） | 三角网格/场景图文件读写 | gltf、tobj、stl_io | EXPLORED |
| GPU 抽象层 | 跨后端图形 API 抽象（Vulkan/Metal/WebGPU） | wgpu、glow、vulkano | UNEXPLORED |
| 3D 场景渲染引擎 | 场景图、PBR 材质、光照与相机系统 | three-d、bevy_render | UNEXPLORED |

## I4 2D 绘图与动画

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| 2D 矢量绘图内核 | 路径/贝塞尔/描边填充/合成模式的绘图后端 | tiny-skia、piet、skia-safe | UNEXPLORED |
| SVG 图表 | SVG 生成与解析、图表语法（data-driven 图表库） | plotters、echarts、vega-lite | EXPLORED |
| 缓动与关键帧动画 | easing 函数集、时间线/关键帧插值 | gsap、d3-ease | EXPLORED |

## I5 音频

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| 音频编解码 | WAV/FLAC/MP3/Opus 编解码 | symphonia、hound | EXPLORED |

---

# J. AI 与 LLM 应用

推理（ONNX）已探；MoonBit 定位最契合的 LLM 配套族（tokenizer/RAG/eval/服务化）全部未探。

## J1 推理引擎

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| ONNX 推理 | ONNX Runtime 绑定或纯实现模型推理 | ort、tract | EXPLORED |
| 原生推理与训练框架 | 纯语言实现的张量库+autograd+训练循环 | candle、burn | UNEXPLORED |

## J2 数据与词法

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| tokenizer（BPE/SentencePiece） | 训练/加载分词器、词表与特殊 token 管理 | tiktoken-rs、tokenizers | UNEXPLORED |
| NPY 科学数据格式 | NumPy .npy/.npz 读写 | ndarray-npy、npyz | EXPLORED |

## J3 LLM 应用工程

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| LLM 客户端与 agent 编排 | 多厂商 API 客户端、工具调用循环、agent 拓扑 | async-openai、rig | UNEXPLORED |
| RAG 分块与检索管道 | 语义分块策略、嵌入、重排序管道组件 | LlamaIndex、text-splitter、fastembed | UNEXPLORED |
| prompt 管理与版本 | prompt 模板化、版本对比、线上回放 | langfuse、pezzo | UNEXPLORED |
| LLM eval 评测框架 | 断言式/LLM-as-judge 评测、回归数据集管理 | promptfoo、lm-evaluation-harness、DeepEval | UNEXPLORED |
| 推理服务化 | OpenAI 兼容 serving、KV cache、批调度 | vllm、llama.cpp server | UNEXPLORED |

## J4 语音

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| ASR/TTS | 语音识别与合成推理 | whisper-rs、piper、sherpa-onnx | EXPLORED |

---

# K. 垂直行业

行业协议族：金融（FIX）、地图（OSM/路径规划）、生医化、工控（CAN/OPC-UA）大量未探。

## K1 金融支付

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| 金融撮合与交易模拟 | 限价订单簿、价格时间优先撮合、回测模拟 | nautilus_trader、p2p-derivatives/matching-engine | EXPLORED |
| FIX 行情协议 | FIX 4.4/5.0 编解码与会话层（心跳/重传/序号） | QuickFIX、quickfix-rs | UNEXPLORED |
| 支付与对账 | 支付网关 SDK 对接、对账文件解析、复式记账 | async-stripe、wechat-pay、hledger、beancount | UNEXPLORED |

## K2 地图与出行

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| OSM 数据解析 | PBF/XML 解析、路网抽取与简化 | osmpbf、osmium | UNEXPLORED |
| 路径规划引擎 | 收缩层次/双向 Dijkstra/A* 大规模路网导航 | osrm、valhalla、graphhopper、fast_paths | UNEXPLORED |

## K3 生医化

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| 生物信息格式 | FASTA/FASTQ/VCF/PDB/BAM 读写与序列操作 | rust-bio、noodles、rust-htslib | UNEXPLORED |
| 化学信息学 | SMILES/InChI 解析、分子指纹与相似度 | rdkit、openbabel | UNEXPLORED |
| 医疗影像与标准 | DICOM/NIfTI 影像与 FHIR 互操作资源 | dicom-rs、dcm4che | EXPLORED |

## K4 工控与硬件

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| Modbus 与串口 | Modbus TCP/RTU 主从栈与串口通信 | tokio-modbus、libmodbus、serialport | EXPLORED |
| CAN 总线 | CAN 帧收发、DBC 解析、UDS/isotp 诊断 | socketcan、python-can、can-isotp | UNEXPLORED |
| OPC-UA | 工业互操作协议栈（地址空间/订阅/安全通道） | opcua (crate)、open62541 | UNEXPLORED |

## K5 区块链与游戏

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| 以太坊 SDK | 地址/交易/合约 ABI 与 RPC 客户端 | ethers-rs、alloy | EXPLORED |
| ECS 实体组件系统 | 实体-组件-数据导向架构内核 | bevy_ecs、specs、hecs | EXPLORED |
| 游戏 netcode 与回放 | rollback/帧同步网络代码、输入回放与录屏系统 | ggrs、bevy_replicon | UNEXPLORED |
| 模拟器（CHIP-8/GB） | 经典主机/掌机模拟器（CPU/PPU/APU 复刻） | boytacean、rustual-boy | UNEXPLORED |

## K6 自动化与效率

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| 通知机器人 | IM 机器人框架（Telegram/Slack/Matrix/钉钉） | teloxide、matrix-rust-sdk | EXPLORED |
| 二维码 | QR 生成/识别与纠错级别 | qrcode、rxing、zxing | EXPLORED |
| RPA 桌面自动化 | 键鼠模拟、窗口查找、屏幕截图流水线 | enigo、nut.js、RobotJS | UNEXPLORED |
| 无头浏览器与动态爬虫 | CDP 协议驱动浏览器、页面等待与抓取编排 | chromiumoxide、headless_chrome、fantoccini | UNEXPLORED |

---

# L. 前端交互组件

通用 UI 件已探密集；GUI 框架层、桌面集成与状态机范式未探。

## L1 数据输入

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| 动态表单 | Schema 驱动表单渲染、校验与联动 | Formily、formik、react-jsonschema-form | EXPLORED |
| 拖拽 | 拖拽排序、跨容器拖放、碰撞检测 | dnd-kit、react-dnd、sortablejs | EXPLORED |
| 快捷键管理 | 组合键注册、作用域与冲突处理 | hotkeys-js、mousetrap | EXPLORED |

## L2 数据展示

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| 表格引擎 | 虚拟滚动大数据表格、单元格编辑、聚合分组 | ag-grid、handsontable、glide-data-grid | EXPLORED |
| Excel/CSV 解析 | 工作簿读写、样式/公式/合并单元格 | calamine、SheetJS、exceljs | EXPLORED |
| 日历排班 | 日历视图、排班/资源预订、时区处理 | FullCalendar、toast-ui calendar | EXPLORED |

## L3 画布编辑

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| 节点图编辑器 | 流程图/计算图编辑：端口连线、自动布局 | reactflow、rete.js | EXPLORED |
| 无限画布 | 平移缩放画布、图形选择变换、对齐吸附 | tldraw、konva、excalidraw | EXPLORED |

## L4 交互原语

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| 撤销重做 | 命令栈/补丁式历史管理、事务合并 | zundo、immer patches | EXPLORED |
| 树形编辑器 | 大树虚拟化、增删改拖、多选与展开状态 | react-arborist | EXPLORED |
| 状态机 | 层级状态机/状态图定义与可视化执行 | xstate、statig、rust-fsm | UNEXPLORED |
| Schema 映射 | 异构 schema 字段映射与数据变换管道 | JSONata、JMESPath | EXPLORED |

## L5 GUI 与终端

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| TUI | 终端 UI 框架：部件、布局、事件 | ratatui、bubbletea | EXPLORED |
| GUI 工具包 | 保留模式/立即模式 GUI 部件库 | iced、egui、slint | UNEXPLORED |
| 窗口与事件循环 | 跨平台窗口创建与输入事件抽象 | winit、tao | UNEXPLORED |
| 无障碍（AccessKit） | UI 无障碍树暴露给屏幕阅读器/辅助技术 | accesskit | UNEXPLORED |

## L6 桌面集成

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| 剪贴板/托盘/系统通知 | 系统级集成：剪贴板读写、托盘图标、桌面通知 | arboard、tray-icon、notify-rust | UNEXPLORED |
| 文件系统监控 | 目录变更监听（inotify/FSEvents/ReadDirectoryChangesW） | notify、chokidar | UNEXPLORED |

---

# M. 系统与运行时

进程/信号/可观测已探；系统接口封装与 FFI 互操作层未探。

## M1 进程与信号

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| 进程管理 | 子进程孵化、管道、退出码与守护 | std::process、command-group | EXPLORED |
| 信号处理 | SIGINT/SIGTERM/SIGHUP 处理器注册与优雅退出 | signal-hook | EXPLORED |

## M2 系统互操作

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| 系统信息与硬件探测 | CPU/内存/磁盘/OS 信息与用户/权限查询 | sysinfo、os_info | UNEXPLORED |
| FFI 绑定/动态加载/分配器 | C 头文件绑定生成、动态库加载、自定义全局分配器 | bindgen、uniffi、libloading、mimalloc | UNEXPLORED |

## M3 可观测性

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| prometheus 指标 | 指标导出：counter/gauge/histogram 与 exposition 格式 | prometheus (crate)、metrics-rs | EXPLORED |
| tracing 追踪 | 结构化 span 日志与上下文传播 | tracing、tracing-subscriber | EXPLORED |
| OpenTelemetry | OTLP 导出、跨语言 trace 传播、语义约定 | opentelemetry-rust | UNEXPLORED |

## M4 调度

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| cron 调度 | cron 表达式解析与任务调度器 | cron、cronexpr | EXPLORED |

---

# N. 测试与质量

BDD/snapshot 已探；PBT/mock/覆盖率等工程化测试基建未探。

## N1 测试范式

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| BDD/cram/snapshot 测试 | Gherkin BDD、cram CLI 测试、golden 快照对比 | cucumber-rs、insta | EXPLORED |
| property-based 测试 | 随机用例生成、收缩（shrinking）、状态机测试 | proptest、quickcheck、hypothesis | UNEXPLORED |
| 契约测试 | 消费者驱动契约与 schema 幂等校验 | pact-rust、schemathesis | UNEXPLORED |

## N2 mock

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| mock 与 HTTP 假服务 | trait mock 生成与本地 HTTP mock server（含测试数据生成） | mockall、httpmock、fake-rs | UNEXPLORED |

## N3 覆盖率与基准

| 能力 | 说明 | 成熟生态参考 | 状态 |
|---|---|---|---|
| 覆盖率 | 行/分支覆盖率采集与报告（lcov/原生格式） | tarpaulin、cargo-llvm-cov | UNEXPLORED |
| 基准测试 | 统计稳健微基准与性能回归门禁 | criterion、divan | UNEXPLORED |

---

# UNEXPLORED 叶子全清单（114 项）

> 纯清单，供批量语义检索直接使用。建议每项 1-3 条查询词组合（中英各一）。

1. 持久化不可变数据结构（HAMT/RRB）
2. 有序索引与并发容器（跳表/B+树/ART/无锁队列）
3. 压缩位图与概率集合（Roaring/布隆/HyperLogLog）
4. 图算法库（最短路/连通性/中心性）
5. 计算几何（凸包/Voronoi/多边形布尔）
6. 组合优化与规划（TSP/指派/ILP）
7. 符号计算与数论（CAS）
8. 自动微分
9. 非密码哈希族（xxHash/murmur）
10. 嵌入式 KV 与 LSM 引擎
11. WAL 与 MVCC 事务原语
12. 嵌入式分析引擎（OLAP/duckdb 式）
13. 时序数据库引擎
14. 图数据库与图查询
15. 向量数据库与 ANN 索引（HNSW/IVF）
16. MsgPack 二进制序列化
17. YAML/TOML/INI 配置格式
18. XML 与 XPath/XSLT
19. 归档格式读写（tar/7z/rar 写入）
20. Parquet 与 Arrow 列式内存
21. HDF5/NetCDF 科学格式
22. SQL 解析器与方言转换
23. DataFrame 计算内核（polars 式）
24. 流计算与 CDC（窗口/watermark/变更捕获）
25. Raft/Paxos 共识库
26. gossip 成员协议（SWIM）
27. 分布式锁与领导选举
28. 消息队列协议客户端（AMQP/Kafka/NATS/STOMP）
29. MQTT 生态（客户端/broker/QoS）
30. 服务发现与注册中心（consul/nacos 式）
31. 配置中心（动态下发/灰度）
32. 弹性模式（熔断/重试/舱壁）
33. 分布式事务（Saga/TCC/2PC）
34. QUIC/HTTP3
35. WebRTC 与 ICE
36. Web 服务端框架（路由/中间件）
37. WebSocket（RFC 6455）
38. SSE 与 Webhook（签名/重投递）
39. 邮件协议（SMTP/IMAP/POP3）
40. FTP/SFTP 文件传输
41. SOCKS 代理协议
42. parser 生成器与增量解析（PEG/LR/tree-sitter）
43. 字节码 VM 与解释器框架
44. 编译器后端与 JIT（cranelift 式）
45. WASM 工具链（解析/验证/汇编/组件模型）
46. WASM 运行时与 WASI
47. 调试器与 DWARF（GDB remote/DAP）
48. 性能分析器（采样/火焰图）
49. 反汇编与 ELF/PE/Mach-O 解析
50. LSP 语言服务器与代码格式化
51. 后量子密码 PQC（Kyber/Dilithium）
52. 侧信道防护（constant-time）
53. WebAuthn/passkey（FIDO2）
54. 零知识证明（ZKP/SNARK/STARK）
55. 安全多方计算（MPC）
56. 门限签名与秘密分享（FROST/Shamir）
57. 同态加密（FHE：BFV/CKKS/TFHE）
58. Unicode 底层算法与编码检测（NFC/BiDi/chardet）
59. 正则引擎与模糊匹配（RE2/PCRE/fzf）
60. 字体解析（OpenType/WOFF2/子集化）
61. 文本塑形 shaping（harfbuzz 式）
62. 断行/连字符/两端对齐（Knuth-Plass）
63. 字形光栅化（SDF/抗锯齿）
64. 段落排版引擎（cosmic-text 式）
65. Markdown 解析与 AST（CommonMark/GFM）
66. PDF 渲染（内容流解释/栅格化）
67. LaTeX 与数学公式渲染
68. 稀疏矩阵与求解器（CSR/迭代法）
69. ODE 求解与数值积分（RK45/BDF）
70. 统计分布与假设检验
71. 非线性优化与最小二乘（LM 算法）
72. FFT 与谱分析（STFT/窗函数）
73. 滤波器设计与重采样（biquad/rubato）
74. MIDI 与乐理库
75. 音频指纹与声纹（chromaprint/aubio）
76. 地图投影与坐标变换（EPSG/proj）
77. 图像处理算子（卷积/形态学/SIFT/Hough）
78. 色彩管理（ICC/CMYK/宽色域）
79. GPU 抽象层（wgpu 式）
80. 3D 场景渲染引擎（PBR/场景图）
81. 2D 矢量绘图内核（tiny-skia 式）
82. 原生推理与训练框架（candle/burn 式）
83. tokenizer（BPE/SentencePiece）
84. LLM 客户端与 agent 编排
85. RAG 分块与检索管道（text-splitter/重排序）
86. prompt 管理与版本（langfuse 式）
87. LLM eval 评测框架（promptfoo 式）
88. 推理服务化（OpenAI 兼容 serving）
89. FIX 行情与交易协议
90. 支付对账与复式记账（stripe/hledger 式）
91. OSM 数据解析（PBF/XML）
92. 路径规划引擎（osrm/valhalla 式）
93. 生物信息格式（FASTA/FASTQ/VCF/PDB/BAM）
94. 化学信息学（SMILES/InChI/分子指纹）
95. CAN 总线与 UDS 诊断（DBC/isotp）
96. OPC-UA 工业互操作
97. 游戏 netcode 与回放系统（rollback/帧同步）
98. 模拟器（CHIP-8/GameBoy 复刻）
99. RPA 桌面自动化（键鼠模拟/窗口查找）
100. 无头浏览器与动态爬虫（CDP 协议）
101. 状态机框架（xstate 式层级状态机）
102. GUI 工具包（iced/egui 式）
103. 窗口与事件循环（winit 式）
104. 无障碍 AccessKit
105. 剪贴板/托盘/系统通知
106. 文件系统监控（notify 式）
107. 系统信息与硬件探测（sysinfo 式）
108. FFI 绑定生成/动态加载/自定义分配器
109. OpenTelemetry 客户端（OTLP）
110. property-based 测试（proptest 式）
111. 契约测试（pact 式）
112. mock 与 HTTP 假服务（mockall/httpmock，含测试数据生成）
113. 覆盖率工具（lcov/llvm-cov）
114. 基准测试框架（criterion 式）

---

## 第五轮补扫结果（2026-10-17，114 个 UNEXPLORED 叶子全量语义检索）

**结论：约 85% 已有实现，生态密度远超预期。** 子代理预测的 TOP10 空白全部被推翻：

| 原预测空白 | 实际实现 |
|---|---|
| Raft 共识 | `Lfan-ke/moonraft`（0.920） |
| 向量数据库 ANN | `trkbt10/vcdb`（0.927） |
| WASM 工具链 | `0xA672/mwp`（部分） |
| 字体+塑形 | `mizchi/font`（OTF/WOFF2）+ `moonbit-community/harfbuzz` 移植 |
| parser 生成器 | `Ljh684/MoonParse`（组合子） |
| AMQP/Kafka/NATS | `DDD12345-D/moon-amqp` |
| tar 写入 | `bobzhang/tar` |
| 消息队列生态 | `Duckweed/moon-mqtt` 全家 |

其他重量级发现：`moonbitstack/moonquic`（QUIC）、`justjavac/cdp`（Chrome DevTools 协议）、`Milky2018/wgpu_mbt`+`moon-egui`+`window`(winit 移植)+`moon_accesskit`、`CAIMEOX/symbit`（符号计算）、`Luna-Flow/autodiff`、`walkzzz/moon-geometry`（计算几何）、`xcc-ordinary/moonbit-roaring`、`qqq66668/moon_icc`（色彩管理）、`SupremeHuaji/moonsmiles`（化学）、`HK-SHAO/dsp`（FFT）、`ryota0624/moonbit_otel`、`f4ah6o/aletheia`（property 测试）、`Xpeng/mooncov`（覆盖率）、`kokic/katex-parser`、`Milky2018/vcode`（字节码 VM）+`mizchi/libjit`、`liying-han/moonresilience`（熔断）、`dxh8888/moonleasekit`（分布式租约）、`Han-Wentao/mooncontract`（契约测试）、`superbigcup325/moonlake`（嵌入式 OLAP）、`mizchi/bitx_wal`、`bobzhang/sqlglot`（SQL 转译）

### 甄别后的最终残余缺口（~20 项，低分且命中离题）

**前沿密码族（整族缺）**：后量子 PQC（Kyber/Dilithium）、ZKP/SNARK、MPC（注意：检索命中的 `colmugx/mcp` 是 Model Context Protocol，同形异义）、FHE 同态、门限签名 FROST/Shamir、constant-time 侧信道工具
**数据引擎深水区**：Parquet/Arrow 列式、时序数据库 TSDB、图查询语言（Cypher 式）
**分布式中间件**：gossip/SWIM 成员协议、服务发现注册中心、配置中心、Saga 分布式事务
**排版末端**：Knuth-Plass 断行、字形光栅化（SDF）
**科学/统计**：统计分布与假设检验库、原生 ML 训练框架（candle/burn 式）
**垂直行业**：FIX 行情协议、游戏 netcode/回放、CHIP-8/GB 模拟器
**工具链**：prompt 管理版本（langfuse 式）、mock/HTTP 假服务（httpmock 式）

### 方法论闭环

五轮扫描路径：直觉组件 → 安全场景 → 应用配套 → 行业分类 → 标准分类学全量。覆盖率 86+97/200 ≈ 92%（第五轮后基本全探）。语义检索召回率显著高于关键词（多轮验证），但需人工甄别低分命中与同形异义陷阱（tesseract/mcp/whisper 三例）。

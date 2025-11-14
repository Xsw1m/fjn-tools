# 具体优化

- 匹配方式
  - 预编译 lots_re = re.compile('(?:lot1|lot2|...)', re.I) ，一次 search 判断。
  - exclude_re = re.compile(r'(eng|spc)', re.I) 替代逐个 in 检查。
  - 扩展名用 lower.endswith(('.sum', '.txt')) 保持高效。
- 遍历方式
  - 改为 os.scandir 配合显式栈进行 DFS，避免 os.walk 额外的生成器与状态维护开销。
  - 使用 DirEntry.is_file(...) 与 is_dir(...) ，减少 stat 次数。
- 并发复制
  - ThreadPoolExecutor(max_workers=8) 并行执行复制任务，提升网络/磁盘 I/O。
  - 用锁保护统计数据更新，避免并发写导致计数异常。

# 性能影响（经验估算）

- 目录遍历由 os.walk → os.scandir ，在包含大量文件的目录下通常可提升 20%～ 50%。
- 并行复制在网络共享盘下受网络与磁盘限制，通常 1.5 ～ 3 倍提升（取决于瓶颈）。
- 正则与一次性匹配减少 Python 循环次数，轻微降低 CPU 开销。

# 代码要点

- 匹配逻辑
  - lots_re = re.compile(r'(?:' + '|'.join(map(re.escape, norm_lots)) + r')', re.IGNORECASE)
  - exclude_re = re.compile(r'(eng|spc)', re.IGNORECASE)
- 遍历
  - 使用 stack = [src_root] 与 os.scandir(base) ，对子目录 stack.append(Path(entry.path)) 。
- 复制
  - 提交至线程池 pool.submit(\_copy_one) ，复制失败时忽略继续。

# 进一步优化建议 TODO:

## 目录级剪枝是完全不可取的，但是动态线程数、缓存可以帮我加一下

- 扩展名优先裁剪：若目录下文件扩展名分布规律，可在目录层预估（例如不是 .sum 或 .txt 的大量文件目录），直接跳过，加快扫描。
- 动态线程数：根据 os.cpu_count() 与网络情况自适应：IO 密集可取 8–16 ，但需观察共享盘负载。
- 结果缓存（可选）：若同一 source_root 在短时间内重复查询，记录已匹配的目录结构 Hash 与结果，避免重复全量扫描。
- 扫描批次：先按目录名快速筛掉明显不相关的目录，再深入，提升命中率。

import os
import zipfile  # 用于解压缩 zip 文件
import re #引入正则表达式

class mappingNameCheck():  # 要加上self归类
    def __init__(self, TP):
        self.mapping_names = None
        self.zip_mapping_names = None
        self.TP = TP

    # 三、公共方法 用于通过正则匹配校验名字是否符合规范
    def validate_file_name(self, fileName) -> bool:
        # 解析正在表达式
        patten = re.compile(r'^OVT FT\+SLT_A V[3-4].0_[a-zA-Z0-9]{7}_(Nor|New[0-4])\.mapping$')
        # 返回是否符合规范 True/False
        return bool(patten.match(fileName))
    # 一、获取 mapping name
    def get_mapping_name(self):
        # 1. 指定文件夹路径 - 根路径 3270文件夹
        directory_path = r"\\172.33.10.11\3270"
        # 2. 查找mapping文件 "\\172.33.10.11\3270\中符合 TP 的文件或文件夹有哪些"
        files = [f for f in os.listdir(directory_path) if self.TP in f]  # 列表推导式
        # 3. 遍历文件列表
        for file in files:
            # 4. 如果该文件是 压缩包
            if '.zip' in file:
                # 5. 拼接出: 压缩包路径 以及 mapping 文件所存放的目标类路径
                zip_path = os.path.join(directory_path, file)
                target_path = 'Image/ProductFile/Category/'
                try:
                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:  # 解压Zip为 zipFile 文件类型
                        zip_names_results = [] # 初始化一个压缩包 mapping name合集
                        for file_info in zip_ref.infolist():  # 遍历 平铺子集
                            # 如果是 Category 文件夹
                            # if 'ProductFile/Category/' in entry.filename and entry.is_dir():
                            #     for file_info in zip_ref.infolist():
                            # 6. 判断筛选出子集中符合条件的 mapping
                            # ps1: 该文件不是文件夹 且 该文件以Image/ProductFile/Category/开头 且 以.mapping 结尾
                            if not file_info.is_dir() and file_info.filename.startswith(target_path) \
                                    and file_info.filename.endswith('.mapping'):
                                # 7. 如果 这个 文件名 拆分 split Image/ProductFile/Category/ 数组长度大于 1
                                # 说明 arr[1] 为这个子集的 mapping_name
                                if len(file_info.filename.split(target_path)) > 1:
                                    zip_names_results.append(file_info.filename.split(target_path)[1])
                        # 8. 把这个 mapping name 集合给全局参数
                        self.zip_mapping_names = zip_names_results
                except zipfile.BadZipFile:
                    print(f"zip文件损坏: {zip_path}")
            # 4. 如果该文件不是压缩包
            else:
                # 5. 拼接该文件的地址
                file_path = os.path.join(directory_path, file, 'ProductFile', 'Category')
                # 6. 遍历查找其子文件有哪些
                mapping_files = [f for f in os.listdir(file_path) if f.endswith('.mapping')]
                # 7. 把子所有的 mapping 文件赋值给全局参数
                self.mapping_names = mapping_files
        self.check_name()
    # 二、检查已经已经获取的 mapping Name，是否符合规范
    def check_name(self) -> list:
        # 遍历判断 压缩包目标文件夹下的所有 mapping 文件是否符合命名规范
        for f in self.zip_mapping_names:
            if self.validate_file_name(f):
                print(r'压缩包Category中的 mapping 命名均符合规范')
            else:
                print(f'{f} 的命名不符合规范')
        # 遍历判断 非压缩包目标文件夹下的所有 mapping 文件是否符合命名规范
        for file in self.mapping_names:
            if self.validate_file_name(file):
                print(r'Category文件夹中的 mapping 命名均符合规范')
            else:
                print(f'{file} 的命名不符合规范')
# 主逻辑开始 ⬇
if __name__ == '__main__':  # 判断该段代码是作为脚本执行还是模块导入的，如果是脚本运行就用__name__,如果是导入的下面就不会运行
    tp = input("请输入要查询的产品型号: ")
    mapping_is_reflows = mappingNameCheck(tp)
    mapping_is_reflows.get_mapping_name()
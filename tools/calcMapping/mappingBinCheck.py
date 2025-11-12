import os


class mapping_bin():  # 要加上self归类
    def __init__(self, TP):
        self.TP = TP

    # 定义函数 查找 mapping 文件并读取内容 入参： tpName 输出 list(bin是否重流)
    # 需求： 根据TP在3270文件夹下查询大mapping对应名称, 请使用Python根据给出的TffP给出重流与不重流的bin有那些。
    def get_info_from_mapping(self) -> list:
        # 1. 指定文件夹路径 - 根路径 3270文件夹
        directory_path = r"\\172.21.10.201\3270"
        # 2. 查找mapping文件 "\\172.21.10.201\3270\OV09642_SLT_60C_RMB2_EC8201_A\ProductFile\Category"
        software_files = os.path.join(directory_path, self.tpName, "ProductFile", "Category")
        mapping_files = [f for f in os.listdir(software_files) if f.endswith('.mapping')]  # 列表推导式
        print('11111', mapping_files)
        # 因为我遇到的这个文件夹下有且仅有一个文件，所以取第零位
        mapping_file = mapping_files[0]
        open_mapping_file = os.path.join(software_files, mapping_file)
        # 3.判断mapping类型，’r'为只读文件，strip可以去掉两个字符中间的空格，制表符 /t /n
        results = []
        mapping_type = ''
        mapping_type_retest = []
        if not os.path.exists(open_mapping_file):
            print("Mapping file not found.")
            return results
        else:
            if "Nor" in mapping_file:  # 判断mapping的种类并打印出来每个等级对应是否重流
                mapping_type = "mappingtype为Nor，所有不良品等级都重流"
                mapping_type_retest = ['1', '2', '3', '4', '5']
            elif "New0" in mapping_file:
                mapping_type = "mappingType为New0，D级不重流"
                mapping_type_retest = ['1', '2', '3', '5']
            elif "New1" in mapping_file:
                mapping_type = "mappingType为New1，B+D级不重流"
                mapping_type_retest = ['1', '3', '5']
            elif "New2" in mapping_file:
                mapping_type = "mappingType为New2，C+D级不重流"
                mapping_type_retest = ['1', '2', '5']
            elif "New3" in mapping_file:
                mapping_type = "mappingType为New3，B+C级不重流"
                mapping_type_retest = ['1', '4', '5']
            elif "New4" in mapping_file:
                mapping_type = "mappingType为New4，B级不重流"
                mapping_type_retest = ['1', '3', '4', '5']
            else:
                mapping_type = "请确认程式内mappingtype类型是否正确"

        with open(open_mapping_file, 'r', encoding='utf-8') as file:
            # 读取每一行，跳过第一行（表头）
            lines = file.readlines()[1:]
            # print('LINES::::', lines)
            # 遍历读取的行
            for line in lines:
                parts = line.strip().split('\t')  # 使用制表符分割
                if len(parts) < 5:
                    continue  # 确保行的长度足够（至少5个部分）

                software_value = parts[0]  # 获取第一列（Software）
                stack_value = parts[1]  # 获取第二列（Hardware）
                code_value = parts[2]  # 获取第三列（Code）
                description = parts[3]  # 获取第四列（Description）
                pass_value = parts[4]  # 获取第五列（Pass）
                stack_is_retest = ''  # Stack 说明
                if stack_value in mapping_type_retest:
                    stack_is_retest = 'bin对应等级重流'
                else:
                    stack_is_retest = 'bin对应等级不重流'

                results.append({
                    "Bin": software_value,
                    "Bin对应的等级": stack_value,
                    "是否重流": stack_is_retest,
                    "MappingTypeDes": mapping_type,
                })

        return results

    # 将重流和不重流的bin根据results分类
    def get_reflow_list_from_mapping(self) -> object:
        not_reflows = []
        reflows = []
        for item in self.results:
            if item['是否重流'] == 'bin对应等级重流':
                reflows.append(item['Bin'])
            elif item['是否重流'] == 'bin对应等级不重流':
                not_reflows.append(item['Bin'])
            else:
                print(f"{item['Bin']}该 Mapping 有误")
        return {
            '重流的 Bin 有': reflows,
            '不重流的 Bin 有': not_reflows
        }

    # 查询 3270 下 符合输入 tp 的 tpName 有哪些
    def get_tp_name_from_3270(self) -> list:
        directory_path = r"\\172.21.10.201\3270"
        # 获取 3270 文件夹下 都有哪些文件名
        # 且为了保持唯一性（去除 zip 文件）、需要确保 条件1. 该文件是 文件夹 且 满足名字符合 tp 的文件有哪些（isdir的作用）
        mapping_files = [f for f in os.listdir(directory_path)
                         if os.path.isdir(os.path.join(directory_path, f)) and self.TP in f]
        print(f'符合 tp 为 {self.TP} 的 tpName 有：{mapping_files}')
        tpname = input('请输入要查询的 tpName: ')
        self.tpName = tpname
        results = self.get_info_from_mapping()
        self.results = results
        if results:
            is_reflows = self.get_reflow_list_from_mapping()
            print(is_reflows)  # for result in results:


# 主逻辑开始 ⬇
if __name__ == '__main__':  # 判断该段代码是作为脚本执行还是模块导入的，如果是脚本运行就用__name__,如果是导入的下面就不会运行
    tp = input("请输入要查询的产品型号: ")
    mapping_is_reflows = mapping_bin(tp)
    mapping_is_reflows.get_tp_name_from_3270()
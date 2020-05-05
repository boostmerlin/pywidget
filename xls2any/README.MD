# A tool convert xls, xlsx to other language config

currently support:  

* json
* lua

## 环境需求  

python2.7+ or python3
pip install xlrd  

## 用法

* 查看指定用法  
python xls2any.py -h

__xls2any.bat__ or __xls2any.sh__ 实用命令,
会搜索盘里文件夹下包含  **__xlsconfig__**的文件夹，会处理该文件夹下的xlx，之后就不再需要重复输入命令了  
如果要删除之前的配置: `xls2any -d`  
如果只搜索指定的文件夹: `xls2any dir_name`

## 主要特性

* 支持嵌套  
* 支持增量转换，只转换有变更的文件（基于文件时间比较）
* 可以跳过指定的起始行  
* 列重复模式，相同列的配置会被当作数组对待，列重复同理  
* 支持合并单元格处理，合并的格子会被处理成同一数据  
* 支持合并多个单元格数据到一个文件中  

## 数据格式  

每列（Column）是一个字段，字段（Field）可以有一些标记：

* `&` **开头**表示它在table(map)中用作索引,索引可以有多个,但不能所有列都是索引.
* `*` **开头**表示value将会被放入数组中。默认多个重复列才会被处理成数组
* `#` **结尾**表示映射为数字.  
* `$` **结尾**表示映射为字符串,数据转化时会被引号括起来
* `?` **结尾**表示映射为布尔变量,如果填的是字符串,会自动处理常见的值,比如(0, 1, 是,否...).  
* 结尾不是"#$?"的,会按**表格数据类型**照搬

1. 二维表格转化为一个二维数组，不需要指定字段标记的元数据。见test1-array_map

2. 字段标记元数据和数据放在同一地方，作为表头，执行命令时需要添加参数： __--header__, 如果使用--row参数指定数据行的起始行数，则row行应包括表头元数据所在行。见test2-header_mode

3. 单独使用一个sheet来表示其它表的元数据组,每列声明一个表的数据格式(见test3-meta_sheet)：
   SheetName=data_table_name[=start_row][=simple_map?]  
   start_row： 起始行
   simple_map： 是否是简单映射  
   ColumnName=vk_param_or_field_name[=vk_param]...[=vk_param]  
   ColumnName可以是真实列名也可以是VK(virtual key), field_name 即生成的key，VK名不会写到数据里
   目前VK有：
   * VK_INT: 生成指定起始和步长的整数数列  

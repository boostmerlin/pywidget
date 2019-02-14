# A tool convert xls, xlsx to other language config

currently only support Lua
TODO: json, xml

## Usage: 
* 查看指定用法
python xls2any.py -h
* 或者运行：
xls2any.bat  
TODO: xls2any.sh  
如果文件夹下包含__xlsconfig__的文件，则会把该文件夹的文件当作xls来处理  

## 环境需求  
python2.7+ or python3
pip install xlrd  

## 主要特性:
支持多级索引转换,生成层级table  
也支持无索引转换,按行生成数组  
支持差量转换,只转换有变更的文件(基于文件时间比较)  
可以跳过起始行  
列重复模式，相同列的配置会被当作数组对待  

对excel表格的要求,可按两种模式来填写excel表格  

模式1:  
需要在excel中专门建一个Sheet,其中每一列对应一个需要转换的Sheet, 运行时添加参数--meta xx 指定metasheet 名  
第一行指定了该Sheet对应的table名,形如: "SomeSheet=SomeTable"  
其余行表示"数据列"到lua变量的映射,形如: "SomeColumn=SomeField"  
注意SomeField支持一些符号标记:  
'*'开头的映射名表示它在table中用作索引,索引可以有多个,但不能所有列都是索引.  
'#'结尾的映射名表示映射为数字.  
'$'结尾的映射名表示映射为字符串,指明了这种格式时,在excel中填写时无需加引号.  
'?'结尾的映射名表示映射为布尔变量,如果填的是字符串,会自动处理常见的值,比如(0, 1, 是,否...).  
结尾不是"#$?"的,会尽可能将表格中的字面值照搬到lua中去,这时如果希望被处理为字符串的,需要在表格中自行添加引号.  

模式2:  
无需在excel文件中加入额外的meta sheet,直接在列标题中标注即可; 标注格式与方式1类似.  
添加参数--header, 并使用--row参数指定数据行的起始行数来跳过备注

#!/usr/bin/python
# -*- coding: utf-8 -*-
# TODO: support xml, yml, ruby, js

import os
import sys
import argparse
import time
import datetime
import xlrd
import pprint

# if sys.version_info.major == 2:
#     reload(sys)
#     sys.setdefaultencoding("utf-8")

_EMPTY = ""
INDENT_NUMBER = 2

class AnyException(Exception):
    pass

def try_decode(text):
    try:
        unicode
        return text.decode("utf-8") if isinstance(text, str) else text
    except NameError:
        return text.decode("utf-8") if isinstance(text, bytes) else text
    except UnicodeDecodeError:
        return text.decode("gb2312") if isinstance(text, str) else text

def identity(v1, v2):
    return id(v1) == id(v2)

def _quote_key(key):
    if key.startswith('"') and key.endswith('"'):
        return key
    return '"%s"' % key

class _TargetConverter(object):
    def __init__(self, parentConverter):
        self.converter = parentConverter
    
    def get_signature(self):
        return "----file signature----"
    
    def convert_sheet(self, sheet_desc):
        data = self._rinse_data(sheet_desc)
        if sheet_desc.has_key:
            self.generate_map(sheet_desc, data)
        else:
            self.generate_array(sheet_desc, data)
    
    def on_convert_over(self, action, name):
        pass

    def before_save(self):
        self.converter.append_line("do any final modification here.")

    def null(self):
        return _EMPTY

    def generate_array(self, sheet_desc, array_data):
        self.converter.append_line("implement generate_array method")

    def generate_map(self, sheet_desc, map_data):
        self.converter.append_line("implement generate_map method")

    def _cell_coord_of_merged(self, sheet, row, col):
        rlo, clo = self.converter.cell_merged_to(sheet, row, col)
        if rlo != None:
            return rlo, clo
        else:
            return row, col

    def _rinse_array_data(self, sheet_desc):
        sheet = self.converter.get_workbook().sheet_by_name(sheet_desc.sheet_name)
        data = list()
        row_start = self.converter.start_row
        if len(sheet_desc.columns) > 0:
            row_start += 1
        
        for row in range(row_start, sheet.nrows):
            row_len = sheet.row_len(row)
            row_list = list()
            for col in range(0, row_len):
                cd = sheet_desc.find_column_desc(col)
                row, col = self._cell_coord_of_merged(sheet, row, col)
                if cd:
                    v = self.converter.get_cell_text(sheet, row, cd, col)
                    row_list.append(v)
                else:
                    cell = sheet.cell(row, col)
                    row_list.append(self.converter.get_cell_value(cell))
            if len(row_list) > 0:
                data.append(row_list)
        return data

    def _gen_field_value(self, sheet, row_idx, column_desc):
        if len(column_desc.column_indexs) == 1:
            row, col = self._cell_coord_of_merged(sheet, row_idx, column_desc.column_indexs[0])
            return self.converter.get_cell_text(sheet, row, column_desc, col)
        else:  # call it column repeat mode.
            ret = []
            for idx in column_desc.column_indexs:
                row, col = self._cell_coord_of_merged(sheet, row_idx, idx)
                ret.append(self.converter.get_cell_text(
                    sheet, row, column_desc, col)
                )
            return ret

    def _last_flag(self, node_list):
        if not node_list or len(node_list) == 0:
            return
        node_list[-1]['last'] = True

    def _rinse_hierachy_data(self, sheet_desc):
        sheet = self.converter.get_workbook().sheet_by_name(sheet_desc.sheet_name)
        data = list()
        # 生成层级数据结构
        for row_idx in range(self.converter.start_row+1, sheet.nrows):
            row_content = dict()
            for column_desc in sheet_desc.columns:
                column_idx = column_desc.column_indexs[0]
                if column_idx < 0 and sheet_desc.vk_generator:  # suppose to be vk
                    row_content[column_desc.field_name] = next(
                        sheet_desc.vk_generator)
                else:
                    row_content[column_desc.field_name] = self._gen_field_value(
                        sheet, row_idx, column_desc)
            node = data
            for key_idx in range(0, len(sheet_desc.keys)):
                key_desc = sheet_desc.keys[key_idx]
                field_value = row_content[key_desc.field_name]
                child = next((kv["v"]
                              for kv in node if kv["k"] == field_value), None)
                if child == None:
                    child = list()
                    comment = key_desc.column_name
                    node.append({"k": field_value, "v": child, "c": comment, 'last': False})
                node = child
            for column_desc in sheet_desc.columns:
                if not column_desc.is_key:
                    field_name = column_desc.field_name
                    field_value = row_content[field_name]
                    comment = column_desc.column_name
                    node.append(
                        {"k": field_name, "v": field_value, "c": comment, 'last': False}
                    )
            self._last_flag(node)
        return data

    # clean xlsx data
    def _rinse_data(self, sheet_desc):
        if sheet_desc.has_key:
            return self._rinse_hierachy_data(sheet_desc)
        else:
            return self._rinse_array_data(sheet_desc)

class _JsonConverter(_TargetConverter):
    BEGIN_ARRAY = "["
    END_ARRAY = "]"
    BEGIN_OBJECT = "{"
    END_OBJECT = "}"
    NAME_SEPARATOR = ":"
    VALUE_SEPARATOR = ","

    def __init__(self, parentConverter):
        super(_JsonConverter, self).__init__(parentConverter)
    
    def get_signature(self):
        return _EMPTY

    def null(self):
        return "null"

    def generate_array(self, sheet_desc, root):
        table_var = _quote_key(sheet_desc.table_name)
        self.converter.append_line(table_var + self.NAME_SEPARATOR + " " + self.BEGIN_ARRAY)
        for row in root:
            line_code = self.converter.indent if len(row) <= 1 else self.converter.indent + self.BEGIN_ARRAY
            cell_idx = 1
            for cell in row:
                if cell_idx != 1:
                    line_code += self.VALUE_SEPARATOR + " "
                line_code += cell
                cell_idx += 1
            line_code += _EMPTY if len(row) <= 1 else self.END_ARRAY
            if not identity(row, root[-1]):
                line_code += self.VALUE_SEPARATOR
            self.converter.append_line(line_code)
            
        self.converter.append_line(self.END_ARRAY)

    def generate_map(self, sheet_desc, root):
        table_var = sheet_desc.table_name
        self._gen_tree_code(sheet_desc, root, 0, len(root)==1, table_var)

    def _format_node(self, node):
        if type(node) == list:
            ret = self.BEGIN_ARRAY
            for v in node:
                ret += v + self.VALUE_SEPARATOR
            ret += self.BEGIN_ARRAY
            return ret
        else:
            return node

    def _gen_tree_code(self, sheet_desc, node, step, last_one, key_name):
        key_name = _quote_key(key_name)
        if step >= len(sheet_desc.keys):
            if sheet_desc.simple_map and len(node) == 1:
                child = node[0]
                line = self.converter.indent * step + \
                    key_name + self.NAME_SEPARATOR + child["v"]
                line += self.VALUE_SEPARATOR
                self.converter.append_line(line)
                return
            line = self.converter.indent * step + key_name + self.NAME_SEPARATOR + self.BEGIN_OBJECT
            first_item = True
            for kv in node:
                key = kv["k"]
                if not first_item:
                    line += self.VALUE_SEPARATOR + " "
                line += "%s%s%s" % (_quote_key(key), self.NAME_SEPARATOR, self._format_node(kv["v"]))
                first_item = False
            line += self.END_OBJECT if last_one else self.END_OBJECT + self.VALUE_SEPARATOR
            self.converter.append_line(line)
            return

        self.converter.append_line(
            self.converter.indent * step + key_name + self.NAME_SEPARATOR, False
        )
        self.converter.append_line(self.BEGIN_OBJECT)
        for kv in node:
            self._gen_tree_code(sheet_desc, kv["v"], step + 1, identity(kv, node[-1]), "%s" % kv["k"])
        self.converter.append_line(
            self.converter.indent * step + self.END_OBJECT +
            (_EMPTY if step == 0 or last_one else self.VALUE_SEPARATOR)
        )

    def before_save(self):
        self.converter.indent_all_lines()
        self.converter.insert_line(self.BEGIN_OBJECT)
        line  = self.converter.get_line(-1)
        line = line.replace(self.VALUE_SEPARATOR, "")
        self.converter.set_line(-1, line)
        self.converter.append_line(self.END_OBJECT, False)
    
    def on_convert_over(self, action, name):
        if action == Converter.SHEET_OVER:
            line  = self.converter.get_line(-1)
            line = line.replace(self.END_OBJECT, self.END_OBJECT+self.VALUE_SEPARATOR)
            line = line.replace(self.END_ARRAY, self.END_ARRAY+self.VALUE_SEPARATOR)
            self.converter.set_line(-1, line)

class _LuaConverter(_TargetConverter):
    def __init__(self, parentConverter):
        super(_LuaConverter, self).__init__(parentConverter)

    def null(self):
        return "nil"

    def get_signature(self):
        desc = "The Code is auto generated by xls2any, DO NOT EDIT."
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return "--%s\n--TIME: %s\n" % (desc, now)

    def before_save(self):
        line = _EMPTY
        if self.converter.scope == "local":
            for table_name in self.converter.tables:
                if line == _EMPTY:
                    line += "return %s" % table_name
                else:
                    line += ", %s" % table_name
        self.converter.append_line(line)

    # private function
    def generate_array(self, sheet_desc, root):
        self.converter.append_line(
            "--%s: %s" % (self.converter.xls_filename, sheet_desc.sheet_name))
        table_var = sheet_desc.table_name
        self.converter.append_line(table_var + " = ", False)
        self.converter.append_line("{")
        for row in root:
            line_code = self.converter.indent if len(row) <= 1 else self.converter.indent + "{"
            cell_idx = 1
            for cell in row:
                if cell_idx != 1:
                    line_code += ", "
                line_code += cell
                cell_idx += 1
            line_code += "," if len(row) <= 1 else "},"
            self.converter.append_line(line_code)
        self.converter.append_line("}")
        self.converter.append_line("")

    def generate_map(self, sheet_desc, root):
        comment = "%s: %s" % (
            self.converter.xls_filename, sheet_desc.sheet_name)
        table_var = self._scope_variable(sheet_desc.table_name)
        self._gen_tree_code(sheet_desc, root, 0, table_var, comment)
        self.converter.append_line()

    def _scope_variable(self, variable_name):
        table_var = "%s%s" % (self.converter.scope == "local" and "local " or 
                            self.converter.scope == "global" and "_G." or 
                            _EMPTY, variable_name)
        return table_var

    def _format_node(self, node):
        if type(node) == list:
            ret = "{"
            for v in node:
                ret += v + ","
            ret += "}"
            return ret
        else:
            return node

    def _gen_tree_code(self, sheet_desc, node, step, key_name, comment):
        if comment != None:
            self.converter.append_line(
                self.converter.indent * step + "--" + comment)

        if step >= len(sheet_desc.keys):
            if sheet_desc.simple_map and len(node) == 1:
                child = node[0]
                line = self.converter.indent * step + \
                    key_name + " = " + child["v"]
                if comment != None:
                    line += ", --%s" % child["c"]
                else:
                    line += ","
                self.converter.append_line(line)
                return
            line = self.converter.indent * step + key_name + " = {"
            first_item = True
            for kv in node:
                lua_name = kv["k"]
                if not first_item:
                    line += ", "
                line += "%s=%s" % (lua_name, self._format_node(kv["v"]))
                first_item = False
            line += "},"
            self.converter.append_line(line)
            return

        self.converter.append_line(
            self.converter.indent * step + key_name + " =")
        self.converter.append_line(self.converter.indent * step + "{")
        firstNode = True
        for kv in node:
            comment = kv["c"] if firstNode else None
            self._gen_tree_code(
                sheet_desc, kv["v"], step + 1, "[%s]" % kv["k"], comment)
            firstNode = False
        self.converter.append_line(
            self.converter.indent * step + "}" + (_EMPTY if step == 0 else ","))

class _ColumnDesc(object):
    def __init__(self, column_name, field_name, column_idx):
        first_char = field_name[0]
        last_char = field_name[-1]
        map_table = {"?": "bool", "#": "number", "$": "string"}
        field_name = field_name if first_char != "*" else field_name[1:]
        field_name = field_name if last_char not in map_table else field_name[:-1]
        self.column_name = column_name
        self.column_indexs = column_idx
        self.is_key = first_char == "*"
        self.field_name = field_name
        self.map_type = map_table[last_char] if last_char in map_table else "raw"


class _SheetDesc(object):
    def __init__(self, sheet_name, table_name):
        self.sheet_name = sheet_name
        self.table_name = table_name
        self.columns = list()
        self.maps = dict()
        self.keys = list()
        self.has_key = False
        self.vk_generator = None
        self.start_row = 0
        # 当数据只有一列时，可以选择性的不要name名
        self.simple_map = False

    def map(self, column_name, field_name, column_idx):
        desc = _ColumnDesc(column_name, field_name, column_idx)
        self.columns.append(desc)
        self.maps[column_name] = desc
        if desc.is_key:
            self.keys.append(desc)
            self.has_key = True

    def find_column_desc(self, col):
        for cd in self.columns:
            if col in cd.column_indexs:
                return cd
        return None

    def check_skip(self, row):
        return self.start_row > row

    def vk_int(self, column_desc, vk_param):
        column_desc.map_type = "number"
        def ff(start, step):
            n = start
            while True:
                yield str(n)
                n += step
        start = int(vk_param[0])
        step = int(vk_param[1]) if len(vk_param) >= 2 else 1
        self.vk_generator = ff(start, step)

    VK_HANDLER = {
        "VK_INT": vk_int
    }

    def set_virtual_key(self, vk_name, *vk_param):
        desc = _ColumnDesc(vk_name, vk_name, [-1])
        self.columns.append(desc)
        self.maps[vk_name] = desc
        desc.is_key = True
        if desc.is_key:
            self.keys.append(desc)
            self.has_key = True
        self.VK_HANDLER[vk_name.upper()](self, desc, vk_param)

class Converter(object):
    scope = None
    INTENT = chr(32)
    tables = None
    FILE_OVER = 2
    SHEET_OVER = 1
    SUPPORTED_LANGUAGE = {"lua": _LuaConverter, 'json': _JsonConverter}
    VIRTUAL_KEYS = ("VK_INT",)

    @staticmethod
    def to_bool(text):
        falses = [_EMPTY, "nil", "0", "false", "no", "none", u"否", u"无", "null"]
        if not text or text.lower() in falses:
            return False
        return True

    @staticmethod
    def is_file_newer(input_file, output_file):
        '''
            比较文件时间戳,如果output_file比较新或者不存在,则返回True,否则False
        '''
        if not os.path.isfile(output_file):
            return True
        input_time = os.path.getmtime(input_file)
        output_time = os.path.getmtime(output_file)
        return input_time >= output_time

    @staticmethod
    def cell_merged_to(sheet, row, col):
        for crange in sheet.merged_cells:
            rlo, rhi, clo, chi = crange
            if row >= rlo and row < rhi and col >= clo and col < chi:
                return rlo, clo
        return None, None

    @staticmethod
    def merged_cell(sheet, row, col):
        rlo, clo = Converter.cell_merged_to(sheet, row, col)
        if rlo != None:
            return sheet.cell(rlo, clo)
        else:
            return sheet.cell(row, col)

    def __init__(self, args):
        target = args.target
        self._lines = None
        self.target = target
        self.bool_formater = {}
        # row from 0
        self.start_row = args.row and args.row-1 or 0
        if target not in self.SUPPORTED_LANGUAGE:
            raise AnyException("Unsupported language: %s" % target)
        self.scope = args.scope
        self.indent = not args.indent and self.INTENT * INDENT_NUMBER or self.INTENT * args.indent
        self._meta = args.meta
        self._header_mode = args.header_mode
        self._targetConverter = self.SUPPORTED_LANGUAGE[target](self)
        self.reset()
    
    def default_null(self):
        return self._targetConverter.null()

    def get_target_file(self, name):
        return os.path.splitext(name)[0] + "." + self.target

    def get_workbook(self):
        return self._workbook

    def log_warnings(self):
        pass

    def convert(self, xls_filename, on_convert_over_callback=None, dry_run=False):
        self._meta_tables = list()
        try:
            self._workbook = xlrd.open_workbook(xls_filename)
            self._xls_filetime = os.path.getmtime(xls_filename)
            self.xls_filename = xls_filename
        except:
            print("!! Failed to load workbook, not a excel: " + xls_filename)
            return

        self._sheet_names = self._workbook.sheet_names()
        if self._meta in self._sheet_names:
            self._load_meta_sheet()
        else:
            self._load_meta_header()

        if dry_run:
            self.log_warnings()
            return

        for sheet_desc in self._meta_tables:
            self._targetConverter.convert_sheet(sheet_desc)
            self.tables.append(sheet_desc.table_name)
            print("process sheet: [%s] over" % sheet_desc.sheet_name)
            self._targetConverter.on_convert_over(self.SHEET_OVER, sheet_desc.table_name)
            if callable(on_convert_over_callback):
                on_convert_over_callback(
                    self, self.SHEET_OVER, sheet_desc.table_name)
        print("process file: [%s] over" % xls_filename)
        self._targetConverter.on_convert_over(self.FILE_OVER, xls_filename)
        if callable(on_convert_over_callback):
            on_convert_over_callback(self, self.FILE_OVER, xls_filename)

    def append_line(self, line = _EMPTY, line_break=True):
        self._lines.append(line_break and "%s%s" % (line, "\n") or line)
    
    def insert_line(self, line = _EMPTY, line_break=True):
        self._lines.insert(0, line_break and "%s%s" % (line, "\n") or line)

    def indent_all_lines(self):
        for i in range(0, len(self._lines)):
            self._lines[i] = self.indent + self._lines[i]
    
    def get_line(self, at):
        if at >= len(self._lines) or len(self._lines)+at >= len(self._lines):
            raise AnyException("get_line index error")
        return self._lines[at]
    
    def set_line(self, at, line):
        if at >= len(self._lines) or len(self._lines)+at >= len(self._lines):
            raise AnyException("set_line index error")
        self._lines[at] = line

    def get_meta_table(self):
        return self._meta_tables

    def save(self, filename):
        filename = self.get_target_file(filename)
        lua_dir = os.path.split(filename)[0]
        if lua_dir != _EMPTY and not os.path.exists(lua_dir):
            os.makedirs(lua_dir)
        self._targetConverter.before_save()
        code = _EMPTY.join(self._lines)
        open(filename, "wb").write(code.encode("utf-8"))

    def reset(self):
        self._lines = list()
        signature = self._targetConverter.get_signature()
        if signature:
            self._lines.append(self._targetConverter.get_signature())
        self.tables = list()

    # meta_tables: list of _SheetDesc
    def _load_meta_sheet(self):
        meta_sheet = self._workbook.sheet_by_name(self._meta)
        for column_idx in range(0, meta_sheet.ncols):
            self._load_meta_column(meta_sheet, column_idx)

    def _get_base_sheet_desc(self, text):
        if not text or text == _EMPTY:
            return

        text_split = [x.strip() for x in text.split("=")]
        sheet_name = text_split[0]
        table_name = text_split[1]
        if sheet_name not in self._sheet_names:
            raise AnyException("Meta error, sheet not exist: %s" % sheet_name)

        start_row = len(text_split) >= 3 and int(
            text_split[2]) - 1 or self.start_row
        simple_map = len(text_split) >= 4 and self.to_bool(text_split[3]) or False
        sheet_desc = _SheetDesc(sheet_name, table_name)
        self._meta_tables.append(sheet_desc)
        sheet_desc.start_row = start_row
        sheet_desc.simple_map = simple_map
        return sheet_desc

    # meta_sheet中,每列定义了一个sheet的映射
    # 本函数将每列数据load为一个meta_table:
    def _load_meta_column(self, meta_sheet, column_idx):
        text = meta_sheet.cell(0, column_idx).value
        if not text:
            return

        sheet_desc = self._get_base_sheet_desc(text)
        sheet_name = sheet_desc.sheet_name
        data_sheet = self._workbook.sheet_by_name(sheet_name)
        column_headers = self._parse_data_header(data_sheet)

        for row_idx in range(1, meta_sheet.nrows):
            cell = meta_sheet.cell(row_idx, column_idx)
            if cell.ctype != xlrd.XL_CELL_TEXT or cell.value == _EMPTY:
                continue
            text_split = cell.value.split("=")
            column_name = text_split[0]
            if column_name not in self.VIRTUAL_KEYS:
                field_name = text_split[1]
                if column_name not in column_headers:
                    raise AnyException("Meta data error, column(%s) not exist in sheet %s" % (
                        column_name, sheet_name))
                sheet_desc.map(column_name, field_name,
                               column_headers[column_name])
            else:
                sheet_desc.set_virtual_key(column_name, *text_split[1:])

        if len(sheet_desc.keys) > 0 and len(sheet_desc.keys) == len(sheet_desc.columns):
            raise AnyException(
                "Meta data error, too many keys, sheet: %s" % sheet_name)
        return True

    def _parse_data_header(self, data_sheet):
        column_headers = dict()
        row = self.start_row
        for col in range(0, data_sheet.ncols):
            cell = self.merged_cell(data_sheet, row, col)
            column_header = self.get_cell_value(cell)
            if not column_header:
                continue
            if column_header in column_headers:
                column_headers[column_header].append(col)
            else:
                column_headers[column_header] = [col]
        return column_headers

    def _load_meta_header(self):
        for sheet_name in self._sheet_names:
            data_sheet = self._workbook.sheet_by_name(sheet_name)
            if data_sheet.ncols == 0:
                return
            sheet_desc = _SheetDesc(sheet_name, sheet_name)
            self._meta_tables.append(sheet_desc)
            if not self._header_mode:
                continue
            
            column_headers = self._parse_data_header(data_sheet)
            for k, v in column_headers.items():
                sheet_desc.map(k, k, v)

            # 不能所有的列都是索引
            if len(sheet_desc.columns) > 0 and len(sheet_desc.keys) == len(sheet_desc.columns):
                raise AnyException(
                    "Meta data error, too many keys for columns, sheet: %s" % sheet_name
                )

    def _get_cell_string(self, cell):
        return _quote_key(self.get_cell_value(cell))

    def _get_cell_number(self, cell):
        raw = self._get_cell_raw(cell)
        try:
            float(raw)
        except ValueError:
            raise AnyException("{} is not numberic".format(raw))

        return raw
    
    def _get_cell_raw(self, cell):
        if cell.ctype == xlrd.XL_CELL_NUMBER:
            return str(cell.value).rstrip("0").rstrip(".")
        if cell.ctype == xlrd.XL_CELL_DATE:
            dt = xlrd.xldate.xldate_as_datetime(
                cell.value, self._workbook.datemode)
            return "%d" % time.mktime(dt.timetuple())
        return try_decode(cell.value)

    # 该函数尽可能返回xls看上去的字面值
    def get_cell_value(self, cell):
        return self._get_cell_raw(cell)

    def _bool_string(self, bool_value):
        formater = self.bool_formater.get('bool')
        if callable(formater):
            return formater(bool_value)
        else:
            return self._default_bool_text(bool_value)

    def _get_cell_bool(self, cell):
        text = self.get_cell_value(cell)
        b = self.to_bool(text)
        return self._bool_string(b)
    
    @staticmethod
    def _default_bool_text(bool_value):
        return str(bool_value).lower()

    def format_bool_delegate(self, func):
        self.bool_formater['bool'] = func

    def get_cell_text(self, sheet, row_idx, column_desc, column_idx):
        cell = sheet.cell(row_idx, column_idx)
        if column_desc.map_type == "number":
            return self._get_cell_number(cell)
        if column_desc.map_type == "bool":
            return self._get_cell_bool(cell)
        if column_desc.map_type == "string":
            return self._get_cell_string(cell)
        text = self.get_cell_value(cell)
        return text if text != _EMPTY else self.default_null()

def _parse_argument():
    parser = argparse.ArgumentParser(
        description="convert excel to target scripts.")
    parser.add_argument("-s", "--scope", dest="scope",
                        help="table scope,local,global", choices=["local", "global", "default"])
    parser.add_argument("-i", "--indent", dest="indent",
                        help="indent size, 0 for tab, default 2 (spaces)", type=int, default=INDENT_NUMBER, choices=[0, 2, 4, 8])
    parser.add_argument("-m", "--meta", dest="meta",
                        help="meta sheet name, default 'xls2any'", default="xls2any")
    parser.add_argument("-f", "--force", dest="force",
                        action="store_true", help="force convert all config")
    parser.add_argument("--header", dest="header_mode", action="store_true",
                        help="is header mode, if no meta sheet, analyze sheet header.")
    parser.add_argument("-r", "--row", dest="row", action="store",
                        type=int, default=1, help="start row to process.")
    parser.add_argument("-o", "--output", dest="output",
                        help="specify a file name, if not, convert into multiple files according to meta table.")
    parser.add_argument("-d", "--dir", dest="outdir", default=".",
                        help="output dir, default is current where converter is.")
    parser.add_argument("-t", "--target", dest="target", default="json",
                        help="target language file ext", choices=["json", "lua"])
    parser.add_argument('inputs', nargs='+', help="input excel files")
    args = parser.parse_args()
    return args

def args_adapter(**param):
    return args

def convert_all_sheet(converter, args):
    output_file = os.path.isabs(args.output) and args.output or os.path.join(
        args.outdir, args.output)
    if args.force or any(converter.is_file_newer(filename, output_file) for filename in args.inputs):
        for filename in args.inputs:
            converter.convert(filename)
        converter.save(output_file)
        print("Convert all xls file into [%s] over:" %
              converter.target, args.output)

def convert_by_each_sheet(converter, args):
    if args.force:
        for filename in args.inputs:
            converter.convert(filename, on_convert_over_callback)
    else:
        for filename in args.inputs:
            converter.convert(filename, dry_run=True)
            any_newer = False
            for metadata in converter.get_meta_table():
                output_file = converter.get_target_file(
                    os.path.join(args.outdir, metadata.table_name))
                if converter.is_file_newer(filename, output_file):
                    any_newer = True
                    break
            if any_newer:
                converter.reset()
                converter.convert(filename, on_convert_over_callback)

def on_convert_over_callback(converter, action, name):
    if action == Converter.SHEET_OVER:
        converter.save(os.path.join(args.outdir, name))
        print("Convert a sheet into [%s.%s] over" %
                (name, converter.target))
        converter.reset()

if __name__ == "__main__":
    args = _parse_argument()
    output_into_one = args.output
    converter = Converter(args)
    if output_into_one:
        convert_all_sheet(converter, args)
    else:
        convert_by_each_sheet(converter, args)
import os
import re
import sys
import getopt
import shutil
import time
import fnmatch

# A helper script to generate binding declarations for nanobind
# bind function 调用顺序有依赖，否则会出现import失败，或者运行时候时候失败（bad cast)

LIB_HEADER = '<nanobind/nanobind.h>'
LIB_NS = 'nanobind'
LIB_SHORT_NS = 'nb'
LIB_CLS = 'module_'
BIND_SIGN = 'bind'
MODULE_DECL = 'NB_MODULE'
HEADER_FILE = '{}.g.h'


def is_comment_line(line):
    line = line.strip()
    if line.startswith('//') or line.startswith('/*') or line.startswith('*'):
        return True
    if '//' in line or '/*' in line:
        return True
    return False


def extract_bind_functions(cpp_file):
    """从 cpp 文件中提取 bind 函数声明，支持命名空间中的函数"""
    bind_functions = []
    in_comment_block = False
    namespace_stack = ['']
    is_template = False
    brace_count = 0
    namespace_brace_positions = []  # location for ns
    waiting_for_brace = False

    with open(cpp_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for line in lines:
        if '/*' in line and '*/' not in line:
            in_comment_block = True
            continue
        elif '*/' in line and '/*' not in line:
            in_comment_block = False
            continue
        elif is_comment_line(line) or in_comment_block:
            continue

        namespace_open_match = re.search(r'^\s*namespace\s+(\w+)\s+({)?(?!\s*=)', line)
        if namespace_open_match:
            ns_name = namespace_open_match.group(1)
            namespace_stack.append(ns_name)
            if namespace_open_match.group(2):
                brace_count += 1
                namespace_brace_positions.append(brace_count)
            else:
                waiting_for_brace = True

        anonymous_namespace_match = re.search(r'^\s*namespace\s+({)?$', line)
        if anonymous_namespace_match:
            namespace_stack.append('a')  # 特殊标记表示匿名命名空间
            if anonymous_namespace_match.group(1):
                brace_count += 1
                namespace_brace_positions.append(brace_count)
            else:
                waiting_for_brace = True
        curly_start = line.strip().startswith('{')
        if waiting_for_brace and curly_start and not namespace_open_match and not anonymous_namespace_match:
            brace_count += 1
            namespace_brace_positions.append(brace_count)

        additional_open_braces = line.count('{')
        if namespace_open_match and namespace_open_match.group(2):
            additional_open_braces -= 1
        if anonymous_namespace_match and anonymous_namespace_match.group(1):
            additional_open_braces -= 1
        if waiting_for_brace and curly_start:
            waiting_for_brace = False
            additional_open_braces -= 1

        brace_count += additional_open_braces

        close_braces = line.count('}')

        for _ in range(close_braces):
            brace_count -= 1
            if namespace_brace_positions and brace_count < namespace_brace_positions[-1]:
                namespace_brace_positions.pop()
                if len(namespace_stack) > 1:
                    namespace_stack.pop()

        # Check for template<> pattern
        if re.search(r'template\s*<\s*.*>', line):
            is_template = True
            continue

        if 'a' in namespace_stack:
            continue

        # Look for bind function declarations
        pattern = (rf'^\s*void\s+({BIND_SIGN}\w+|\w+{BIND_SIGN})\s*\(\s*(?:const\s+)?'
                   rf'(?:{LIB_SHORT_NS}::{LIB_CLS}|{LIB_NS}::{LIB_CLS})\s*&\s*\w+\s*\)')
        match = re.search(pattern, line)
        if match:
            func_name = match.group(1)
            func_decl = match.group(0)
            if not func_decl.endswith(';'):
                func_decl += ';'

            # Add namespace qualification if inside a namespace
            if len(namespace_stack) > 1:
                namespaces = '::'.join([ns for ns in namespace_stack if ns and ns != 'a'])
                if namespaces:
                    func_decl = func_decl.replace(f'void {func_name}', f'void {namespaces}::{func_name}')
            if not is_template:
                bind_functions.append(func_decl)
            else:
                is_template = False

    return bind_functions


def update_ext_cpp(module_dir, bind_functions):
    """更新 *_ext.cpp 文件中的 MODULE 调用"""
    ext_file = os.path.join(module_dir, f'{get_module_name(module_dir)}_ext.cpp')

    if not os.path.isfile(ext_file):
        print(f'Warning: {ext_file} not found')
        return

    backup_file = ext_file + '.bak'
    try:
        shutil.copy2(ext_file, backup_file)
        print(f'Created backup: {backup_file}')
    except Exception as e:
        print(f'Warning: Failed to create backup for {ext_file}: {e}')
        return

    with open(ext_file, 'r', encoding='utf-8') as f:
        content = f.read()

    module_pattern = rf'({MODULE_DECL}\s*\(\s*\w+\s*,\s*\w+\s*\)\s*{{[^}}]*}})'
    match = re.search(module_pattern, content)
    if not match:
        print(f'Warning: No {MODULE_DECL} block found in {ext_file}')
        return

    module_block = match.group(1)

    existing_calls = set()
    bind_func_pattern = rf'(?:\w+::)*\w*{BIND_SIGN}\w*'
    for line in module_block.split('\n'):
        for func in bind_functions:
            func_name = re.search(bind_func_pattern, func).group(0)
            if func_name in line:
                existing_calls.add(func_name)

    new_calls = []
    for func in bind_functions:
        func_name = re.search(bind_func_pattern, func).group(0)
        if func_name not in existing_calls:
            new_calls.append(f'    {func_name}(m);')

    if new_calls:
        new_content = content.replace(
            module_block,
            module_block[:-1] + '\n' + '\n'.join(new_calls) + '\n}'
        )

        with open(ext_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f'Updated {ext_file} with {len(new_calls)} new bind function calls')


def read_gitignore(module_dir):
    module_dir = os.path.normpath(module_dir)
    ignore_dirs = [module_dir]
    while True:
        parent_dir = os.path.dirname(module_dir)
        if parent_dir == module_dir or os.path.isdir(os.path.join(module_dir, '.git')):
            break
        ignore_dirs.append(parent_dir)
        module_dir = parent_dir
    ignore_patterns = set()
    for ignore_dir in ignore_dirs:
        gitignore_file = os.path.join(ignore_dir, '.gitignore')
        if os.path.isfile(gitignore_file):
            with open(gitignore_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        ignore_patterns.add(line)

    return ignore_patterns


def should_ignore(path, ignore_patterns):
    if not ignore_patterns:
        return False

    rel_path = os.path.relpath(path)
    for pattern in ignore_patterns:
        if fnmatch.fnmatch(rel_path, pattern):
            return True
        if fnmatch.fnmatch(os.path.basename(rel_path), pattern):
            return True
    return False


def get_module_name(module_dir):
    return os.path.basename(os.path.normpath(module_dir))


def generate_bindings_header(module_dir, include):
    ignore_patterns = read_gitignore(module_dir) if not include else []
    cpp_files = []

    for root, _, files in os.walk(module_dir):
        for file in files:
            if file.endswith('.cpp') and not file.endswith('_ext.cpp'):
                file_path = os.path.join(root, file)
                if not should_ignore(file_path, ignore_patterns):
                    cpp_files.append(file_path)

    all_bind_functions = []
    for cpp_file in cpp_files:
        bind_functions = extract_bind_functions(cpp_file)
        all_bind_functions.extend(bind_functions)

    # Remove duplicates
    all_bind_functions = set(all_bind_functions)

    namespace_functions = {}
    global_functions = []

    for func_decl in all_bind_functions:
        namespace_match = re.search(r'void\s+(.*)::\w+\s*\(', func_decl)

        if namespace_match:
            ns = namespace_match.group(1)
            if ns not in namespace_functions:
                namespace_functions[ns] = []

            base_func = func_decl.replace(f'{ns}::', '')
            namespace_functions[ns].append(base_func)
        else:
            global_functions.append(func_decl)

    time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
    header_content = f'// This file is auto-generated at {time_str}. Do not edit manually.\n'
    header_content += '#pragma once\n\n'
    header_content += f'#include {LIB_HEADER}\n\n'
    header_content += f'namespace {LIB_SHORT_NS} = {LIB_NS};\n\n'

    def write_func_line(functions, last):
        nonlocal header_content
        for func in functions:
            header_content += f'{func}\n' + ('\n' if func != last else '')

    last_func = ''

    # Add global functions first
    global_functions = sorted(global_functions)
    if not namespace_functions:
        last_func = global_functions[-1] if global_functions else None
    write_func_line(global_functions, last_func)

    # Then add namespaced functions grouped by namespace
    for ns, funcs in sorted(namespace_functions.items()):
        header_content += f'namespace {ns} {{ \n'
        funcs = sorted(funcs)
        last_func = funcs[-1] if funcs else None
        write_func_line(funcs, last_func)
        header_content += '}\n\n'

    output_file = os.path.join(module_dir, f'{get_module_name(module_dir)}.g.h')
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(header_content)

    print(f'Generated {output_file} with {len(all_bind_functions)} bind function declarations')
    return all_bind_functions


def validate_module_dir(path):
    if not os.path.isdir(path):
        print(f'Error: {path} is not a directory')
        return False

    # if os.path.isabs(path):
    #     print(f'Error: {path} is an absolute path not support')
    #     return False

    init_file = os.path.join(path, '__init__.py')
    if not os.path.isfile(init_file):
        print(f'Error: {path} not a python module dir')
        return False

    return True


def restore_backup(module_dir):
    """Restore the backup file by removing .bak extension"""
    module_name = get_module_name(module_dir)
    backup_file = os.path.join(module_dir, f'{module_name}_ext.cpp.bak')
    target_file = os.path.join(module_dir, f'{module_name}_ext.cpp')

    if not os.path.isfile(backup_file):
        print(f'Error: Backup file {backup_file} not found')
        return False

    response = input(f'Are you sure you want to restore {backup_file}? Original file will be overwrite. (y/n): ')
    if response.lower() != 'y':
        print('Restore operation cancelled')
        return False

    try:
        shutil.copy2(backup_file, target_file)
        os.remove(backup_file)
        print(f'Successfully restored {target_file} from backup, backup file removed')
        return True
    except Exception as e:
        print(f'Error restoring backup: {e}')
        return False


def print_usage():
    print('Usage: python gen_bind_declare.py <MODULE> [-a] [-b]')
    print('  <MODULE>  Path to the Python module directory')
    print('  -a        Update <MODULE>_ext.cpp file with bind function calls')
    print('  -b        Restore <MODULE>_ext.cpp from backup file')
    print('  -i        Include files ignored by .gitignore')


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'habi', ['help'])

        update_ext = False
        restore_backup_flag = False
        git_include_flag = False
        for opt, arg in opts:
            if opt in ('-h', '--help'):
                print_usage()
                sys.exit(0)
            elif opt == '-a':
                update_ext = True
            elif opt == '-b':
                restore_backup_flag = True
            elif opt == '-i':
                git_include_flag = True

        if len(args) != 1:
            print('Error: Module directory is required')
            print_usage()
            sys.exit(1)

        module_dir = args[0]

        if not validate_module_dir(module_dir):
            sys.exit(1)

        if restore_backup_flag:
            if not restore_backup(module_dir):
                sys.exit(1)
            sys.exit(0)

        print(f'Processing module directory: {module_dir}')
        bind_functions = generate_bindings_header(module_dir, git_include_flag)

        if update_ext:
            update_ext_cpp(module_dir, bind_functions)

    except getopt.GetoptError as e:
        print(f'Error: {e}')
        print_usage()
        sys.exit(1)


if __name__ == '__main__':
    main()

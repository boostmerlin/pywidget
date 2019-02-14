# -*- coding:utf-8 -*-

#author： merlin
#find and replace baseon file or directory name.
#Usage:
#python checkreplacefiles.py [--dryrun] [srcdir] destdir
#如果目录下有pkg文件，则目录下的每个文件和文件夹是一个资源单位(pkg)，作为查找和拷贝的最小单位
#否则: 将在子目录下进行查找
#如果不匹配destdir，即destdir中没有这个pkg，不作拷贝替换

import os
import sys
import shutil

def copy(src, dst, root=None, exts: list=None):
    relpath = None
    if root:
        relpath = os.path.relpath(src, root)
    try:
        if os.path.isfile(src):
            dstdir = dst
            if relpath:
                dstdir = os.path.join(dst, os.path.dirname(relpath))
            if not os.path.isdir(dstdir):
                os.makedirs(dstdir)
            ext = os.path.splitext(src)[1]
            if not exts or ext in exts:
                shutil.copy(src, dstdir)
        else:
            names = os.listdir(src)
            for name in names:
                srcname = os.path.join(src, name)
                dstname = dst
                if os.path.isdir(srcname):
                    curroot = root
                    if root:
                        dstname = os.path.join(dst, name)
                        curroot = os.path.join(root, name)
                    copy(srcname, dstname, curroot)
                else:
                    copy(srcname, dstname, root)
    except Exception as e:
        print(e)

dry_run = False

def find_and_replace(srcdir, destdir):
    srcdirpkgs = {}
    for root, dirs, files in os.walk(srcdir, topdown=True):
        if not os.path.isfile(os.path.join(root, "pkg")):
            continue
        for name in dirs:
            srcdirpkgs[name] = os.path.join(root, name)
        for name in files:
            if name == __file__ or name == "pkg":
                continue
            srcdirpkgs[name] = os.path.join(root, name)

    #backup = []
    if not os.path.exists(destdir):
        print("destination folder not exist!")
        return
    for root, dirs, files in os.walk(destdir):
        for name in dirs:
            if name in srcdirpkgs:
                assetdir = os.path.join(root, name)
                print("<d><d><d><d> find assetdir:", name)
                #backup.append(assetdir)
                #shutil.rmtree(assetdir)
                if not dry_run:
                    print("copy asset from:", srcdirpkgs[name], "to:", assetdir)
                    copy(srcdirpkgs[name], assetdir, srcdirpkgs[name])
                #shutil.copytree(srcdirpkgs[name], assetdir)
        for name in files:
            if name in srcdirpkgs:
                assetfile = os.path.join(root, name)
                print("[f][f][f][f] find assetfile:", name)
                # os.remove(assetfile)
                if not dry_run:
                    print("copy asset from:", srcdirpkgs[name], "to:", assetfile)
                    shutil.copyfile(srcdirpkgs[name], assetfile)

if __name__ == "__main__":
    argn = len(sys.argv)
    if not (argn == 2 or argn == 3 or argn == 4):
        print("Usage python checkreplacefiles.py [--dryrun] [srcdir] destdir")
        exit(0)

    args = sys.argv[1:]
    argn -= 1
    if "--dryrun" == args[0]:
        dry_run = True
        argn -= 1
        del args[0]
    if argn == 1:
        srcdirRoot = "."
        destdirRoot = args[0]
    elif argn == 2:
        srcdirRoot = args[0]
        destdirRoot = args[1]

    if not (os.path.exists(srcdirRoot) and os.path.exists(destdirRoot)):
        print("Src directory or dest directory not exist!")
        exit(0)
    # print("关闭其它打开的文件以防失败，是否继续？")
    # a = input("y/n:\n")
    # if a != 'y' and a != "yes":
    #     exit(0)   
    print("src dir:", srcdirRoot, "|dest dir:", destdirRoot, "|dry run? ", dry_run)
    find_and_replace(srcdirRoot, destdirRoot)

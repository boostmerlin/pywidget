#!/usr/bin/python
# -*- coding: utf-8 -*-
import socket
import threading
import re
import subprocess
import sys,os
import signal

if sys.version_info.major == 3:
    from urllib.parse import urlparse
else:
    from urlparse import urlparse

keepalive_timeout = 10
class SocketServer:
    def __init__(self, host, port):
        self.host = host
        self.port = port

    def start(self, handle_func):
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            server_sock.bind((self.host, self.port))
            server_sock.listen(5)
            print("start server listen on: ", self.host)
            while True:
                client_sock, addr = server_sock.accept()
                t = threading.Thread(target=handle_func, args=(client_sock, addr))
                t.start()
        except OSError as e:
            print("socket error.", e)
        except Exception as e:
            print("Other exception: ", e)
        finally:
            server_sock.close()

class HttpHandler:
    readsize = 128
    implement_methods = ("GET", "POST")
    bodylimits = 8192 #8k
    INTERNAL_OK = 0
    http_status_msg = {
        100: "Continue",
        101: "Switching Protocols",
        200: "OK",
        201: "Created",
        202: "Accepted",
        203: "Non-Authoritative Information",
        204: "No Content",
        205: "Reset Content",
        206: "Partial Content",
        300: "Multiple Choices",
        301: "Moved Permanently",
        302: "Found",
        303: "See Other",
        304: "Not Modified",
        305: "Use Proxy",
        307: "Temporary Redirect",
        400: "Bad Request",
        401: "Unauthorized",
        402: "Payment Required",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
        406: "Not Acceptable",
        407: "Proxy Authentication Required",
        408: "Request Time-out",
        409: "Conflict",
        410: "Gone",
        411: "Length Required",
        412: "Precondition Failed",
        413: "Request Entity Too Large",
        414: "Request-URI Too Large",
        415: "Unsupported Media Type",
        416: "Requested range not satisfiable",
        417: "Expectation Failed",
        500: "Internal Server Error",
        501: "Method Not Implemented",
        502: "Bad Gateway",
        503: "Service Unavailable",
        504: "Gateway Time-out",
        505: "HTTP Version Not supported",
    }

    @staticmethod
    def _parseHeader(readfunc):
        array = bytearray()
    #    buffer = memoryview(array)
        while True:
            readbytes = readfunc()
            sz1 = len(array)
            array[sz1:] = readbytes
            e = array.find(b'\r\n\r\n', -len(readbytes)-3)
            if e > 0:
                partbody = array[e+4:]
                break
        print("Raw bytes: ", array)
        headerlines = array.split(b'\r\n')
        headers = {}
        for i in range(1, len(headerlines)):
            line = headerlines[i]
            if line == b'':
                break
            strline = line.decode()
            m = re.split(r':\s*', strline, 1)
            if len(m) == 2:
                headers[m[0]] = m[1]
            else:
                print("wrong header line: ", strline)

        return headerlines[0].decode(), headers, partbody

    @staticmethod
    def _parseIdentity(cls, readfunc, headers, partbody):
        print("parse identity")
        length = headers.get("Content-Length", None)
        body = b''
        if length:
            length = int(length)
            if length > cls.bodylimits:
                return 413
            partlen = len(partbody)
            if partlen >= length:
                body = bytes(partbody[0:length])  # bytes array
            else:
                lefts = readfunc(length - partlen)
                body = b''.join((partbody, lefts))
        return 0, body

    @staticmethod
    def _parseOneChunk(readfunc, body):
        print("parse chunked")
        sep = b'\r\n'
        while True:
            s = body.find(sep)
            if s > 0:
                sz = int(body[0:s-1], 16)
                lefts = body[s+len(sep):]
                return sz, lefts
            else:
                print("watch if loop always in here")
                newbytes = readfunc()
                for b in newbytes:
                    body.append(b)

    @staticmethod
    def _parseChunked(cls, readfunc, partbody):
        sizeall = 0
        body = partbody
        result = memoryview(bytearray(cls.bodylimits))
        while True:
            sz, body = cls._parseOneChunk(readfunc, body)
            if sz == 0:
                break
            sizeall += sz
            if sizeall > cls.bodylimits:
                return None
            if len(body) >= sz:
                print("body larger than sz, next chunked data?")
                result[sizeall-sz:] = body[0:sz]
                body = body[sz:]
            else:
                result[sizeall-sz:] = b''.join(body, readfunc(sz-len(body)))
                body = b''
        ret = result[0:sizeall].tobytes()
        result.release()
        return 0, ret

    # 当客户端向服务器请求一个静态页面或者一张图片时，服务器可以很清楚的知道内容大小，然后通过Content - length消息首部字段告诉客户端
    # 需要接收多少数据。但是如果是动态页面等时，服务器是不可能预先知道内容大小，这时就可以使用Transfer - Encoding：chunk模式来传输
    # 数据了。即如果要一边产生数据，一边发给客户端，服务器就需要使用
    # "Transfer-Encoding: chunked"
    # 这样的方式来代替Content - Length
    # chunk编码将数据分成一块一块的发生。Chunked编码将使用若干个Chunk串连而成，由一个标明长度为0
    # 的chunk标示结束。每个Chunk分为头部和正文两部分，头部内容指定正文的字符总数（十六进制的数字 ）和数量单位（一般不写），正文部分就是指定长度的实际内容，两部分之间用回车换行(CRLF)
    # 隔开。在最后一个长度为0的Chunk中的内容是称为footer的内容，是一些附加的Header信息（通常可以直接忽略）。 Chunk编码的格式如下：

    @classmethod
    def parse(cls, readfunc):
        requestline, headers, partbody = cls._parseHeader(readfunc)
        #request line GET /abc HTTP/1.1
        print("requestline: ", requestline)
        m = re.match(r"^(\w+)\s+(.*?)\s+HTTP/(\d.\d)$", requestline)
        if m:
            method, url, ver = m.groups()
            ver = float(ver)
            if ver > 1.1 or ver < 1.0:
                return 505
            if method not in cls.implement_methods:
                return 501
            mode = headers.get("Transfer-Encoding", None)
            if mode:
                if mode != "identity" and mode != "chunked":
                    return 501
            if mode == "chunked":
                code, body = HttpHandler._parseChunked(HttpHandler, readfunc, partbody)
            else: #identity
                code, body = HttpHandler._parseIdentity(HttpHandler, readfunc, headers, partbody)
        return code, url, method, headers, body

    @classmethod
    def response(cls, writefunc, status, contents, headers=None):
        response_line = "HTTP/1.1 {:03d} {}\r\n".format(status, cls.http_status_msg[status])
        writefunc(response_line.encode())
        if headers and len(headers) > 0:
            for di in headers.items():
                header_line = str.format("{}: {}", di[0], di[1])
                writefunc(header_line.encode())
        if contents:
            writefunc(("Content-Length: %d\r\n\r\n" % len(contents)).encode())
            writefunc(contents)
        else:
            writefunc(b'\r\n')

    @staticmethod
    def write_func(fd):
        return lambda stream: fd.send(stream)

    @classmethod
    def read_func(cls, fd):
        return lambda size=cls.readsize: fd.recv(size)

def read_filebytes(file):
    with open(file, "rb") as f:
        datas = f.read()
    return datas
def errorhtml(status, headers):
    file = "htdocs/error.html"
    with open(file, "rb") as f:
        datas = f.read()
        datas = datas.replace(b"[status]", str(status).encode())
        datas = datas.replace(b"[errormsg]", HttpHandler.http_status_msg[status].encode())
        headers["Content-Type"] = "text/html\r\n"
        return datas

#simply handle get, return url asset. post, cgi call
def handler(url, method, headers, body, response_headers):
    up = urlparse(url)
    datas = b""
    if up.path:
        path = up.path
        if method == "GET":
            contenttype = headers.get("Content-Type", None)
            if contenttype and "text/html" in contenttype or path.endswith(".html"):
                response_headers["Content-Type"] = "text/html;charset=utf-8\r\n"
                try:
                    f = open("htdocs/" + path, "rb")
                    datas = f.read()
                except FileNotFoundError:
                    return 404, datas
                finally:
                    f.close()
            else:
                return 400, datas
        elif method == "POST": # 是否执行cgi 其实与请求方法无关
            os.environ["QUERY_STRING"] = up.query
            cgi = "htdocs" + up.path
            if not os.path.isfile(cgi):
                return 400, datas
        #    r, w = os.pipe()
        #    os.write(r, body)
            p=subprocess.Popen(["python",cgi], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            #p.stdin.write(body)
            datas, errs = p.communicate(input=body)
            del os.environ["QUERY_STRING"]

    return 200, datas

def handle_socket(client_sock, addr):
    print("new sock from: ", addr, client_sock)
    read_func = HttpHandler.read_func(client_sock)
    status, url, method, headers, body = HttpHandler.parse(read_func)
    if url == "/favicon.ico":
        try:
            datas = read_filebytes("htdocs" + url)
            HttpHandler.response(HttpHandler.write_func(client_sock), 200, datas)
        except FileNotFoundError:
            pass
        finally:
            client_sock.close()
      #  HttpHandler.response(HttpHandler.write_func(client_sock), 404, b"")
        return
    print("http request status: {}, url: {}, method: {}, body: {}".format(status, url, method, body))

    response_headers = {}
    if status == HttpHandler.INTERNAL_OK: #continue proceed
        status, datas = handler(url, method, headers, body, response_headers)
    if status != 200:
        datas = errorhtml(status, response_headers)
    HttpHandler.response(HttpHandler.write_func(client_sock), status, datas, response_headers)
    client_sock.close()

def quit(sig, frame):
    print("You stop me: ", sig)
    sys.exit()

if __name__ == "__main__":
    signal.signal(signal.SIGINT, quit)
    signal.signal(signal.SIGTERM, quit)
    ss = SocketServer('127.0.0.1', 8787)
    ss.start(handle_socket)

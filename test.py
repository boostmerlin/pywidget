str1 = "hell, {1} and {0}".format("merlin", "ml")
print(str1)
str2 = "hell, {boy} and {girl}".format(boy="merlin",girl= "ml")
print(str2)

Color = type("Color", (object, ), dict(r=0, g=1, b=1, __str__ = lambda self: "{},{},{}".format(self.r, self.g, self.b)))
print(dir(Color))
color = Color()
#print(color.__format__())
print(str.format("color r: {0.r}", color))
print(str.format("color : {0!s}", color))

num1 = 3.1415927
num2 = -23423
num3 = 0xfdfa

print("{:#x}".format(num3))
print("{:0> #x}".format(num2))
print("{:!<+#010,d}".format(num2))
print("{:!>+#010,d}".format(num2))
#[[fill]align][sign][#][0][width][,][.precision][type]
print("{:^+.2f}".format(num1))

array = bytearray(3)
buffer = memoryview(array)

#memoryview not resizeable..
print(buffer.readonly)
buffer[0:2] = b'za'
#buffer.release()
print(buffer.tobytes())
#print(array)



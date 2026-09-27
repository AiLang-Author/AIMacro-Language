text = "hello\nworld"
prefix = "  "
line = ""
i = 0
n = len(text)
while i < n:
    c = text[i]
    if c == "\n":
        print(prefix + line)
        line = ""
    else:
        line = line + c
    i = i + 1
if line != "":
    print(prefix + line)

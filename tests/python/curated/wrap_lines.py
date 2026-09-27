words = "hello world foo bar baz".split(" ")
line = ""
for w in words:
    if line == "":
        line = w
    else:
        n = line + " " + w
        if len(n) <= 10:
            line = n
        else:
            print(line)
            line = w
if line != "":
    print(line)

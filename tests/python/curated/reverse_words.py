words = "one two three".split(" ")
out = ""
i = len(words)
while i > 0:
    i = i - 1
    if out == "":
        out = words[i]
    else:
        out = out + " " + words[i]
print(out)
